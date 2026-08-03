from datetime import datetime
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st
from naviz_api.demo_data import build_demo_graph
from naviz_api.geometry import decode_polyline, encode_polyline
from naviz_api.models import Coordinate, RouteConstraints, RoutePlanRequest, RoutePreference
from naviz_api.routing import StreetRouter

TZ = ZoneInfo("Asia/Jerusalem")


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=32.03, max_value=32.15, allow_nan=False),
            st.floats(min_value=34.72, max_value=34.86, allow_nan=False),
        ),
        min_size=1,
        max_size=20,
    )
)
def test_polyline6_round_trip_is_within_quantization(points: list[tuple[float, float]]) -> None:
    coordinates = [
        Coordinate(latitude=latitude, longitude=longitude) for latitude, longitude in points
    ]
    decoded = decode_polyline(encode_polyline(coordinates))
    assert len(decoded) == len(coordinates)
    for actual, expected in zip(decoded, coordinates, strict=True):
        assert abs(actual.latitude - expected.latitude) <= 0.00000051
        assert abs(actual.longitude - expected.longitude) <= 0.00000051


@settings(max_examples=30, deadline=None)
@given(st.floats(min_value=0, max_value=30, allow_nan=False))
def test_shade_route_respects_every_supported_detour_cap(cap: float) -> None:
    router = StreetRouter(build_demo_graph(), "property-bundle")
    request = RoutePlanRequest(
        origin=Coordinate(latitude=32.0733, longitude=34.7799),
        destination=Coordinate(latitude=32.0791, longitude=34.7682),
        depart_at=datetime(2026, 8, 2, 13, 0, tzinfo=TZ),
        preference=RoutePreference.MAXIMUM_SHADE,
        constraints=RouteConstraints(maximum_time_detour_percent=cap),
    )
    assert all(route.metrics.detour_time_percent <= cap + 1e-9 for route in router.plan(request))


@given(st.integers(min_value=0, max_value=1_439))
def test_interpolated_shade_exposure_remains_a_fraction(minute: int) -> None:
    edge = next(edge for edge in build_demo_graph().edges if edge.shade_profile)
    at = datetime(2026, 8, 2, minute // 60, minute % 60, tzinfo=TZ)
    assert 0 <= edge.shade_fraction(at) <= 1
