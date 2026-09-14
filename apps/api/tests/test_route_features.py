from __future__ import annotations

import sqlite3
import struct
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from naviz_api.geometry import encode_polyline
from naviz_api.models import (
    Coordinate,
    DataConfidence,
    DataQuality,
    RouteAlternative,
    RouteConstraints,
    RouteMetrics,
    RoutePlanRequest,
    RoutePreference,
    ShadowSceneRequest,
    TravelMode,
)
from naviz_api.route_features import (
    OUTSIDE_VALIDATED_FEATURE_COVERAGE,
    OsmRouteContext,
    RouteContextPort,
    RouteFeatureAnalyzer,
    SqliteOsmRouteContext,
)
from pyproj import Transformer
from shapely.geometry import Point

TZ = ZoneInfo("Asia/Jerusalem")
TO_ITM = Transformer.from_crs("EPSG:4326", "EPSG:2039", always_xy=True)


@pytest.mark.asyncio
async def test_sqlite_context_reads_only_route_corridor_features(tmp_path) -> None:
    database = tmp_path / "features.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE buildings(
            id INTEGER PRIMARY KEY, coordinates BLOB, height_m REAL, confidence TEXT
        );
        CREATE VIRTUAL TABLE building_index USING rtree(
            id, min_lon, max_lon, min_lat, max_lat
        );
        CREATE TABLE signals(id INTEGER PRIMARY KEY, longitude REAL, latitude REAL);
        CREATE VIRTUAL TABLE signal_index USING rtree(
            id, min_lon, max_lon, min_lat, max_lat
        );
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    connection.execute(
        "INSERT INTO metadata VALUES ('coverage_bbox', '[34.69, 31.94, 34.93, 32.20]')"
    )
    coordinates = [
        (34.7790, 32.0730),
        (34.7792, 32.0730),
        (34.7792, 32.0732),
        (34.7790, 32.0732),
        (34.7790, 32.0730),
    ]
    blob = b"".join(
        struct.pack("<ii", round(longitude * 10_000_000), round(latitude * 10_000_000))
        for longitude, latitude in coordinates
    )
    connection.execute("INSERT INTO buildings VALUES (1, ?, 16, 'high')", (blob,))
    connection.execute("INSERT INTO building_index VALUES (1, 34.7790, 34.7792, 32.0730, 32.0732)")
    connection.execute("INSERT INTO signals VALUES (1, 34.7791, 32.0731)")
    connection.execute("INSERT INTO signal_index VALUES (1, 34.7791, 34.7791, 32.0731, 32.0731)")
    connection.execute("INSERT INTO signals VALUES (2, 35.1, 31.8)")
    connection.execute("INSERT INTO signal_index VALUES (2, 35.1, 35.1, 31.8, 31.8)")
    # Inside the route corridor's bounding box but over 260 m from the actual
    # diagonal geometry. A bounding-box-only query would incorrectly include it.
    connection.execute("INSERT INTO signals VALUES (3, 34.7818, 32.0707)")
    connection.execute("INSERT INTO signal_index VALUES (3, 34.7818, 34.7818, 32.0707, 32.0707)")
    connection.commit()
    connection.close()

    route = cast(
        RouteAlternative,
        SimpleNamespace(
            bbox=(34.7785, 32.0725, 34.7800, 32.0740),
            encoded_polyline=encode_polyline(
                [
                    Coordinate(latitude=32.0728, longitude=34.7788),
                    Coordinate(latitude=32.0738, longitude=34.7798),
                ]
            ),
        ),
    )
    context = await SqliteOsmRouteContext(database).context(
        [route], buildings=True, traffic_signals=True
    )

    assert len(context.buildings) == 1
    assert context.buildings[0].height_m == 16
    assert len(context.traffic_signals) == 1

    source = SqliteOsmRouteContext(database)
    scene_request = ShadowSceneRequest(
        encoded_polyline=route.encoded_polyline,
        at=datetime(2026, 8, 17, 12, 0, tzinfo=TZ),
        corridor_m=180,
    )
    scene = await source.shadow_scene(scene_request)
    assert scene.available
    assert scene.solar_elevation_degrees > 0
    assert scene.shadows
    assert scene.high_confidence_shadows
    assert scene.attribution == ["© OpenStreetMap contributors · ODbL"]
    assert await source.shadow_scene(scene_request) is scene

    long_scene = await source.shadow_scene(
        ShadowSceneRequest(
            encoded_polyline=encode_polyline(
                [
                    Coordinate(latitude=31.98, longitude=34.79),
                    Coordinate(latitude=32.06, longitude=34.79),
                ]
            ),
            at=datetime(2026, 8, 17, 12, 0, tzinfo=TZ),
            corridor_m=180,
        )
    )
    assert not long_scene.available
    assert long_scene.warning is not None
    assert "six-kilometre viewing window" in long_scene.warning


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("city", "origin", "destination"),
    [
        (
            "Jerusalem",
            Coordinate(latitude=31.7683, longitude=35.2137),
            Coordinate(latitude=31.7780, longitude=35.2350),
        ),
        (
            "Haifa",
            Coordinate(latitude=32.7940, longitude=34.9896),
            Coordinate(latitude=32.8070, longitude=34.9580),
        ),
        (
            "Be'er Sheva",
            Coordinate(latitude=31.2530, longitude=34.7915),
            Coordinate(latitude=31.2430, longitude=34.7990),
        ),
        (
            "Eilat",
            Coordinate(latitude=29.5577, longitude=34.9519),
            Coordinate(latitude=29.5480, longitude=34.9570),
        ),
    ],
)
async def test_metro_feature_bundle_never_claims_complete_national_context(
    tmp_path, city: str, origin: Coordinate, destination: Coordinate
) -> None:
    del city
    database = tmp_path / "features.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO metadata VALUES (
            'coverage_bbox', '[34.69, 31.94, 34.93, 32.20]'
        );
        """
    )
    connection.commit()
    connection.close()
    route = _context_route(origin, destination)

    source = SqliteOsmRouteContext(database)
    context = await source.context([route], buildings=True, traffic_signals=True)

    assert source.coverage_bbox == (34.69, 31.94, 34.93, 32.20)
    assert not context.complete
    assert context.incomplete_reason == OUTSIDE_VALIDATED_FEATURE_COVERAGE
    assert context.buildings == ()
    assert context.traffic_signals == ()


@pytest.mark.asyncio
async def test_route_corridor_near_feature_boundary_is_not_marked_complete(tmp_path) -> None:
    database = tmp_path / "features.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO metadata VALUES (
            'coverage_bbox', '[34.69, 31.94, 34.93, 32.20]'
        );
        """
    )
    connection.commit()
    connection.close()
    route = _context_route(
        Coordinate(latitude=32.0700, longitude=34.6905),
        Coordinate(latitude=32.0800, longitude=34.6905),
    )

    context = await SqliteOsmRouteContext(database).context(
        [route], buildings=True, traffic_signals=True
    )

    assert not context.complete
    assert context.incomplete_reason == OUTSIDE_VALIDATED_FEATURE_COVERAGE


def test_feature_bundle_requires_validated_coverage_metadata(tmp_path) -> None:
    database = tmp_path / "features.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.close()

    with pytest.raises(ValueError, match="missing coverage_bbox"):
        SqliteOsmRouteContext(database)


def test_shadow_scene_requires_timezone_aware_time() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        ShadowSceneRequest(
            encoded_polyline="abc",
            at=datetime(2026, 8, 17, 12, 0),
        )


def test_outside_feature_coverage_has_distinct_truthful_fallbacks() -> None:
    departure = datetime(2026, 9, 9, 9, 0, tzinfo=TZ)
    route = _route("fast", 35.214, 600, 1_000, departure)
    context = OsmRouteContext(
        complete=False,
        incomplete_reason=OUTSIDE_VALIDATED_FEATURE_COVERAGE,
    )
    walk_request = RoutePlanRequest(
        origin=Coordinate(latitude=31.768, longitude=35.214),
        destination=Coordinate(latitude=31.778, longitude=35.214),
        depart_at=departure,
        mode=TravelMode.WALK,
        preference=RoutePreference.BALANCED_SHADE,
    )
    road_request = walk_request.model_copy(
        update={"mode": TravelMode.CAR, "preference": RoutePreference.FEWER_LIGHTS}
    )

    analyzer = RouteFeatureAnalyzer(cast(RouteContextPort, None))
    shade = analyzer._shade_routes(walk_request, [route], context)[0]
    signals = analyzer._signal_routes(road_request, [route], context)[0]

    assert shade.fallback_reason == "shade_outside_validated_coverage"
    assert signals.fallback_reason == "signal_outside_validated_coverage"
    assert shade.quality.confidence == DataConfidence.LOW
    assert signals.quality.confidence == DataConfidence.LOW
    assert shade.metrics.shade_fraction is None
    assert signals.metrics.traffic_signals is None
    assert "outside validated feature coverage" in shade.warnings[0]
    assert "outside validated feature coverage" in signals.warnings[0]


def test_signal_comparison_returns_total_counts_and_material_reduction() -> None:
    departure = datetime(2026, 8, 17, 9, 0, tzinfo=TZ)
    fastest = _route("fast", 34.780, 600, 1_000, departure)
    low_signal = _route("low", 34.782, 650, 1_100, departure)
    signals = tuple(
        Point(*TO_ITM.transform(longitude, latitude))
        for longitude, latitude in (
            (34.780, 32.072),
            (34.780, 32.075),
            (34.780, 32.078),
            (34.782, 32.075),
        )
    )
    request = RoutePlanRequest(
        origin=Coordinate(latitude=32.070, longitude=34.780),
        destination=Coordinate(latitude=32.080, longitude=34.780),
        depart_at=departure,
        mode=TravelMode.CAR,
        preference=RoutePreference.FASTEST,
    )

    routes = RouteFeatureAnalyzer._signal_routes(
        request,
        [fastest, low_signal],
        OsmRouteContext(traffic_signals=signals, complete=True),
    )

    assert [route.label_key for route in routes] == ["route.fastest", "route.fewerLights"]
    assert [route.metrics.traffic_signals for route in routes] == [3, 1]
    assert routes[1].metrics.signals_avoided == 2


def test_signal_comparison_marks_fastest_when_it_also_has_fewest_lights() -> None:
    departure = datetime(2026, 8, 17, 9, 0, tzinfo=TZ)
    fastest = _route("fast", 34.780, 600, 1_000, departure)
    low_signal = _route("low", 34.782, 601, 1_001, departure)
    signals = tuple(
        Point(*TO_ITM.transform(longitude, latitude))
        for longitude, latitude in (
            (34.780, 32.072),
            (34.780, 32.075),
            (34.780, 32.078),
            (34.782, 32.075),
        )
    )
    request = RoutePlanRequest(
        origin=Coordinate(latitude=32.070, longitude=34.780),
        destination=Coordinate(latitude=32.080, longitude=34.780),
        depart_at=departure,
        mode=TravelMode.CAR,
        preference=RoutePreference.FEWER_LIGHTS,
        constraints=RouteConstraints(maximum_time_detour_percent=0),
    )

    routes = RouteFeatureAnalyzer._signal_routes(
        request,
        [fastest, low_signal],
        OsmRouteContext(traffic_signals=signals, complete=True),
    )

    assert len(routes) == 1
    assert routes[0].label_key == "route.fastestAndFewestLights"
    assert routes[0].fallback_reason is None
    assert routes[0].metrics.traffic_signals == 3


def test_signal_comparison_does_not_advertise_an_immaterial_reduction() -> None:
    departure = datetime(2026, 8, 17, 9, 0, tzinfo=TZ)
    fastest = _route("fast", 34.780, 600, 1_000, departure)
    low_signal = _route("low", 34.782, 630, 1_050, departure)
    signals = tuple(
        Point(*TO_ITM.transform(longitude, 32.071 + index * 0.00085))
        for longitude, count in ((34.780, 10), (34.782, 9))
        for index in range(count)
    )
    request = RoutePlanRequest(
        origin=Coordinate(latitude=32.070, longitude=34.780),
        destination=Coordinate(latitude=32.080, longitude=34.780),
        depart_at=departure,
        mode=TravelMode.CAR,
        preference=RoutePreference.FASTEST,
    )

    routes = RouteFeatureAnalyzer._signal_routes(
        request,
        [fastest, low_signal],
        OsmRouteContext(traffic_signals=signals, complete=True),
    )

    assert len(routes) == 1
    assert routes[0].label_key == "route.fastest"
    assert routes[0].fallback_reason == "no_material_signal_reduction"
    assert routes[0].metrics.traffic_signals == 10


def test_maximum_shade_optimizes_shaded_fraction_not_only_sun_minutes() -> None:
    departure = datetime(2026, 8, 17, 9, 0, tzinfo=TZ)
    fastest = _route("fast", 34.780, 600, 1_000, departure).model_copy(
        update={
            "metrics": RouteMetrics(
                distance_m=1_000,
                duration_s=600,
                shade_fraction=0.20,
                sun_exposure_minutes=8.0,
            )
        }
    )
    shadiest = _route("shade", 34.782, 770, 1_200, departure).model_copy(
        update={
            "metrics": RouteMetrics(
                distance_m=1_200,
                duration_s=770,
                shade_fraction=0.65,
                sun_exposure_minutes=9.5,
            )
        }
    )
    request = RoutePlanRequest(
        origin=Coordinate(latitude=32.070, longitude=34.780),
        destination=Coordinate(latitude=32.080, longitude=34.780),
        depart_at=departure,
        mode=TravelMode.WALK,
    )

    analyzer = RouteFeatureAnalyzer(cast(RouteContextPort, None))
    balanced = analyzer._best_balanced_shade_route(request, [fastest, shadiest], fastest, 15.0)
    maximum = analyzer._best_maximum_shade_route(request, [fastest, shadiest], fastest, 30.0)

    assert balanced.id == fastest.id
    assert maximum.id == shadiest.id


def _route(
    route_id: str,
    longitude: float,
    duration_s: float,
    distance_m: float,
    departure: datetime,
) -> RouteAlternative:
    geometry = [
        Coordinate(latitude=32.070, longitude=longitude),
        Coordinate(latitude=32.080, longitude=longitude),
    ]
    return RouteAlternative(
        id=route_id,
        label_key="route.fastest" if route_id == "fast" else "route.alternative",
        encoded_polyline=encode_polyline(geometry),
        bbox=(longitude, 32.070, longitude, 32.080),
        departure_at=departure,
        arrival_at=departure + timedelta(seconds=duration_s),
        legs=[],
        maneuvers=[],
        annotations=[],
        metrics=RouteMetrics(distance_m=distance_m, duration_s=duration_s),
        quality=DataQuality(confidence=DataConfidence.HIGH),
        expires_at=departure + timedelta(minutes=15),
    )


def _context_route(origin: Coordinate, destination: Coordinate) -> RouteAlternative:
    return cast(
        RouteAlternative,
        SimpleNamespace(
            bbox=(
                min(origin.longitude, destination.longitude),
                min(origin.latitude, destination.latitude),
                max(origin.longitude, destination.longitude),
                max(origin.latitude, destination.latitude),
            ),
            encoded_polyline=encode_polyline([origin, destination]),
        ),
    )
