from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from naviz_api.demo_data import build_demo_graph
from naviz_api.models import (
    Coordinate,
    RouteConstraints,
    RoutePlanRequest,
    RoutePreference,
    TravelMode,
    VehicleProfile,
)
from naviz_api.routing import StreetRouter

TZ = ZoneInfo("Asia/Jerusalem")
ORIGIN = Coordinate(latitude=32.0733, longitude=34.7799)
DESTINATION = Coordinate(latitude=32.0791, longitude=34.7682)


def router() -> StreetRouter:
    return StreetRouter(build_demo_graph(), "test-bundle")


def test_balanced_shade_respects_default_time_cap() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 13, 0, tzinfo=TZ),
        mode=TravelMode.WALK,
        preference=RoutePreference.BALANCED_SHADE,
    )
    routes = router().plan(request)
    assert routes
    assert routes[0].metrics.detour_time_percent <= 15
    assert routes[0].metrics.shade_fraction is not None
    assert routes[0].quality.dataset_versions["regional_bundle"] == "test-bundle"


def test_maximum_shade_obeys_explicit_zero_detour() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 13, 0, tzinfo=TZ),
        mode=TravelMode.WALK,
        preference=RoutePreference.MAXIMUM_SHADE,
        constraints=RouteConstraints(maximum_time_detour_percent=0),
    )
    routes = router().plan(request)
    assert len(routes) == 1
    assert routes[0].metrics.detour_time_percent == 0


def test_fewer_lights_never_exceeds_caps() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=Coordinate(latitude=32.0832, longitude=34.7957),
        depart_at=datetime(2026, 8, 2, 9, 0, tzinfo=TZ),
        mode=TravelMode.CAR,
        preference=RoutePreference.FEWER_LIGHTS,
    )
    routes = router().plan(request)
    assert routes[0].metrics.detour_time_percent <= 10
    assert routes[0].metrics.detour_distance_percent <= 15


def test_truck_warning_when_restriction_data_is_incomplete() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        mode=TravelMode.TRUCK,
        preference=RoutePreference.FASTEST,
        vehicle=VehicleProfile(height_m=3.5, weight_t=12),
    )
    route = router().plan(request)[0]
    assert any("incomplete" in warning.lower() for warning in route.warnings)


def test_invalid_walk_preference_is_rejected() -> None:
    with pytest.raises(ValueError):
        RoutePlanRequest(
            origin=ORIGIN,
            destination=DESTINATION,
            mode=TravelMode.WALK,
            preference=RoutePreference.FEWER_LIGHTS,
        )


def test_street_arrive_by_sets_each_alternative_to_requested_arrival() -> None:
    target = datetime(2026, 8, 2, 14, 0, tzinfo=TZ)
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        arrive_by=target,
        mode=TravelMode.WALK,
        preference=RoutePreference.BALANCED_SHADE,
    )
    routes = router().plan(request)
    assert routes
    assert all(route.arrival_at == target for route in routes)
    assert all(route.departure_at < target for route in routes)
