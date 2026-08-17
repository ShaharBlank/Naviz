from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Protocol, cast
from uuid import uuid4

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK, PyJWKError

from .models import Favorite, HistoryEntry, Place, TravelMode, UserPreferences


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str


class IdentityRepository(Protocol):
    async def initialize(self) -> None: ...

    async def close(self) -> None: ...

    async def favorites(self, subject: str) -> list[Favorite]: ...

    async def save_favorite(self, subject: str, label: str, place: Place) -> Favorite: ...

    async def delete_favorite(self, subject: str, favorite_id: str) -> None: ...

    async def preferences(self, subject: str) -> UserPreferences: ...

    async def save_preferences(
        self, subject: str, preferences: UserPreferences
    ) -> UserPreferences: ...

    async def history(self, subject: str) -> list[HistoryEntry]: ...

    async def add_history(
        self, subject: str, origin_label: str, destination: Place, mode: TravelMode
    ) -> HistoryEntry | None: ...


class InMemoryIdentityRepository:
    """Development adapter. Production supplies the SQLAlchemy/Postgres adapter."""

    def __init__(self) -> None:
        self._favorites: dict[str, list[Favorite]] = {}
        self._preferences: dict[str, UserPreferences] = {}
        self._history: dict[str, list[HistoryEntry]] = {}
        self._lock = RLock()

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def favorites(self, subject: str) -> list[Favorite]:
        with self._lock:
            return list(self._favorites.get(subject, []))

    async def save_favorite(self, subject: str, label: str, place: Place) -> Favorite:
        favorite = Favorite(id=str(uuid4()), label=label, place=place, created_at=datetime.now(UTC))
        with self._lock:
            self._favorites.setdefault(subject, []).append(favorite)
        return favorite

    async def delete_favorite(self, subject: str, favorite_id: str) -> None:
        with self._lock:
            current = self._favorites.get(subject, [])
            self._favorites[subject] = [item for item in current if item.id != favorite_id]

    async def preferences(self, subject: str) -> UserPreferences:
        with self._lock:
            return self._preferences.get(subject, UserPreferences())

    async def save_preferences(
        self, subject: str, preferences: UserPreferences
    ) -> UserPreferences:
        with self._lock:
            self._preferences[subject] = preferences
        return preferences

    async def history(self, subject: str) -> list[HistoryEntry]:
        now = datetime.now(UTC)
        with self._lock:
            retained = [item for item in self._history.get(subject, []) if item.expires_at > now]
            self._history[subject] = retained
            return list(retained)

    async def add_history(
        self, subject: str, origin_label: str, destination: Place, mode: TravelMode
    ) -> HistoryEntry | None:
        if not (await self.preferences(subject)).history_enabled:
            return None
        now = datetime.now(UTC)
        entry = HistoryEntry(
            id=str(uuid4()),
            origin_label=origin_label,
            destination=destination,
            mode=mode,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
        with self._lock:
            self._history.setdefault(subject, []).insert(0, entry)
        return entry


class TokenVerifier:
    def __init__(self, issuer: str | None, audience: str, development: bool) -> None:
        self._issuer = issuer.rstrip("/") if issuer else None
        self._audience = audience
        self._development = development
        self._jwks: dict[str, Any] | None = None

    async def verify(self, authorization: str | None) -> Principal:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthenticationError("Authentication is required for account sync")
        token = authorization.split(" ", 1)[1]
        if self._development and not self._issuer and token == "demo-user":
            return Principal("demo-user")
        if not self._issuer:
            raise AuthenticationError("Account authentication is not configured")
        try:
            header = jwt.get_unverified_header(token)
            key = await self._signing_key(str(header.get("kid", "")))
            claims = jwt.decode(
                token,
                key,
                algorithms=[key.algorithm_name],
                audience=self._audience,
                issuer=self._issuer,
            )
        except (InvalidTokenError, PyJWKError, KeyError, ValueError, httpx.HTTPError) as exc:
            raise AuthenticationError("The access token is invalid or expired") from exc
        subject = claims.get("sub")
        if not subject:
            raise AuthenticationError("The access token has no subject")
        return Principal(str(subject))

    async def _signing_key(self, key_id: str) -> PyJWK:
        if self._jwks is None:
            async with httpx.AsyncClient(timeout=5.0) as client:
                configuration = (
                    (await client.get(f"{self._issuer}/.well-known/openid-configuration"))
                    .raise_for_status()
                    .json()
                )
                payload = (await client.get(configuration["jwks_uri"])).raise_for_status().json()
                self._jwks = cast(dict[str, Any], payload)
        for raw_key in self._jwks.get("keys", []):
            if isinstance(raw_key, dict) and raw_key.get("kid") == key_id:
                return PyJWK.from_dict(raw_key)
        self._jwks = None
        raise AuthenticationError("The signing key is unavailable")


class AuthenticationError(ValueError):
    pass
