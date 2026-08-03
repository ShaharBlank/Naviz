from naviz_api.matching import LocationFix, RouteMatcher
from naviz_api.models import Coordinate


def test_hysteresis_requires_three_off_route_fixes() -> None:
    route = [
        Coordinate(latitude=32.0733, longitude=34.7799),
        Coordinate(latitude=32.0776, longitude=34.7749),
        Coordinate(latitude=32.0819, longitude=34.7806),
    ]
    matcher = RouteMatcher(route)
    far = LocationFix(
        coordinate=Coordinate(latitude=32.10, longitude=34.82),
        accuracy_m=5,
        heading_degrees=0,
    )
    assert matcher.update([far]).off_route is False
    assert matcher.update([far]).off_route is False
    assert matcher.update([far]).off_route is True


def test_progress_does_not_jump_backwards() -> None:
    route = [
        Coordinate(latitude=32.0733, longitude=34.7799),
        Coordinate(latitude=32.0776, longitude=34.7749),
        Coordinate(latitude=32.0819, longitude=34.7806),
    ]
    matcher = RouteMatcher(route)
    result = matcher.update([LocationFix(route[1], accuracy_m=5)])
    assert result.geometry_index >= 1
