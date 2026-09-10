from __future__ import annotations

from typing import Any

import pytest
from naviz_api.config import Settings
from naviz_api.live_search import CoverageArea, PhotonPlaceSearch
from naviz_api.models import Coordinate, Locale


def _photon_payload(name: str, coordinate: Coordinate) -> dict[str, Any]:
    return {
        "features": [
            {
                "geometry": {
                    "coordinates": [coordinate.longitude, coordinate.latitude],
                },
                "properties": {
                    "name": name,
                    "type": "city",
                    "osm_type": "N",
                    "osm_id": name,
                },
            }
        ]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "coordinate"),
    [
        ("Jerusalem", Coordinate(latitude=31.7683, longitude=35.2137)),
        ("Haifa", Coordinate(latitude=32.7940, longitude=34.9896)),
        ("Be'er Sheva", Coordinate(latitude=31.2530, longitude=34.7915)),
        ("Eilat", Coordinate(latitude=29.5577, longitude=34.9519)),
    ],
)
async def test_photon_search_accepts_national_results(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    coordinate: Coordinate,
) -> None:
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        assert path == "/api/"
        assert params["lang"] == "en"
        return _photon_payload(name, coordinate)

    monkeypatch.setattr(adapter, "_get", fake_get)

    results = await adapter.search(name, language=Locale.ENGLISH, proximity=coordinate)

    assert [result.name for result in results] == [name]
    assert results[0].coordinate == coordinate


@pytest.mark.asyncio
async def test_photon_language_is_forwarded_and_separates_cache_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinate = Coordinate(latitude=31.7683, longitude=35.2137)
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )
    languages: list[str] = []

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        del path
        language = str(params["lang"])
        languages.append(language)
        name = "ירושלים" if language == "he" else "Jerusalem"
        return _photon_payload(name, coordinate)

    monkeypatch.setattr(adapter, "_get", fake_get)

    hebrew = await adapter.search("Jerusalem", language=Locale.HEBREW)
    english = await adapter.search("Jerusalem", language=Locale.ENGLISH)

    assert languages == ["he", "en"]
    assert hebrew[0].name == "ירושלים"
    assert english[0].name == "Jerusalem"


@pytest.mark.asyncio
async def test_photon_collapses_duplicate_osm_representations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinate = Coordinate(latitude=32.0775, longitude=34.7749)
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        del path, params
        features = []
        for osm_type, osm_id, feature_type in (
            ("N", 1, "place"),
            ("W", 2, "house"),
            ("R", 3, "locality"),
        ):
            features.append(
                {
                    "geometry": {
                        "coordinates": [
                            coordinate.longitude + osm_id / 1_000_000,
                            coordinate.latitude,
                        ]
                    },
                    "properties": {
                        "name": "Dizengoff Square",
                        "type": feature_type,
                        "osm_type": osm_type,
                        "osm_id": osm_id,
                        "city": "Tel Aviv-Yafo",
                    },
                }
            )
        return {"features": features}

    monkeypatch.setattr(adapter, "_get", fake_get)

    results = await adapter.search("Dizengoff Square", language=Locale.ENGLISH)

    assert len(results) == 1
    assert results[0].name == "Dizengoff Square"
