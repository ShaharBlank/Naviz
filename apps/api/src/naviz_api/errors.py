from __future__ import annotations


class NavizError(Exception):
    def __init__(self, detail: str, *, code: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


class OutsideCoverageError(NavizError):
    def __init__(self) -> None:
        super().__init__(
            "Naviz currently routes within the Tel Aviv metropolitan coverage area.",
            code="outside_coverage",
            status_code=422,
        )


class RoutingUnavailableError(NavizError):
    def __init__(self) -> None:
        super().__init__(
            "Routing is temporarily unavailable. Please try again shortly.",
            code="routing_unavailable",
            status_code=503,
        )


class NoRouteError(NavizError):
    def __init__(self) -> None:
        super().__init__(
            "No route was found for the selected mode and preferences.",
            code="no_route",
            status_code=404,
        )
