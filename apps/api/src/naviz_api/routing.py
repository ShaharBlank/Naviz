from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from .geometry import bbox, bearing_degrees, encode_polyline, turn_modifier
from .graph import CompactGraph, GraphEdge, PathResult
from .models import (
    Coordinate,
    DataConfidence,
    DataQuality,
    Maneuver,
    RouteAlternative,
    RouteLeg,
    RouteMetrics,
    RoutePlanRequest,
    RoutePreference,
    SegmentAnnotation,
    TravelMode,
)

TEL_AVIV_TZ = ZoneInfo("Asia/Jerusalem")


MODE_SPEED_MPS: dict[TravelMode, float] = {
    TravelMode.WALK: 1.35,
    TravelMode.BIKE: 4.7,
    TravelMode.SCOOTER: 5.0,
    TravelMode.CAR: 10.5,
    TravelMode.MOTORCYCLE: 11.5,
    TravelMode.TRUCK: 8.5,
}


@dataclass(frozen=True, slots=True)
class PlannedPath:
    label_key: str
    path: PathResult
    fallback_reason: str | None = None


class StreetRouter:
    def __init__(self, graph: CompactGraph, data_version: str) -> None:
        self._graph = graph
        self.data_version = data_version

    def plan(self, request: RoutePlanRequest, expires_in_s: int = 900) -> list[RouteAlternative]:
        if request.mode not in MODE_SPEED_MPS:
            raise ValueError(f"{request.mode.value} is not a street-only mode")
        departure = normalize_departure(request.depart_at or request.arrive_by)
        fastest = self._shortest(request, departure)
        if request.arrive_by:
            # Time-dependent profiles require a small fixed-point iteration because the
            # requested timestamp is an arrival, while edge exposure is evaluated on entry.
            for _ in range(3):
                departure = normalize_departure(request.arrive_by) - timedelta(
                    seconds=fastest.duration_s
                )
                updated = self._shortest(request, departure)
                if abs(updated.duration_s - fastest.duration_s) < 1:
                    fastest = updated
                    break
                fastest = updated
        planned = [PlannedPath("route.fastest", fastest)]

        if request.mode == TravelMode.WALK and request.preference in {
            RoutePreference.BALANCED_SHADE,
            RoutePreference.MAXIMUM_SHADE,
        }:
            cap = self._detour_cap(request)
            preferred = self._best_shaded(request, departure, fastest, cap)
            if preferred.edges != fastest.edges:
                label = (
                    "route.balancedShade"
                    if request.preference == RoutePreference.BALANCED_SHADE
                    else "route.maximumShade"
                )
                planned.insert(0, PlannedPath(label, preferred))
            else:
                planned[0] = PlannedPath(
                    planned[0].label_key,
                    fastest,
                    "No shaded alternative satisfies the detour limit.",
                )
        elif request.preference == RoutePreference.FEWER_LIGHTS:
            low_signal = self._fewer_lights(request, departure, fastest)
            if low_signal is not None:
                planned.insert(0, PlannedPath("route.fewerLights", low_signal))
            else:
                planned[0] = PlannedPath(
                    "route.fastest",
                    fastest,
                    "No materially lower-signal route satisfies the detour limits.",
                )
        elif request.preference == RoutePreference.SAFER_STREETS:
            comfortable = self._safer_streets(request, departure, fastest)
            if comfortable.edges != fastest.edges:
                planned.insert(0, PlannedPath("route.saferStreets", comfortable))

        return [
            self._to_alternative(
                request=request,
                departure=departure,
                planned=item,
                fastest=fastest,
                expires_in_s=expires_in_s,
            )
            for item in _deduplicate(planned)
        ]

    def path_for_access(
        self,
        origin: Coordinate,
        destination: Coordinate,
        mode: TravelMode,
        departure: datetime,
    ) -> PathResult:
        speed = MODE_SPEED_MPS[mode]

        def cost(edge: GraphEdge, elapsed: float) -> tuple[float, float, float]:
            duration = edge.distance_m / speed
            at = departure + timedelta(seconds=elapsed)
            sun = duration * (1 - edge.shade_fraction(at)) if mode == TravelMode.WALK else 0
            return duration, duration, sun

        from .models import VehicleProfile

        return self._graph.shortest_path(
            origin,
            destination,
            mode,
            VehicleProfile(),
            cost,
            maximum_speed_mps=speed,
        )

    def _shortest(self, request: RoutePlanRequest, departure: datetime) -> PathResult:
        speed = MODE_SPEED_MPS[request.mode]

        def cost(edge: GraphEdge, elapsed: float) -> tuple[float, float, float]:
            duration = edge.distance_m / speed
            at = departure + timedelta(seconds=elapsed)
            sun = duration * (1 - edge.shade_fraction(at)) if request.mode == TravelMode.WALK else 0
            return duration, duration, sun

        return self._graph.shortest_path(
            request.origin,
            request.destination,
            request.mode,
            request.vehicle,
            cost,
            maximum_speed_mps=speed,
            allow_low_confidence_crossings=request.constraints.allow_low_confidence_crossings,
        )

    def _best_shaded(
        self,
        request: RoutePlanRequest,
        departure: datetime,
        fastest: PathResult,
        cap: float,
    ) -> PathResult:
        speed = MODE_SPEED_MPS[TravelMode.WALK]
        candidates = [fastest]
        penalties = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
        for penalty in penalties:

            def cost(
                edge: GraphEdge, elapsed: float, factor: float = penalty
            ) -> tuple[float, float, float]:
                duration = edge.distance_m / speed
                at = departure + timedelta(seconds=elapsed)
                sun = duration * (1 - edge.shade_fraction(at))
                return duration + factor * sun, duration, sun

            path = self._graph.shortest_path(
                request.origin,
                request.destination,
                request.mode,
                request.vehicle,
                cost,
                maximum_speed_mps=speed,
                allow_low_confidence_crossings=request.constraints.allow_low_confidence_crossings,
            )
            if path.duration_s <= fastest.duration_s * (1 + cap / 100):
                candidates.append(path)
        return min(candidates, key=lambda path: (path.sun_exposure_s, path.duration_s))

    def _fewer_lights(
        self,
        request: RoutePlanRequest,
        departure: datetime,
        fastest: PathResult,
    ) -> PathResult | None:
        speed = MODE_SPEED_MPS[request.mode]

        def cost(edge: GraphEdge, _: float) -> tuple[float, float, float]:
            duration = edge.distance_m / speed
            signal_delay = 25.0 if edge.traffic_signal_id else 0.0
            return duration + signal_delay, duration, 0.0

        candidate = self._graph.shortest_path(
            request.origin,
            request.destination,
            request.mode,
            request.vehicle,
            cost,
            maximum_speed_mps=speed,
        )
        reduction = len(fastest.signal_ids) - len(candidate.signal_ids)
        material = reduction >= 2 or (
            len(fastest.signal_ids) > 0 and reduction / len(fastest.signal_ids) >= 0.2
        )
        time_cap = request.constraints.maximum_time_detour_percent or 10.0
        distance_cap = request.constraints.maximum_distance_detour_percent or 15.0
        if not material:
            return None
        if candidate.duration_s > fastest.duration_s * (1 + time_cap / 100):
            return None
        if candidate.distance_m > fastest.distance_m * (1 + distance_cap / 100):
            return None
        return candidate

    def _safer_streets(
        self,
        request: RoutePlanRequest,
        departure: datetime,
        fastest: PathResult,
    ) -> PathResult:
        speed = MODE_SPEED_MPS[request.mode]

        def cost(edge: GraphEdge, _: float) -> tuple[float, float, float]:
            duration = edge.distance_m / speed
            discomfort = duration * (1 - edge.bicycle_comfort) * 1.5
            return duration + discomfort, duration, 0.0

        candidate = self._graph.shortest_path(
            request.origin,
            request.destination,
            request.mode,
            request.vehicle,
            cost,
            maximum_speed_mps=speed,
        )
        return candidate if candidate.duration_s <= fastest.duration_s * 1.2 else fastest

    @staticmethod
    def _detour_cap(request: RoutePlanRequest) -> float:
        if request.constraints.maximum_time_detour_percent is not None:
            return request.constraints.maximum_time_detour_percent
        return 15.0 if request.preference == RoutePreference.BALANCED_SHADE else 30.0

    def _to_alternative(
        self,
        request: RoutePlanRequest,
        departure: datetime,
        planned: PlannedPath,
        fastest: PathResult,
        expires_in_s: int,
    ) -> RouteAlternative:
        path = planned.path
        if request.arrive_by:
            departure = normalize_departure(request.arrive_by) - timedelta(seconds=path.duration_s)
        geometry = path.geometry
        maneuvers = build_maneuvers(path)
        annotations = build_annotations(path, departure, request.mode)
        shade_distance = sum(
            edge.distance_m * edge.shade_fraction(departure) for edge in path.edges
        )
        high_confidence_shade = sum(
            edge.distance_m * edge.shade_fraction(departure)
            for edge in path.edges
            if edge.shade_confidence == DataConfidence.HIGH
        )
        shade_fraction = shade_distance / path.distance_m if path.distance_m else None
        high_fraction = high_confidence_shade / path.distance_m if path.distance_m else None
        encoded = encode_polyline(geometry)
        route_id = sha256(
            f"{self.data_version}|{request.mode}|{planned.label_key}|{encoded}".encode()
        ).hexdigest()[:20]
        arrival = departure + timedelta(seconds=path.duration_s)
        warnings = [planned.fallback_reason] if planned.fallback_reason else []
        if request.mode == TravelMode.TRUCK and any(
            edge.max_height_m is None or edge.max_weight_t is None for edge in path.edges
        ):
            warnings.append("Truck restriction data is incomplete on part of this route.")
        metrics = RouteMetrics(
            distance_m=round(path.distance_m, 1),
            duration_s=round(path.duration_s, 1),
            walking_distance_m=round(path.distance_m, 1) if request.mode == TravelMode.WALK else 0,
            cycling_distance_m=(
                round(path.distance_m, 1)
                if request.mode in {TravelMode.BIKE, TravelMode.SCOOTER}
                else 0
            ),
            shade_fraction=round(shade_fraction, 4)
            if request.mode == TravelMode.WALK and shade_fraction is not None
            else None,
            high_confidence_shade_fraction=(
                round(high_fraction, 4)
                if request.mode == TravelMode.WALK and high_fraction is not None
                else None
            ),
            sun_exposure_minutes=(
                round(path.sun_exposure_s / 60, 2) if request.mode == TravelMode.WALK else None
            ),
            traffic_signals=len(path.signal_ids)
            if request.mode
            in {
                TravelMode.CAR,
                TravelMode.MOTORCYCLE,
                TravelMode.TRUCK,
            }
            else None,
            signals_avoided=(
                max(0, len(fastest.signal_ids) - len(path.signal_ids))
                if request.preference == RoutePreference.FEWER_LIGHTS
                else None
            ),
            detour_time_percent=_percent(path.duration_s, fastest.duration_s),
            detour_distance_percent=_percent(path.distance_m, fastest.distance_m),
        )
        quality_warnings = [
            "Bundled demo graph: replace with a validated Tel Aviv data artifact before field use."
        ]
        return RouteAlternative(
            id=route_id,
            label_key=planned.label_key,
            encoded_polyline=encoded,
            bbox=bbox(geometry),
            departure_at=departure,
            arrival_at=arrival,
            legs=[
                RouteLeg(
                    mode=request.mode,
                    from_name="Origin",
                    to_name="Destination",
                    encoded_polyline=encoded,
                    distance_m=metrics.distance_m,
                    duration_s=metrics.duration_s,
                    maneuvers=maneuvers,
                    annotations=annotations,
                )
            ],
            maneuvers=maneuvers,
            annotations=annotations,
            metrics=metrics,
            quality=DataQuality(
                confidence=DataConfidence.MEDIUM,
                shade_sources=["demo:directional-horizon-profile"]
                if request.mode == TravelMode.WALK
                else [],
                warnings=quality_warnings,
                dataset_versions={"regional_bundle": self.data_version},
            ),
            warnings=warnings,
            fallback_reason=planned.fallback_reason,
            expires_at=datetime.now(TEL_AVIV_TZ) + timedelta(seconds=expires_in_s),
        )


def normalize_departure(value: datetime | None) -> datetime:
    result = value or datetime.now(TEL_AVIV_TZ)
    if result.tzinfo is None:
        return result.replace(tzinfo=TEL_AVIV_TZ)
    return result.astimezone(TEL_AVIV_TZ)


def build_maneuvers(path: PathResult) -> list[Maneuver]:
    if not path.edges:
        return []
    result: list[Maneuver] = []
    previous_bearing: float | None = None
    geometry_index = 0
    for index, edge in enumerate(path.edges):
        current_bearing = bearing_degrees(edge.geometry[0], edge.geometry[-1])
        modifier = (
            "depart"
            if previous_bearing is None
            else turn_modifier(previous_bearing, current_bearing)
        )
        result.append(
            Maneuver(
                id=f"maneuver-{edge.id}",
                instruction_key="navigation.depart" if index == 0 else "navigation.turn",
                modifier=modifier,
                street_name=edge.name,
                distance_m=round(edge.distance_m, 1),
                duration_s=0,
                geometry_index=geometry_index,
                coordinate=edge.geometry[0],
            )
        )
        geometry_index += len(edge.geometry) - 1
        previous_bearing = current_bearing
    result.append(
        Maneuver(
            id="maneuver-arrive",
            instruction_key="navigation.arrive",
            modifier="arrive",
            distance_m=0,
            duration_s=0,
            geometry_index=geometry_index,
            coordinate=path.edges[-1].geometry[-1],
        )
    )
    return result


def build_annotations(
    path: PathResult, departure: datetime, mode: TravelMode
) -> list[SegmentAnnotation]:
    result: list[SegmentAnnotation] = []
    geometry_index = 0
    elapsed = 0.0
    speed = MODE_SPEED_MPS[mode]
    for edge in path.edges:
        shade = edge.shade_fraction(departure + timedelta(seconds=elapsed))
        if shade >= 0.75:
            classification = "shade"
        elif shade >= 0.25:
            classification = "mixed"
        else:
            classification = "sun"
        result.append(
            SegmentAnnotation(
                start_index=geometry_index,
                end_index=geometry_index + len(edge.geometry) - 1,
                classification=classification,
                selected_side=edge.selected_side,
                shade_fraction=round(shade, 4) if mode == TravelMode.WALK else None,
                confidence=edge.shade_confidence,
                crossing_kind=edge.crossing_kind,
            )
        )
        geometry_index += len(edge.geometry) - 1
        elapsed += edge.distance_m / speed
    return result


def _percent(value: float, baseline: float) -> float:
    if baseline <= 0:
        return 0
    return round(max(0.0, (value / baseline - 1) * 100), 2)


def _deduplicate(paths: Iterable[PlannedPath]) -> list[PlannedPath]:
    result: list[PlannedPath] = []
    seen: set[tuple[int, ...]] = set()
    for planned in paths:
        key = tuple(edge.id for edge in planned.path.edges)
        if key not in seen:
            result.append(planned)
            seen.add(key)
    return result
