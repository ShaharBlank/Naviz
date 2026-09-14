from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from time import monotonic
from typing import Any, cast

import httpx

from .errors import OutsideCoverageError, RoutingUnavailableError
from .geometry import haversine_m
from .models import Coordinate, DataConfidence, Locale, Place

_GENERIC_QUERY_PREFIXES = re.compile(
    r"^(?:מסעד(?:ה|ת)|בית קפה|קפה|מלון|בסיס|תחנ(?:ה|ת)|קניון|סופרמרקט|"
    r"עיריית|מגדל(?:\u05d9)?|"
    r"restaurant|cafe|coffee|hotel|base|station|mall|supermarket)\s+",
    re.IGNORECASE,
)

_CATEGORY_ALIASES = {
    "restaurant": "restaurant",
    "fast_food": "restaurant",
    "cafe": "cafe",
    "coffee_shop": "cafe",
    "bar": "nightlife",
    "pub": "nightlife",
    "townhall": "government",
    "government": "government",
    "bus_stop": "transit",
    "bus_station": "transit",
    "station": "transit",
    "train_station": "transit",
    "tram_stop": "transit",
    "subway_entrance": "transit",
    "mall": "shopping",
    "supermarket": "shopping",
    "convenience": "shopping",
    "hotel": "hotel",
    "hostel": "hotel",
    "museum": "culture",
    "theatre": "culture",
    "cinema": "culture",
    "hospital": "health",
    "clinic": "health",
    "pharmacy": "health",
    "school": "education",
    "university": "education",
    "college": "education",
    "park": "park",
    "garden": "park",
    "beach": "outdoors",
    "parking": "parking",
    "fuel": "fuel",
}


@dataclass(frozen=True, slots=True)
class CoverageArea:
    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    @classmethod
    def from_tuple(cls, value: tuple[float, float, float, float]) -> CoverageArea:
        return cls(*value)

    def contains(self, coordinate: Coordinate) -> bool:
        return (
            self.min_latitude <= coordinate.latitude <= self.max_latitude
            and self.min_longitude <= coordinate.longitude <= self.max_longitude
        )

    def require(self, coordinate: Coordinate) -> None:
        if not self.contains(coordinate):
            raise OutsideCoverageError

    @property
    def photon_bbox(self) -> str:
        return ",".join(
            str(value)
            for value in (
                self.min_longitude,
                self.min_latitude,
                self.max_longitude,
                self.max_latitude,
            )
        )


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: object


class PhotonPlaceSearch:
    """Regional Photon adapter with bounded results and a short in-process TTL cache."""

    def __init__(
        self,
        base_url: str,
        coverage: CoverageArea,
        *,
        data_version: str,
        user_agent: str,
        cache_seconds: int = 300,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.data_version = data_version
        self._base_url = base_url.rstrip("/")
        self._coverage = coverage
        self._headers = {"User-Agent": user_agent}
        self._cache_seconds = cache_seconds
        self._timeout = timeout_seconds
        self._cache: dict[tuple[object, ...], _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def search(
        self,
        query: str,
        *,
        language: Locale,
        proximity: Coordinate | None = None,
        limit: int = 8,
        category: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Place]:
        normalized = query.strip()
        if not normalized:
            return []
        if proximity is not None and not self._coverage.contains(proximity):
            proximity = None
        effective_bbox = self._intersect_bbox(bbox)
        key = (
            "search",
            normalized.casefold(),
            language.value,
            round(proximity.latitude, 3) if proximity else None,
            round(proximity.longitude, 3) if proximity else None,
            limit,
            category,
            effective_bbox,
        )
        cached = self._cached(key)
        if cached is not None:
            return cast(list[Place], cached)
        places: list[Place] = []
        for variant in _query_variants(normalized):
            params: dict[str, str | int | float] = {
                "q": variant,
                # Photon may return multiple OSM representations for a single
                # result. Fetch enough candidates to leave a useful result set
                # after semantic de-duplication.
                "limit": min(50, max(limit * 3, 16)),
                "bbox": ",".join(str(value) for value in effective_bbox),
            }
            # The public Photon service currently accepts only default, de, en and fr.
            # Omitting `lang` preserves local OSM names (including Hebrew); sending
            # `lang=he` makes every Hebrew search fail with HTTP 400.
            if language is Locale.ENGLISH:
                params["lang"] = language.value
            if proximity is not None:
                params.update(lat=proximity.latitude, lon=proximity.longitude)
            request_params = [params]
            # Photon localizes `name` and does not expose every alternative name.
            # A Latin query in the Hebrew UI therefore cannot be matched against
            # the localized result text. Fetch the English representation too and
            # merge both by their stable OSM id: English remains searchable while
            # Hebrew remains the display name for the Hebrew client.
            if language is Locale.HEBREW and not _contains_hebrew(variant):
                request_params.append({**params, "lang": Locale.ENGLISH.value})
            for localized_params in request_params:
                payload = await self._get("/api/", localized_params)
                places = _merge_places(places, self._places(payload, category=category))
            if len(places) >= limit:
                break
        places = _rank_places(places, normalized, proximity)[:limit]
        await self._store(key, places)
        return places

    async def reverse(self, coordinate: Coordinate, *, language: Locale) -> Place | None:
        self._coverage.require(coordinate)
        key = (
            "reverse",
            language.value,
            round(coordinate.latitude, 5),
            round(coordinate.longitude, 5),
        )
        cached = self._cached(key)
        if cached is not None:
            return cast(Place | None, cached)
        params: dict[str, str | int | float] = {
            "lat": coordinate.latitude,
            "lon": coordinate.longitude,
        }
        if language is Locale.ENGLISH:
            params["lang"] = language.value
        payload = await self._get("/reverse", params)
        places = self._places(payload)
        result = places[0] if places else None
        await self._store(key, result)
        return result

    async def _get(self, path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingUnavailableError from exc

    def _places(self, payload: dict[str, Any], category: str | None = None) -> list[Place]:
        allowed = {item.strip() for item in category.split(",")} if category else set()
        result: list[Place] = []
        seen_identifiers: set[str] = set()
        seen_places: set[tuple[str, str]] = set()
        for raw_feature in _list(payload.get("features")):
            feature = _mapping(raw_feature)
            properties = _mapping(feature.get("properties"))
            raw_coordinates = _list(_mapping(feature.get("geometry")).get("coordinates"))
            if len(raw_coordinates) < 2:
                continue
            try:
                coordinate = Coordinate(
                    latitude=float(raw_coordinates[1]),
                    longitude=float(raw_coordinates[0]),
                )
            except (TypeError, ValueError):
                continue
            if not self._coverage.contains(coordinate):
                continue
            place_category = _place_category(properties)
            raw_categories = {
                place_category,
                _string(properties.get("type")).casefold(),
                _string(properties.get("osm_value")).casefold(),
            }
            if allowed and not raw_categories.intersection(allowed):
                continue
            osm_type = _string(properties.get("osm_type"), "osm")
            osm_id = _string(properties.get("osm_id"), f"{coordinate.latitude:.6f}")
            identifier = f"osm:{osm_type}:{osm_id}"
            if identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)
            name, subtitle = _display_text(properties)
            if not name:
                continue
            # Photon can return the same real-world feature as a node, way and
            # relation (and sometimes once per translated OSM name). Keeping
            # all of those consumes the entire result sheet with duplicates.
            # Use the user-visible identity as a second, stable de-duplication
            # key while retaining genuinely different places with the same
            # name when their locality differs.
            semantic_key = (
                name.casefold(),
                (subtitle or "").casefold(),
            )
            if semantic_key in seen_places:
                continue
            seen_places.add(semantic_key)
            result.append(
                Place(
                    id=identifier,
                    name=name,
                    name_he=(
                        _first_string(properties, "name:he", "name_he")
                        or (name if _contains_hebrew(name) else None)
                    ),
                    subtitle=subtitle,
                    coordinate=coordinate,
                    category=place_category,
                    confidence=DataConfidence.HIGH,
                )
            )
        return result

    def _intersect_bbox(
        self, requested: tuple[float, float, float, float] | None
    ) -> tuple[float, float, float, float]:
        coverage = (
            self._coverage.min_longitude,
            self._coverage.min_latitude,
            self._coverage.max_longitude,
            self._coverage.max_latitude,
        )
        if requested is None:
            return coverage
        result = (
            max(requested[0], coverage[0]),
            max(requested[1], coverage[1]),
            min(requested[2], coverage[2]),
            min(requested[3], coverage[3]),
        )
        if result[0] > result[2] or result[1] > result[3]:
            raise OutsideCoverageError
        return result

    def _cached(self, key: tuple[object, ...]) -> object | None:
        entry = self._cache.get(key)
        if entry is None or entry.expires_at <= monotonic():
            self._cache.pop(key, None)
            return None
        return entry.value

    async def _store(self, key: tuple[object, ...], value: object) -> None:
        async with self._lock:
            if len(self._cache) >= 512:
                oldest = min(self._cache, key=lambda item: self._cache[item].expires_at)
                self._cache.pop(oldest, None)
            self._cache[key] = _CacheEntry(monotonic() + self._cache_seconds, value)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return default


def _first_string(properties: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _string(properties.get(key))
        if value:
            return value
    return ""


def _display_text(properties: dict[str, Any]) -> tuple[str, str | None]:
    named_place = _first_string(properties, "name")
    street = _first_string(properties, "street")
    house_number = _string(properties.get("housenumber"))
    city = _first_string(properties, "city", "town", "village", "district")
    locality = _first_string(properties, "locality", "county")
    if named_place:
        name = named_place
        address = " ".join(part for part in (street, house_number) if part)
    else:
        name = " ".join(part for part in (street, house_number) if part)
        if not name:
            name = city or locality
        address = ""
    subtitle = (
        " · ".join(
            part
            for part in (address, city, locality)
            if part and part.casefold() != name.casefold()
        )
        or None
    )
    return name, subtitle


def _place_category(properties: dict[str, Any]) -> str:
    osm_value = _string(properties.get("osm_value")).casefold()
    if osm_value in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[osm_value]
    feature_type = _string(properties.get("type"), "place").casefold()
    if feature_type == "house" and not _first_string(properties, "name"):
        return "address"
    if feature_type in {"street", "locality", "district", "city", "state", "country"}:
        return feature_type
    return _CATEGORY_ALIASES.get(feature_type, "place")


def _query_variants(query: str) -> tuple[str, ...]:
    simplified = _GENERIC_QUERY_PREFIXES.sub("", query).strip()
    without_article = simplified[1:].strip() if simplified.startswith("ה") else simplified
    return tuple(dict.fromkeys(item for item in (query, simplified, without_article) if item))


def _merge_places(existing: list[Place], incoming: list[Place]) -> list[Place]:
    result = list(existing)
    indexes_by_id = {place.id: index for index, place in enumerate(result)}
    seen_semantic = {(place.name.casefold(), (place.subtitle or "").casefold()) for place in result}
    for place in incoming:
        semantic = (place.name.casefold(), (place.subtitle or "").casefold())
        existing_index = indexes_by_id.get(place.id)
        if existing_index is not None:
            result[existing_index] = _merge_localized_place(result[existing_index], place)
            continue
        if semantic in seen_semantic:
            continue
        indexes_by_id[place.id] = len(result)
        seen_semantic.add(semantic)
        result.append(place)
    return result


def _merge_localized_place(existing: Place, incoming: Place) -> Place:
    existing_is_hebrew = _contains_hebrew(existing.name)
    incoming_is_hebrew = _contains_hebrew(incoming.name)
    if existing_is_hebrew and not incoming_is_hebrew:
        return existing.model_copy(
            update={
                "name": incoming.name,
                "name_he": existing.name_he or existing.name,
            }
        )
    if incoming_is_hebrew and not existing_is_hebrew:
        return existing.model_copy(update={"name_he": incoming.name_he or incoming.name})
    if existing.name_he is None and incoming.name_he is not None:
        return existing.model_copy(update={"name_he": incoming.name_he})
    return existing


def _rank_places(places: list[Place], query: str, proximity: Coordinate | None) -> list[Place]:
    query_text = _normalized_search_text(query)
    simplified_text = _normalized_search_text(_GENERIC_QUERY_PREFIXES.sub("", query))
    query_tokens = tuple(
        dict.fromkeys(
            token[1:] if token.startswith("ה") and len(token) > 3 else token
            for token in simplified_text.split()
            if len(token) > 1
        )
    )
    requested_category = _requested_category(query_text)

    def key(
        indexed_place: tuple[int, Place],
    ) -> tuple[int, int, int, int, int, float, int]:
        index, place = indexed_place
        searchable = _normalized_search_text(
            " ".join(
                part
                for part in (
                    place.name,
                    place.name_he or "",
                    place.subtitle or "",
                    place.category,
                )
                if part
            )
        )
        names = {_normalized_search_text(name) for name in (place.name, place.name_he) if name}
        matched_tokens = sum(token in searchable for token in query_tokens)
        phrase_match = int(bool(simplified_text and simplified_text in searchable))
        name_match = int(
            bool(
                simplified_text
                and any(name in simplified_text or simplified_text in name for name in names)
            )
        )
        exact_name = int(bool(names.intersection({query_text, simplified_text})))
        category_match = int(
            requested_category is not None and place.category == requested_category
        )
        distance = haversine_m(proximity, place.coordinate) if proximity else 0.0
        return (
            -exact_name,
            -category_match,
            -matched_tokens,
            -phrase_match,
            -name_match,
            distance,
            index,
        )

    return [place for _, place in sorted(enumerate(places), key=key)]


def _normalized_search_text(value: str) -> str:
    return " ".join(re.findall(r"[\w\u0590-\u05ff]+", value.casefold()))


def _requested_category(query: str) -> str | None:
    prefixes = {
        "מסעד": "restaurant",
        "restaurant": "restaurant",
        "קפה": "cafe",
        "cafe": "cafe",
        "מלון": "hotel",
        "hotel": "hotel",
        "עיריית": "government",
        "קניון": "shopping",
        "mall": "shopping",
        "תחנ": "transit",
        "station": "transit",
    }
    return next(
        (category for prefix, category in prefixes.items() if query.startswith(prefix)),
        None,
    )


def _contains_hebrew(value: str) -> bool:
    return any("\u0590" <= character <= "\u05ff" for character in value)
