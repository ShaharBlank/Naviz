from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from math import cos, radians
from typing import Any, Protocol, cast

import httpx

from .errors import NoRouteError, RoutingUnavailableError
from .geometry import decode_polyline, haversine_m
from .models import Coordinate, RoutePlanRequest, TravelMode, VehicleKind
from .routing import normalize_departure


@dataclass(frozen=True, slots=True)
class EngineManeuver:
    instruction: str
    begin_geometry_index: int
    distance_m: float
    duration_s: float
    street_name: str | None = None
    modifier: str | None = None


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
    departure_at: datetime | None = None
    arrival_at: datetime | None = None


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

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 8.0,
        user_agent: str = "Naviz/0.2",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._headers = {"User-Agent": user_agent}

    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]:
        payload = self.request_payload(request)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
                response = await client.post(f"{self._base_url}/route", json=payload)
                response.raise_for_status()
                result = self.normalize(cast(dict[str, Any], response.json()), request)
                if result:
                    alternative_payloads = self._alternative_payloads(request, result[0])
                    responses = await asyncio.gather(
                        *(
                            client.post(f"{self._base_url}/route", json=item)
                            for item in alternative_payloads
                        ),
                        return_exceptions=True,
                    )
                    for candidate_response in responses:
                        if not isinstance(candidate_response, httpx.Response):
                            continue
                        if candidate_response.status_code >= 400:
                            continue
                        result.extend(
                            self.normalize(
                                cast(dict[str, Any], candidate_response.json()), request
                            )
                        )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {400, 404}:
                raise NoRouteError from exc
            raise RoutingUnavailableError from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingUnavailableError from exc
        if not result:
            raise NoRouteError
        fastest = min(
            (item.arrival_at - item.departure_at).total_seconds() for item in result
        )
        unique: list[EngineItinerary] = []
        seen: set[tuple[tuple[float, float], ...]] = set()
        for itinerary in sorted(
            result, key=lambda item: (item.arrival_at - item.departure_at).total_seconds()
        ):
            duration = (itinerary.arrival_at - itinerary.departure_at).total_seconds()
            if duration > fastest * 1.5:
                continue
            key = tuple(
                (round(point.latitude, 4), round(point.longitude, 4))
                for leg in itinerary.legs
                for point in leg.geometry[:: max(1, len(leg.geometry) // 20)]
            )
            if key not in seen:
                unique.append(itinerary)
                seen.add(key)
        return unique[:3]

    @classmethod
    def _alternative_payloads(
        cls, request: RoutePlanRequest, primary: EngineItinerary
    ) -> list[dict[str, object]]:
        geometry = [point for leg in primary.legs for point in leg.geometry]
        if len(geometry) < 3:
            return []
        midpoint = geometry[len(geometry) // 2]
        first, last = geometry[0], geometry[-1]
        delta_lat = last.latitude - first.latitude
        delta_lon = (last.longitude - first.longitude) * cos(radians(midpoint.latitude))
        magnitude = max((delta_lat**2 + delta_lon**2) ** 0.5, 1e-9)
        perpendicular_lat = -delta_lon / magnitude
        perpendicular_lon = delta_lat / magnitude
        offset_m = 220 if request.mode == TravelMode.WALK else 320
        payloads = []
        for direction in (-1, 1):
            via_lat = midpoint.latitude + direction * perpendicular_lat * offset_m / 111_320
            via_lon = midpoint.longitude + direction * perpendicular_lon * offset_m / (
                111_320 * cos(radians(midpoint.latitude))
            )
            payload = cls.request_payload(request)
            payload["locations"] = [
                {"lat": request.origin.latitude, "lon": request.origin.longitude},
                {"lat": via_lat, "lon": via_lon, "type": "through"},
                {"lat": request.destination.latitude, "lon": request.destination.longitude},
            ]
            payload["alternates"] = 0
            payloads.append(payload)
        return payloads

    @staticmethod
    def request_payload(request: RoutePlanRequest) -> dict[str, object]:
        costing = {
            TravelMode.WALK: "pedestrian",
            TravelMode.BIKE: "bicycle",
            # A Naviz scooter is a standing micromobility device, not a road
            # motorcycle. Bicycle costing is the closest legal street profile.
            TravelMode.SCOOTER: "bicycle",
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
                # Valhalla expects local civil time without a UTC offset.
                "value": effective_time.strftime("%Y-%m-%dT%H:%M"),
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
                        modifier=_maneuver_modifier(
                            _string(item.get("instruction")),
                            _integer(item.get("type")),
                        ),
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


class TransitousAdapter:
    """MOTIS v5 multimodal boundary used with a pinned/self-hostable API contract."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 15.0,
        user_agent: str = "Naviz/0.2",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._headers = {"User-Agent": user_agent}

    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
                response = await client.get(
                    f"{self._base_url}/api/v5/plan",
                    params=self.request_parameters(request),
                )
                response.raise_for_status()
            result = self.normalize(cast(dict[str, Any], response.json()), request)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {400, 404}:
                raise NoRouteError from exc
            raise RoutingUnavailableError from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingUnavailableError from exc
        if not result:
            raise NoRouteError
        return result

    @staticmethod
    def request_parameters(request: RoutePlanRequest) -> dict[str, str]:
        if request.mode not in {
            TravelMode.TRANSIT,
            TravelMode.BIKE_TRANSIT,
            TravelMode.SCOOTER_TRANSIT,
            TravelMode.RENTAL_TRANSIT,
        }:
            raise ValueError("MOTIS is only configured for transit modes")
        effective = _request_time(request)
        params = {
            "fromPlace": f"{request.origin.latitude},{request.origin.longitude}",
            "toPlace": f"{request.destination.latitude},{request.destination.longitude}",
            # MOTIS v5 currently misparses ISO timestamps with microsecond
            # precision. Whole seconds are sufficient for journey planning and
            # keep the requested calendar date stable.
            "time": effective.isoformat(timespec="seconds"),
            "arriveBy": str(request.arrive_by is not None).lower(),
            "detailedTransfers": "true",
            "language": request.locale.value,
            "maxTransfers": "2",
            "directModes": "WALK",
            "preTransitModes": "WALK",
            "postTransitModes": "WALK",
        }
        if request.mode in {TravelMode.BIKE_TRANSIT, TravelMode.SCOOTER_TRANSIT}:
            params.update(
                directModes="BIKE",
                preTransitModes="BIKE",
                postTransitModes="BIKE",
                requireBikeTransport=str(
                    request.vehicle.kind == VehicleKind.FULL_SIZE_BIKE
                ).lower(),
            )
        elif request.mode == TravelMode.RENTAL_TRANSIT:
            params.update(
                directModes="BIKE_SHARING",
                preTransitModes="WALK,BIKE_SHARING",
                postTransitModes="WALK,BIKE_SHARING",
            )
        if request.preference.value == "fewer_transfers":
            params["maxTransfers"] = "1"
        if request.accessibility.require_step_free:
            params["pedestrianProfile"] = "WHEELCHAIR"
        return params

    @staticmethod
    def normalize(payload: dict[str, Any], request: RoutePlanRequest) -> list[EngineItinerary]:
        result: list[EngineItinerary] = []
        for raw_itinerary in _list(payload.get("itineraries")):
            itinerary = _mapping(raw_itinerary)
            legs: list[EngineLeg] = []
            permitted = True
            for raw_leg in _list(itinerary.get("legs")):
                leg = _mapping(raw_leg)
                raw_mode = _string(leg.get("mode"))
                mode = _otp_mode(raw_mode)
                if request.mode == TravelMode.SCOOTER_TRANSIT and mode == TravelMode.BIKE:
                    mode = TravelMode.SCOOTER
                if raw_mode.upper() == "BIKE_SHARING":
                    mode = TravelMode.BIKE
                if mode == TravelMode.TRANSIT and request.mode in {
                    TravelMode.BIKE_TRANSIT,
                    TravelMode.SCOOTER_TRANSIT,
                }:
                    # MOTIS applies effective GTFS/operator bicycle rules when
                    # requireBikeTransport=true. Never accept an explicitly denied leg.
                    bikes_allowed = leg.get("bikesAllowed")
                    folded_vehicle = request.vehicle.can_fold and request.vehicle.kind in {
                        VehicleKind.FOLDING_BIKE,
                        VehicleKind.PERSONAL_SCOOTER,
                    }
                    if not folded_vehicle and bikes_allowed is not True:
                        permitted = False
                        break
                encoded = _string(_mapping(leg.get("legGeometry")).get("points"))
                geometry = tuple(decode_polyline(encoded, precision=6)) if encoded else ()
                if len(geometry) < 2:
                    continue
                reported_distance = _number(leg.get("distance"))
                distance_m = reported_distance or sum(
                    haversine_m(start, end) for start, end in pairwise(geometry)
                )
                from_payload = _mapping(leg.get("from"))
                to_payload = _mapping(leg.get("to"))
                legs.append(
                    EngineLeg(
                        mode=mode,
                        geometry=geometry,
                        distance_m=distance_m,
                        duration_s=_number(leg.get("duration")),
                        from_name=_display_text(from_payload.get("name"), "Origin"),
                        to_name=_display_text(to_payload.get("name"), "Destination"),
                        agency=_optional_string(leg.get("agencyName")),
                        route_name=(
                            _optional_string(leg.get("displayName"))
                            or _optional_string(leg.get("routeShortName"))
                        ),
                        headsign=_optional_display_text(leg.get("headsign")),
                        bicycle_permission=(
                            "ALLOWED_FOLDED_POLICY"
                            if request.vehicle.can_fold
                            and request.vehicle.kind
                            in {VehicleKind.FOLDING_BIKE, VehicleKind.PERSONAL_SCOOTER}
                            else "ALLOWED_GTFS"
                            if leg.get("bikesAllowed") is True
                            else None
                        ),
                        departure_at=_optional_iso_datetime(leg.get("startTime")),
                        arrival_at=_optional_iso_datetime(leg.get("endTime")),
                    )
                )
            if not permitted or not legs:
                continue
            departure_at = _iso_datetime(itinerary.get("startTime"))
            arrival_at = _iso_datetime(itinerary.get("endTime"))
            requested_at = _request_time(request)
            if request.arrive_by is not None:
                if arrival_at > requested_at + timedelta(seconds=60):
                    continue
            elif departure_at < requested_at - timedelta(seconds=60):
                # Never surface a provider/cache anomaly as a valid journey in
                # the past. The mobile client always sends depart_at explicitly.
                continue
            result.append(
                EngineItinerary(
                    departure_at=departure_at,
                    arrival_at=arrival_at,
                    legs=tuple(legs),
                )
            )
        result.sort(
            key=lambda item: (
                len([leg for leg in item.legs if leg.mode == TravelMode.TRANSIT])
                if request.preference.value == "fewer_transfers"
                else (item.arrival_at - item.departure_at).total_seconds(),
                item.arrival_at,
            )
        )
        return result[:4]


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
        "BIKE_SHARING": TravelMode.BIKE,
    }.get(value.upper(), TravelMode.TRANSIT)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _display_text(value: object, default: str = "") -> str:
    raw = _string(value, default)
    parts = [part.strip() for part in raw.split("_") if part.strip()]
    return " · ".join(parts) if parts else default


def _optional_display_text(value: object) -> str | None:
    return _display_text(value) if isinstance(value, str) else None


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _integer(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def _epoch_millis(value: object) -> datetime:
    if not isinstance(value, int | float):
        raise ValueError("OTP itinerary is missing an epoch-millisecond timestamp")
    return datetime.fromtimestamp(float(value) / 1_000, tz=UTC)


def _iso_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Itinerary is missing an ISO-8601 timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _optional_iso_datetime(value: object) -> datetime | None:
    return _iso_datetime(value) if isinstance(value, str) else None


def _request_time(request: RoutePlanRequest) -> datetime:
    return normalize_departure(request.depart_at or request.arrive_by)


def _maneuver_modifier(instruction: str, maneuver_type: int) -> str:
    typed = {
        4: "arrive",
        5: "arrive",
        6: "arrive",
        9: "slight_right",
        10: "right",
        11: "right",
        12: "uturn",
        13: "uturn",
        14: "left",
        15: "left",
        16: "slight_left",
    }.get(maneuver_type)
    if typed is not None:
        return typed
    normalized = instruction.casefold()
    if "destination" in normalized:
        return "arrive"
    if "u-turn" in normalized or "uturn" in normalized:
        return "uturn"
    if "slight left" in normalized or "bear left" in normalized:
        return "slight_left"
    if "slight right" in normalized or "bear right" in normalized:
        return "slight_right"
    if "left" in normalized:
        return "left"
    if "right" in normalized:
        return "right"
    return "straight"
