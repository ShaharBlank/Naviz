from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile

REQUIRED_FILES = frozenset({"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"})


@dataclass(frozen=True, slots=True)
class GtfsValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int]


def validate_gtfs(path: Path) -> GtfsValidation:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    try:
        with ZipFile(path) as archive:
            names = {Path(name).name for name in archive.namelist()}
            missing = REQUIRED_FILES - names
            if missing:
                errors.append(f"Missing required GTFS files: {', '.join(sorted(missing))}")
                return GtfsValidation(False, tuple(errors), tuple(warnings), counts)
            stops = _rows(archive, "stops.txt", errors)
            routes = _rows(archive, "routes.txt", errors)
            trips = _rows(archive, "trips.txt", errors)
            stop_times = _rows(archive, "stop_times.txt", errors)
            counts.update(
                stops=len(stops),
                routes=len(routes),
                trips=len(trips),
                stop_times=len(stop_times),
            )
            _unique(stops, "stop_id", "stops.txt", errors)
            _unique(routes, "route_id", "routes.txt", errors)
            _unique(trips, "trip_id", "trips.txt", errors)
            stop_ids = {row.get("stop_id", "") for row in stops}
            route_ids = {row.get("route_id", "") for row in routes}
            trip_ids = {row.get("trip_id", "") for row in trips}
            _references(trips, "route_id", route_ids, "trips.txt", "routes.txt", errors)
            _references(stop_times, "trip_id", trip_ids, "stop_times.txt", "trips.txt", errors)
            _references(stop_times, "stop_id", stop_ids, "stop_times.txt", "stops.txt", errors)
            _coordinates(stops, errors)
            _stop_sequences(stop_times, errors)
            if not ({"calendar.txt", "calendar_dates.txt"} & names):
                errors.append("GTFS has neither calendar.txt nor calendar_dates.txt")
            if "feed_info.txt" not in names:
                warnings.append(
                    "feed_info.txt is missing; publisher/version metadata is unavailable"
                )
    except (BadZipFile, FileNotFoundError, OSError) as exc:
        errors.append(f"Cannot read GTFS archive: {exc}")
    return GtfsValidation(not errors, tuple(errors), tuple(warnings), counts)


def _rows(archive: ZipFile, name: str, errors: list[str]) -> list[dict[str, str]]:
    try:
        with archive.open(name) as raw, TextIOWrapper(
            raw, encoding="utf-8-sig", newline=""
        ) as text:
            reader = csv.DictReader(text)
            if not reader.fieldnames:
                errors.append(f"{name} has no header")
                return []
            return [dict(row) for row in reader]
    except (KeyError, UnicodeDecodeError, csv.Error) as exc:
        errors.append(f"Cannot parse {name}: {exc}")
        return []


def _unique(rows: Iterable[dict[str, str]], key: str, name: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        value = row.get(key, "").strip()
        if not value:
            errors.append(f"{name}:{row_number} has an empty {key}")
        elif value in seen:
            errors.append(f"{name}:{row_number} duplicates {key}={value}")
        seen.add(value)


def _references(
    rows: Iterable[dict[str, str]],
    key: str,
    targets: set[str],
    source_name: str,
    target_name: str,
    errors: list[str],
) -> None:
    for row_number, row in enumerate(rows, start=2):
        value = row.get(key, "").strip()
        if value not in targets:
            errors.append(
                f"{source_name}:{row_number} references missing {key}={value} in {target_name}"
            )


def _coordinates(stops: Iterable[dict[str, str]], errors: list[str]) -> None:
    for row_number, stop in enumerate(stops, start=2):
        try:
            latitude = float(stop.get("stop_lat", ""))
            longitude = float(stop.get("stop_lon", ""))
        except ValueError:
            errors.append(f"stops.txt:{row_number} has an invalid coordinate")
            continue
        if not (29 <= latitude <= 34 and 33 <= longitude <= 36):
            errors.append(f"stops.txt:{row_number} is outside plausible Israel bounds")


def _stop_sequences(stop_times: Iterable[dict[str, str]], errors: list[str]) -> None:
    last_by_trip: dict[str, int] = {}
    for row_number, row in enumerate(stop_times, start=2):
        trip_id = row.get("trip_id", "")
        try:
            sequence = int(row.get("stop_sequence", ""))
        except ValueError:
            errors.append(f"stop_times.txt:{row_number} has an invalid stop_sequence")
            continue
        if sequence <= last_by_trip.get(trip_id, -1):
            errors.append(f"stop_times.txt:{row_number} stop_sequence is not increasing")
        last_by_trip[trip_id] = sequence
