from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .geometry import haversine_m
from .graph import CompactGraph, GraphEdge, GraphNode
from .models import Coordinate, DataConfidence, Place, TravelMode, VehicleKind

TEL_AVIV_TZ = ZoneInfo("Asia/Jerusalem")


ALL_STREET_MODES = frozenset(
    {
        TravelMode.WALK,
        TravelMode.BIKE,
        TravelMode.SCOOTER,
        TravelMode.CAR,
        TravelMode.MOTORCYCLE,
        TravelMode.TRUCK,
    }
)
ACTIVE_MODES = frozenset({TravelMode.WALK, TravelMode.BIKE, TravelMode.SCOOTER})


@dataclass(frozen=True, slots=True)
class TransitStop:
    id: str
    name: str
    name_he: str
    coordinate: Coordinate
    step_free: bool = True


@dataclass(frozen=True, slots=True)
class StopTime:
    stop_id: str
    arrival_offset_s: int
    departure_offset_s: int


@dataclass(frozen=True, slots=True)
class ScheduledTrip:
    id: str
    route_id: str
    route_short_name: str
    agency: str
    headsign: str
    first_departure: time
    frequency_s: int
    stop_times: tuple[StopTime, ...]
    allowed_vehicles: frozenset[VehicleKind]
    policy_source: str

    def next_start(self, after: datetime) -> datetime | None:
        service_start = datetime.combine(after.date(), self.first_departure, TEL_AVIV_TZ)
        if after <= service_start:
            return service_start
        elapsed = (after - service_start).total_seconds()
        run = int((elapsed + self.frequency_s - 1) // self.frequency_s)
        candidate = service_start + timedelta(seconds=run * self.frequency_s)
        final = datetime.combine(after.date(), time(23, 30), TEL_AVIV_TZ)
        return candidate if candidate <= final else None


def _shade_profile(daylight_shade: float) -> tuple[float, ...]:
    return tuple(
        1.0 if (slot * 5) // 60 < 6 or (slot * 5) // 60 >= 19 else daylight_shade
        for slot in range(288)
    )


def build_demo_graph() -> CompactGraph:
    nodes = {
        1: GraphNode(1, Coordinate(latitude=32.0733, longitude=34.7799), "Habima"),
        2: GraphNode(2, Coordinate(latitude=32.0776, longitude=34.7749), "Dizengoff"),
        3: GraphNode(3, Coordinate(latitude=32.0819, longitude=34.7806), "Rabin"),
        4: GraphNode(4, Coordinate(latitude=32.0740, longitude=34.7925), "Azrieli"),
        5: GraphNode(5, Coordinate(latitude=32.0718, longitude=34.7857), "Sarona"),
        6: GraphNode(6, Coordinate(latitude=32.0832, longitude=34.7957), "Savidor"),
        7: GraphNode(7, Coordinate(latitude=32.0791, longitude=34.7682), "Gordon Beach"),
        8: GraphNode(8, Coordinate(latitude=32.0680, longitude=34.7695), "Carmel Market"),
        9: GraphNode(9, Coordinate(latitude=32.0864, longitude=34.7827), "Kikar HaMedina"),
    }
    edges: list[GraphEdge] = []
    edge_id = 1

    def connect(
        source: int,
        target: int,
        name: str,
        *,
        modes: frozenset[TravelMode] = ALL_STREET_MODES,
        shade: float = 0.25,
        signal: str | None = None,
        side: str | None = "right",
        crossing: str | None = None,
        crossing_confidence: DataConfidence = DataConfidence.HIGH,
        comfort: float = 0.6,
        truck_height: float | None = None,
    ) -> None:
        nonlocal edge_id
        a, b = nodes[source].coordinate, nodes[target].coordinate
        distance = haversine_m(a, b) * 1.08
        for left, right, selected_side in (
            (source, target, side),
            (target, source, "left" if side == "right" else side),
        ):
            geometry = (nodes[left].coordinate, nodes[right].coordinate)
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=left,
                    target=right,
                    geometry=geometry,
                    distance_m=distance,
                    name=name,
                    modes=modes,
                    shade_profile=_shade_profile(shade),
                    shade_confidence=DataConfidence.HIGH,
                    selected_side=selected_side,
                    crossing_kind=crossing,
                    crossing_confidence=crossing_confidence,
                    traffic_signal_id=signal,
                    bicycle_comfort=comfort,
                    max_height_m=truck_height,
                )
            )
            edge_id += 1

    connect(1, 2, "Dizengoff Street", shade=0.78, signal="dizengoff-habima")
    connect(2, 3, "Frishman Street", shade=0.62, signal="frishman-rabin")
    connect(3, 6, "Namir Road", shade=0.18, signal="namir-1", comfort=0.35)
    connect(6, 4, "Menachem Begin Road", shade=0.12, signal="begin-1", comfort=0.3)
    connect(4, 5, "Kaplan Street", shade=0.34, signal="kaplan-1")
    connect(5, 1, "Rothschild Boulevard", shade=0.86, comfort=0.9)
    connect(2, 7, "Gordon Street", shade=0.2, signal="gordon-1")
    connect(7, 8, "Herbert Samuel Promenade", shade=0.05, comfort=0.85)
    connect(8, 1, "Allenby Street", shade=0.72, signal="allenby-1")
    connect(3, 9, "Weizmann Street", shade=0.54, signal="weizmann-1")
    connect(9, 6, "Arlozorov Street", shade=0.4, signal="arlozorov-1")
    connect(2, 5, "King George Street", shade=0.25, signal="king-george-1")
    connect(3, 5, "Ibn Gabirol Street", shade=0.3, signal="gabirol-1")
    connect(
        1,
        7,
        "Shaded pedestrian passage",
        modes=ACTIVE_MODES,
        shade=0.95,
        crossing="marked_crossing",
        comfort=0.95,
    )
    connect(
        5,
        8,
        "Market pedestrian route",
        modes=ACTIVE_MODES,
        shade=0.8,
        crossing="mapped_crossing",
        comfort=0.9,
    )
    return CompactGraph(nodes=nodes, edges=tuple(edges))


def demo_places() -> list[Place]:
    return [
        Place(
            id="osm:place:habima",
            name="Habima Square",
            name_he="כיכר הבימה",
            subtitle="Tarsat Boulevard, Tel Aviv-Yafo",
            coordinate=Coordinate(latitude=32.0733, longitude=34.7799),
            category="landmark",
        ),
        Place(
            id="osm:place:rabin",
            name="Rabin Square",
            name_he="כיכר רבין",
            subtitle="Ibn Gabirol Street, Tel Aviv-Yafo",
            coordinate=Coordinate(latitude=32.0819, longitude=34.7806),
            category="landmark",
        ),
        Place(
            id="osm:place:azrieli",
            name="Azrieli Center",
            name_he="מרכז עזריאלי",
            subtitle="Menachem Begin Road, Tel Aviv-Yafo",
            coordinate=Coordinate(latitude=32.0740, longitude=34.7925),
            category="shopping",
        ),
        Place(
            id="osm:place:savidor",
            name="Tel Aviv Savidor Center",
            name_he="תל אביב סבידור מרכז",
            subtitle="Railway and bus terminal",
            coordinate=Coordinate(latitude=32.0832, longitude=34.7957),
            category="transit",
        ),
        Place(
            id="osm:place:gordon",
            name="Gordon Beach",
            name_he="חוף גורדון",
            subtitle="Herbert Samuel Promenade",
            coordinate=Coordinate(latitude=32.0791, longitude=34.7682),
            category="beach",
        ),
        Place(
            id="osm:place:carmel",
            name="Carmel Market",
            name_he="שוק הכרמל",
            subtitle="HaCarmel Street, Tel Aviv-Yafo",
            coordinate=Coordinate(latitude=32.0680, longitude=34.7695),
            category="market",
        ),
    ]


def demo_transit() -> tuple[dict[str, TransitStop], tuple[ScheduledTrip, ...]]:
    stops = {
        "habima": TransitStop(
            "habima", "Habima", "הבימה", Coordinate(latitude=32.0733, longitude=34.7799)
        ),
        "rabin": TransitStop(
            "rabin", "Rabin Square", "כיכר רבין", Coordinate(latitude=32.0819, longitude=34.7806)
        ),
        "savidor": TransitStop(
            "savidor",
            "Savidor Center",
            "סבידור מרכז",
            Coordinate(latitude=32.0832, longitude=34.7957),
        ),
        "azrieli": TransitStop(
            "azrieli", "Azrieli", "עזריאלי", Coordinate(latitude=32.0740, longitude=34.7925)
        ),
    }
    trips = (
        ScheduledTrip(
            id="demo-18",
            route_id="18",
            route_short_name="18",
            agency="Naviz Demo Transit",
            headsign="Savidor Center",
            first_departure=time(5, 30),
            frequency_s=600,
            stop_times=(
                StopTime("habima", 0, 0),
                StopTime("rabin", 360, 390),
                StopTime("savidor", 840, 840),
            ),
            allowed_vehicles=frozenset({VehicleKind.FOLDING_BIKE, VehicleKind.PERSONAL_SCOOTER}),
            policy_source="demo-policy:folded-only",
        ),
        ScheduledTrip(
            id="demo-70",
            route_id="70",
            route_short_name="70",
            agency="Naviz Demo Transit",
            headsign="Azrieli",
            first_departure=time(5, 35),
            frequency_s=900,
            stop_times=(
                StopTime("savidor", 0, 0),
                StopTime("azrieli", 480, 480),
            ),
            allowed_vehicles=frozenset({VehicleKind.FOLDING_BIKE, VehicleKind.PERSONAL_SCOOTER}),
            policy_source="demo-policy:folded-only",
        ),
    )
    return stops, trips


DEMO_BUNDLE_DATE = date(2026, 8, 2)
