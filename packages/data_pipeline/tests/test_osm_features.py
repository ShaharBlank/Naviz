from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from naviz_data.osm_features import validate_osm_feature_bundle


def _bundle(path: Path, *, building_count: str = "1") -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE buildings(
            id INTEGER PRIMARY KEY, osm_id INTEGER, min_lon REAL, min_lat REAL,
            max_lon REAL, max_lat REAL, height_m REAL, confidence TEXT,
            coordinates BLOB
        );
        CREATE VIRTUAL TABLE building_index USING rtree(
            id, min_lon, max_lon, min_lat, max_lat
        );
        CREATE TABLE signals(
            id INTEGER PRIMARY KEY, osm_id INTEGER, longitude REAL, latitude REAL
        );
        CREATE VIRTUAL TABLE signal_index USING rtree(
            id, min_lon, max_lon, min_lat, max_lat
        );
        INSERT INTO buildings VALUES (1, 10, 34.79, 32.08, 34.80, 32.09, 12, 'medium', X'00');
        INSERT INTO building_index VALUES (1, 34.79, 34.80, 32.08, 32.09);
        INSERT INTO signals VALUES (1, 20, 34.795, 32.085);
        INSERT INTO signal_index VALUES (1, 34.795, 34.795, 32.085, 32.085);
        """
    )
    metadata = {
        "schema_version": "1",
        "source": "OpenStreetMap via Geofabrik",
        "source_version": "test",
        "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors",
        "coverage_bbox": json.dumps([34.15, 29.35, 35.95, 33.40]),
        "building_count": building_count,
        "signal_count": "1",
    }
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
    connection.commit()
    connection.close()


def test_validates_streamable_feature_bundle(tmp_path: Path) -> None:
    path = tmp_path / "features.sqlite3"
    _bundle(path)

    result = validate_osm_feature_bundle(path)

    assert result.valid
    assert result.errors == ()
    assert result.metadata["coverage_bbox"] == "[34.15, 29.35, 35.95, 33.4]"


def test_rejects_metadata_count_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "features.sqlite3"
    _bundle(path, building_count="2")

    result = validate_osm_feature_bundle(path)

    assert not result.valid
    assert "buildings count mismatch: metadata=2, actual=1" in result.errors
