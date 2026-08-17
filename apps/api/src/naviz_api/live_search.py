from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Any, cast

import httpx

from .errors import OutsideCoverageError, RoutingUnavailableError
from .models import Coordinate, DataConfidence, Locale, Place


@dataclass(frozen=True, slots=True)
class CoverageArea:
    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    @classmethod
    def from_tuple(cls, value: tuple[float, float, float, float]) -> CoverageArea:
        return cls(*value)

    def contains(self, coordinate: Coordinate) -> bool:
        return (
            self.min_latitude <= coordinate.latitude <= self.max_latitude
            and self.min_longitude <= coordinate.longitude <= self.max_longitude
        )

    def require(self, coordinate: Coordinate) -> None:
        if not self.contains(coordinate):
            raise OutsideCoverageError

    @property
    def photon_bbox(self) -> str:
        return ",".join(
            str(value)
            for value in (
                self.min_longitude,
                self.min_latitude,
                self.max_longitude,
                self.max_latitude,
            )
        )


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: object


class PhotonPlaceSearch:
    """Regional Photon adapter with bounded results and a short in-process TTL cache."""

    def __init__(
        self,
        base_url: str,
        coverage: CoverageArea,
        *,
        data_version: str,
        user_agent: str,
        cache_seconds: int = 300,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.data_version = data_version
        self._base_url = base_url.rstrip("/")
        self._coverage = coverage
        self._headers = {"User-Agent": user_agent}
        self._cache_seconds = cache_seconds
        self._timeout = timeout_seconds
        self._cache: dict[tuple[object, ...], _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def search(
        self,
        query: str,
        *,
        language: Locale,
        proximity: Coordinate | None = None,
        limit: int = 8,
        category: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Place]:
        del language
        normalized = query.strip()
        if not normalized:
            return []
        if proximity is not None and not self._coverage.contains(proximity):
            proximity = None
        effective_bbox = self._intersect_bbox(bbox)
        key = (
            "search",
            normalized.casefold(),
            round(proximity.latitude, 3) if proximity else None,
            round(proximity.longitude, 3) if proximity else None,
            limit,
            category,
            effective_bbox,
        )
        cached = self._cached(key)
        if cached is not None:
            return cast(list[Place], cached)
        params: dict[str, str | int | float] = {
            "q": normalized,
            "limit": min(20, max(limit * 2, 8)),
            "bbox": ",".join(str(value) for value in effective_bbox),
        }
        if proximity is not None:
            params.update(lat=proximity.latitude, lon=proximity.longitude)
        payload = await self._get("/api/", params)
        places = self._places(payload, category=category)[:limit]
        await self._store(key, places)
        return places

    async def reverse(self, coordinate: Coordinate, *, language: Locale) -> Place | None:
        del language
        self._coverage.require(coordinate)
        key = ("reverse", round(coordinate.latitude, 5), round(coordinate.longitude, 5))
        cached = self._cached(key)
        if cached is not None:
            return cast(Place | None, cached)
        payload = await self._get(
            "/reverse",
            {"lat": coordinate.latitude, "lon": coordinate.longitude},
        )
        places = self._places(payload)
        result = places[0] if places else None
        await self._store(key, result)
        return result

    async def _get(self, path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingUnavailableError from exc

    def _places(self, payload: dict[str, Any], category: str | None = None) -> list[Place]:
        allowed = {item.strip() for item in category.split(",")} if category else set()
        result: list[Place] = []
        seen: set[str] = set()
        for raw_feature in _list(payload.get("features")):
            feature = _mapping(raw_feature)
            properties = _mapping(feature.get("properties"))
            raw_coordinates = _list(_mapping(feature.get("geometry")).get("coordinates"))
            if len(raw_coordinates) < 2:
                continue
            try:
                coordinate = Coordinate(
                    latitude=float(raw_coordinates[1]),
                    longitude=float(raw_coordinates[0]),
                )
            except (TypeError, ValueError):
                continue
            if not self._coverage.contains(coordinate):
                continue
            place_category = _string(properties.get("type"), "place")
            if allowed and place_category not in allowed:
                continue
            osm_type = _string(properties.get("osm_type"), "osm")
            osm_id = _string(properties.get("osm_id"), f"{coordinate.latitude:.6f}")
            identifier = f"osm:{osm_type}:{osm_id}"
            if identifier in seen:
                continue
            seen.add(identifier)
            name = _display_name(properties)
            if not name:
                continue
            city = _first_string(properties, "city", "town", "village", "district")
            street = _first_string(properties, "street", "locality", "county")
            subtitle = " · ".join(part for part in (street, city) if part and part != name) or None
            result.append(
                Place(
                    id=identifier,
                    name=name,
                    name_he=name if _contains_hebrew(name) else None,
                    subtitle=subtitle,
                    coordinate=coordinate,
                    category=place_category,
                    confidence=DataConfidence.HIGH,
                )
            )
        return result

    def _intersect_bbox(
        self, requested: tuple[float, float, float, float] | None
    ) -> tuple[float, float, float, float]:
        coverage = (
            self._coverage.min_longitude,
            self._coverage.min_latitude,
            self._coverage.max_longitude,
            self._coverage.max_latitude,
        )
        if requested is None:
            return coverage
        result = (
            max(requested[0], coverage[0]),
            max(requested[1], coverage[1]),
            min(requested[2], coverage[2]),
            min(requested[3], coverage[3]),
        )
        if result[0] > result[2] or result[1] > result[3]:
            raise OutsideCoverageError
        return result

    def _cached(self, key: tuple[object, ...]) -> object | None:
        entry = self._cache.get(key)
        if entry is None or entry.expires_at <= monotonic():
            self._cache.pop(key, None)
            return None
        return entry.value

    async def _store(self, key: tuple[object, ...], value: object) -> None:
        async with self._lock:
            if len(self._cache) >= 512:
                oldest = min(self._cache, key=lambda item: self._cache[item].expires_at)
                self._cache.pop(oldest, None)
            self._cache[key] = _CacheEntry(monotonic() + self._cache_seconds, value)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return default


def _first_string(properties: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _string(properties.get(key))
        if value:
            return value
    return ""


def _display_name(properties: dict[str, Any]) -> str:
    name = _first_string(properties, "name", "street", "city", "district")
    house_number = _string(properties.get("housenumber"))
    return " ".join(part for part in (name, house_number) if part)


def _contains_hebrew(value: str) -> bool:
    return any("\u0590" <= character <= "\u05ff" for character in value)
