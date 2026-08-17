from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import pairwise

from .demo_data import ScheduledTrip, TransitStop
from .geometry import bbox, encode_polyline, haversine_m
from .graph import PathResult
from .models import (
    DataConfidence,
    DataQuality,
    RouteAlternative,
    RouteLeg,
    RouteMetrics,
    RoutePlanRequest,
    TransitDetails,
    TravelMode,
    VehicleKind,
)
from .route_comparison import transit_comparison_routes
from .routing import StreetRouter, build_annotations, build_maneuvers, normalize_departure


@dataclass(frozen=True, slots=True)
class TransitRide:
    trip: ScheduledTrip
    service_start: datetime
    board_index: int
    alight_index: int


@dataclass(frozen=True, slots=True)
class TransitLabel:
    arrival: datetime
    access_path: PathResult
    rides: tuple[TransitRide, ...]


class RangeRaptor:
    """Compact bounded-round RAPTOR used by the $0 hosted profile."""

    def __init__(
        self,
        stops: Mapping[str, TransitStop],
        trips: tuple[ScheduledTrip, ...],
        street_router: StreetRouter,
        data_version: str,
    ) -> None:
        self._stops = stops
        self._trips = trips
        self._street = street_router
        self.data_version = data_version

    def plan(self, request: RoutePlanRequest, expires_in_s: int = 900) -> list[RouteAlternative]:
        if request.arrive_by:
            target = normalize_departure(request.arrive_by)
            for minutes_before in range(5, 241, 5):
                trial = request.model_copy(
                    update={
                        "depart_at": target - timedelta(minutes=minutes_before),
                        "arrive_by": None,
                    }
                )
                try:
                    routes = self.plan(trial, expires_in_s)
                except ValueError:
                    continue
                feasible = [route for route in routes if route.arrival_at <= target]
                if feasible:
                    return sorted(feasible, key=lambda route: route.arrival_at, reverse=True)
            raise ValueError("No permitted transit itinerary arrives by the requested time")
        departure = normalize_departure(request.depart_at)
        access_mode, onboard_vehicle = self._modes(request)
        labels = self._initial_labels(request, departure, access_mode)
        transit_labels: dict[str, TransitLabel] = {}
        for _round in range(3):
            next_labels = self._scan_round(labels, onboard_vehicle)
            for stop_id, label in next_labels.items():
                current = transit_labels.get(stop_id)
                if current is None or label.arrival < current.arrival:
                    transit_labels[stop_id] = label
            if not next_labels:
                break
            labels = next_labels

        candidates: list[tuple[datetime, str, TransitLabel, PathResult]] = []
        for stop_id, label in transit_labels.items():
            stop = self._stops[stop_id]
            try:
                egress = self._street.path_for_access(
                    stop.coordinate, request.destination, access_mode, label.arrival
                )
            except ValueError:
                continue
            final_arrival = label.arrival + timedelta(seconds=egress.duration_s)
            candidates.append((final_arrival, stop_id, label, egress))
        if not candidates:
            vehicle = onboard_vehicle.value.replace("_", " ")
            raise ValueError(
                f"No permitted transit itinerary was found for {vehicle}; "
                "operator rules are conservative."
            )
        candidates.sort(key=lambda item: (item[0], len(item[2].rides)))
        routes = [
            self._to_alternative(request, departure, stop_id, label, egress, expires_in_s)
            for _, stop_id, label, egress in candidates[:3]
        ]
        if request.include_comparisons:
            return transit_comparison_routes(routes, request.preference)
        return routes

    def _initial_labels(
        self, request: RoutePlanRequest, departure: datetime, access_mode: TravelMode
    ) -> dict[str, TransitLabel]:
        labels: dict[str, TransitLabel] = {}
        for stop_id, stop in self._stops.items():
            try:
                path = self._street.path_for_access(
                    request.origin, stop.coordinate, access_mode, departure
                )
            except ValueError:
                continue
            if path.distance_m > 3_000:
                continue
            labels[stop_id] = TransitLabel(
                arrival=departure + timedelta(seconds=path.duration_s),
                access_path=path,
                rides=(),
            )
        return labels

    def _scan_round(
        self, labels: Mapping[str, TransitLabel], vehicle: VehicleKind
    ) -> dict[str, TransitLabel]:
        results: dict[str, TransitLabel] = {}
        for trip in self._trips:
            if vehicle != VehicleKind.NONE and vehicle not in trip.allowed_vehicles:
                continue
            for board_index, board_time in enumerate(trip.stop_times[:-1]):
                previous = labels.get(board_time.stop_id)
                if previous is None:
                    continue
                service_start = trip.next_start(
                    previous.arrival - timedelta(seconds=board_time.departure_offset_s)
                )
                if service_start is None:
                    continue
                departure_at = service_start + timedelta(seconds=board_time.departure_offset_s)
                if departure_at < previous.arrival:
                    continue
                for alight_index in range(board_index + 1, len(trip.stop_times)):
                    alight_time = trip.stop_times[alight_index]
                    arrival = service_start + timedelta(seconds=alight_time.arrival_offset_s)
                    candidate = TransitLabel(
                        arrival=arrival,
                        access_path=previous.access_path,
                        rides=(
                            *previous.rides,
                            TransitRide(trip, service_start, board_index, alight_index),
                        ),
                    )
                    current = results.get(alight_time.stop_id)
                    if current is None or candidate.arrival < current.arrival:
                        results[alight_time.stop_id] = candidate
        return results

    def _to_alternative(
        self,
        request: RoutePlanRequest,
        departure: datetime,
        final_stop_id: str,
        label: TransitLabel,
        egress: PathResult,
        expires_in_s: int,
    ) -> RouteAlternative:
        access_mode, _ = self._modes(request)
        legs: list[RouteLeg] = []
        access_geometry = label.access_path.geometry or [request.origin]
        all_geometry = access_geometry.copy()
        access_polyline = encode_polyline(access_geometry)
        legs.append(
            RouteLeg(
                mode=access_mode,
                from_name="Origin",
                to_name="Transit stop",
                encoded_polyline=access_polyline,
                distance_m=round(label.access_path.distance_m, 1),
                duration_s=round(label.access_path.duration_s, 1),
                maneuvers=build_maneuvers(label.access_path),
                annotations=build_annotations(label.access_path, departure, access_mode),
            )
        )
        current_time = departure + timedelta(seconds=label.access_path.duration_s)
        transit_distance = 0.0
        for ride in label.rides:
            trip = ride.trip
            board = trip.stop_times[ride.board_index]
            alight = trip.stop_times[ride.alight_index]
            ride_geometry = [
                self._stops[item.stop_id].coordinate
                for item in trip.stop_times[ride.board_index : ride.alight_index + 1]
            ]
            if all_geometry[-1] != ride_geometry[0]:
                all_geometry.append(ride_geometry[0])
            all_geometry.extend(ride_geometry[1:])
            distance = sum(haversine_m(first, second) for first, second in pairwise(ride_geometry))
            transit_distance += distance
            board_at = ride.service_start + timedelta(seconds=board.departure_offset_s)
            alight_at = ride.service_start + timedelta(seconds=alight.arrival_offset_s)
            legs.append(
                RouteLeg(
                    mode=TravelMode.TRANSIT,
                    from_name=self._stops[board.stop_id].name,
                    to_name=self._stops[alight.stop_id].name,
                    encoded_polyline=encode_polyline(ride_geometry),
                    distance_m=round(distance, 1),
                    duration_s=(alight_at - board_at).total_seconds(),
                    transit=TransitDetails(
                        agency=trip.agency,
                        route_short_name=trip.route_short_name,
                        headsign=trip.headsign,
                        departure_at=board_at,
                        arrival_at=alight_at,
                        stops=ride.alight_index - ride.board_index,
                        realtime=False,
                        vehicle_rule_source=trip.policy_source,
                    ),
                )
            )
            current_time = alight_at
        egress_geometry = egress.geometry or [
            self._stops[final_stop_id].coordinate,
            request.destination,
        ]
        if all_geometry[-1] != egress_geometry[0]:
            all_geometry.append(egress_geometry[0])
        all_geometry.extend(egress_geometry[1:])
        legs.append(
            RouteLeg(
                mode=access_mode,
                from_name=self._stops[final_stop_id].name,
                to_name="Destination",
                encoded_polyline=encode_polyline(egress_geometry),
                distance_m=round(egress.distance_m, 1),
                duration_s=round(egress.duration_s, 1),
                maneuvers=build_maneuvers(egress),
                annotations=build_annotations(egress, current_time, access_mode),
            )
        )
        final_arrival = label.arrival + timedelta(seconds=egress.duration_s)
        encoded = encode_polyline(all_geometry)
        route_id = sha256(
            f"{self.data_version}|transit|{encoded}|{departure.isoformat()}".encode()
        ).hexdigest()[:20]
        active_distance = label.access_path.distance_m + egress.distance_m
        warnings = [
            "Times are scheduled; no Ministry SIRI credentials are configured.",
            "Demo policy data must be replaced with cited, effective-dated operator rules.",
        ]
        return RouteAlternative(
            id=route_id,
            label_key="route.transitRecommended",
            encoded_polyline=encoded,
            bbox=bbox(all_geometry),
            departure_at=departure,
            arrival_at=final_arrival,
            legs=legs,
            maneuvers=[maneuver for leg in legs for maneuver in leg.maneuvers],
            annotations=[annotation for leg in legs for annotation in leg.annotations],
            metrics=RouteMetrics(
                distance_m=round(active_distance + transit_distance, 1),
                duration_s=(final_arrival - departure).total_seconds(),
                walking_distance_m=round(active_distance, 1)
                if access_mode == TravelMode.WALK
                else 0,
                cycling_distance_m=round(active_distance, 1)
                if access_mode in {TravelMode.BIKE, TravelMode.SCOOTER}
                else 0,
                transfers=max(0, len(label.rides) - 1),
            ),
            quality=DataQuality(
                confidence=DataConfidence.MEDIUM,
                scheduled_transit=True,
                realtime_transit=False,
                warnings=warnings,
                dataset_versions={"regional_bundle": self.data_version, "gtfs": "demo"},
            ),
            warnings=warnings,
            expires_at=datetime.now(departure.tzinfo) + timedelta(seconds=expires_in_s),
        )

    @staticmethod
    def _modes(request: RoutePlanRequest) -> tuple[TravelMode, VehicleKind]:
        if request.mode == TravelMode.BIKE_TRANSIT:
            kind = request.vehicle.kind
            if kind == VehicleKind.NONE:
                kind = VehicleKind.FULL_SIZE_BIKE
            return TravelMode.BIKE, kind
        if request.mode == TravelMode.SCOOTER_TRANSIT:
            kind = request.vehicle.kind
            if kind == VehicleKind.NONE:
                kind = VehicleKind.PERSONAL_SCOOTER
            return TravelMode.SCOOTER, kind
        return TravelMode.WALK, VehicleKind.NONE
