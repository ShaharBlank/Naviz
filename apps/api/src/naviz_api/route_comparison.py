from __future__ import annotations

from .models import RouteAlternative, RoutePreference


def transit_comparison_routes(
    routes: list[RouteAlternative], preference: RoutePreference
) -> list[RouteAlternative]:
    """Return the distinct fastest and fewest-transfer choices in preference order."""
    if not routes:
        return []
    fastest = min(routes, key=lambda route: route.metrics.duration_s)
    fewest_transfers = min(
        routes,
        key=lambda route: (route.metrics.transfers, route.metrics.duration_s),
    )
    if fastest.encoded_polyline == fewest_transfers.encoded_polyline:
        return [fastest.model_copy(update={"label_key": "route.fastestFewestTransfers"})]
    fastest = fastest.model_copy(update={"label_key": "route.fastest"})
    fewest_transfers = fewest_transfers.model_copy(update={"label_key": "route.fewerTransfers"})
    if preference == RoutePreference.FEWER_TRANSFERS:
        return [fewest_transfers, fastest]
    return [fastest, fewest_transfers]
