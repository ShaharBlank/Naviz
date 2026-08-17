import type {
  Coordinate,
  DataStatus,
  Locale,
  MobilityResponse,
  ProblemDetail,
  RoutePlanRequest,
  RoutePlanResponse,
  SearchResponse,
} from "./types";
import { offlineSearchPlaces } from "../features/search/offlineSearch";

const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
    readonly requestId?: string,
  ) {
    super(message);
  }

  get couldBeColdStart() {
    return this.status === null || this.status === 502 || this.status === 503;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort();
  if (init?.signal?.aborted) controller.abort();
  init?.signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...init?.headers,
      },
      signal: controller.signal,
    });
    if (!response.ok) {
      let problem: ProblemDetail | null = null;
      try {
        problem = (await response.json()) as ProblemDetail;
      } catch {
        // The host can return an HTML cold-start page.
      }
      throw new ApiError(
        problem?.detail ?? `Naviz API returned ${response.status}`,
        response.status,
        problem?.code ?? "http_error",
        problem?.request_id,
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const message = error instanceof Error ? error.message : "Network request failed";
    throw new ApiError(message, null, "network_error");
  } finally {
    clearTimeout(timer);
    init?.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function searchPlaces(
  query: string,
  locale: Locale,
  proximity?: Coordinate,
): Promise<SearchResponse> {
  const parameters = new URLSearchParams({ q: query, language: locale, limit: "8" });
  if (proximity) {
    parameters.set("latitude", String(proximity.latitude));
    parameters.set("longitude", String(proximity.longitude));
  }
  try {
    return await fetchJson(`/v1/search?${parameters.toString()}`);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== null) throw error;
    return offlineSearchPlaces(query, locale, proximity);
  }
}

export function planRoute(
  payload: RoutePlanRequest,
  signal?: AbortSignal,
): Promise<RoutePlanResponse> {
  return fetchJson(
    "/v1/routes/plan",
    { method: "POST", body: JSON.stringify(payload), ...(signal ? { signal } : {}) },
    90_000,
  );
}

export function reroute(
  payload: Omit<RoutePlanRequest, "origin"> & {
    current_position: Coordinate;
    original_route_id: string;
    heading_degrees?: number;
    accuracy_m?: number;
  },
): Promise<RoutePlanResponse> {
  const { current_position, original_route_id, heading_degrees, accuracy_m, ...request } = payload;
  return fetchJson(
    "/v1/routes/reroute",
    {
      method: "POST",
      body: JSON.stringify({
        ...request,
        current_position,
        original_route_id,
        heading_degrees,
        accuracy_m,
      }),
    },
    90_000,
  );
}

export function getDataStatus(): Promise<DataStatus> {
  return fetchJson("/v1/data/status", undefined, 8_000);
}

export function getMobilityVehicles(center: Coordinate): Promise<MobilityResponse> {
  // Roughly a one-kilometre walking catchment in metropolitan Tel Aviv.
  // Keeping the view local avoids an unreadable wall of fleet markers.
  const latitudeRadius = 0.008;
  const longitudeRadius = 0.009;
  const parameters = new URLSearchParams({
    min_latitude: String(center.latitude - latitudeRadius),
    min_longitude: String(center.longitude - longitudeRadius),
    max_latitude: String(center.latitude + latitudeRadius),
    max_longitude: String(center.longitude + longitudeRadius),
  });
  return fetchJson(`/v1/mobility/vehicles?${parameters.toString()}`, undefined, 12_000);
}
