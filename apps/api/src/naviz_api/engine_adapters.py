from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

import httpx

from .geometry import decode_polyline
from .models import Coordinate, RoutePlanRequest, TravelMode, VehicleKind
from .routing import normalize_departure


@dataclass(frozen=True, slots=True)
class EngineManeuver:
    instruction: str
    begin_geometry_index: int
    distance_m: float
    duration_s: float
    street_name: str | None = None


@dataclass(frozen=True, slots=True)
class EngineLeg:
    mode: TravelMode
    geometry: tuple[Coordinate, ...]
    distance_m: float
    duration_s: float
    from_name: str
    to_name: str
    maneuvers: tuple[EngineManeuver, ...] = ()
    agency: str | None = None
    route_name: str | None = None
    headsign: str | None = None
    bicycle_permission: str | None = None


@dataclass(frozen=True, slots=True)
class EngineItinerary:
    departure_at: datetime
    arrival_at: datetime
    legs: tuple[EngineLeg, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


class StreetEnginePort(Protocol):
    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]: ...


class TransitEnginePort(Protocol):
    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]: ...


class ValhallaAdapter:
    """Production-street-engine boundary using Valhalla's native route contract."""

    def __init__(self, base_url: str, timeout_seconds: float = 8.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]:
        payload = self.request_payload(request)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/route", json=payload)
            response.raise_for_status()
        return self.normalize(cast(dict[str, Any], response.json()), request)

    @staticmethod
    def request_payload(request: RoutePlanRequest) -> dict[str, object]:
        costing = {
            TravelMode.WALK: "pedestrian",
            TravelMode.BIKE: "bicycle",
            TravelMode.SCOOTER: "motor_scooter",
            TravelMode.CAR: "auto",
            TravelMode.MOTORCYCLE: "motorcycle",
            TravelMode.TRUCK: "truck",
        }.get(request.mode)
        if costing is None:
            raise ValueError(f"Valhalla cannot plan {request.mode.value} transit itineraries")
        costing_options: dict[str, object] = {}
        if request.mode == TravelMode.TRUCK:
            costing_options["truck"] = {
                key: value
                for key, value in {
                    "height": request.vehicle.height_m,
                    "width": request.vehicle.width_m,
                    "weight": request.vehicle.weight_t,
                }.items()
                if value is not None
            }
        effective_time = _request_time(request)
        return {
            "locations": [
                {"lat": request.origin.latitude, "lon": request.origin.longitude},
                {"lat": request.destination.latitude, "lon": request.destination.longitude},
            ],
            "costing": costing,
            "costing_options": costing_options,
            "date_time": {
                "type": 2 if request.arrive_by else 1,
                "value": effective_time.isoformat(),
            },
            "directions_options": {"units": "kilometers", "language": request.locale.value},
            "alternates": 2,
        }

    @staticmethod
    def normalize(payload: dict[str, Any], request: RoutePlanRequest) -> list[EngineItinerary]:
        trip_payloads = [_mapping(payload.get("trip"))]
        trip_payloads.extend(
            _mapping(_mapping(alternate).get("trip"))
            for alternate in _list(payload.get("alternates"))
        )
        result: list[EngineItinerary] = []
        for trip in trip_payloads:
            normalized_legs: list[EngineLeg] = []
            for raw_leg in _list(trip.get("legs")):
                leg = _mapping(raw_leg)
                shape = _string(leg.get("shape"))
                geometry = tuple(decode_polyline(shape, precision=6))
                summary = _mapping(leg.get("summary"))
                maneuvers = tuple(
                    EngineManeuver(
                        instruction=_string(item.get("instruction"), "Continue"),
                        begin_geometry_index=_integer(item.get("begin_shape_index")),
                        distance_m=_number(item.get("length")) * 1_000,
                        duration_s=_number(item.get("time")),
                        street_name=(_list(item.get("street_names")) or [None])[0],
                    )
                    for value in _list(leg.get("maneuvers"))
                    if (item := _mapping(value))
                )
                normalized_legs.append(
                    EngineLeg(
                        mode=request.mode,
                        geometry=geometry,
                        distance_m=_number(summary.get("length")) * 1_000,
                        duration_s=_number(summary.get("time")),
                        from_name="Origin",
                        to_name="Destination",
                        maneuvers=maneuvers,
                    )
                )
            if not normalized_legs:
                continue
            duration_s = sum(leg.duration_s for leg in normalized_legs)
            effective_time = _request_time(request)
            departure_at = (
                effective_time - timedelta(seconds=duration_s)
                if request.arrive_by
                else effective_time
            )
            result.append(
                EngineItinerary(
                    departure_at=departure_at,
                    arrival_at=departure_at + timedelta(seconds=duration_s),
                    legs=tuple(normalized_legs),
                )
            )
        return result


class OpenTripPlannerAdapter:
    """OTP planner boundary normalized independently of the mobile API."""

    def __init__(self, base_url: str, timeout_seconds: float = 12.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/otp/routers/default/plan",
                params=self.request_parameters(request),
            )
            response.raise_for_status()
        return self.normalize(cast(dict[str, Any], response.json()), request)

    @staticmethod
    def request_parameters(request: RoutePlanRequest) -> dict[str, str]:
        modes = {
            TravelMode.TRANSIT: "WALK,TRANSIT",
            TravelMode.BIKE_TRANSIT: "BICYCLE,TRANSIT",
            TravelMode.SCOOTER_TRANSIT: "SCOOTER,TRANSIT",
            TravelMode.RENTAL_TRANSIT: "BICYCLE_RENT,TRANSIT",
        }.get(request.mode)
        if modes is None:
            raise ValueError(f"OTP is only configured for transit modes, not {request.mode.value}")
        effective = _request_time(request)
        return {
            "fromPlace": f"{request.origin.latitude},{request.origin.longitude}",
            "toPlace": f"{request.destination.latitude},{request.destination.longitude}",
            "date": effective.date().isoformat(),
            "time": effective.strftime("%H:%M"),
            "mode": modes,
            "arriveBy": str(request.arrive_by is not None).lower(),
            "numItineraries": "4",
            "locale": request.locale.value,
        }

    @staticmethod
    def normalize(payload: dict[str, Any], request: RoutePlanRequest) -> list[EngineItinerary]:
        itineraries = _list(_mapping(payload.get("plan")).get("itineraries"))
        result: list[EngineItinerary] = []
        for raw_itinerary in itineraries:
            itinerary = _mapping(raw_itinerary)
            legs: list[EngineLeg] = []
            unknown_bicycle_rule = False
            for raw_leg in _list(itinerary.get("legs")):
                leg = _mapping(raw_leg)
                mode = _otp_mode(_string(leg.get("mode")))
                bicycle_permission = _optional_string(leg.get("bikesAllowed"))
                if (
                    mode == TravelMode.TRANSIT
                    and request.vehicle.kind == VehicleKind.FULL_SIZE_BIKE
                    and bicycle_permission != "ALLOWED"
                ):
                    unknown_bicycle_rule = True
                encoded = _string(_mapping(leg.get("legGeometry")).get("points"))
                legs.append(
                    EngineLeg(
                        mode=mode,
                        geometry=tuple(decode_polyline(encoded, precision=5)),
                        distance_m=_number(leg.get("distance")),
                        duration_s=_number(leg.get("duration")),
                        from_name=_string(_mapping(leg.get("from")).get("name"), "Origin"),
                        to_name=_string(_mapping(leg.get("to")).get("name"), "Destination"),
                        agency=_optional_string(leg.get("agencyName")),
                        route_name=_optional_string(leg.get("routeShortName")),
                        headsign=_optional_string(leg.get("headsign")),
                        bicycle_permission=bicycle_permission,
                    )
                )
            if not legs or unknown_bicycle_rule:
                continue
            result.append(
                EngineItinerary(
                    departure_at=_epoch_millis(itinerary.get("startTime")),
                    arrival_at=_epoch_millis(itinerary.get("endTime")),
                    legs=tuple(legs),
                    warnings=("Scheduled transit times",),
                )
            )
        return result


def _otp_mode(value: str) -> TravelMode:
    return {
        "WALK": TravelMode.WALK,
        "BICYCLE": TravelMode.BIKE,
        "SCOOTER": TravelMode.SCOOTER,
        "CAR": TravelMode.CAR,
        "BUS": TravelMode.TRANSIT,
        "RAIL": TravelMode.TRANSIT,
        "SUBWAY": TravelMode.TRANSIT,
        "TRAM": TravelMode.TRANSIT,
        "FERRY": TravelMode.TRANSIT,
    }.get(value.upper(), TravelMode.TRANSIT)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _integer(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def _epoch_millis(value: object) -> datetime:
    if not isinstance(value, int | float):
        raise ValueError("OTP itinerary is missing an epoch-millisecond timestamp")
    return datetime.fromtimestamp(float(value) / 1_000, tz=UTC)


def _request_time(request: RoutePlanRequest) -> datetime:
    return normalize_departure(request.depart_at or request.arrive_by)
