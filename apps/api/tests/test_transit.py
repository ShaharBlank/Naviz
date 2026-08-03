from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from naviz_api.demo_data import build_demo_graph, demo_transit
from naviz_api.models import (
    Coordinate,
    RoutePlanRequest,
    TravelMode,
    VehicleKind,
    VehicleProfile,
)
from naviz_api.routing import StreetRouter
from naviz_api.transit import RangeRaptor

TZ = ZoneInfo("Asia/Jerusalem")


def planner() -> RangeRaptor:
    street = StreetRouter(build_demo_graph(), "test-bundle")
    stops, trips = demo_transit()
    return RangeRaptor(stops, trips, street, "test-bundle")


def request(kind: VehicleKind) -> RoutePlanRequest:
    return RoutePlanRequest(
        origin=Coordinate(latitude=32.0733, longitude=34.7799),
        destination=Coordinate(latitude=32.0740, longitude=34.7925),
        depart_at=datetime(2026, 8, 2, 8, 0, tzinfo=TZ),
        mode=TravelMode.BIKE_TRANSIT,
        vehicle=VehicleProfile(kind=kind, can_fold=kind == VehicleKind.FOLDING_BIKE),
    )


def test_folding_bike_can_use_cited_demo_policy() -> None:
    routes = planner().plan(request(VehicleKind.FOLDING_BIKE))
    transit_legs = [leg for leg in routes[0].legs if leg.transit]
    assert transit_legs
    assert all(leg.transit.vehicle_rule_source for leg in transit_legs if leg.transit)
    assert routes[0].metrics.transfers <= 1


def test_full_size_bike_is_not_silently_allowed() -> None:
    with pytest.raises(ValueError, match="No permitted transit itinerary"):
        planner().plan(request(VehicleKind.FULL_SIZE_BIKE))


def test_arrive_by_returns_only_feasible_scheduled_itineraries() -> None:
    payload = request(VehicleKind.FOLDING_BIKE).model_copy(
        update={
            "depart_at": None,
            "arrive_by": datetime(2026, 8, 2, 9, 30, tzinfo=TZ),
        }
    )
    routes = planner().plan(payload)
    assert routes
    assert all(route.arrival_at <= payload.arrive_by for route in routes if payload.arrive_by)
