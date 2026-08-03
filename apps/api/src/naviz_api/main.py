from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from . import __version__
from .config import get_settings
from .identity import AuthenticationError, Principal
from .models import (
    Coordinate,
    DataStatus,
    Favorite,
    FavoriteCreate,
    HistoryEntry,
    Locale,
    MobilityResponse,
    Place,
    ProblemDetail,
    RerouteRequest,
    RoutePlanRequest,
    RoutePlanResponse,
    SearchResponse,
    UserPreferences,
)
from .services import Services, build_services


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.services = build_services(get_settings())
    await app.state.services.identity.initialize()
    try:
        yield
    finally:
        await app.state.services.identity.close()


app = FastAPI(
    title="Naviz API",
    version=__version__,
    summary="Tel Aviv shaded, multimodal, and low-signal navigation",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Request validation failed",
        "validation_error",
        "; ".join(error["msg"] for error in exc.errors()),
    )


@app.exception_handler(AuthenticationError)
async def authentication_problem(request: Request, exc: AuthenticationError) -> JSONResponse:
    return _problem(request, 401, "Authentication failed", "authentication_failed", str(exc))


@app.exception_handler(ValueError)
async def domain_problem(request: Request, exc: ValueError) -> JSONResponse:
    return _problem(request, 400, "Unable to complete request", "domain_error", str(exc))


def get_services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


async def current_principal(
    services: Annotated[Services, Depends(get_services)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    return await services.tokens.verify(authorization)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/data/status", response_model=DataStatus, tags=["data"])
async def data_status(services: Annotated[Services, Depends(get_services)]) -> DataStatus:
    return services.status()


@app.get("/v1/search", response_model=SearchResponse, tags=["search"])
async def search(
    services: Annotated[Services, Depends(get_services)],
    q: Annotated[str, Query(min_length=0, max_length=120)] = "",
    language: Locale = Locale.HEBREW,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    category: str | None = None,
    bbox: str | None = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> SearchResponse:
    del language
    proximity = (
        Coordinate(latitude=latitude, longitude=longitude)
        if latitude is not None and longitude is not None
        else None
    )
    return SearchResponse(
        query=q,
        results=services.search.search(
            q,
            proximity=proximity,
            limit=limit,
            category=category,
            bbox=_parse_bbox(bbox) if bbox else None,
        ),
        data_version=services.search.data_version,
    )


@app.get("/v1/search/reverse", response_model=Place, tags=["search"])
async def reverse_search(
    services: Annotated[Services, Depends(get_services)],
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
) -> Place:
    place = services.search.reverse(Coordinate(latitude=latitude, longitude=longitude))
    if place is None:
        raise ValueError("No indexed place is close to this coordinate")
    return place


@app.post("/v1/routes/plan", response_model=RoutePlanResponse, tags=["routing"])
async def plan_route(
    payload: RoutePlanRequest,
    request: Request,
    services: Annotated[Services, Depends(get_services)],
) -> RoutePlanResponse:
    return services.routes.plan(payload, request.state.request_id)


@app.post("/v1/routes/reroute", response_model=RoutePlanResponse, tags=["routing"])
async def reroute(
    payload: RerouteRequest,
    request: Request,
    services: Annotated[Services, Depends(get_services)],
) -> RoutePlanResponse:
    return services.routes.plan(payload.to_plan_request(), request.state.request_id)


@app.get("/v1/mobility/vehicles", response_model=MobilityResponse, tags=["mobility"])
async def mobility_vehicles(
    services: Annotated[Services, Depends(get_services)],
    min_latitude: Annotated[float, Query(ge=-90, le=90)],
    min_longitude: Annotated[float, Query(ge=-180, le=180)],
    max_latitude: Annotated[float, Query(ge=-90, le=90)],
    max_longitude: Annotated[float, Query(ge=-180, le=180)],
) -> MobilityResponse:
    if min_latitude > max_latitude or min_longitude > max_longitude:
        raise ValueError("Bounding box minimums must not exceed maximums")
    return await services.mobility.nearby(
        minimum_latitude=min_latitude,
        minimum_longitude=min_longitude,
        maximum_latitude=max_latitude,
        maximum_longitude=max_longitude,
    )


@app.get("/v1/me/favorites", response_model=list[Favorite], tags=["account"])
async def list_favorites(
    principal: Annotated[Principal, Depends(current_principal)],
    services: Annotated[Services, Depends(get_services)],
) -> list[Favorite]:
    return await services.identity.favorites(principal.subject)


@app.post(
    "/v1/me/favorites",
    response_model=Favorite,
    status_code=status.HTTP_201_CREATED,
    tags=["account"],
)
async def save_favorite(
    payload: FavoriteCreate,
    principal: Annotated[Principal, Depends(current_principal)],
    services: Annotated[Services, Depends(get_services)],
) -> Favorite:
    return await services.identity.save_favorite(principal.subject, payload.label, payload.place)


@app.delete("/v1/me/favorites/{favorite_id}", status_code=204, tags=["account"])
async def delete_favorite(
    favorite_id: str,
    principal: Annotated[Principal, Depends(current_principal)],
    services: Annotated[Services, Depends(get_services)],
) -> Response:
    await services.identity.delete_favorite(principal.subject, favorite_id)
    return Response(status_code=204)


@app.get("/v1/me/preferences", response_model=UserPreferences, tags=["account"])
async def get_preferences(
    principal: Annotated[Principal, Depends(current_principal)],
    services: Annotated[Services, Depends(get_services)],
) -> UserPreferences:
    return await services.identity.preferences(principal.subject)


@app.put("/v1/me/preferences", response_model=UserPreferences, tags=["account"])
async def update_preferences(
    payload: UserPreferences,
    principal: Annotated[Principal, Depends(current_principal)],
    services: Annotated[Services, Depends(get_services)],
) -> UserPreferences:
    return await services.identity.save_preferences(principal.subject, payload)


@app.get("/v1/me/history", response_model=list[HistoryEntry], tags=["account"])
async def get_history(
    principal: Annotated[Principal, Depends(current_principal)],
    services: Annotated[Services, Depends(get_services)],
) -> list[HistoryEntry]:
    return await services.identity.history(principal.subject)


def _problem(
    request: Request,
    status_code: int,
    title: str,
    code: str,
    detail: str,
) -> JSONResponse:
    problem = ProblemDetail(
        type=f"https://naviz.app/problems/{code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        code=code,
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        result = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise ValueError("bbox must contain min_lon,min_lat,max_lon,max_lat") from exc
    if len(result) != 4:
        raise ValueError("bbox must contain min_lon,min_lat,max_lon,max_lat")
    min_lon, min_lat, max_lon, max_lat = result
    if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
        raise ValueError("bbox is outside valid coordinate bounds")
    return min_lon, min_lat, max_lon, max_lat
