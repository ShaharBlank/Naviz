from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .models import Coordinate, MobilityResponse, MobilityVehicle, VehicleKind


@dataclass(frozen=True, slots=True)
class GbfsFeed:
    provider: str
    discovery_url: str
    deep_link: str | None = None


@dataclass(slots=True)
class _CacheEntry:
    observed_at: datetime
    vehicles: list[MobilityVehicle]


class MobilityService:
    def __init__(
        self,
        feeds: tuple[GbfsFeed, ...] = (),
        *,
        ttl_seconds: int = 30,
        stale_seconds: int = 120,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._feeds = feeds
        self._ttl = timedelta(seconds=ttl_seconds)
        self._stale = timedelta(seconds=stale_seconds)
        self._client = client
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def nearby(
        self,
        *,
        minimum_latitude: float,
        minimum_longitude: float,
        maximum_latitude: float,
        maximum_longitude: float,
    ) -> MobilityResponse:
        now = datetime.now(UTC)
        warnings: list[str] = []
        if not self._feeds:
            vehicles: list[MobilityVehicle] = []
        else:
            results = await asyncio.gather(
                *(self._load(feed, now) for feed in self._feeds), return_exceptions=True
            )
            vehicles = []
            for feed, result in zip(self._feeds, results, strict=True):
                if isinstance(result, BaseException):
                    warnings.append(f"{feed.provider} availability is temporarily unavailable.")
                else:
                    vehicles.extend(result)
        filtered = [
            vehicle
            for vehicle in vehicles
            if minimum_latitude <= vehicle.coordinate.latitude <= maximum_latitude
            and minimum_longitude <= vehicle.coordinate.longitude <= maximum_longitude
            and vehicle.available
            and not vehicle.stale
        ]
        return MobilityResponse(vehicles=filtered, generated_at=now, warnings=warnings)

    async def _load(self, feed: GbfsFeed, now: datetime) -> list[MobilityVehicle]:
        cached = self._cache.get(feed.provider)
        if cached and now - cached.observed_at <= self._ttl:
            return self._mark_stale(cached.vehicles, now)
        async with self._lock:
            cached = self._cache.get(feed.provider)
            if cached and now - cached.observed_at <= self._ttl:
                return self._mark_stale(cached.vehicles, now)
            client = self._client or httpx.AsyncClient(timeout=8.0, follow_redirects=True)
            owns_client = self._client is None
            try:
                discovery = (await client.get(feed.discovery_url)).raise_for_status().json()
                free_bike_url = _find_feed_url(discovery, "free_bike_status") or _find_feed_url(
                    discovery, "vehicle_status"
                )
                vehicle_types_url = _find_feed_url(discovery, "vehicle_types")
                if not free_bike_url:
                    raise ValueError("GBFS discovery document has no vehicle status feed")
                status_response, types_response = await asyncio.gather(
                    client.get(free_bike_url),
                    client.get(vehicle_types_url) if vehicle_types_url else _empty_response(),
                )
                status_response.raise_for_status()
                type_map = _vehicle_type_map(types_response.json()) if vehicle_types_url else {}
                observed_at = _observed_at(status_response.json(), now)
                vehicles = _parse_vehicles(
                    feed,
                    status_response.json(),
                    type_map,
                    observed_at,
                    now - observed_at > self._stale,
                )
                self._cache[feed.provider] = _CacheEntry(observed_at, vehicles)
                return vehicles
            finally:
                if owns_client:
                    await client.aclose()

    def _mark_stale(self, vehicles: list[MobilityVehicle], now: datetime) -> list[MobilityVehicle]:
        return [
            vehicle.model_copy(update={"stale": now - vehicle.observed_at > self._stale})
            for vehicle in vehicles
        ]

async def _empty_response() -> httpx.Response:
    return httpx.Response(200, json={"data": {"vehicle_types": []}})


def _find_feed_url(discovery: Mapping[str, Any], name: str) -> str | None:
    data = discovery.get("data", {})
    if isinstance(data, dict) and "feeds" in data:
        feeds = data["feeds"]
    elif isinstance(data, dict):
        language_data = next((value for value in data.values() if isinstance(value, dict)), {})
        feeds = language_data.get("feeds", [])
    else:
        feeds = []
    for feed in feeds:
        if feed.get("name") == name:
            return str(feed.get("url"))
    return None


def _vehicle_type_map(payload: Mapping[str, Any]) -> dict[str, VehicleKind]:
    result: dict[str, VehicleKind] = {}
    for item in payload.get("data", {}).get("vehicle_types", []):
        form_factor = str(item.get("form_factor", "")).lower()
        kind = VehicleKind.SHARED_SCOOTER if "scooter" in form_factor else VehicleKind.SHARED_BIKE
        result[str(item.get("vehicle_type_id"))] = kind
    return result


def _observed_at(payload: Mapping[str, Any], fallback: datetime) -> datetime:
    timestamp = payload.get("last_updated")
    if timestamp is None:
        return fallback
    try:
        return datetime.fromtimestamp(int(timestamp), UTC)
    except (TypeError, ValueError, OSError):
        return fallback


def _parse_vehicles(
    feed: GbfsFeed,
    payload: Mapping[str, Any],
    type_map: Mapping[str, VehicleKind],
    observed_at: datetime,
    stale: bool,
) -> list[MobilityVehicle]:
    data = payload.get("data", {})
    items = data.get("bikes") or data.get("vehicles") or []
    result: list[MobilityVehicle] = []
    for item in items:
        if item.get("is_reserved") or item.get("is_disabled"):
            continue
        vehicle_type = str(item.get("vehicle_type_id", ""))
        kind = type_map.get(vehicle_type)
        if kind is None:
            kind = (
                VehicleKind.SHARED_SCOOTER
                if "scooter" in vehicle_type.lower()
                else VehicleKind.SHARED_BIKE
            )
        battery = item.get("current_fuel_percent")
        if isinstance(battery, float) and battery <= 1:
            battery = round(battery * 100)
        result.append(
            MobilityVehicle(
                provider=feed.provider,
                id=str(item.get("bike_id") or item.get("vehicle_id")),
                kind=kind,
                coordinate=Coordinate(latitude=float(item["lat"]), longitude=float(item["lon"])),
                battery_percent=int(battery) if battery is not None else None,
                deep_link=(
                    str(item.get("rental_uris", {}).get("android") or feed.deep_link or "") or None
                ),
                observed_at=observed_at,
                stale=stale,
            )
        )
    return result
