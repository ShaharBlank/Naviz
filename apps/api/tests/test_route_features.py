from __future__ import annotations

import sqlite3
import struct
from types import SimpleNamespace
from typing import cast

import pytest
from naviz_api.geometry import encode_polyline
from naviz_api.models import Coordinate, RouteAlternative
from naviz_api.route_features import SqliteOsmRouteContext


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
    connection.execute(
        "INSERT INTO building_index VALUES (1, 34.7790, 34.7792, 32.0730, 32.0732)"
    )
    connection.execute("INSERT INTO signals VALUES (1, 34.7791, 32.0731)")
    connection.execute(
        "INSERT INTO signal_index VALUES (1, 34.7791, 34.7791, 32.0731, 32.0731)"
    )
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
