from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Any, Protocol, cast

import httpx
import numpy as np
from astral import Observer
from astral.sun import azimuth, elevation
from pyproj import Transformer
from shapely import affinity, intersects, intersects_xy, linestrings, prepare
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
_BALANCED_SHADE_DETOUR_PERCENT = 15.0
_MAXIMUM_SHADE_DETOUR_PERCENT = 50.0
OUTSIDE_VALIDATED_FEATURE_COVERAGE = "outside_validated_feature_coverage"


@dataclass(frozen=True, slots=True)
class Building:
    footprint: Polygon | MultiPolygon
    height_m: float
    confidence: DataConfidence


@dataclass(frozen=True, slots=True)
class _BuildingHeightGroup:
    height_m: float
    footprints: BaseGeometry
    high_confidence_footprints: BaseGeometry


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
        bucketed_request = request.model_copy(update={"at": minute})
        response = await asyncio.to_thread(self._build_shadow_scene, bucketed_request)
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
            [_WGS84_TO_ITM.transform(point.longitude, point.latitude) for point in points]
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
                encoded_polyline=request.encoded_polyline,
                solar_azimuth_degrees=round(sun_azimuth, 3),
                solar_elevation_degrees=round(sun_elevation, 3),
                coverage_bbox=self._coverage_bbox,
                model_version="osm-2.5d-v2",
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
                encoded_polyline=request.encoded_polyline,
                solar_azimuth_degrees=round(sun_azimuth, 3),
                solar_elevation_degrees=round(sun_elevation, 3),
                coverage_bbox=self._coverage_bbox,
                model_version="osm-2.5d-v2",
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
        clipped = shadows.intersection(visible_corridor).simplify(0.65, preserve_topology=True)
        clipped_high = high_shadows.intersection(visible_corridor).simplify(
            0.65, preserve_topology=True
        )
        return ShadowSceneResponse(
            available=True,
            at=request.at,
            encoded_polyline=request.encoded_polyline,
            solar_azimuth_degrees=round(sun_azimuth, 3),
            solar_elevation_degrees=round(sun_elevation, 3),
            shadows=_shadow_polygons(clipped),
            high_confidence_shadows=_shadow_polygons(clipped_high),
            segment_annotations=_snapshot_shade_annotations(
                points,
                shadows,
                high_shadows,
                sun_elevation > 0,
            ),
            coverage_bbox=self._coverage_bbox,
            model_version="osm-2.5d-v2",
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
            # Polygon projection and point sampling are CPU-bound. Keeping
            # them off the event loop lets health, search and cancellation
            # requests stay responsive on the single-worker hosted profile.
            return await asyncio.to_thread(self._shade_routes, request, routes, context)
        return await asyncio.to_thread(self._signal_routes, request, routes, context)

    async def signal_probe_coordinates(
        self,
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
    ) -> tuple[Coordinate, ...]:
        """Return signals on the fastest route only when normal alternatives do not improve it."""
        context = await self._context.context(
            routes,
            buildings=False,
            traffic_signals=True,
        )
        if not context.complete or not context.traffic_signals:
            return ()
        enriched = [_annotate_signals(route, context.traffic_signals) for route in routes]
        if len(self._signal_routes(request, enriched, context)) > 1:
            return ()
        fastest = min(enriched, key=lambda route: route.metrics.duration_s)
        geometry = decode_polyline(fastest.encoded_polyline)
        line = LineString(
            [_WGS84_TO_ITM.transform(point.longitude, point.latitude) for point in geometry]
        )
        result = []
        for signal in context.traffic_signals:
            if line.distance(signal) > 18:
                continue
            longitude, latitude = _ITM_TO_WGS84.transform(signal.x, signal.y)
            coordinate = Coordinate(latitude=latitude, longitude=longitude)
            # Excluding a signal at an endpoint can make an otherwise valid
            # route impossible and cannot improve the user's journey anyway.
            if haversine_m(request.origin, coordinate) < 60:
                continue
            if haversine_m(request.destination, coordinate) < 60:
                continue
            result.append(coordinate)
        return tuple(result)

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
        shadow_cache: dict[
            tuple[datetime, float, float], tuple[BaseGeometry, BaseGeometry, bool]
        ] = {}
        sampling_corridor = _route_sampling_corridor(routes)
        building_groups = _building_height_groups(context.buildings)
        enriched = [
            _annotate_shade_time_dependent(
                route,
                context.buildings,
                shadow_cache,
                observer_coordinate=request.origin,
                sampling_corridor=sampling_corridor,
                building_groups=building_groups,
            )
            for route in routes
        ]
        fastest = min(enriched, key=lambda route: route.metrics.duration_s)
        if request.include_comparisons:
            balanced = self._best_balanced_shade_route(
                request,
                enriched,
                fastest,
                _BALANCED_SHADE_DETOUR_PERCENT,
            ).model_copy(update={"label_key": "route.balancedShade"})
            maximum = self._best_maximum_shade_route(
                request,
                enriched,
                fastest,
                _MAXIMUM_SHADE_DETOUR_PERCENT,
            ).model_copy(update={"label_key": "route.maximumShade"})
            fastest_label = (
                "route.fastestAndShadiest" if maximum.id == fastest.id else "route.fastest"
            )
            comparison = [fastest.model_copy(update={"label_key": fastest_label})]
            if balanced.id not in {fastest.id, maximum.id}:
                comparison.append(balanced)
            if maximum.id != fastest.id:
                comparison.append(maximum)
            return comparison[:3]
        if request.preference == RoutePreference.FASTEST:
            return enriched
        cap = (
            _BALANCED_SHADE_DETOUR_PERCENT
            if request.preference == RoutePreference.BALANCED_SHADE
            else _MAXIMUM_SHADE_DETOUR_PERCENT
        )
        if request.constraints.maximum_time_detour_percent is not None:
            cap = request.constraints.maximum_time_detour_percent
        candidates = [
            route
            for route in enriched
            if route.metrics.duration_s <= fastest.metrics.duration_s * (1 + cap / 100)
        ]
        preferred = (
            self._best_balanced_shade_route(request, candidates, fastest, cap)
            if request.preference == RoutePreference.BALANCED_SHADE
            else self._best_maximum_shade_route(request, candidates, fastest, cap)
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
    def _shade_candidates(
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
        fastest: RouteAlternative,
        default_cap: float,
    ) -> list[RouteAlternative]:
        cap = (
            request.constraints.maximum_time_detour_percent
            if request.constraints.maximum_time_detour_percent is not None
            else default_cap
        )
        return [
            route
            for route in routes
            if route.metrics.duration_s <= fastest.metrics.duration_s * (1 + cap / 100)
        ]

    @classmethod
    def _best_balanced_shade_route(
        cls,
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
        fastest: RouteAlternative,
        default_cap: float,
    ) -> RouteAlternative:
        candidates = cls._shade_candidates(request, routes, fastest, default_cap)
        return min(
            candidates,
            key=lambda route: (
                route.metrics.sun_exposure_minutes or 0,
                route.metrics.duration_s,
            ),
        )

    @classmethod
    def _best_maximum_shade_route(
        cls,
        request: RoutePlanRequest,
        routes: list[RouteAlternative],
        fastest: RouteAlternative,
        default_cap: float,
    ) -> RouteAlternative:
        candidates = cls._shade_candidates(request, routes, fastest, default_cap)
        return min(
            candidates,
            key=lambda route: (
                -(route.metrics.shade_fraction or 0),
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
            if route.metrics.duration_s > fastest.metrics.duration_s * (1 + time_cap / 100):
                continue
            if route.metrics.distance_m > fastest.metrics.distance_m * (1 + distance_cap / 100):
                continue
            candidates.append((signals, route.metrics.duration_s + signals * 25, route))
        if not candidates:
            return [fastest.model_copy(update={"label_key": "route.fastest"})]
        _, _, preferred = min(candidates, key=lambda item: (item[0], item[1]))
        reduction = baseline_signals - (preferred.metrics.traffic_signals or 0)
        if preferred.id == fastest.id or reduction <= 0:
            return [
                fastest.model_copy(
                    update={
                        "label_key": "route.fastestAndFewestLights",
                        "fallback_reason": None,
                    }
                )
            ]
        material_reduction = reduction >= 2 or (
            baseline_signals > 0 and reduction / baseline_signals >= 0.2
        )
        if not material_reduction:
            return [
                fastest.model_copy(
                    update={
                        "label_key": "route.fastest",
                        "fallback_reason": "no_material_signal_reduction",
                    }
                )
            ]
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
    sampling_corridor: BaseGeometry | None = None,
) -> tuple[BaseGeometry, BaseGeometry, bool, float, float]:
    observer = Observer(latitude=coordinate.latitude, longitude=coordinate.longitude)
    sun_elevation = float(elevation(observer, when))
    sun_azimuth = float(azimuth(observer, when))
    if sun_elevation <= 0:
        empty = Polygon()
        return empty, empty, False, sun_azimuth, sun_elevation
    all_shadows = []
    high_shadows = []
    target_bounds = sampling_corridor.bounds if sampling_corridor is not None else None
    for building in buildings:
        length = min(250.0, building.height_m / math.tan(math.radians(sun_elevation)))
        direction = math.radians((sun_azimuth + 180) % 360)
        dx = length * math.sin(direction)
        dy = length * math.cos(direction)
        if target_bounds is not None and not _translated_bounds_overlap(
            building.footprint.bounds,
            dx,
            dy,
            target_bounds,
        ):
            continue
        shadow = _shadow_for_geometry(building.footprint, dx, dy)
        if shadow.is_empty or (
            sampling_corridor is not None and not sampling_corridor.intersects(shadow)
        ):
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
        polygons = [item for item in getattr(converted, "geoms", ()) if isinstance(item, Polygon)]
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


def _snapshot_shade_annotations(
    geometry: list[Coordinate],
    shadows: BaseGeometry,
    high_shadows: BaseGeometry,
    sun_up: bool,
) -> list[SegmentAnnotation]:
    annotations: list[SegmentAnnotation] = []
    for index, (first, second) in enumerate(pairwise(geometry)):
        distance = haversine_m(first, second)
        samples = _segment_samples(first, second, distance)
        shaded, _ = _sampled_shade_fractions(samples, shadows, high_shadows, sun_up)
        annotations.append(
            SegmentAnnotation(
                start_index=index,
                end_index=index + 1,
                classification=_shade_classification(shaded),
                shade_fraction=round(shaded, 4),
                confidence=DataConfidence.MEDIUM,
            )
        )
    return annotations


def _annotate_shade_time_dependent(
    route: RouteAlternative,
    buildings: tuple[Building, ...],
    cache: dict[tuple[datetime, float, float], tuple[BaseGeometry, BaseGeometry, bool]],
    *,
    observer_coordinate: Coordinate | None = None,
    sampling_corridor: BaseGeometry | None = None,
    building_groups: tuple[_BuildingHeightGroup, ...] | None = None,
) -> RouteAlternative:
    geometry = decode_polyline(route.encoded_polyline)
    segment_distances = [haversine_m(first, second) for first, second in pairwise(geometry)]
    route_distance = sum(segment_distances)
    if not geometry or route_distance <= 0:
        return route
    # All alternatives share the trip origin. Solar angles change by far less
    # than the source-data uncertainty across a metropolitan route, while a
    # shared observer lets alternatives reuse the same five-minute shadow
    # surfaces instead of rebuilding identical unions for every route.
    observer_coordinate = observer_coordinate or geometry[len(geometry) // 2]
    segment_samples = [
        _segment_samples(first, second, distance)
        for (first, second), distance in zip(pairwise(geometry), segment_distances, strict=True)
    ]
    segment_times: list[tuple[datetime, datetime, float]] = []
    elapsed_distance = 0.0
    for distance in segment_distances:
        midpoint_fraction = (elapsed_distance + distance / 2) / route_distance
        predicted_at = route.departure_at + timedelta(
            seconds=route.metrics.duration_s * midpoint_fraction
        )
        segment_times.append(_five_minute_bounds(predicted_at))
        elapsed_distance += distance

    shade_masks: dict[
        datetime,
        tuple[
            np.ndarray[Any, np.dtype[np.bool_]],
            np.ndarray[Any, np.dtype[np.bool_]],
        ],
    ] = {}
    sample_ranges: list[tuple[int, int]] = []
    if building_groups is not None:
        x_coordinates = np.concatenate(
            [np.asarray(samples[0], dtype=np.float64) for samples in segment_samples]
        )
        y_coordinates = np.concatenate(
            [np.asarray(samples[1], dtype=np.float64) for samples in segment_samples]
        )
        cursor = 0
        for samples in segment_samples:
            end = cursor + len(samples[0])
            sample_ranges.append((cursor, end))
            cursor = end
        for when in {value for bounds in segment_times for value in bounds[:2]}:
            shade_masks[when] = _building_shade_masks(
                x_coordinates,
                y_coordinates,
                building_groups,
                when,
                observer_coordinate,
            )

    annotations: list[SegmentAnnotation] = []
    shaded_distance = high_distance = total_distance = 0.0
    sun_exposure_seconds = 0.0
    for index, (distance, samples, time_bounds) in enumerate(
        zip(segment_distances, segment_samples, segment_times, strict=True)
    ):
        lower_at, upper_at, interpolation = time_bounds
        if building_groups is None:
            lower = _cached_shadow_union(
                cache,
                buildings,
                lower_at,
                observer_coordinate,
                sampling_corridor,
            )
            upper = _cached_shadow_union(
                cache,
                buildings,
                upper_at,
                observer_coordinate,
                sampling_corridor,
            )
            lower_shade, lower_high = _sampled_shade_fractions(samples, *lower)
            upper_shade, upper_high = _sampled_shade_fractions(samples, *upper)
        else:
            start, end = sample_ranges[index]
            lower_shade, lower_high = _mask_fractions(shade_masks[lower_at], start, end)
            upper_shade, upper_high = _mask_fractions(shade_masks[upper_at], start, end)
        shaded = lower_shade + (upper_shade - lower_shade) * interpolation
        high = lower_high + (upper_high - lower_high) * interpolation
        segment_duration = route.metrics.duration_s * distance / route_distance
        sun_exposure_seconds += segment_duration * (1 - shaded)
        shaded_distance += distance * shaded
        high_distance += distance * high
        total_distance += distance
        annotations.append(
            SegmentAnnotation(
                start_index=index,
                end_index=index + 1,
                classification=_shade_classification(shaded),
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
            "sun_exposure_minutes": round(sun_exposure_seconds / 60, 2),
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


def _five_minute_bounds(when: datetime) -> tuple[datetime, datetime, float]:
    lower = when.replace(minute=when.minute - when.minute % 5, second=0, microsecond=0)
    upper = lower + timedelta(minutes=5)
    interpolation = (when - lower).total_seconds() / 300
    return lower, upper, interpolation


def _cached_shadow_union(
    cache: dict[tuple[datetime, float, float], tuple[BaseGeometry, BaseGeometry, bool]],
    buildings: tuple[Building, ...],
    when: datetime,
    coordinate: Coordinate,
    sampling_corridor: BaseGeometry | None = None,
) -> tuple[BaseGeometry, BaseGeometry, bool]:
    key = (when, round(coordinate.latitude, 3), round(coordinate.longitude, 3))
    cached = cache.get(key)
    if cached is not None:
        return cached
    if sampling_corridor is None:
        shadows, high_shadows, sun_up, _, _ = _shadow_unions(buildings, when, coordinate)
    else:
        shadows, high_shadows, sun_up, _, _ = _shadow_unions(
            buildings,
            when,
            coordinate,
            sampling_corridor,
        )
    result = (shadows, high_shadows, sun_up)
    cache[key] = result
    return result


def _sampled_shade_fractions(
    samples: tuple[list[float], list[float]],
    shadows: BaseGeometry,
    high_shadows: BaseGeometry,
    sun_up: bool,
) -> tuple[float, float]:
    if not sun_up:
        return 1.0, 1.0
    x_coordinates, y_coordinates = samples
    sample_count = len(x_coordinates)
    return (
        float(intersects_xy(shadows, x_coordinates, y_coordinates).sum()) / sample_count,
        float(intersects_xy(high_shadows, x_coordinates, y_coordinates).sum()) / sample_count,
    )


def _building_height_groups(
    buildings: tuple[Building, ...],
) -> tuple[_BuildingHeightGroup, ...]:
    footprints_by_height: dict[float, list[BaseGeometry]] = {}
    high_footprints_by_height: dict[float, list[BaseGeometry]] = {}
    for building in buildings:
        footprints_by_height.setdefault(building.height_m, []).append(building.footprint)
        if building.confidence == DataConfidence.HIGH:
            high_footprints_by_height.setdefault(building.height_m, []).append(building.footprint)
    groups: list[_BuildingHeightGroup] = []
    for height_m, footprints in footprints_by_height.items():
        footprint_union = unary_union(footprints)
        high_union = (
            unary_union(high_footprints_by_height[height_m])
            if height_m in high_footprints_by_height
            else Polygon()
        )
        prepare(footprint_union)
        if not high_union.is_empty:
            prepare(high_union)
        groups.append(
            _BuildingHeightGroup(
                height_m=height_m,
                footprints=footprint_union,
                high_confidence_footprints=high_union,
            )
        )
    return tuple(groups)


def _building_shade_masks(
    x_coordinates: np.ndarray[Any, np.dtype[np.float64]],
    y_coordinates: np.ndarray[Any, np.dtype[np.float64]],
    groups: tuple[_BuildingHeightGroup, ...],
    when: datetime,
    coordinate: Coordinate,
) -> tuple[np.ndarray[Any, np.dtype[np.bool_]], np.ndarray[Any, np.dtype[np.bool_]]]:
    observer = Observer(latitude=coordinate.latitude, longitude=coordinate.longitude)
    sun_elevation = float(elevation(observer, when))
    shaded = np.zeros(len(x_coordinates), dtype=np.bool_)
    high_shaded = np.zeros(len(x_coordinates), dtype=np.bool_)
    if sun_elevation <= 0:
        shaded[:] = True
        high_shaded[:] = True
        return shaded, high_shaded
    direction = math.radians((float(azimuth(observer, when)) + 180) % 360)
    for group in groups:
        length = min(250.0, group.height_m / math.tan(math.radians(sun_elevation)))
        dx = length * math.sin(direction)
        dy = length * math.cos(direction)
        ray_coordinates = np.empty((len(x_coordinates), 2, 2), dtype=np.float64)
        ray_coordinates[:, 0, 0] = x_coordinates
        ray_coordinates[:, 0, 1] = y_coordinates
        ray_coordinates[:, 1, 0] = x_coordinates - dx
        ray_coordinates[:, 1, 1] = y_coordinates - dy
        rays = linestrings(ray_coordinates)
        outside = ~intersects_xy(group.footprints, x_coordinates, y_coordinates)
        shaded |= intersects(group.footprints, rays) & outside
        if not group.high_confidence_footprints.is_empty:
            high_outside = ~intersects_xy(
                group.high_confidence_footprints,
                x_coordinates,
                y_coordinates,
            )
            high_shaded |= intersects(group.high_confidence_footprints, rays) & high_outside
    return shaded, high_shaded


def _mask_fractions(
    masks: tuple[np.ndarray[Any, np.dtype[np.bool_]], np.ndarray[Any, np.dtype[np.bool_]]],
    start: int,
    end: int,
) -> tuple[float, float]:
    count = end - start
    return float(masks[0][start:end].sum()) / count, float(masks[1][start:end].sum()) / count


def _shade_classification(shaded: float) -> str:
    return "shade" if shaded >= 0.75 else "mixed" if shaded >= 0.25 else "sun"


def _annotate_signals(route: RouteAlternative, signals: tuple[Point, ...]) -> RouteAlternative:
    geometry = decode_polyline(route.encoded_polyline)
    line = LineString(
        [_WGS84_TO_ITM.transform(point.longitude, point.latitude) for point in geometry]
    )
    count = sum(line.distance(signal) <= 18 for signal in signals)
    return route.model_copy(
        update={"metrics": route.metrics.model_copy(update={"traffic_signals": count})}
    )


def _segment_samples(
    first: Coordinate,
    second: Coordinate,
    distance_m: float,
) -> tuple[list[float], list[float]]:
    count = max(1, math.ceil(distance_m / 5))
    x_coordinates: list[float] = []
    y_coordinates: list[float] = []
    for index in range(count + 1):
        fraction = index / count
        longitude = first.longitude + (second.longitude - first.longitude) * fraction
        latitude = first.latitude + (second.latitude - first.latitude) * fraction
        x, y = _WGS84_TO_ITM.transform(longitude, latitude)
        x_coordinates.append(x)
        y_coordinates.append(y)
    return x_coordinates, y_coordinates


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


def _route_sampling_corridor(routes: list[RouteAlternative]) -> BaseGeometry:
    lines = []
    for route in routes:
        coordinates = [
            _WGS84_TO_ITM.transform(point.longitude, point.latitude)
            for point in decode_polyline(route.encoded_polyline)
        ]
        if len(coordinates) >= 2:
            lines.append(LineString(coordinates))
    if not lines:
        raise ValueError("Shade sampling requires at least one valid route")
    # Six metres covers encoded-geometry rounding, opposite sidewalk sides and
    # the positional uncertainty of OSM building footprints without retaining
    # shadows that cannot affect any displayed alternative.
    return unary_union(lines).buffer(6)


def _translated_bounds_overlap(
    source: tuple[float, float, float, float],
    dx: float,
    dy: float,
    target: tuple[float, float, float, float],
) -> bool:
    source_min_x, source_min_y, source_max_x, source_max_y = source
    shadow_min_x = min(source_min_x, source_min_x + dx)
    shadow_min_y = min(source_min_y, source_min_y + dy)
    shadow_max_x = max(source_max_x, source_max_x + dx)
    shadow_max_y = max(source_max_y, source_max_y + dy)
    target_min_x, target_min_y, target_max_x, target_max_y = target
    return not (
        shadow_max_x < target_min_x
        or shadow_min_x > target_max_x
        or shadow_max_y < target_min_y
        or shadow_min_y > target_max_y
    )


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


def _feature_unavailable_reason(feature: str, context: OsmRouteContext) -> tuple[str, str]:
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


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
