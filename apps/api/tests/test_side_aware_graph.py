from naviz_api.graph import CompactGraph, GraphEdge, GraphNode
from naviz_api.models import Coordinate, DataConfidence, TravelMode, VehicleProfile

WALK = frozenset({TravelMode.WALK})


def test_side_switch_is_blocked_without_a_crossing() -> None:
    graph = CompactGraph(
        nodes=_nodes(3),
        edges=(
            _edge(1, 0, 1, selected_side="left", distance=1),
            _edge(2, 1, 2, selected_side="right", distance=1),
            _edge(3, 1, 2, selected_side="left", distance=10),
        ),
    )
    path = graph.shortest_path(
        graph.nodes[0].coordinate,
        graph.nodes[2].coordinate,
        TravelMode.WALK,
        VehicleProfile(),
        edge_cost=lambda edge, elapsed: (edge.distance_m, edge.distance_m, 0),
        maximum_speed_mps=1,
    )
    assert [edge.id for edge in path.edges] == [1, 3]


def test_mapped_crossing_resets_side_context() -> None:
    graph = CompactGraph(
        nodes=_nodes(4),
        edges=(
            _edge(1, 0, 1, selected_side="left", distance=1),
            _edge(2, 1, 2, crossing="marked", distance=1),
            _edge(3, 2, 3, selected_side="right", distance=1),
        ),
    )
    path = graph.shortest_path(
        graph.nodes[0].coordinate,
        graph.nodes[3].coordinate,
        TravelMode.WALK,
        VehicleProfile(),
        edge_cost=lambda edge, elapsed: (edge.distance_m, edge.distance_m, 0),
        maximum_speed_mps=1,
    )
    assert [edge.id for edge in path.edges] == [1, 2, 3]


def _nodes(count: int) -> dict[int, GraphNode]:
    return {
        index: GraphNode(
            index,
            Coordinate(latitude=32.07, longitude=34.77 + index * 0.00001),
        )
        for index in range(count)
    }


def _edge(
    edge_id: int,
    source: int,
    target: int,
    *,
    distance: float,
    selected_side: str | None = None,
    crossing: str | None = None,
) -> GraphEdge:
    nodes = _nodes(max(source, target) + 1)
    return GraphEdge(
        id=edge_id,
        source=source,
        target=target,
        geometry=(nodes[source].coordinate, nodes[target].coordinate),
        distance_m=distance,
        name="Test",
        modes=WALK,
        selected_side=selected_side,
        crossing_kind=crossing,
        crossing_confidence=DataConfidence.HIGH,
    )
