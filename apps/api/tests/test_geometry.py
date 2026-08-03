from naviz_api.geometry import decode_polyline, encode_polyline, haversine_m
from naviz_api.models import Coordinate


def test_polyline6_round_trip() -> None:
    points = [
        Coordinate(latitude=32.0733, longitude=34.7799),
        Coordinate(latitude=32.0819, longitude=34.7806),
    ]
    decoded = decode_polyline(encode_polyline(points))
    assert len(decoded) == 2
    assert haversine_m(points[0], decoded[0]) < 0.2
    assert haversine_m(points[1], decoded[1]) < 0.2
