from pathlib import Path
from zipfile import ZipFile

from naviz_data.gtfs import validate_gtfs


def test_valid_minimal_gtfs(tmp_path: Path) -> None:
    archive = tmp_path / "gtfs.zip"
    _write_gtfs(archive)
    result = validate_gtfs(archive)
    assert result.valid, result.errors
    assert result.counts == {"stops": 2, "routes": 1, "trips": 1, "stop_times": 2}


def test_broken_stop_reference_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "gtfs.zip"
    _write_gtfs(archive, second_stop="missing")
    result = validate_gtfs(archive)
    assert not result.valid
    assert any("missing stop_id=missing" in error for error in result.errors)


def _write_gtfs(path: Path, second_stop: str = "b") -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon\na,A,32.08,34.78\nb,B,32.09,34.79\n",
        )
        archive.writestr("routes.txt", "route_id,route_short_name\nr,1\n")
        archive.writestr("trips.txt", "route_id,service_id,trip_id\nr,s,t\n")
        archive.writestr(
            "stop_times.txt",
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "t,08:00:00,08:00:00,a,1\n"
            f"t,08:10:00,08:10:00,{second_stop},2\n",
        )
        archive.writestr(
            "calendar_dates.txt",
            "service_id,date,exception_type\ns,20260802,1\n",
        )
