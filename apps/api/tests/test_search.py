from naviz_api.demo_data import demo_places
from naviz_api.models import Coordinate
from naviz_api.search import PlaceIndex


def test_bilingual_prefix_search() -> None:
    index = PlaceIndex(demo_places(), "test")
    assert index.search("Hab")[0].id == "osm:place:habima"
    assert index.search("הבי")[0].id == "osm:place:habima"


def test_reverse_is_regional_and_bounded() -> None:
    index = PlaceIndex(demo_places(), "test")
    assert index.reverse(Coordinate(latitude=32.0733, longitude=34.7799)) is not None
    assert index.reverse(Coordinate(latitude=31.7, longitude=35.2)) is None


def test_search_applies_category_and_bbox_filters() -> None:
    index = PlaceIndex(demo_places(), "test")
    results = index.search(
        "",
        category="landmark,transit",
        bbox=(34.77, 32.06, 34.80, 32.09),
    )
    assert results
    assert all(place.category in {"landmark", "transit"} for place in results)
    assert all(34.77 <= place.coordinate.longitude <= 34.80 for place in results)
