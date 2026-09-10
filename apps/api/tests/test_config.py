import sqlite3

from naviz_api.config import Settings
from naviz_api.live_search import CoverageArea
from naviz_api.models import Coordinate
from naviz_api.services import build_services


def test_settings_parse_comma_separated_environment_values(monkeypatch) -> None:
    monkeypatch.setenv(
        "NAVIZ_ALLOWED_ORIGINS",
        "https://naviz.app,https://preview.naviz.app",
    )
    monkeypatch.setenv("NAVIZ_GBFS_FEEDS", "https://example.test/gbfs.json")

    settings = Settings(_env_file=None)

    assert settings.allowed_origins == (
        "https://naviz.app",
        "https://preview.naviz.app",
    )
    assert settings.gbfs_feeds == ("https://example.test/gbfs.json",)


def test_default_service_coverage_contains_major_israel_regions() -> None:
    coverage = CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox)

    for coordinate in (
        Coordinate(latitude=31.7683, longitude=35.2137),  # Jerusalem
        Coordinate(latitude=32.7940, longitude=34.9896),  # Haifa
        Coordinate(latitude=31.2530, longitude=34.7915),  # Be'er Sheva
        Coordinate(latitude=29.5577, longitude=34.9519),  # Eilat
    ):
        assert coverage.contains(coordinate)


def test_live_data_status_separates_service_and_feature_coverage(tmp_path) -> None:
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
    settings = Settings(
        _env_file=None,
        live_providers=True,
        valhalla_url="https://valhalla.example.test",
        transitous_url="https://transit.example.test",
        photon_url="https://photon.example.test",
        feature_bundle_path=str(database),
    )

    status = build_services(settings).status()

    assert status.coverage == "Israel nationwide routing coverage"
    assert status.service_coverage_bbox == (34.15, 29.35, 35.95, 33.4)
    assert status.feature_coverage_bbox == (34.69, 31.94, 34.93, 32.20)
    assert status.capabilities["street_routing"].coverage_bbox == status.service_coverage_bbox
    assert status.capabilities["shade"].coverage_bbox == status.feature_coverage_bbox
