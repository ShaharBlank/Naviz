from __future__ import annotations

import json
import sqlite3
import unicodedata
from collections.abc import Iterable
from threading import RLock

from .geometry import haversine_m
from .models import Coordinate, Place


class PlaceIndex:
    """Small regional FTS index; production loads the same schema from an artifact."""

    def __init__(self, places: Iterable[Place], data_version: str) -> None:
        self.data_version = data_version
        self._lock = RLock()
        self._connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._connection.execute(
            "CREATE VIRTUAL TABLE places USING fts5("
            "id UNINDEXED, name, name_he, subtitle, category, payload UNINDEXED, "
            "tokenize='unicode61')"
        )
        self._places: list[Place] = list(places)
        self._connection.executemany(
            "INSERT INTO places(id, name, name_he, subtitle, category, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    place.id,
                    _normalize(place.name),
                    _normalize(place.name_he or ""),
                    _normalize(place.subtitle or ""),
                    place.category,
                    place.model_dump_json(),
                )
                for place in self._places
            ],
        )

    def search(
        self,
        query: str,
        *,
        proximity: Coordinate | None = None,
        limit: int = 8,
        category: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Place]:
        normalized = _normalize(query).strip()
        categories = {value.strip() for value in category.split(",")} if category else set()
        if not normalized:
            return self._rank(
                self._filter(self._places, categories=categories, bbox=bbox), proximity
            )[:limit]
        tokens = [token.replace('"', "") for token in normalized.split() if token]
        expression = " AND ".join(f'"{token}"*' for token in tokens)
        sql = "SELECT payload FROM places WHERE places MATCH ?"
        parameters: list[object] = [expression]
        sql += " ORDER BY bm25(places) LIMIT ?"
        parameters.append(max(limit * 8, 50))
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        places = self._filter(
            [Place.model_validate(json.loads(row[0])) for row in rows],
            categories=categories,
            bbox=bbox,
        )
        return self._rank(places, proximity)[:limit]

    def reverse(self, coordinate: Coordinate) -> Place | None:
        if not self._places:
            return None
        nearest = min(self._places, key=lambda place: haversine_m(place.coordinate, coordinate))
        return nearest if haversine_m(nearest.coordinate, coordinate) <= 2_000 else None

    @staticmethod
    def _rank(places: Iterable[Place], proximity: Coordinate | None) -> list[Place]:
        result = list(places)
        if proximity:
            result.sort(key=lambda place: haversine_m(place.coordinate, proximity))
        return result

    @staticmethod
    def _filter(
        places: Iterable[Place],
        *,
        categories: set[str],
        bbox: tuple[float, float, float, float] | None,
    ) -> list[Place]:
        result = [place for place in places if not categories or place.category in categories]
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            result = [
                place
                for place in result
                if min_lat <= place.coordinate.latitude <= max_lat
                and min_lon <= place.coordinate.longitude <= max_lon
            ]
        return result


def _normalize(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(character)
    )
