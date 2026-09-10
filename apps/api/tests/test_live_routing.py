from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from naviz_api.config import Settings
from naviz_api.engine_adapters import EngineItinerary, EngineLeg, EngineManeuver
from naviz_api.errors import OutsideCoverageError
from naviz_api.live_routing import LiveRoutePlanner
from naviz_api.live_search import CoverageArea
from naviz_api.models import Coordinate, RoutePlanRequest, TravelMode

TZ = ZoneInfo("Asia/Jerusalem")
ORIGIN = Coordinate(latitude=32.0733, longitude=34.7799)
DESTINATION = Coordinate(latitude=32.0837, longitude=34.8141)


class FakeEngine:
    async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]:
        departure = request.depart_at or datetime(2026, 8, 6, 9, 0, tzinfo=TZ)
        return [
            EngineItinerary(
                departure_at=departure,
                arrival_at=departure + timedelta(minutes=12),
                legs=(
                    EngineLeg(
                        mode=request.mode,
                        geometry=(request.origin, request.destination),
                        distance_m=2_400,
                        duration_s=720,
                        from_name="Origin",
                        to_name="Destination",
                        maneuvers=(
                            EngineManeuver(
                                instruction="Turn right onto Arlozorov Street.",
                                begin_geometry_index=0,
                                distance_m=2_400,
                                duration_s=720,
                                street_name="Arlozorov Street",
                                modifier="right",
                            ),
                        ),
                    ),
                ),
            )
        ]


@pytest.fixture
def planner() -> LiveRoutePlanner:
    engine = FakeEngine()
    return LiveRoutePlanner(
        engine,
        engine,
        CoverageArea(34.69, 31.94, 34.93, 32.2),
        data_version="test-regional",
        route_ttl_seconds=900,
    )


@pytest.mark.asyncio
async def test_live_planner_normalizes_real_engine_contract(planner: LiveRoutePlanner) -> None:
    response = await planner.plan(
        RoutePlanRequest(
            origin=ORIGIN,
            destination=DESTINATION,
            depart_at=datetime(2026, 8, 6, 9, 0, tzinfo=TZ),
            mode=TravelMode.WALK,
        ),
        "request-1",
    )
    assert response.engine_profile == "regional-live"
    assert response.routes[0].metrics.distance_m == 2_400
    assert response.routes[0].maneuvers[0].modifier == "right"
    assert response.routes[0].warnings == []


@pytest.mark.asyncio
async def test_live_planner_rejects_outside_coverage_before_engine_call(
    planner: LiveRoutePlanner,
) -> None:
    with pytest.raises(OutsideCoverageError):
        await planner.plan(
            RoutePlanRequest(
                origin=Coordinate(latitude=31.77, longitude=35.21),
                destination=DESTINATION,
                mode=TravelMode.WALK,
            ),
            "request-2",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("origin", "destination"),
    [
        (
            Coordinate(latitude=31.7683, longitude=35.2137),
            Coordinate(latitude=31.7780, longitude=35.2350),
        ),
        (
            Coordinate(latitude=32.7940, longitude=34.9896),
            Coordinate(latitude=32.8070, longitude=34.9580),
        ),
        (
            Coordinate(latitude=31.2530, longitude=34.7915),
            Coordinate(latitude=31.2430, longitude=34.7990),
        ),
        (
            Coordinate(latitude=29.5577, longitude=34.9519),
            Coordinate(latitude=29.5480, longitude=34.9570),
        ),
    ],
)
async def test_default_live_coverage_accepts_national_routes(
    origin: Coordinate, destination: Coordinate
) -> None:
    engine = FakeEngine()
    national_planner = LiveRoutePlanner(
        engine,
        engine,
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        route_ttl_seconds=900,
    )

    response = await national_planner.plan(
        RoutePlanRequest(origin=origin, destination=destination, mode=TravelMode.WALK),
        "national-request",
    )

    assert response.routes
    assert response.routes[0].encoded_polyline


@pytest.mark.asyncio
async def test_transit_legs_generate_boarding_and_arrival_guidance() -> None:
    class TransitEngine:
        async def routes(self, request: RoutePlanRequest) -> list[EngineItinerary]:
            departure = request.depart_at or datetime(2026, 8, 6, 9, 0, tzinfo=TZ)
            return [
                EngineItinerary(
                    departure_at=departure,
                    arrival_at=departure + timedelta(minutes=10),
                    legs=(
                        EngineLeg(
                            mode=TravelMode.TRANSIT,
                            geometry=(request.origin, request.destination),
                            distance_m=2_400,
                            duration_s=600,
                            from_name="Habima",
                            to_name="Rabin Square",
                            route_name="9",
                            headsign="Reading",
                        ),
                    ),
                    fallback_reason="rental_availability_unavailable",
                )
            ]

    engine = TransitEngine()
    transit_planner = LiveRoutePlanner(
        engine,
        engine,
        CoverageArea(34.69, 31.94, 34.93, 32.2),
        data_version="test-regional",
        route_ttl_seconds=900,
    )
    response = await transit_planner.plan(
        RoutePlanRequest(
            origin=ORIGIN,
            destination=DESTINATION,
            depart_at=datetime(2026, 8, 6, 9, 0, tzinfo=TZ),
            mode=TravelMode.TRANSIT,
        ),
        "request-transit",
    )

    assert [item.modifier for item in response.routes[0].maneuvers] == ["board", "arrive"]
    assert response.routes[0].maneuvers[0].street_name == "9 Reading"
    assert response.routes[0].fallback_reason == "rental_availability_unavailable"


def test_live_alternatives_compare_distance_against_the_fastest_route(
    planner: LiveRoutePlanner,
) -> None:
    departure = datetime(2026, 8, 6, 9, 0, tzinfo=TZ)

    def itinerary(duration_s: int, distance_m: int) -> EngineItinerary:
        return EngineItinerary(
            departure_at=departure,
            arrival_at=departure + timedelta(seconds=duration_s),
            legs=(
                EngineLeg(
                    mode=TravelMode.CAR,
                    geometry=(ORIGIN, DESTINATION),
                    distance_m=distance_m,
                    duration_s=duration_s,
                    from_name="Origin",
                    to_name="Destination",
                ),
            ),
        )

    routes = planner._alternatives(
        RoutePlanRequest(origin=ORIGIN, destination=DESTINATION, mode=TravelMode.CAR),
        [itinerary(600, 1_000), itinerary(660, 1_200)],
    )

    assert routes[0].metrics.detour_distance_percent == 0
    assert routes[1].metrics.detour_time_percent == 10
    assert routes[1].metrics.detour_distance_percent == 20
