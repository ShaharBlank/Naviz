import { render } from "@testing-library/react-native";

import type { RouteAlternative, ShadowSceneResponse } from "../src/api/types";
import {
  NavizMap,
  buildHeadingFeatureCollection,
  buildRouteLegFeatureCollection,
  buildRouteMarkerFeatureCollection,
  buildShadowFeatureCollection,
  navigationBearing,
  navigationCameraProfile,
  navigationCameraTarget,
  navigationMarkerCoordinate,
  navigationMarkerKind,
  navigationMarkerRotation,
  solarStyleLight,
} from "../src/components/NavizMap";
import "../src/i18n";

describe("NavizMap 3D shade helpers", () => {
  const scene: ShadowSceneResponse = {
    available: true,
    at: "2026-08-17T12:00:00+03:00",
    solar_azimuth_degrees: 190,
    solar_elevation_degrees: 70,
    shadows: [
      {
        rings: [
          [
            { latitude: 32.07, longitude: 34.78 },
            { latitude: 32.07, longitude: 34.781 },
            { latitude: 32.071, longitude: 34.781 },
            { latitude: 32.07, longitude: 34.78 },
          ],
        ],
      },
    ],
    high_confidence_shadows: [],
    coverage_bbox: [34.15, 29.35, 35.95, 33.4],
    model_version: "osm-2.5d-v1",
    attribution: ["© OpenStreetMap contributors · ODbL"],
    warning: null,
  };

  it("maps API latitude/longitude rings into GeoJSON longitude/latitude order", () => {
    const collection = buildShadowFeatureCollection(scene, false);
    expect(collection.features).toHaveLength(1);
    expect(collection.features[0]?.geometry.coordinates[0]?.[0]).toEqual([
      34.78, 32.07,
    ]);
  });

  it("keeps high-confidence shadow geometry in its own layer", () => {
    expect(buildShadowFeatureCollection(scene, true).features).toHaveLength(0);
  });

  it("returns bounded MapLibre light values for Israel", () => {
    const light = solarStyleLight(new Date(scene.at), {
      latitude: 32.07,
      longitude: 34.78,
    });
    expect(light.anchor).toBe("map");
    expect(light.intensity).toBeGreaterThanOrEqual(0.25);
    expect(light.intensity).toBeLessThanOrEqual(0.55);
    const position = light.position as [number, number, number];
    expect(position[1]).toBeGreaterThanOrEqual(0);
    expect(position[1]).toBeLessThan(360);
  });

  it("renders every multimodal leg independently and marks handoffs", () => {
    const route = {
      id: "multi",
      encoded_polyline: "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
      legs: [
        {
          mode: "bike",
          encoded_polyline: "_p~iF~ps|U_ulLnnqC",
        },
        {
          mode: "transit",
          encoded_polyline: "_ulLnnqC_mqNvxq`@",
        },
      ],
    } as RouteAlternative;

    const legs = buildRouteLegFeatureCollection(route, "bike_transit");
    expect(legs.features.map((feature) => feature.properties?.mode)).toEqual([
      "bike",
      "transit",
    ]);
    expect(legs.features[0]?.properties?.color).not.toBe(
      legs.features[1]?.properties?.color,
    );

    const markers = buildRouteMarkerFeatureCollection(route);
    expect(markers.features.map((feature) => feature.properties?.kind)).toEqual(
      ["handoff", "destination"],
    );
  });

  it("uses mode-aware look-ahead cameras while preserving route progress", () => {
    const geometry = [
      { latitude: 32.08, longitude: 34.78 },
      { latitude: 32.081, longitude: 34.78 },
      { latitude: 32.083, longitude: 34.78 },
      { latitude: 32.086, longitude: 34.78 },
    ];
    const user = { latitude: 32.0801, longitude: 34.78 };

    const walkingTarget = navigationCameraTarget(geometry, user, "walk");
    const drivingTarget = navigationCameraTarget(geometry, user, "car");
    expect(drivingTarget.latitude).toBeGreaterThan(walkingTarget.latitude);
    expect(drivingTarget.latitude).toBeLessThan(geometry[2]!.latitude);
    expect(navigationCameraProfile("car").lookAheadM).toBeGreaterThan(
      navigationCameraProfile("walk").lookAheadM,
    );
  });

  it("draws a directional puck only when the sensor heading is valid", () => {
    const user = { latitude: 32.08, longitude: 34.78 };
    expect(buildHeadingFeatureCollection(user, -1).features).toHaveLength(0);

    const heading = buildHeadingFeatureCollection(user, 90);
    expect(heading.features).toHaveLength(1);
    const coordinates = heading.features[0]?.geometry.coordinates;
    expect(coordinates?.[1]?.[0]).toBeGreaterThan(coordinates?.[0]?.[0] ?? 0);
  });

  it("selects a clear navigation avatar for every travel family", () => {
    expect(navigationMarkerKind("walk")).toBe("person");
    expect(navigationMarkerKind("motorcycle")).toBe("two_wheeler");
    expect(navigationMarkerKind("car")).toBe("car");
    expect(navigationMarkerKind("truck")).toBe("truck");
    expect(navigationMarkerKind("bike_transit")).toBe("transit");
  });

  it("keeps the avatar aligned with travel while the map rotates", () => {
    expect(navigationMarkerRotation(10, 350)).toBe(20);
    expect(navigationMarkerRotation(350, 10)).toBe(-20);
    expect(navigationMarkerRotation(95, 95)).toBe(0);
  });

  it("ignores a stale stationary GPS heading during active navigation", () => {
    expect(navigationBearing(88, 0, true)).toBe(88);
    expect(navigationBearing(88, 72, true)).toBe(88);
    expect(navigationBearing(88, 0, false)).toBe(0);
  });

  it("places the avatar on the route without hiding genuine off-route drift", () => {
    const route = [
      { latitude: 32.08, longitude: 34.78 },
      { latitude: 32.082, longitude: 34.78 },
    ];
    const nearRoute = { latitude: 32.081, longitude: 34.7801 };
    const snapped = navigationMarkerCoordinate(route, nearRoute);
    expect(snapped?.longitude).toBeCloseTo(34.78, 5);

    const farFromRoute = { latitude: 32.081, longitude: 34.79 };
    expect(navigationMarkerCoordinate(route, farFromRoute)).toEqual(
      farFromRoute,
    );
  });

  it("keeps MapLibre source and layer identities stable across 2D/3D changes", () => {
    const route = {
      id: "drive",
      label_key: "route.fastest",
      encoded_polyline: "_p~iF~ps|U_ulLnnqC",
      bbox: [34.77, 32.07, 34.79, 32.09],
      departure_at: "2026-08-17T09:00:00+03:00",
      arrival_at: "2026-08-17T09:10:00+03:00",
      legs: [],
      maneuvers: [],
      annotations: [],
      metrics: {
        distance_m: 1_000,
        duration_s: 600,
        walking_distance_m: 0,
        cycling_distance_m: 0,
        transfers: 0,
        detour_time_percent: 0,
        detour_distance_percent: 0,
      },
      quality: {
        confidence: "high",
        scheduled_transit: false,
        realtime_transit: false,
        shade_sources: [],
        warnings: [],
        dataset_versions: {},
      },
      warnings: [],
      fallback_reason: null,
      expires_at: "2026-08-17T09:15:00+03:00",
    } as RouteAlternative;
    const shared = {
      routes: [route],
      selectedRouteId: route.id,
      userCoordinate: { latitude: 32.07, longitude: 34.78 },
      userHeadingDegrees: 30,
      shadowScene: null,
      mobilityVehicles: [],
      following: true,
      navigationActive: true,
      travelMode: "car" as const,
      onRecenter: jest.fn(),
      onOverview: jest.fn(),
      onDisplayModeChange: jest.fn(),
      onMobilityVehiclePress: jest.fn(),
    };
    const screen = render(<NavizMap {...shared} displayMode="2d" />);

    expect(() =>
      screen.rerender(<NavizMap {...shared} displayMode="3d" />),
    ).not.toThrow();
    expect(() =>
      screen.rerender(<NavizMap {...shared} displayMode="2d" />),
    ).not.toThrow();
  });

  it("keeps technical shadow explanations off the map even when shadows are available", () => {
    const route = {
      id: "walk",
      label_key: "route.fastest",
      encoded_polyline: "_p~iF~ps|U_ulLnnqC",
      bbox: [34.77, 32.07, 34.79, 32.09],
      departure_at: "2026-08-17T09:00:00+03:00",
      arrival_at: "2026-08-17T09:10:00+03:00",
      legs: [],
      maneuvers: [],
      annotations: [],
      metrics: {
        distance_m: 1_000,
        duration_s: 600,
        walking_distance_m: 1_000,
        cycling_distance_m: 0,
        transfers: 0,
        detour_time_percent: 0,
        detour_distance_percent: 0,
      },
      quality: {
        confidence: "medium",
        scheduled_transit: false,
        realtime_transit: false,
        shade_sources: [],
        warnings: [],
        dataset_versions: {},
      },
      warnings: [],
      fallback_reason: null,
      expires_at: "2026-08-17T09:15:00+03:00",
    } as RouteAlternative;
    const screen = render(
      <NavizMap
        routes={[route]}
        selectedRouteId={route.id}
        userCoordinate={{ latitude: 32.07, longitude: 34.78 }}
        userHeadingDegrees={null}
        displayMode="3d"
        shadowScene={scene}
        mobilityVehicles={[]}
        following={false}
        navigationActive={false}
        travelMode="walk"
        onRecenter={jest.fn()}
        onOverview={jest.fn()}
        onDisplayModeChange={jest.fn()}
        onMobilityVehiclePress={jest.fn()}
      />,
    );

    expect(screen.queryByText("Route time")).toBeNull();
    expect(screen.queryByText(/Building shadows at/)).toBeNull();
    expect(screen.queryByText(/darker = verified height/)).toBeNull();
  });
});
