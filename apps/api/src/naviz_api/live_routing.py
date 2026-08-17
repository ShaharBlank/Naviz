from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from time import monotonic
from typing import Protocol

from .engine_adapters import EngineItinerary, StreetEnginePort, TransitEnginePort
from .errors import NoRouteError
from .geometry import bbox, encode_polyline
from .live_search import CoverageArea
from .models import (
    Coordinate,
    DataConfidence,
    DataQuality,
    Maneuver,
    RouteAlternative,
    RouteLeg,
    RouteMetrics,
    RoutePlanRequest,
    RoutePlanResponse,
    RoutePreference,
    TransitDetails,
    TravelMode,
)
from .route_comparison import transit_comparison_routes
from .route_features import RouteFeatureAnalyzer
from .routing import TEL_AVIV_TZ


class AsyncRoutePlanner(Protocol):
    async def plan(self, request: RoutePlanRequest, request_id: str) -> RoutePlanResponse: ...


@dataclass(slots=True)
class _RouteCacheEntry:
    expires_at: float
    response: RoutePlanResponse


class LiveRoutePlanner:
    def __init__(
        self,
        street: StreetEnginePort,
        transit: TransitEnginePort,
        coverage: CoverageArea,
        *,
        data_version: str,
        route_ttl_seconds: int,
        cache_seconds: int = 300,
        feature_analyzer: RouteFeatureAnalyzer | None = None,
    ) -> None:
        self._street = street
        self._transit = transit
        self._coverage = coverage
        self._data_version = data_version
        self._ttl = route_ttl_seconds
        self._cache_seconds = cache_seconds
        self._feature_analyzer = feature_analyzer
        self._cache: dict[str, _RouteCacheEntry] = {}
        self._lock = asyncio.Lock()

    async def plan(self, request: RoutePlanRequest, request_id: str) -> RoutePlanResponse:
        self._coverage.require(request.origin)
        self._coverage.require(request.destination)
        cache_key = sha256(request.model_dump_json().encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None and cached.expires_at > monotonic():
            return cached.response.model_copy(update={"request_id": request_id})
        engine = self._transit if request.mode in _TRANSIT_MODES else self._street
        itineraries = await engine.routes(request)
        routes = self._alternatives(request, itineraries)
        if self._feature_analyzer is not None:
            routes = await self._feature_analyzer.enrich(request, routes)
        if not routes:
            raise NoRouteError
        response = RoutePlanResponse(
            request_id=request_id,
            routes=routes,
            data_version=self._data_version,
            engine_profile="regional-live",
        )
        async with self._lock:
            if len(self._cache) >= 128:
                oldest = min(self._cache, key=lambda item: self._cache[item].expires_at)
                self._cache.pop(oldest, None)
            self._cache[cache_key] = _RouteCacheEntry(
                expires_at=monotonic() + self._cache_seconds,
                response=response,
            )
        return response

    def _alternatives(
        self, request: RoutePlanRequest, itineraries: list[EngineItinerary]
    ) -> list[RouteAlternative]:
        fastest_duration = min(
            (item.arrival_at - item.departure_at).total_seconds() for item in itineraries
        )
        result = [
            self._to_alternative(request, itinerary, index, fastest_duration)
            for index, itinerary in enumerate(itineraries)
        ]
        if request.mode in _TRANSIT_MODES and request.include_comparisons:
            return transit_comparison_routes(result, request.preference)
        if request.preference == RoutePreference.FEWER_TRANSFERS:
            result.sort(key=lambda route: (route.metrics.transfers, route.metrics.duration_s))
        else:
            result.sort(key=lambda route: route.metrics.duration_s)
        return result[:3]

    def _to_alternative(
        self,
        request: RoutePlanRequest,
        itinerary: EngineItinerary,
        index: int,
        fastest_duration: float,
    ) -> RouteAlternative:
        all_geometry: list[Coordinate] = []
        route_legs: list[RouteLeg] = []
        route_maneuvers: list[Maneuver] = []
        walking_distance = cycling_distance = total_distance = 0.0
        transit_legs = 0
        geometry_offset = 0
        for leg_index, leg in enumerate(itinerary.legs):
            geometry = list(leg.geometry)
            if not geometry:
                continue
            if all_geometry and all_geometry[-1] == geometry[0]:
                all_geometry.extend(geometry[1:])
            else:
                all_geometry.extend(geometry)
            maneuvers = [
                Maneuver(
                    id=f"engine-{index}-{leg_index}-{maneuver_index}",
                    instruction_key=(
                        "navigation.arrive"
                        if maneuver.modifier == "arrive"
                        else "navigation.depart"
                        if maneuver_index == 0 and leg_index == 0
                        else "navigation.turn"
                    ),
                    instruction_text=maneuver.instruction,
                    modifier=maneuver.modifier,
                    street_name=maneuver.street_name,
                    distance_m=round(maneuver.distance_m, 1),
                    duration_s=round(maneuver.duration_s, 1),
                    geometry_index=min(
                        geometry_offset + maneuver.begin_geometry_index,
                        max(0, len(all_geometry) - 1),
                    ),
                    coordinate=geometry[min(maneuver.begin_geometry_index, len(geometry) - 1)],
                )
                for maneuver_index, maneuver in enumerate(leg.maneuvers)
            ]
            if not maneuvers and request.mode in _TRANSIT_MODES:
                if leg.mode == TravelMode.TRANSIT:
                    service = " ".join(value for value in (leg.route_name, leg.headsign) if value)
                    instruction_key = "navigation.board"
                    modifier = "board"
                    street_name = service or leg.to_name
                else:
                    instruction_key = "navigation.depart"
                    modifier = "depart"
                    street_name = leg.to_name
                maneuvers = [
                    Maneuver(
                        id=f"engine-{index}-{leg_index}-handoff",
                        instruction_key=instruction_key,
                        modifier=modifier,
                        street_name=street_name,
                        distance_m=round(leg.distance_m, 1),
                        duration_s=round(leg.duration_s, 1),
                        geometry_index=geometry_offset,
                        coordinate=geometry[0],
                    )
                ]
            if leg.mode == TravelMode.TRANSIT:
                transit_legs += 1
            elif leg.mode == TravelMode.WALK:
                walking_distance += leg.distance_m
            elif leg.mode in {TravelMode.BIKE, TravelMode.SCOOTER}:
                cycling_distance += leg.distance_m
            total_distance += leg.distance_m
            transit = None
            if leg.mode == TravelMode.TRANSIT:
                departure = leg.departure_at or itinerary.departure_at
                arrival = leg.arrival_at or departure + timedelta(seconds=leg.duration_s)
                transit = TransitDetails(
                    agency=leg.agency or "",
                    route_short_name=leg.route_name or "",
                    headsign=leg.headsign or "",
                    departure_at=departure,
                    arrival_at=arrival,
                    stops=0,
                    realtime=False,
                    vehicle_rule_source=(
                        "Israel Ministry of Transport 2023 folded-vehicle policy"
                        if leg.bicycle_permission == "ALLOWED_FOLDED_POLICY"
                        else "MOTIS effective GTFS bicycle permission"
                        if leg.bicycle_permission == "ALLOWED_GTFS"
                        else None
                    ),
                )
            route_legs.append(
                RouteLeg(
                    mode=leg.mode,
                    from_name=leg.from_name,
                    to_name=leg.to_name,
                    encoded_polyline=encode_polyline(geometry),
                    distance_m=round(leg.distance_m, 1),
                    duration_s=round(leg.duration_s, 1),
                    maneuvers=maneuvers,
                    transit=transit,
                )
            )
            route_maneuvers.extend(maneuvers)
            geometry_offset = max(0, len(all_geometry) - 1)
        if len(all_geometry) < 2:
            raise NoRouteError
        duration_s = (itinerary.arrival_at - itinerary.departure_at).total_seconds()
        encoded = encode_polyline(all_geometry)
        route_id = sha256(
            f"{self._data_version}|{request.mode.value}|{encoded}|{itinerary.departure_at}".encode()
        ).hexdigest()[:20]
        label_key = (
            "route.transitRecommended"
            if request.mode in _TRANSIT_MODES
            else ("route.fastest" if index == 0 else "route.alternative")
        )
        if not route_maneuvers and request.mode not in _TRANSIT_MODES:
            route_maneuvers = [
                Maneuver(
                    id=f"engine-{index}-depart",
                    instruction_key="navigation.depart",
                    modifier="depart",
                    distance_m=round(total_distance, 1),
                    duration_s=round(duration_s, 1),
                    geometry_index=0,
                    coordinate=all_geometry[0],
                ),
                Maneuver(
                    id=f"engine-{index}-arrive",
                    instruction_key="navigation.arrive",
                    modifier="arrive",
                    distance_m=0,
                    duration_s=0,
                    geometry_index=len(all_geometry) - 1,
                    coordinate=all_geometry[-1],
                ),
            ]
        elif request.mode in _TRANSIT_MODES:
            route_maneuvers.append(
                Maneuver(
                    id=f"engine-{index}-arrive",
                    instruction_key="navigation.arrive",
                    modifier="arrive",
                    distance_m=0,
                    duration_s=0,
                    geometry_index=len(all_geometry) - 1,
                    coordinate=all_geometry[-1],
                )
            )
        return RouteAlternative(
            id=route_id,
            label_key=label_key,
            encoded_polyline=encoded,
            bbox=bbox(all_geometry),
            departure_at=itinerary.departure_at,
            arrival_at=itinerary.arrival_at,
            legs=route_legs,
            maneuvers=route_maneuvers,
            annotations=[],
            metrics=RouteMetrics(
                distance_m=round(total_distance, 1),
                duration_s=round(duration_s, 1),
                walking_distance_m=round(walking_distance, 1),
                cycling_distance_m=round(cycling_distance, 1),
                transfers=max(0, transit_legs - 1),
                detour_time_percent=_percent(duration_s, fastest_duration),
            ),
            quality=DataQuality(
                confidence=DataConfidence.HIGH,
                scheduled_transit=request.mode in _TRANSIT_MODES,
                realtime_transit=False,
                dataset_versions={"regional_data": self._data_version},
            ),
            warnings=list(itinerary.warnings),
            fallback_reason=itinerary.fallback_reason,
            expires_at=datetime.now(TEL_AVIV_TZ) + timedelta(seconds=self._ttl),
        )


_TRANSIT_MODES = {
    TravelMode.TRANSIT,
    TravelMode.BIKE_TRANSIT,
    TravelMode.SCOOTER_TRANSIT,
    TravelMode.RENTAL_TRANSIT,
}


def _percent(value: float, baseline: float) -> float:
    return 0 if baseline <= 0 else round(max(0.0, (value / baseline - 1) * 100), 2)
