from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast

from .config import Settings
from .demo_data import DEMO_BUNDLE_DATE, build_demo_graph, demo_places, demo_transit
from .engine_adapters import TransitousAdapter, ValhallaAdapter
from .identity import IdentityRepository, InMemoryIdentityRepository, TokenVerifier
from .identity_sql import SqlAlchemyIdentityRepository
from .live_routing import AsyncRoutePlanner, LiveRoutePlanner
from .live_search import CoverageArea, PhotonPlaceSearch
from .mobility import GbfsFeed, MobilityService
from .models import (
    Coordinate,
    DataStatus,
    Locale,
    Place,
    RoutePlanRequest,
    RoutePlanResponse,
    TravelMode,
)
from .route_features import (
    OverpassRouteContext,
    RouteContextPort,
    RouteFeatureAnalyzer,
    SqliteOsmRouteContext,
)
from .routing import StreetRouter
from .search import PlaceIndex
from .transit import RangeRaptor

TRANSIT_MODES = {
    TravelMode.TRANSIT,
    TravelMode.BIKE_TRANSIT,
    TravelMode.SCOOTER_TRANSIT,
    TravelMode.RENTAL_TRANSIT,
}


class SearchPort(Protocol):
    data_version: str

    async def search(
        self,
        query: str,
        *,
        language: Locale,
        proximity: Coordinate | None = None,
        limit: int = 8,
        category: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Place]: ...

    async def reverse(self, coordinate: Coordinate, *, language: Locale) -> Place | None: ...


class LocalPlaceSearch:
    def __init__(self, index: PlaceIndex) -> None:
        self._index = index
        self.data_version = index.data_version

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
        del language
        return self._index.search(
            query,
            proximity=proximity,
            limit=limit,
            category=category,
            bbox=bbox,
        )

    async def reverse(self, coordinate: Coordinate, *, language: Locale) -> Place | None:
        del language
        return self._index.reverse(coordinate)


class CompactRoutePlanner:
    def __init__(
        self,
        street: StreetRouter,
        transit: RangeRaptor,
        data_version: str,
        route_ttl_seconds: int,
    ) -> None:
        self._street = street
        self._transit = transit
        self._data_version = data_version
        self._ttl = route_ttl_seconds

    async def plan(self, request: RoutePlanRequest, request_id: str) -> RoutePlanResponse:
        routes = (
            self._transit.plan(request, self._ttl)
            if request.mode in TRANSIT_MODES
            else self._street.plan(request, self._ttl)
        )
        return RoutePlanResponse(
            request_id=request_id,
            routes=routes,
            data_version=self._data_version,
            engine_profile="compact",
        )


@dataclass(slots=True)
class Services:
    settings: Settings
    search: SearchPort
    routes: AsyncRoutePlanner
    mobility: MobilityService
    identity: IdentityRepository
    tokens: TokenVerifier
    started_at: datetime

    def status(self) -> DataStatus:
        if self.settings.live_providers:
            return DataStatus(
                coverage=(
                    "Tel Aviv metropolitan area: Tel Aviv-Yafo, Ramat Gan, Givatayim, "
                    "Bnei Brak, Bat Yam, Holon, and nearby corridors"
                ),
                data_version=self.settings.data_bundle,
                engine_profile="regional-live",
                warmed=True,
                updated_at=self.started_at,
                feeds={
                    "osm": {"status": "online", "realtime": False},
                    "gtfs": {"status": "scheduled", "realtime": False},
                    "siri": {"status": "not_configured", "realtime": False},
                    "gbfs": {
                        "status": "configured" if self.settings.gbfs_feeds else "not_configured",
                        "realtime": bool(self.settings.gbfs_feeds),
                    },
                },
            )
        return DataStatus(
            coverage="Tel Aviv-Yafo test fixture",
            data_version=self.settings.data_bundle,
            engine_profile="compact",
            warmed=True,
            updated_at=datetime.combine(DEMO_BUNDLE_DATE, datetime.min.time(), tzinfo=UTC),
            feeds={
                "osm": {"status": "test_fixture", "realtime": False},
                "gtfs": {"status": "scheduled_fixture", "realtime": False},
                "siri": {"status": "not_configured", "realtime": False},
                "gbfs": {
                    "status": "configured" if self.settings.gbfs_feeds else "not_configured",
                    "realtime": bool(self.settings.gbfs_feeds),
                },
            },
        )


def build_services(settings: Settings) -> Services:
    feeds = tuple(_parse_feed(value) for value in settings.gbfs_feeds)
    identity: IdentityRepository = (
        SqlAlchemyIdentityRepository(settings.database_url)
        if settings.database_url
        else InMemoryIdentityRepository()
    )
    search: SearchPort
    routes: AsyncRoutePlanner
    if settings.live_providers:
        if (
            not settings.valhalla_url
            or not settings.transitous_url
            or not settings.photon_url
            or (not settings.overpass_url and not settings.feature_bundle_path)
        ):
            raise ValueError(
                "Live providers require NAVIZ_VALHALLA_URL, NAVIZ_TRANSITOUS_URL, "
                "NAVIZ_PHOTON_URL, and either NAVIZ_FEATURE_BUNDLE_PATH or "
                "NAVIZ_OVERPASS_URL"
            )
        coverage = CoverageArea.from_tuple(settings.coverage_bbox)
        user_agent = f"Naviz/0.2 ({settings.provider_contact})"
        search = cast(
            SearchPort,
            PhotonPlaceSearch(
                settings.photon_url,
                coverage,
                data_version=settings.data_bundle,
                user_agent=user_agent,
                cache_seconds=settings.provider_cache_seconds,
            ),
        )
        feature_context: RouteContextPort
        if settings.feature_bundle_path:
            feature_context = SqliteOsmRouteContext(settings.feature_bundle_path)
        else:
            feature_context = OverpassRouteContext(
                cast(str, settings.overpass_url),
                user_agent=user_agent,
                cache_seconds=max(settings.provider_cache_seconds, 1_800),
            )
        routes = LiveRoutePlanner(
            ValhallaAdapter(settings.valhalla_url, user_agent=user_agent),
            TransitousAdapter(settings.transitous_url, user_agent=user_agent),
            coverage,
            data_version=settings.data_bundle,
            route_ttl_seconds=settings.route_ttl_seconds,
            cache_seconds=settings.provider_cache_seconds,
            feature_analyzer=RouteFeatureAnalyzer(feature_context),
        )
    else:
        graph = build_demo_graph()
        street = StreetRouter(graph, settings.data_bundle)
        stops, trips = demo_transit()
        transit = RangeRaptor(stops, trips, street, settings.data_bundle)
        search = LocalPlaceSearch(PlaceIndex(demo_places(), settings.data_bundle))
        routes = CompactRoutePlanner(
            street,
            transit,
            settings.data_bundle,
            settings.route_ttl_seconds,
        )
    return Services(
        settings=settings,
        search=search,
        routes=routes,
        mobility=MobilityService(
            feeds,
            ttl_seconds=settings.gbfs_ttl_seconds,
            stale_seconds=settings.gbfs_stale_seconds,
        ),
        identity=identity,
        tokens=TokenVerifier(
            settings.auth_issuer,
            settings.auth_audience,
            development=not settings.is_production,
        ),
        started_at=datetime.now(UTC),
    )


def _parse_feed(value: str) -> GbfsFeed:
    parts = value.split("|", 2)
    if len(parts) < 2:
        raise ValueError("GBFS feed must use provider|discovery_url[|deep_link]")
    return GbfsFeed(parts[0], parts[1], parts[2] if len(parts) == 3 else None)
