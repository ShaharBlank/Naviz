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
async def test_photon_uses_default_names_for_hebrew_and_separates_cache_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinate = Coordinate(latitude=31.7683, longitude=35.2137)
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )
    languages: list[str | None] = []

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        del path
        language = str(params["lang"]) if "lang" in params else None
        languages.append(language)
        name = "ירושלים" if language is None else "Jerusalem"
        payload = _photon_payload(name, coordinate)
        payload["features"][0]["properties"]["osm_id"] = 1
        return payload

    monkeypatch.setattr(adapter, "_get", fake_get)

    hebrew = await adapter.search("Jerusalem", language=Locale.HEBREW)
    english = await adapter.search("Jerusalem", language=Locale.ENGLISH)

    assert languages == [None, "en", "en"]
    assert hebrew[0].name == "Jerusalem"
    assert hebrew[0].name_he == "ירושלים"
    assert english[0].name == "Jerusalem"


@pytest.mark.asyncio
async def test_photon_latin_query_in_hebrew_keeps_exact_bilingual_result_ahead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )
    languages: list[str | None] = []

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        assert path == "/api/"
        language = str(params["lang"]) if "lang" in params else None
        languages.append(language)
        localized = language is None
        return {
            "features": [
                {
                    "geometry": {"coordinates": [34.7673653, 32.059583]},
                    "properties": {
                        "name": "גבולות" if localized else "Gevulot",
                        "type": "street",
                        "osm_type": "W",
                        "osm_id": 10,
                        "city": "תל אביב-יפו" if localized else "Tel Aviv",
                    },
                },
                {
                    "geometry": {"coordinates": [34.7952189, 32.1401006]},
                    "properties": {
                        "name": "גלילות" if localized else "Glilot",
                        "type": "district",
                        "osm_type": "W",
                        "osm_id": 20,
                        "city": "תל אביב-יפו" if localized else "Tel Aviv",
                    },
                },
            ]
        }

    monkeypatch.setattr(adapter, "_get", fake_get)

    results = await adapter.search(
        "Glilot",
        language=Locale.HEBREW,
        proximity=Coordinate(latitude=32.085099, longitude=34.77015),
    )

    assert languages == [None, "en"]
    assert results[0].name == "Glilot"
    assert results[0].name_he == "גלילות"
    assert results[0].subtitle == "תל אביב-יפו"


@pytest.mark.asyncio
async def test_photon_reverse_omits_unsupported_hebrew_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinate = Coordinate(latitude=31.7683, longitude=35.2137)
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        assert path == "/reverse"
        assert "lang" not in params
        return _photon_payload("ירושלים", coordinate)

    monkeypatch.setattr(adapter, "_get", fake_get)

    result = await adapter.reverse(coordinate, language=Locale.HEBREW)

    assert result is not None
    assert result.name == "ירושלים"


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


@pytest.mark.asyncio
async def test_photon_expands_sparse_generic_query_and_preserves_poi_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )
    queries: list[str] = []

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        assert path == "/api/"
        query = str(params["q"])
        queries.append(query)
        if query == "מסעדת הפרוזדור תל אביב":
            return {
                "features": [
                    {
                        "geometry": {"coordinates": [34.7749, 32.0775]},
                        "properties": {
                            "name": "פרוזדור",
                            "type": "house",
                            "osm_value": "restaurant",
                            "osm_type": "N",
                            "osm_id": 1,
                            "street": "מנדלי מוכר ספרים",
                            "housenumber": "6",
                            "city": "תל אביב-יפו",
                        },
                    }
                ]
            }
        return {
            "features": [
                {
                    "geometry": {"coordinates": [34.817, 32.142]},
                    "properties": {
                        "name": "גלילות",
                        "type": "district",
                        "osm_type": "R",
                        "osm_id": 2,
                        "city": "תל אביב-יפו",
                    },
                }
            ]
        }

    monkeypatch.setattr(adapter, "_get", fake_get)

    restaurant = await adapter.search("מסעדת הפרוזדור תל אביב", language=Locale.HEBREW, limit=8)
    base = await adapter.search("בסיס גלילות", language=Locale.HEBREW, limit=8)

    assert restaurant[0].name == "פרוזדור"
    assert restaurant[0].category == "restaurant"
    assert restaurant[0].subtitle == "מנדלי מוכר ספרים 6 · תל אביב-יפו"
    assert [place.name for place in base] == ["גלילות"]
    assert queries == [
        "מסעדת הפרוזדור תל אביב",
        "הפרוזדור תל אביב",
        "פרוזדור תל אביב",
        "בסיס גלילות",
        "גלילות",
    ]


@pytest.mark.asyncio
async def test_photon_reranks_ambiguous_places_by_text_and_proximity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = PhotonPlaceSearch(
        "https://photon.example.test",
        CoverageArea.from_tuple(Settings(_env_file=None).coverage_bbox),
        data_version="israel-test",
        user_agent="Naviz/test",
    )

    async def fake_get(path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        del path, params
        return {
            "features": [
                {
                    "geometry": {"coordinates": [34.907, 32.177]},
                    "properties": {
                        "name": "תחנה מרכזית כפר סבא",
                        "type": "house",
                        "osm_value": "bus_station",
                        "osm_type": "N",
                        "osm_id": 1,
                        "city": "כפר סבא",
                    },
                },
                {
                    "geometry": {"coordinates": [34.779, 32.055]},
                    "properties": {
                        "name": "התחנה המרכזית החדשה",
                        "type": "house",
                        "osm_value": "bus_station",
                        "osm_type": "W",
                        "osm_id": 2,
                        "city": "תל אביב-יפו",
                    },
                },
            ]
        }

    monkeypatch.setattr(adapter, "_get", fake_get)

    results = await adapter.search(
        "תחנה מרכזית תל אביב",
        language=Locale.HEBREW,
        proximity=Coordinate(latitude=32.08, longitude=34.78),
    )

    assert results[0].name == "התחנה המרכזית החדשה"
    assert results[0].category == "transit"
