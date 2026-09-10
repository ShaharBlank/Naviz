from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Any, Protocol, cast

import httpx
from astral import Observer
from astral.sun import azimuth, elevation
from pyproj import Transformer
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union

from .geometry import decode_polyline, haversine_m
from .models import (
    Coordinate,
    DataConfidence,
    RouteAlternative,
    RoutePlanRequest,
    RoutePreference,
    SegmentAnnotation,
    ShadowPolygon,
    ShadowSceneRequest,
    ShadowSceneResponse,
    TravelMode,
)

_WGS84_TO_ITM = Transformer.from_crs("EPSG:4326", "EPSG:2039", always_xy=True)
_ITM_TO_WGS84 = Transformer.from_crs("EPSG:2039", "EPSG:4326", always_xy=True)
_ROAD_MODES = {TravelMode.CAR, TravelMode.MOTORCYCLE, TravelMode.TRUCK}
_ROUTE_CONTEXT_CORRIDOR_M = 260.0
_MAX_SHADOW_SCENE_ROUTE_M = 6_000.0
OUTSIDE_VALIDATED_FEATURE_COVERAGE = "outside_validated_feature_coverage"


@dataclass(frozen=True, slots=True)
class Building:
    footprint: Polygon | MultiPolygon
    height_m: float
    confidence: DataConfidence


@dataclass(frozen=True, slots=True)
class OsmRouteContext:
    buildings: tuple[Building, ...] = ()
    traffic_signals: tuple[Point, ...] = ()
    complete: bool = True
    incomplete_reason: str | None = None


@dataclass(slots=True)
class _ContextCacheEntry:
    expires_at: float
    context: OsmRouteContext


@dataclass(slots=True)
class _ShadowSceneCacheEntry:
    expires_at: float
    response: ShadowSceneResponse


class RouteContextPort(Protocol):
    async def context(
        self,
        routes: list[RouteAlternative],
        *,
        buildings: bool,
        traffic_signals: bool,
    ) -> OsmRouteContext: ...


class SqliteOsmRouteContext:
    """Reads a pinned, spatially indexed OSM feature bundle.

    Building extraction belongs in the offline data pipeline. Keeping the
    immutable result in SQLite removes a slow, failure-prone Overpass request
    from every route plan while preserving the same enrichment contract.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        if not self._database_path.is_file():
            raise FileNotFoundError(self._database_path)
        self._coverage_bbox = self._read_coverage_bbox()
        self._scene_cache: dict[tuple[object, ...], _ShadowSceneCacheEntry] = {}
        self._scene_lock = asyncio.Lock()

    @property
    def coverage_bbox(self) -> tuple[float, float, float, float]:
        return self._coverage_bbox

    async def context(
        self,
        routes: list[RouteAlternative],
        *,
        buildings: bool,
        traffic_signals: bool,
    ) -> OsmRouteContext:
        corridor = _route_corridor(routes)
        bounds = _projected_bounds_to_wgs84(corridor.bounds)
        if not _bbox_contains(self._coverage_bbox, bounds):
            return OsmRouteContext(
                complete=False,
                incomplete_reason=OUTSIDE_VALIDATED_FEATURE_COVERAGE,
            )
        return await asyncio.to_thread(
            self._load,
            bounds,
            corridor,
            buildings=buildings,
            traffic_signals=traffic_signals,
        )

    async def shadow_scene(self, request: ShadowSceneRequest) -> ShadowSceneResponse:
        """Project bounded 2.5-D building shadows around one route corridor."""
        minute = request.at.replace(second=0, microsecond=0)
        key = (request.encoded_polyline, minute, round(request.corridor_m, 1))
        cached = self._scene_cache.get(key)
        if cached is not None and cached.expires_at > monotonic():
            return cached.response
        response = await asyncio.to_thread(self._build_shadow_scene, request)
        async with self._scene_lock:
            if len(self._scene_cache) >= 24:
                oldest = min(
                    self._scene_cache,
                    key=lambda item: self._scene_cache[item].expires_at,
                )
                self._scene_cache.pop(oldest, None)
            self._scene_cache[key] = _ShadowSceneCacheEntry(
                expires_at=monotonic() + 300,
                response=response,
            )
        return response

    def _build_shadow_scene(self, request: ShadowSceneRequest) -> ShadowSceneResponse:
        points = decode_polyline(request.encoded_polyline)
        if len(points) < 2:
            raise ValueError("Shadow scene requires a route with at least two points")
        line = LineString(
            [
                _WGS84_TO_ITM.transform(point.longitude, point.latitude)
                for point in points
            ]
        )
        visible_corridor = line.buffer(request.corridor_m)
        # A building outside the visible corridor can still cast into it.
        source_corridor = visible_corridor.buffer(250)
        bounds = _projected_bounds_to_wgs84(source_corridor.bounds)
        observer = Observer(latitude=points[0].latitude, longitude=points[0].longitude)
        sun_azimuth = float(azimuth(observer, request.at))
        sun_elevation = float(elevation(observer, request.at))
        if line.length > _MAX_SHADOW_SCENE_ROUTE_M:
            return ShadowSceneResponse(
                available=False,
                at=request.at,
                solar_azimuth_degrees=round(sun_azimuth, 3),
                solar_elevation_degrees=round(sun_elevation, 3),
                coverage_bbox=self._coverage_bbox,
                model_version="osm-2.5d-v1",
                attribution=["© OpenStreetMap contributors · ODbL"],
                warning=(
                    "Shadow scenes are limited to a six-kilometre viewing window; "
                    "request the corridor around the current route position."
                ),
            )
        if not _bbox_contains(self._coverage_bbox, bounds):
            return ShadowSceneResponse(
                available=False,
                at=request.at,
                solar_azimuth_degrees=round(sun_azimuth, 3),
                solar_elevation_degrees=round(sun_elevation, 3),
                coverage_bbox=self._coverage_bbox,
                model_version="osm-2.5d-v1",
                attribution=["© OpenStreetMap contributors · ODbL"],
                warning="Route corridor is outside validated building coverage.",
            )
        context = self._load(
            bounds,
            source_corridor,
            buildings=True,
            traffic_signals=False,
        )
        shadows, high_shadows, _, sun_azimuth, sun_elevation = _shadow_unions(
            context.buildings,
            request.at,
            points[0],
        )
        clipped = shadows.intersection(visible_corridor).simplify(
            0.65, preserve_topology=True
        )
        clipped_high = high_shadows.intersection(visible_corridor).simplify(
            0.65, preserve_topology=True
        )
        return ShadowSceneResponse(
            available=True,
            at=request.at,
            solar_azimuth_degrees=round(sun_azimuth, 3),
            solar_elevation_degrees=round(sun_elevation, 3),
            shadows=_shadow_polygons(clipped),
            high_confidence_shadows=_shadow_polygons(clipped_high),
            coverage_bbox=self._coverage_bbox,
            model_version="osm-2.5d-v1",
            attribution=["© OpenStreetMap contributors · ODbL"],
        )

    def _read_coverage_bbox(self) -> tuple[float, float, float, float]:
        connection = sqlite3.connect(f"file:{self._database_path}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'coverage_bbox'"
            ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError("Feature bundle is missing readable coverage metadata") from exc
        finally:
            connection.close()
        if row is None:
            raise ValueError("Feature bundle metadata is missing coverage_bbox")
        try:
            raw = json.loads(str(row[0]))
            values = tuple(float(value) for value in raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Feature bundle coverage_bbox is malformed") from exc
        if len(values) != 4:
            raise ValueError("Feature bundle coverage_bbox must contain four coordinates")
        west, south, east, north = values
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Feature bundle coverage_bbox must contain finite coordinates")
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Feature bundle coverage_bbox is outside valid coordinate bounds")
        return west, south, east, north

    def _load(
        self,
        bounds: tuple[float, float, float, float],
        corridor: BaseGeometry,
        *,
        buildings: bool,
        traffic_signals: bool,
    ) -> OsmRouteContext:
        west, south, east, north = bounds
        building_items: list[Building] = []
        signal_items: list[Point] = []
        connection = sqlite3.connect(f"file:{self._database_path}?mode=ro", uri=True)
        try:
            if buildings:
                rows = connection.execute(
                    """
                    SELECT b.coordinates, b.height_m, b.confidence
                    FROM building_index AS i
                    JOIN buildings AS b ON b.id = i.id
                    WHERE i.max_lon >= ? AND i.min_lon <= ?
                      AND i.max_lat >= ? AND i.min_lat <= ?
                    """,
                    (west, east, south, north),
                )
                for coordinates, height_m, confidence in rows:
                    polygon = _polygon_from_coordinate_blob(coordinates)
                    if polygon is not None and corridor.intersects(polygon):
                        building_items.append(
                            Building(polygon, float(height_m), DataConfidence(confidence))
                        )
            if traffic_signals:
                rows = connection.execute(
                    """
                    SELECT s.longitude, s.latitude
                    FROM signal_index AS i
                    JOIN signals AS s ON s.id = i.id
                    WHERE i.max_lon >= ? AND i.min_lon <= ?
                      AND i.max_lat >= ? AND i.min_lat <= ?
                    """,
                    (west, east, south, north),
                )
                for longitude, latitude in rows:
                    x, y = _WGS84_TO_ITM.transform(float(longitude), float(latitude))
                    signal = Point(x, y)
                    # The RTree query deliberately starts with the corridor's
                    # bounding box, but a long diagonal route can make that box
                    # cover most of a region. Keep only signals close enough to
                    # an actual alternative before clustering. Besides being the
                    # correct semantic boundary, this prevents the clustering
                    # pass from becoming quadratic in every signal between two
                    # distant cities.
                    if corridor.intersects(signal):
                        signal_items.append(signal)
        finally:
            connection.close()
        return OsmRouteContext(
            buildings=tuple(building_items),
            traffic_signals=tuple(_cluster_signals(signal_items)),
        )


class OverpassRouteContext:
    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str,
        cache_seconds: int = 1_800,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"User-Agent": user_agent}
        self._cache_seconds = cache_seconds
        self._timeout = timeout_seconds
        self._cache: dict[tuple[object, ...], _ContextCacheEntry] = {}
        self._lock = asyncio.Lock()

    async def context(
        self,
        routes: list[RouteAlternative],
        *,
        buildings: bool,
        traffic_signals: bool,
    ) -> OsmRouteContext:
        west, south, east, north = _route_bounds(routes)
        bounds = tuple(round(value, 4) for value in (south, west, north, east))
        key = (*bounds, buildings, traffic_signals)
        cached = self._cache.get(key)
        if cached is not None and cached.expires_at > monotonic():
            return cached.context
        clauses = []
        bbox_value = ",".join(str(value) for value in bounds)
        if traffic_signals:
            clauses.append(f'node["highway"="traffic_signals"]({bbox_value});')
        if buildings:
            clauses.append(f'way["building"]({bbox_value});')
        query = f"[out:json][timeout:15];({''.join(clauses)});out tags geom;"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
                follow_redirects=True,
            ) as client:
                # POST keeps a building-rich corridor query out of the URL and is
                # accepted consistently by the public Overpass frontends. Long
                # percent-encoded GET URLs are commonly rejected with HTTP 406.
                response = await client.post(self._base_url, data={"data": query})
                response.raise_for_status()
            context = self._normalize(cast(dict[str, Any], response.json()))
        except (httpx.HTTPError, ValueError):
            context = OsmRouteContext(complete=False)
        async with self._lock:
            if len(self._cache) >= 64:
                oldest = min(self._cache, key=lambda item: self._cache[item].expires_at)
                self._cache.pop(oldest, None)
            self._cache[key] = _ContextCacheEntry(monotonic() + self._cache_seconds, context)
        return context

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> OsmRouteContext:
        buildings: list[Building] = []
        signals: list[Point] = []
        for raw_element in _list(payload.get("elements")):
            element = _mapping(raw_element)
            tags = _mapping(element.get("tags"))
            if tags.get("highway") == "traffic_signals":
                try:
                    x, y = _WGS84_TO_ITM.transform(float(element["lon"]), float(element["lat"]))
                    signals.append(Point(x, y))
                except (KeyError, TypeError, ValueError):
                    continue
            if "building" not in tags:
                continue
            coordinates = []
            for raw_point in _list(element.get("geometry")):
                point = _mapping(raw_point)
                try:
                    coordinates.append(
                        _WGS84_TO_ITM.transform(float(point["lon"]), float(point["lat"]))
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            if len(coordinates) < 4:
                continue
            polygon = Polygon(coordinates)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or not isinstance(polygon, Polygon | MultiPolygon):
                continue
            height, confidence = _building_height(tags)
            buildings.append(Building(polygon, height, confidence))
        return OsmRouteContext(
            buildings=tuple(buildings[:10_000]),
            traffic_signals=tuple(_cluster_signals(signals)),
            complete=True,
        )


class RouteFeatureAnalyzer:
    def __init__(self, context: RouteContextPort) -> None:
        self._context = context

    async def enrich(
        self, request: RoutePlanRequest, routes: list[RouteAlternative]
    ) -> list[RouteAlternative]:
        needs_shade = request.mode == TravelMode.WALK
        needs_signals = request.mode in _ROAD_MODES
        if not needs_shade and not needs_signals:
            return routes
        context = await self._context.context(
            routes,
            buildings=needs_shade,
            traffic_signals=needs_signals,
        )
        if needs_shade:
            return self._shade_routes(request, routes, context)
        return self._signal_routes(request, routes, context)

    def _shade_routes(
        self,
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
        context: OsmRouteContext,
    ) -> list[RouteAlternative]:
        if not context.complete:
            fallback_reason, warning = _feature_unavailable_reason("shade", context)
            if request.include_comparisons or request.preference != RoutePreference.FASTEST:
                fastest = min(routes, key=lambda route: route.metrics.duration_s)
                return [
                    _mark_feature_unavailable(
                        fastest.model_copy(update={"label_key": "route.fastest"}),
                        fallback_reason=fallback_reason,
                        warning=warning,
                    )
                ]
            return [
                _mark_feature_unavailable(
                    route,
                    fallback_reason=fallback_reason,
                    warning=warning,
                )
                for route in routes
            ]
        departure = routes[0].departure_at
        center = decode_polyline(routes[0].encoded_polyline)[0]
        shadows, high_shadows, sun_up, _, _ = _shadow_unions(
            context.buildings,
            departure,
            center,
        )
        enriched = [_annotate_shade(route, shadows, high_shadows, sun_up) for route in routes]
        fastest = min(enriched, key=lambda route: route.metrics.duration_s)
        if request.include_comparisons:
            balanced = self._best_shade_route(request, enriched, fastest, 15.0).model_copy(
                update={"label_key": "route.balancedShade"}
            )
            maximum = self._best_shade_route(request, enriched, fastest, 30.0).model_copy(
                update={"label_key": "route.maximumShade"}
            )
            fastest = fastest.model_copy(update={"label_key": "route.fastest"})
            preference_label = {
                RoutePreference.BALANCED_SHADE: "route.balancedShade",
                RoutePreference.MAXIMUM_SHADE: "route.maximumShade",
            }.get(request.preference, "route.fastest")
            comparison = [fastest, balanced, maximum]
            comparison = [
                route
                for _, route in sorted(
                    enumerate(comparison),
                    key=lambda item: (item[1].label_key != preference_label, item[0]),
                )
            ]
            comparison = _deduplicate_route_geometry(comparison)
            if len(comparison) == 1:
                comparison[0] = comparison[0].model_copy(
                    update={"fallback_reason": "least_exposed_route"}
                )
            return comparison[:3]
        if request.preference == RoutePreference.FASTEST:
            return enriched
        cap = 15.0 if request.preference == RoutePreference.BALANCED_SHADE else 30.0
        if request.constraints.maximum_time_detour_percent is not None:
            cap = request.constraints.maximum_time_detour_percent
        candidates = [
            route
            for route in enriched
            if route.metrics.duration_s <= fastest.metrics.duration_s * (1 + cap / 100)
        ]
        preferred = min(
            candidates,
            key=lambda route: (
                route.metrics.sun_exposure_minutes or 0,
                route.metrics.duration_s,
            ),
        )
        label = (
            "route.balancedShade"
            if request.preference == RoutePreference.BALANCED_SHADE
            else "route.maximumShade"
        )
        preferred = preferred.model_copy(update={"label_key": label})
        ordered = [preferred]
        if preferred.id != fastest.id:
            ordered.append(fastest.model_copy(update={"label_key": "route.fastest"}))
        ordered.extend(route for route in enriched if route.id not in {item.id for item in ordered})
        if preferred.id == fastest.id:
            ordered[0] = ordered[0].model_copy(update={"fallback_reason": "least_exposed_route"})
        return ordered[:3]

    @staticmethod
    def _best_shade_route(
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
        fastest: RouteAlternative,
        default_cap: float,
    ) -> RouteAlternative:
        cap = (
            request.constraints.maximum_time_detour_percent
            if request.constraints.maximum_time_detour_percent is not None
            else default_cap
        )
        candidates = [
            route
            for route in routes
            if route.metrics.duration_s <= fastest.metrics.duration_s * (1 + cap / 100)
        ]
        return min(
            candidates,
            key=lambda route: (
                route.metrics.sun_exposure_minutes or 0,
                route.metrics.duration_s,
            ),
        )

    @staticmethod
    def _signal_routes(
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
        context: OsmRouteContext,
    ) -> list[RouteAlternative]:
        if not context.complete:
            fallback_reason, warning = _feature_unavailable_reason("signal", context)
            if request.include_comparisons or request.preference == RoutePreference.FEWER_LIGHTS:
                fastest = min(routes, key=lambda route: route.metrics.duration_s)
                return [
                    _mark_feature_unavailable(
                        fastest.model_copy(update={"label_key": "route.fastest"}),
                        fallback_reason=fallback_reason,
                        warning=warning,
                    )
                ]
            return [
                _mark_feature_unavailable(
                    route,
                    fallback_reason=fallback_reason,
                    warning=warning,
                )
                for route in routes
            ]
        enriched = [_annotate_signals(route, context.traffic_signals) for route in routes]
        fastest = min(enriched, key=lambda route: route.metrics.duration_s)
        if not request.include_comparisons and request.preference != RoutePreference.FEWER_LIGHTS:
            return enriched
        time_cap = (
            request.constraints.maximum_time_detour_percent
            if request.constraints.maximum_time_detour_percent is not None
            else 10.0
        )
        distance_cap = (
            request.constraints.maximum_distance_detour_percent
            if request.constraints.maximum_distance_detour_percent is not None
            else 15.0
        )
        baseline_signals = fastest.metrics.traffic_signals or 0
        candidates = []
        for route in enriched:
            signals = route.metrics.traffic_signals or 0
            reduction = baseline_signals - signals
            material = reduction >= 2 or (
                baseline_signals > 0 and reduction / baseline_signals >= 0.2
            )
            if not material:
                continue
            if route.metrics.duration_s > fastest.metrics.duration_s * (1 + time_cap / 100):
                continue
            if route.metrics.distance_m > fastest.metrics.distance_m * (1 + distance_cap / 100):
                continue
            candidates.append((route.metrics.duration_s + signals * 25, route, reduction))
        if not candidates:
            return [fastest.model_copy(update={"fallback_reason": "no_material_signal_reduction"})]
        _, preferred, reduction = min(candidates, key=lambda item: item[0])
        preferred = preferred.model_copy(
            update={
                "label_key": "route.fewerLights",
                "metrics": preferred.metrics.model_copy(update={"signals_avoided": reduction}),
            }
        )
        fastest = fastest.model_copy(update={"label_key": "route.fastest"})
        result = (
            [preferred, fastest]
            if request.preference == RoutePreference.FEWER_LIGHTS
            else [fastest, preferred]
        )
        return result


def _shadow_unions(
    buildings: tuple[Building, ...],
    when: datetime,
    coordinate: Coordinate,
) -> tuple[BaseGeometry, BaseGeometry, bool, float, float]:
    observer = Observer(latitude=coordinate.latitude, longitude=coordinate.longitude)
    sun_elevation = float(elevation(observer, when))
    sun_azimuth = float(azimuth(observer, when))
    if sun_elevation <= 0:
        empty = Polygon()
        return empty, empty, False, sun_azimuth, sun_elevation
    all_shadows = []
    high_shadows = []
    for building in buildings:
        length = min(250.0, building.height_m / math.tan(math.radians(sun_elevation)))
        direction = math.radians((sun_azimuth + 180) % 360)
        dx = length * math.sin(direction)
        dy = length * math.cos(direction)
        shadow = _shadow_for_geometry(building.footprint, dx, dy)
        if shadow.is_empty:
            continue
        all_shadows.append(shadow)
        if building.confidence == DataConfidence.HIGH:
            high_shadows.append(shadow)
    return (
        unary_union(all_shadows) if all_shadows else Polygon(),
        unary_union(high_shadows) if high_shadows else Polygon(),
        True,
        sun_azimuth,
        sun_elevation,
    )


def _shadow_polygons(geometry: BaseGeometry) -> list[ShadowPolygon]:
    if geometry.is_empty:
        return []
    converted = transform_geometry(_ITM_TO_WGS84.transform, geometry)
    if isinstance(converted, Polygon):
        polygons = [converted]
    elif isinstance(converted, MultiPolygon):
        polygons = list(converted.geoms)
    else:
        polygons = [
            item
            for item in getattr(converted, "geoms", ())
            if isinstance(item, Polygon)
        ]
    result: list[ShadowPolygon] = []
    for polygon in sorted(polygons, key=lambda item: item.area, reverse=True)[:400]:
        rings = [
            [
                Coordinate(latitude=float(latitude), longitude=float(longitude))
                for longitude, latitude in ring.coords
            ]
            for ring in [polygon.exterior, *polygon.interiors]
            if len(ring.coords) >= 4
        ]
        if rings:
            result.append(ShadowPolygon(rings=rings))
    return result


def _shadow_for_geometry(geometry: Polygon | MultiPolygon, dx: float, dy: float) -> BaseGeometry:
    polygons = [geometry] if isinstance(geometry, Polygon) else list(geometry.geoms)
    shadows = []
    for polygon in polygons:
        translated = affinity.translate(polygon, xoff=dx, yoff=dy)
        points = list(polygon.exterior.coords)
        connectors = [
            Polygon(
                [first, second, (second[0] + dx, second[1] + dy), (first[0] + dx, first[1] + dy)]
            )
            for first, second in pairwise(points)
        ]
        shadows.append(unary_union([translated, *connectors]).difference(polygon))
    return unary_union(shadows)


def _annotate_shade(
    route: RouteAlternative,
    shadows: BaseGeometry,
    high_shadows: BaseGeometry,
    sun_up: bool,
) -> RouteAlternative:
    geometry = decode_polyline(route.encoded_polyline)
    annotations = []
    shaded_distance = high_distance = total_distance = 0.0
    for index, (first, second) in enumerate(pairwise(geometry)):
        distance = haversine_m(first, second)
        total_distance += distance
        samples = _segment_samples(first, second, distance)
        if sun_up:
            shaded = sum(shadows.covers(point) for point in samples) / len(samples)
            high = sum(high_shadows.covers(point) for point in samples) / len(samples)
        else:
            shaded = high = 1.0
        shaded_distance += distance * shaded
        high_distance += distance * high
        classification = "shade" if shaded >= 0.75 else "mixed" if shaded >= 0.25 else "sun"
        annotations.append(
            SegmentAnnotation(
                start_index=index,
                end_index=index + 1,
                classification=classification,
                shade_fraction=round(shaded, 4),
                confidence=DataConfidence.MEDIUM,
            )
        )
    fraction = shaded_distance / total_distance if total_distance else 0.0
    high_fraction = high_distance / total_distance if total_distance else 0.0
    metrics = route.metrics.model_copy(
        update={
            "shade_fraction": round(fraction, 4),
            "high_confidence_shade_fraction": round(high_fraction, 4),
            "sun_exposure_minutes": round(route.metrics.duration_s * (1 - fraction) / 60, 2),
        }
    )
    quality = route.quality.model_copy(
        update={
            "confidence": DataConfidence.MEDIUM,
            "shade_sources": [
                "OpenStreetMap building footprints and height tags",
                "Astral solar position",
            ],
        }
    )
    legs = [leg.model_copy(update={"annotations": annotations}) for leg in route.legs]
    return route.model_copy(
        update={"annotations": annotations, "legs": legs, "metrics": metrics, "quality": quality}
    )


def _annotate_signals(route: RouteAlternative, signals: tuple[Point, ...]) -> RouteAlternative:
    geometry = decode_polyline(route.encoded_polyline)
    line = LineString(
        [_WGS84_TO_ITM.transform(point.longitude, point.latitude) for point in geometry]
    )
    count = sum(line.distance(signal) <= 18 for signal in signals)
    return route.model_copy(
        update={"metrics": route.metrics.model_copy(update={"traffic_signals": count})}
    )


def _segment_samples(first: Coordinate, second: Coordinate, distance_m: float) -> list[Point]:
    count = max(1, math.ceil(distance_m / 5))
    result = []
    for index in range(count + 1):
        fraction = index / count
        longitude = first.longitude + (second.longitude - first.longitude) * fraction
        latitude = first.latitude + (second.latitude - first.latitude) * fraction
        x, y = _WGS84_TO_ITM.transform(longitude, latitude)
        result.append(Point(x, y))
    return result


def _route_bounds(routes: list[RouteAlternative]) -> tuple[float, float, float, float]:
    return (
        min(route.bbox[0] for route in routes) - 0.001,
        min(route.bbox[1] for route in routes) - 0.001,
        max(route.bbox[2] for route in routes) + 0.001,
        max(route.bbox[3] for route in routes) + 0.001,
    )


def _route_corridor(routes: list[RouteAlternative]) -> BaseGeometry:
    lines = []
    for route in routes:
        coordinates = [
            _WGS84_TO_ITM.transform(point.longitude, point.latitude)
            for point in decode_polyline(route.encoded_polyline)
        ]
        if len(coordinates) >= 2:
            lines.append(LineString(coordinates).buffer(_ROUTE_CONTEXT_CORRIDOR_M))
    if not lines:
        raise ValueError("Route context requires at least one route with valid geometry")
    return unary_union(lines)


def _projected_bounds_to_wgs84(
    bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    coordinates = (
        _ITM_TO_WGS84.transform(minimum_x, minimum_y),
        _ITM_TO_WGS84.transform(minimum_x, maximum_y),
        _ITM_TO_WGS84.transform(maximum_x, minimum_y),
        _ITM_TO_WGS84.transform(maximum_x, maximum_y),
    )
    longitudes = [coordinate[0] for coordinate in coordinates]
    latitudes = [coordinate[1] for coordinate in coordinates]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _bbox_contains(
    coverage: tuple[float, float, float, float],
    required: tuple[float, float, float, float],
) -> bool:
    west, south, east, north = coverage
    required_west, required_south, required_east, required_north = required
    return (
        west <= required_west
        and south <= required_south
        and east >= required_east
        and north >= required_north
    )


def _feature_unavailable_reason(
    feature: str, context: OsmRouteContext
) -> tuple[str, str]:
    if context.incomplete_reason == OUTSIDE_VALIDATED_FEATURE_COVERAGE:
        if feature == "shade":
            return (
                "shade_outside_validated_coverage",
                "Shade metrics are unavailable outside validated feature coverage.",
            )
        return (
            "signal_outside_validated_coverage",
            "Traffic-signal metrics are unavailable outside validated feature coverage.",
        )
    if feature == "shade":
        return (
            "shade_data_temporarily_unavailable",
            "Shade metrics are temporarily unavailable.",
        )
    return (
        "signal_data_temporarily_unavailable",
        "Traffic-signal metrics are temporarily unavailable.",
    )


def _mark_feature_unavailable(
    route: RouteAlternative,
    *,
    fallback_reason: str,
    warning: str,
) -> RouteAlternative:
    route_warnings = list(dict.fromkeys([*route.warnings, warning]))
    quality_warnings = list(dict.fromkeys([*route.quality.warnings, warning]))
    return route.model_copy(
        update={
            "fallback_reason": fallback_reason,
            "warnings": route_warnings,
            "quality": route.quality.model_copy(
                update={
                    "confidence": DataConfidence.LOW,
                    "warnings": quality_warnings,
                }
            ),
        }
    )


def _polygon_from_coordinate_blob(value: object) -> Polygon | MultiPolygon | None:
    if not isinstance(value, bytes) or len(value) < 32 or len(value) % 8:
        return None
    coordinates = [
        _WGS84_TO_ITM.transform(longitude / 10_000_000, latitude / 10_000_000)
        for longitude, latitude in struct.iter_unpack("<ii", value)
    ]
    polygon = Polygon(coordinates)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or not isinstance(polygon, Polygon | MultiPolygon):
        return None
    return polygon


def _building_height(tags: dict[str, Any]) -> tuple[float, DataConfidence]:
    height = _number_from_tag(tags.get("height"))
    if height is not None and 1 <= height <= 300:
        return height, DataConfidence.HIGH
    levels = _number_from_tag(tags.get("building:levels"))
    if levels is not None and 1 <= levels <= 80:
        return levels * 3.2, DataConfidence.MEDIUM
    return 10.0, DataConfidence.LOW


def _number_from_tag(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    cleaned = value.lower().replace("meters", "").replace("meter", "").replace("m", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cluster_signals(signals: list[Point]) -> list[Point]:
    clusters: list[list[Point]] = []
    for signal in signals:
        cluster = next(
            (items for items in clusters if min(signal.distance(item) for item in items) <= 25),
            None,
        )
        if cluster is None:
            clusters.append([signal])
        else:
            cluster.append(signal)
    return [unary_union(cluster).centroid for cluster in clusters]


def _deduplicate_route_geometry(routes: list[RouteAlternative]) -> list[RouteAlternative]:
    result: list[RouteAlternative] = []
    seen: set[str] = set()
    for route in routes:
        if route.encoded_polyline in seen:
            continue
        result.append(route)
        seen.add(route.encoded_polyline)
    return result


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
