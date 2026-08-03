from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .config import Settings
from .demo_data import DEMO_BUNDLE_DATE, build_demo_graph, demo_places, demo_transit
from .identity import IdentityRepository, InMemoryIdentityRepository, TokenVerifier
from .identity_sql import SqlAlchemyIdentityRepository
from .mobility import GbfsFeed, MobilityService
from .models import DataStatus, RoutePlanRequest, RoutePlanResponse, TravelMode
from .routing import StreetRouter
from .search import PlaceIndex
from .transit import RangeRaptor

TRANSIT_MODES = {
    TravelMode.TRANSIT,
    TravelMode.BIKE_TRANSIT,
    TravelMode.SCOOTER_TRANSIT,
    TravelMode.RENTAL_TRANSIT,
}


class RoutePlanner:
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

    def plan(self, request: RoutePlanRequest, request_id: str) -> RoutePlanResponse:
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
    search: PlaceIndex
    routes: RoutePlanner
    mobility: MobilityService
    identity: IdentityRepository
    tokens: TokenVerifier
    started_at: datetime

    def status(self) -> DataStatus:
        return DataStatus(
            coverage="Tel Aviv-Yafo demo fixture; production target is municipality + 5 km buffer",
            data_version=self.settings.data_bundle,
            engine_profile="compact",
            warmed=True,
            updated_at=datetime.combine(DEMO_BUNDLE_DATE, datetime.min.time(), tzinfo=UTC),
            feeds={
                "osm": {"status": "demo", "realtime": False},
                "gtfs": {"status": "scheduled-demo", "realtime": False},
                "siri": {"status": "not_configured", "realtime": False},
                "gbfs": {
                    "status": "configured" if self.settings.gbfs_feeds else "demo",
                    "realtime": bool(self.settings.gbfs_feeds),
                },
            },
        )


def build_services(settings: Settings) -> Services:
    graph = build_demo_graph()
    street = StreetRouter(graph, settings.data_bundle)
    stops, trips = demo_transit()
    transit = RangeRaptor(stops, trips, street, settings.data_bundle)
    feeds = tuple(_parse_feed(value) for value in settings.gbfs_feeds)
    identity: IdentityRepository = (
        SqlAlchemyIdentityRepository(settings.database_url)
        if settings.database_url
        else InMemoryIdentityRepository()
    )
    return Services(
        settings=settings,
        search=PlaceIndex(demo_places(), settings.data_bundle),
        routes=RoutePlanner(street, transit, settings.data_bundle, settings.route_ttl_seconds),
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
