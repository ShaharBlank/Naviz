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
    TravelMode,
)
from naviz_api.route_features import OsmRouteContext, RouteFeatureAnalyzer, SqliteOsmRouteContext
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
        """
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


def test_signal_comparison_honors_an_explicit_zero_detour_cap() -> None:
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
    assert routes[0].label_key == "route.fastest"
    assert routes[0].fallback_reason == "no_material_signal_reduction"
    assert routes[0].metrics.traffic_signals == 3


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
