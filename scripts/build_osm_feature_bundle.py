"""Build Naviz's compact metropolitan building and traffic-signal index.

The input is a pinned Geofabrik ``.osm.pbf`` extract. PyOsmium is deliberately
kept out of the API runtime; run this script with ``uv run --with osmium``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

import osmium

DEFAULT_BBOX = (34.69, 31.94, 34.93, 32.20)


def _number(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.lower().replace("meters", "").replace("meter", "").replace("m", "")
    try:
        return float(cleaned.strip())
    except ValueError:
        return None


def _height(tags: Any) -> tuple[float, str]:
    height = _number(tags.get("height"))
    if height is not None and 1 <= height <= 300:
        return height, "high"
    levels = _number(tags.get("building:levels"))
    if levels is not None and 1 <= levels <= 80:
        return levels * 3.2, "medium"
    return 10.0, "low"


def _coordinate_blob(coordinates: list[tuple[float, float]]) -> bytes:
    result = bytearray()
    for longitude, latitude in coordinates:
        result.extend(
            struct.pack("<ii", round(longitude * 10_000_000), round(latitude * 10_000_000))
        )
    return bytes(result)


class FeatureHandler(osmium.SimpleHandler):
    def __init__(
        self,
        connection: sqlite3.Connection,
        bbox: tuple[float, float, float, float],
    ) -> None:
        super().__init__()
        self.connection = connection
        self.west, self.south, self.east, self.north = bbox
        self.building_count = 0
        self.signal_count = 0

    def node(self, node: Any) -> None:
        if node.tags.get("highway") != "traffic_signals" or not node.location.valid():
            return
        longitude = float(node.location.lon)
        latitude = float(node.location.lat)
        if not self._contains(longitude, latitude):
            return
        cursor = self.connection.execute(
            "INSERT INTO signals(osm_id, longitude, latitude) VALUES (?, ?, ?)",
            (int(node.id), longitude, latitude),
        )
        feature_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO signal_index VALUES (?, ?, ?, ?, ?)",
            (feature_id, longitude, longitude, latitude, latitude),
        )
        self.signal_count += 1

    def way(self, way: Any) -> None:
        if not way.tags.get("building") or len(way.nodes) < 4:
            return
        coordinates: list[tuple[float, float]] = []
        try:
            for node in way.nodes:
                if not node.location.valid():
                    return
                coordinates.append((float(node.location.lon), float(node.location.lat)))
        except osmium.InvalidLocationError:
            return
        if coordinates[0] != coordinates[-1]:
            return
        longitudes = [item[0] for item in coordinates]
        latitudes = [item[1] for item in coordinates]
        bounds = min(longitudes), min(latitudes), max(longitudes), max(latitudes)
        if not self._intersects(bounds):
            return
        height_m, confidence = _height(way.tags)
        cursor = self.connection.execute(
            """
            INSERT INTO buildings(osm_id, min_lon, min_lat, max_lon, max_lat,
                                  height_m, confidence, coordinates)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (int(way.id), *bounds, height_m, confidence, _coordinate_blob(coordinates)),
        )
        feature_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO building_index VALUES (?, ?, ?, ?, ?)",
            (feature_id, bounds[0], bounds[2], bounds[1], bounds[3]),
        )
        self.building_count += 1
        if self.building_count % 10_000 == 0:
            self.connection.commit()

    def _contains(self, longitude: float, latitude: float) -> bool:
        return self.west <= longitude <= self.east and self.south <= latitude <= self.north

    def _intersects(self, bounds: tuple[float, float, float, float]) -> bool:
        west, south, east, north = bounds
        return (
            east >= self.west
            and west <= self.east
            and north >= self.south
            and south <= self.north
        )


def build_bundle(
    source: Path,
    output: Path,
    *,
    bbox: tuple[float, float, float, float],
    source_version: str,
) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE buildings(
                id INTEGER PRIMARY KEY,
                osm_id INTEGER NOT NULL UNIQUE,
                min_lon REAL NOT NULL,
                min_lat REAL NOT NULL,
                max_lon REAL NOT NULL,
                max_lat REAL NOT NULL,
                height_m REAL NOT NULL,
                confidence TEXT NOT NULL,
                coordinates BLOB NOT NULL
            );
            CREATE VIRTUAL TABLE building_index USING rtree(
                id, min_lon, max_lon, min_lat, max_lat
            );
            CREATE TABLE signals(
                id INTEGER PRIMARY KEY,
                osm_id INTEGER NOT NULL UNIQUE,
                longitude REAL NOT NULL,
                latitude REAL NOT NULL
            );
            CREATE VIRTUAL TABLE signal_index USING rtree(
                id, min_lon, max_lon, min_lat, max_lat
            );
            """
        )
        handler = FeatureHandler(connection, bbox)
        handler.apply_file(str(source), locations=True, idx="flex_mem")
        metadata = {
            "schema_version": "1",
            "source": "OpenStreetMap via Geofabrik",
            "source_version": source_version,
            "license": "ODbL-1.0",
            "attribution": "© OpenStreetMap contributors",
            "coverage_bbox": json.dumps(bbox),
            "building_count": str(handler.building_count),
            "signal_count": str(handler.signal_count),
        }
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
        connection.commit()
        connection.execute("ANALYZE")
        connection.execute("VACUUM")
        connection.commit()
    finally:
        connection.close()
    temporary.replace(output)
    return {
        "output": str(output),
        "size_bytes": output.stat().st_size,
        "buildings": handler.building_count,
        "signals": handler.signal_count,
        "source_version": source_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX)
    arguments = parser.parse_args()
    result = build_bundle(
        arguments.source,
        arguments.output,
        bbox=tuple(arguments.bbox),
        source_version=arguments.source_version,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
