from __future__ import annotations

from array import array
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from heapq import heappop, heappush
from itertools import count
from math import inf

from .geometry import haversine_m
from .models import Coordinate, DataConfidence, TravelMode, VehicleProfile
from .shade_profiles import interpolate_daily_bins


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: int
    coordinate: Coordinate
    name: str = ""


@dataclass(frozen=True, slots=True)
class GraphEdge:
    id: int
    source: int
    target: int
    geometry: tuple[Coordinate, ...]
    distance_m: float
    name: str
    modes: frozenset[TravelMode]
    shade_profile: tuple[float, ...] = ()
    shade_confidence: DataConfidence = DataConfidence.UNKNOWN
    selected_side: str | None = None
    crossing_kind: str | None = None
    crossing_confidence: DataConfidence = DataConfidence.UNKNOWN
    traffic_signal_id: str | None = None
    bicycle_comfort: float = 0.5
    max_height_m: float | None = None
    max_width_m: float | None = None
    max_weight_t: float | None = None

    def shade_fraction(self, at: datetime) -> float:
        return interpolate_daily_bins(self.shade_profile, at)


@dataclass(frozen=True, slots=True)
class PathResult:
    node_ids: tuple[int, ...]
    edges: tuple[GraphEdge, ...]
    distance_m: float
    duration_s: float
    weighted_cost: float
    sun_exposure_s: float
    signal_ids: frozenset[str]

    @property
    def geometry(self) -> list[Coordinate]:
        result: list[Coordinate] = []
        for edge in self.edges:
            if not result:
                result.extend(edge.geometry)
            else:
                result.extend(edge.geometry[1:])
        return result


EdgeCost = Callable[[GraphEdge, float], tuple[float, float, float]]


@dataclass(slots=True)
class CompactGraph:
    nodes: Mapping[int, GraphNode]
    edges: tuple[GraphEdge, ...]
    _node_ids: tuple[int, ...] = field(init=False, repr=False)
    _index_by_node: dict[int, int] = field(init=False, repr=False)
    _offsets: array[int] = field(init=False, repr=False)
    _edge_indices: array[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._node_ids = tuple(sorted(self.nodes))
        self._index_by_node = {node_id: index for index, node_id in enumerate(self._node_ids)}
        grouped: dict[int, list[int]] = {node_id: [] for node_id in self._node_ids}
        for edge_index, edge in enumerate(self.edges):
            if edge.source not in grouped or edge.target not in self.nodes:
                raise ValueError(f"Edge {edge.id} references an unknown node")
            grouped[edge.source].append(edge_index)
        offsets = array("I", [0])
        edge_indices = array("I")
        for node_id in self._node_ids:
            edge_indices.extend(grouped[node_id])
            offsets.append(len(edge_indices))
        self._offsets = offsets
        self._edge_indices = edge_indices

    def outgoing(self, node_id: int) -> Iterable[GraphEdge]:
        index = self._index_by_node[node_id]
        for cursor in range(self._offsets[index], self._offsets[index + 1]):
            yield self.edges[self._edge_indices[cursor]]

    def nearest_node(self, coordinate: Coordinate, mode: TravelMode) -> GraphNode:
        eligible = {edge.source for edge in self.edges if mode in edge.modes} | {
            edge.target for edge in self.edges if mode in edge.modes
        }
        if not eligible:
            raise ValueError(f"No graph coverage for {mode}")
        return min(
            (self.nodes[node_id] for node_id in eligible),
            key=lambda node: haversine_m(coordinate, node.coordinate),
        )

    def shortest_path(
        self,
        origin: Coordinate,
        destination: Coordinate,
        mode: TravelMode,
        vehicle: VehicleProfile,
        edge_cost: EdgeCost,
        maximum_speed_mps: float,
        forbidden_edges: frozenset[int] = frozenset(),
        allow_low_confidence_crossings: bool = False,
    ) -> PathResult:
        start = self.nearest_node(origin, mode).id
        goal = self.nearest_node(destination, mode).id
        start_state = (start, "center")
        sequence = count()
        queue: list[tuple[float, int, tuple[int, str]]] = []
        heappush(queue, (0.0, next(sequence), start_state))
        best: dict[tuple[int, str], float] = {start_state: 0.0}
        elapsed: dict[tuple[int, str], float] = {start_state: 0.0}
        sun: dict[tuple[int, str], float] = {start_state: 0.0}
        previous: dict[tuple[int, str], tuple[tuple[int, str], GraphEdge]] = {}
        goal_state: tuple[int, str] | None = None

        while queue:
            _, _, state = heappop(queue)
            node_id, side = state
            if node_id == goal:
                goal_state = state
                break
            current_cost = best[state]
            current_elapsed = elapsed[state]
            for edge in self.outgoing(node_id):
                if edge.id in forbidden_edges or mode not in edge.modes:
                    continue
                if not self._vehicle_allowed(edge, vehicle):
                    continue
                if (
                    edge.crossing_kind
                    and edge.crossing_confidence == DataConfidence.LOW
                    and not allow_low_confidence_crossings
                ):
                    continue
                next_side = self._side_transition(side, edge, mode)
                if next_side is None:
                    continue
                next_state = (edge.target, next_side)
                incremental_cost, duration_s, sun_exposure_s = edge_cost(edge, current_elapsed)
                candidate = current_cost + incremental_cost
                if candidate >= best.get(next_state, inf):
                    continue
                best[next_state] = candidate
                elapsed[next_state] = current_elapsed + duration_s
                sun[next_state] = sun[state] + sun_exposure_s
                previous[next_state] = (state, edge)
                heuristic = (
                    haversine_m(self.nodes[edge.target].coordinate, self.nodes[goal].coordinate)
                    / maximum_speed_mps
                )
                heappush(queue, (candidate + heuristic, next(sequence), next_state))

        if goal_state is None:
            raise NoPathError(start, goal, mode)
        edge_path: list[GraphEdge] = []
        node_path = [goal]
        cursor = goal_state
        while cursor != start_state:
            prior, edge = previous[cursor]
            edge_path.append(edge)
            node_path.append(prior[0])
            cursor = prior
        edge_path.reverse()
        node_path.reverse()
        signals = frozenset(edge.traffic_signal_id for edge in edge_path if edge.traffic_signal_id)
        return PathResult(
            node_ids=tuple(node_path),
            edges=tuple(edge_path),
            distance_m=sum(edge.distance_m for edge in edge_path),
            duration_s=elapsed[goal_state],
            weighted_cost=best[goal_state],
            sun_exposure_s=sun[goal_state],
            signal_ids=signals,
        )

    @staticmethod
    def _vehicle_allowed(edge: GraphEdge, vehicle: VehicleProfile) -> bool:
        if vehicle.height_m and edge.max_height_m and vehicle.height_m > edge.max_height_m:
            return False
        if vehicle.width_m and edge.max_width_m and vehicle.width_m > edge.max_width_m:
            return False
        return not (vehicle.weight_t and edge.max_weight_t and vehicle.weight_t > edge.max_weight_t)

    @staticmethod
    def _side_transition(current: str, edge: GraphEdge, mode: TravelMode) -> str | None:
        if mode != TravelMode.WALK:
            return "center"
        if edge.crossing_kind:
            return "center"
        edge_side = edge.selected_side if edge.selected_side in {"left", "right"} else None
        if edge_side is None:
            # Preserve side context through centerline sidewalks/footways. This prevents
            # an unmapped side switch from being hidden inside an ordinary center edge.
            return current
        if current in {"left", "right"} and current != edge_side:
            return None
        return edge_side


class NoPathError(ValueError):
    def __init__(self, start: int, goal: int, mode: TravelMode) -> None:
        super().__init__(f"No {mode.value} path from node {start} to {goal}")
        self.start = start
        self.goal = goal
        self.mode = mode
