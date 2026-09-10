from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

FEATURE_SCHEMA_VERSION = 1
REQUIRED_METADATA = frozenset(
    {
        "schema_version",
        "source",
        "source_version",
        "license",
        "attribution",
        "coverage_bbox",
        "building_count",
        "signal_count",
    }
)


@dataclass(frozen=True, slots=True)
class FeatureBundleValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: dict[str, str]


def validate_osm_feature_bundle(path: Path) -> FeatureBundleValidation:
    """Validate a spatial feature bundle without loading its rows into memory."""

    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, str] = {}
    if not path.is_file():
        return FeatureBundleValidation(
            False,
            (f"Feature bundle does not exist: {path}",),
            (),
            {},
        )

    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            if integrity != "ok":
                errors.append(f"SQLite quick_check failed: {integrity}")
            metadata = {
                str(key): str(value)
                for key, value in connection.execute("SELECT key, value FROM metadata")
            }
            missing = REQUIRED_METADATA - metadata.keys()
            if missing:
                errors.append(f"Missing metadata: {', '.join(sorted(missing))}")
            _validate_metadata(metadata, errors, warnings)
            _validate_table_count(connection, metadata, "buildings", "building_count", errors)
            _validate_table_count(connection, metadata, "signals", "signal_count", errors)
            _validate_index_count(connection, "building_index", "buildings", errors)
            _validate_index_count(connection, "signal_index", "signals", errors)
            _validate_coordinate_extents(connection, metadata, errors)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        errors.append(f"Cannot validate feature bundle: {exc}")
    return FeatureBundleValidation(not errors, tuple(errors), tuple(warnings), metadata)


def _validate_metadata(
    metadata: dict[str, str], errors: list[str], warnings: list[str]
) -> None:
    try:
        schema_version = int(metadata["schema_version"])
        if schema_version != FEATURE_SCHEMA_VERSION:
            errors.append(
                f"Unsupported feature schema {schema_version}; expected {FEATURE_SCHEMA_VERSION}"
            )
    except (KeyError, ValueError):
        errors.append("schema_version is not an integer")

    try:
        bbox = json.loads(metadata["coverage_bbox"])
        west, south, east, north = (float(value) for value in bbox)
        if west >= east or south >= north:
            errors.append("coverage_bbox has inverted or empty bounds")
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            errors.append("coverage_bbox longitude is invalid")
        if not (-90 <= south <= 90 and -90 <= north <= 90):
            errors.append("coverage_bbox latitude is invalid")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        errors.append("coverage_bbox must be a four-number JSON array")

    if metadata.get("license") != "ODbL-1.0":
        warnings.append("Expected the OSM feature layer to declare ODbL-1.0")
    if "OpenStreetMap" not in metadata.get("attribution", ""):
        errors.append("OpenStreetMap attribution is missing")


def _validate_table_count(
    connection: sqlite3.Connection,
    metadata: dict[str, str],
    table: str,
    metadata_key: str,
    errors: list[str],
) -> None:
    try:
        expected = int(metadata[metadata_key])
        actual = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except (KeyError, TypeError, ValueError, sqlite3.Error):
        errors.append(f"Cannot validate {table} count")
        return
    if expected != actual:
        errors.append(f"{table} count mismatch: metadata={expected}, actual={actual}")
    if actual == 0:
        errors.append(f"{table} is empty")


def _validate_index_count(
    connection: sqlite3.Connection,
    index_table: str,
    data_table: str,
    errors: list[str],
) -> None:
    try:
        index_count = int(
            connection.execute(f"SELECT COUNT(*) FROM {index_table}").fetchone()[0]
        )
        data_count = int(
            connection.execute(f"SELECT COUNT(*) FROM {data_table}").fetchone()[0]
        )
    except (TypeError, ValueError, sqlite3.Error):
        errors.append(f"Cannot validate {index_table}")
        return
    if index_count != data_count:
        errors.append(
            f"{index_table} count mismatch: index={index_count}, data={data_count}"
        )


def _validate_coordinate_extents(
    connection: sqlite3.Connection, metadata: dict[str, str], errors: list[str]
) -> None:
    try:
        west, south, east, north = (
            float(value) for value in json.loads(metadata["coverage_bbox"])
        )
        signal_extent = connection.execute(
            "SELECT MIN(longitude), MIN(latitude), MAX(longitude), MAX(latitude) FROM signals"
        ).fetchone()
        building_extent = connection.execute(
            "SELECT MIN(min_lon), MIN(min_lat), MAX(max_lon), MAX(max_lat) FROM buildings"
        ).fetchone()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, sqlite3.Error):
        return
    tolerance = 0.001
    for label, extent in (("signals", signal_extent), ("buildings", building_extent)):
        if extent is None or any(value is None for value in extent):
            continue
        min_lon, min_lat, max_lon, max_lat = (float(value) for value in extent)
        if (
            min_lon < west - tolerance
            or min_lat < south - tolerance
            or max_lon > east + tolerance
            or max_lat > north + tolerance
        ):
            errors.append(f"{label} coordinates exceed coverage_bbox")
