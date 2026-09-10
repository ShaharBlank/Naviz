from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from naviz_data.artifact_fetch import materialize_feature_artifact


def _archive(tmp_path: Path) -> tuple[bytes, str]:
    database = tmp_path / "israel-osm-features.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE buildings(id INTEGER PRIMARY KEY, osm_id INTEGER, min_lon REAL,
          min_lat REAL, max_lon REAL, max_lat REAL, height_m REAL, confidence TEXT,
          coordinates BLOB);
        CREATE VIRTUAL TABLE building_index USING rtree(id, min_lon, max_lon, min_lat, max_lat);
        CREATE TABLE signals(id INTEGER PRIMARY KEY, osm_id INTEGER, longitude REAL, latitude REAL);
        CREATE VIRTUAL TABLE signal_index USING rtree(id, min_lon, max_lon, min_lat, max_lat);
        INSERT INTO buildings VALUES (1, 1, 34.7, 32.0, 34.8, 32.1, 10, 'low', X'00');
        INSERT INTO building_index VALUES (1, 34.7, 34.8, 32.0, 32.1);
        INSERT INTO signals VALUES (1, 1, 34.75, 32.05);
        INSERT INTO signal_index VALUES (1, 34.75, 34.75, 32.05, 32.05);
        """
    )
    metadata = {
        "schema_version": "1",
        "source": "OpenStreetMap via Geofabrik",
        "source_version": "test",
        "license": "ODbL-1.0",
        "attribution": "OpenStreetMap contributors",
        "coverage_bbox": "[34.15, 29.35, 35.95, 33.4]",
        "building_count": "1",
        "signal_count": "1",
    }
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
    connection.commit()
    connection.close()
    raw_database = database.read_bytes()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(database.name, raw_database)
    return stream.getvalue(), hashlib.sha256(raw_database).hexdigest()


def _manifest(
    path: Path, archive: bytes, database_sha: str, *, archive_sha: str | None = None
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_id": "israel-test",
                "url": "https://example.test/features.zip",
                "archive_sha256": archive_sha or hashlib.sha256(archive).hexdigest(),
                "archive_member": "israel-osm-features.sqlite3",
                "database_sha256": database_sha,
            }
        ),
        encoding="utf-8",
    )


def test_materializes_only_a_verified_valid_database(tmp_path: Path) -> None:
    archive, database_sha = _archive(tmp_path)
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "output" / "features.sqlite3"
    _manifest(manifest, archive, database_sha)

    result = materialize_feature_artifact(
        manifest, output, open_url=lambda _: io.BytesIO(archive)
    )

    assert result.bundle_id == "israel-test"
    assert output.is_file()
    assert hashlib.sha256(output.read_bytes()).hexdigest() == database_sha


def test_rejects_archive_checksum_before_extraction(tmp_path: Path) -> None:
    archive, database_sha = _archive(tmp_path)
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "features.sqlite3"
    _manifest(manifest, archive, database_sha, archive_sha="0" * 64)

    with pytest.raises(ValueError, match="archive checksum"):
        materialize_feature_artifact(
            manifest, output, open_url=lambda _: io.BytesIO(archive)
        )

    assert not output.exists()
