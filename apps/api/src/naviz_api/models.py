from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Locale(StrEnum):
    HEBREW = "he"
    ENGLISH = "en"


class TravelMode(StrEnum):
    WALK = "walk"
    BIKE = "bike"
    SCOOTER = "scooter"
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    TRUCK = "truck"
    TRANSIT = "transit"
    BIKE_TRANSIT = "bike_transit"
    SCOOTER_TRANSIT = "scooter_transit"
    RENTAL_TRANSIT = "rental_transit"


class RoutePreference(StrEnum):
    FASTEST = "fastest"
    BALANCED_SHADE = "balanced_shade"
    MAXIMUM_SHADE = "maximum_shade"
    FEWER_LIGHTS = "fewer_lights"
    SAFER_STREETS = "safer_streets"
    FEWER_TRANSFERS = "fewer_transfers"


class VehicleKind(StrEnum):
    NONE = "none"
    FULL_SIZE_BIKE = "full_size_bike"
    FOLDING_BIKE = "folding_bike"
    PERSONAL_SCOOTER = "personal_scooter"
    SHARED_BIKE = "shared_bike"
    SHARED_SCOOTER = "shared_scooter"


class DataConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Coordinate(ApiModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]


class VehicleProfile(ApiModel):
    kind: VehicleKind = VehicleKind.NONE
    height_m: Annotated[float | None, Field(gt=0, le=10)] = None
    width_m: Annotated[float | None, Field(gt=0, le=5)] = None
    weight_t: Annotated[float | None, Field(gt=0, le=100)] = None
    can_fold: bool = False


class AccessibilityPreferences(ApiModel):
    avoid_stairs: bool = False
    require_step_free: bool = False
    maximum_carry_distance_m: Annotated[int, Field(ge=0, le=10_000)] = 500


class RouteConstraints(ApiModel):
    maximum_time_detour_percent: Annotated[float | None, Field(ge=0, le=100)] = None
    maximum_distance_detour_percent: Annotated[float | None, Field(ge=0, le=100)] = None
    allow_low_confidence_crossings: bool = False


class RoutePlanRequest(ApiModel):
    origin: Coordinate
    destination: Coordinate
    depart_at: datetime | None = None
    arrive_by: datetime | None = None
    locale: Locale = Locale.HEBREW
    mode: TravelMode = TravelMode.WALK
    preference: RoutePreference = RoutePreference.FASTEST
    vehicle: VehicleProfile = Field(default_factory=VehicleProfile)
    accessibility: AccessibilityPreferences = Field(default_factory=AccessibilityPreferences)
    constraints: RouteConstraints = Field(default_factory=RouteConstraints)

    @model_validator(mode="after")
    def validate_time_and_preference(self) -> RoutePlanRequest:
        if self.depart_at and self.arrive_by:
            raise ValueError("Provide depart_at or arrive_by, not both")
        walk_preferences = {
            RoutePreference.FASTEST,
            RoutePreference.BALANCED_SHADE,
            RoutePreference.MAXIMUM_SHADE,
        }
        road_preferences = {RoutePreference.FASTEST, RoutePreference.FEWER_LIGHTS}
        road_modes = {TravelMode.CAR, TravelMode.MOTORCYCLE, TravelMode.TRUCK}
        if self.mode == TravelMode.WALK and self.preference not in walk_preferences:
            raise ValueError("Unsupported walking preference")
        if self.mode in road_modes and self.preference not in road_preferences:
            raise ValueError("Unsupported road preference")
        return self


class RerouteRequest(ApiModel):
    current_position: Coordinate
    destination: Coordinate
    heading_degrees: Annotated[float | None, Field(ge=0, lt=360)] = None
    accuracy_m: Annotated[float | None, Field(gt=0, le=1_000)] = None
    original_route_id: str | None = None
    depart_at: datetime | None = None
    locale: Locale = Locale.HEBREW
    mode: TravelMode = TravelMode.WALK
    preference: RoutePreference = RoutePreference.FASTEST
    vehicle: VehicleProfile = Field(default_factory=VehicleProfile)
    accessibility: AccessibilityPreferences = Field(default_factory=AccessibilityPreferences)
    constraints: RouteConstraints = Field(default_factory=RouteConstraints)

    def to_plan_request(self) -> RoutePlanRequest:
        return RoutePlanRequest(
            origin=self.current_position,
            destination=self.destination,
            depart_at=self.depart_at,
            locale=self.locale,
            mode=self.mode,
            preference=self.preference,
            vehicle=self.vehicle,
            accessibility=self.accessibility,
            constraints=self.constraints,
        )


class Place(ApiModel):
    id: str
    name: str
    name_he: str | None = None
    subtitle: str | None = None
    coordinate: Coordinate
    category: str
    confidence: DataConfidence = DataConfidence.HIGH


class SearchResponse(ApiModel):
    query: str
    results: list[Place]
    data_version: str


class Maneuver(ApiModel):
    id: str
    instruction_key: str
    modifier: str | None = None
    street_name: str | None = None
    distance_m: float
    duration_s: float
    geometry_index: int
    coordinate: Coordinate


class SegmentAnnotation(ApiModel):
    start_index: int
    end_index: int
    classification: str
    selected_side: str | None = None
    shade_fraction: Annotated[float | None, Field(ge=0, le=1)] = None
    confidence: DataConfidence = DataConfidence.UNKNOWN
    crossing_kind: str | None = None


class TransitDetails(ApiModel):
    agency: str
    route_short_name: str
    headsign: str
    departure_at: datetime
    arrival_at: datetime
    stops: int
    realtime: bool = False
    vehicle_rule_source: str | None = None


class RentalDetails(ApiModel):
    provider: str
    vehicle_id: str
    deep_link: str | None = None
    battery_percent: int | None = None
    observed_at: datetime


class RouteLeg(ApiModel):
    mode: TravelMode
    from_name: str
    to_name: str
    encoded_polyline: str
    distance_m: float
    duration_s: float
    maneuvers: list[Maneuver] = Field(default_factory=list)
    annotations: list[SegmentAnnotation] = Field(default_factory=list)
    transit: TransitDetails | None = None
    rental: RentalDetails | None = None


class RouteMetrics(ApiModel):
    distance_m: float
    duration_s: float
    walking_distance_m: float = 0
    cycling_distance_m: float = 0
    transfers: int = 0
    shade_fraction: Annotated[float | None, Field(ge=0, le=1)] = None
    high_confidence_shade_fraction: Annotated[float | None, Field(ge=0, le=1)] = None
    sun_exposure_minutes: float | None = None
    traffic_signals: int | None = None
    signals_avoided: int | None = None
    detour_time_percent: float = 0
    detour_distance_percent: float = 0


class DataQuality(ApiModel):
    confidence: DataConfidence
    scheduled_transit: bool = True
    realtime_transit: bool = False
    shade_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dataset_versions: dict[str, str] = Field(default_factory=dict)


class RouteAlternative(ApiModel):
    id: str
    label_key: str
    encoded_polyline: str
    bbox: tuple[float, float, float, float]
    departure_at: datetime
    arrival_at: datetime
    legs: list[RouteLeg]
    maneuvers: list[Maneuver]
    annotations: list[SegmentAnnotation]
    metrics: RouteMetrics
    quality: DataQuality
    warnings: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None
    expires_at: datetime


class RoutePlanResponse(ApiModel):
    request_id: str
    routes: list[RouteAlternative]
    data_version: str
    engine_profile: str


class MobilityVehicle(ApiModel):
    provider: str
    id: str
    kind: VehicleKind
    coordinate: Coordinate
    battery_percent: Annotated[int | None, Field(ge=0, le=100)] = None
    deep_link: str | None = None
    observed_at: datetime
    available: bool = True
    stale: bool = False


class MobilityResponse(ApiModel):
    vehicles: list[MobilityVehicle]
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class Favorite(ApiModel):
    id: str
    label: str
    place: Place
    created_at: datetime


class FavoriteCreate(ApiModel):
    label: Annotated[str, Field(min_length=1, max_length=80)]
    place: Place


class UserPreferences(ApiModel):
    locale: Locale = Locale.HEBREW
    default_mode: TravelMode = TravelMode.WALK
    default_walk_preference: RoutePreference = RoutePreference.BALANCED_SHADE
    history_enabled: bool = False


class HistoryEntry(ApiModel):
    id: str
    origin_label: str
    destination: Place
    mode: TravelMode
    created_at: datetime
    expires_at: datetime


class DataStatus(ApiModel):
    coverage: str
    data_version: str
    engine_profile: str
    warmed: bool
    updated_at: datetime
    feeds: dict[str, dict[str, Any]]


class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str
    request_id: str | None = None
