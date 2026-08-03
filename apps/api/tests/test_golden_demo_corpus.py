from datetime import datetime
from zoneinfo import ZoneInfo

from naviz_api.demo_data import build_demo_graph
from naviz_api.geometry import decode_polyline
from naviz_api.models import RoutePlanRequest, RoutePreference, TravelMode
from naviz_api.routing import StreetRouter

TZ = ZoneInfo("Asia/Jerusalem")


def test_288_pinned_demo_od_time_scenarios_are_connected_and_reproducible() -> None:
    graph = build_demo_graph()
    router = StreetRouter(graph, "golden-demo-2026-08-02")
    scenarios = [
        (origin.coordinate, destination.coordinate, hour)
        for origin in graph.nodes.values()
        for destination in graph.nodes.values()
        if origin.id != destination.id
        for hour in (6, 12, 16, 20)
    ]
    assert len(scenarios) == 288
    fingerprints: list[tuple[str, float, float]] = []
    for origin, destination, hour in scenarios:
        request = RoutePlanRequest(
            origin=origin,
            destination=destination,
            depart_at=datetime(2026, 8, 2, hour, 0, tzinfo=TZ),
            mode=TravelMode.WALK,
            preference=RoutePreference.FASTEST,
        )
        route = router.plan(request)[0]
        geometry = decode_polyline(route.encoded_polyline)
        assert len(geometry) >= 2
        assert route.metrics.distance_m > 0
        assert route.metrics.duration_s > 0
        assert route.metrics.detour_time_percent == 0
        fingerprints.append(
            (route.encoded_polyline, route.metrics.distance_m, route.metrics.duration_s)
        )

    rerun: list[tuple[str, float, float]] = []
    for origin, destination, hour in scenarios:
        route = router.plan(
            RoutePlanRequest(
                origin=origin,
                destination=destination,
                depart_at=datetime(2026, 8, 2, hour, 0, tzinfo=TZ),
                mode=TravelMode.WALK,
                preference=RoutePreference.FASTEST,
            )
        )[0]
        rerun.append((route.encoded_polyline, route.metrics.distance_m, route.metrics.duration_s))
    assert rerun == fingerprints
