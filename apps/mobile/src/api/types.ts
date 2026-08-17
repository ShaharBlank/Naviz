import type { components } from "./schema";

type Schemas = components["schemas"];

// Public API DTOs are generated from FastAPI's checked-in OpenAPI document.
// RoutePlanRequest is narrowed to the fields this client always sends.
export type Locale = Schemas["Locale"];
export type TravelMode = Schemas["TravelMode"];
export type RoutePreference = Schemas["RoutePreference"];
export type VehicleKind = Schemas["VehicleKind"];
export type Coordinate = Schemas["Coordinate"];
export type Place = Schemas["Place"];
export type SearchResponse = Schemas["SearchResponse"];
export type Maneuver = Schemas["Maneuver"];
export type SegmentAnnotation = Schemas["SegmentAnnotation"];
export type TransitDetails = Schemas["TransitDetails"];
export type RentalDetails = Schemas["RentalDetails"];
export type RouteLeg = Schemas["RouteLeg"];
export type RouteMetrics = Schemas["RouteMetrics"];
export type DataQuality = Schemas["DataQuality"];
export type RouteAlternative = Schemas["RouteAlternative"];
export type RoutePlanResponse = Schemas["RoutePlanResponse"];
export type DataStatus = Schemas["DataStatus"];
export type MobilityVehicle = Schemas["MobilityVehicle"];
export type MobilityResponse = Schemas["MobilityResponse"];

type GeneratedRoutePlanRequest = Schemas["RoutePlanRequest"];
export type RoutePlanRequest = GeneratedRoutePlanRequest & {
  depart_at: string;
  locale: Locale;
  mode: TravelMode;
  preference: RoutePreference;
};

// RFC 9457 responses are returned by middleware/exception handlers and are not
// tied to a successful operation response in OpenAPI.
export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  code: string;
  request_id?: string;
}
