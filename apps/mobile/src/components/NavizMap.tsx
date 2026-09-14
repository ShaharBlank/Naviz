import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
  Marker,
  type LightSpecification,
} from "@maplibre/maplibre-react-native";
import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { decodePolyline, distanceMeters } from "../api/polyline";
import type {
  Coordinate,
  MobilityVehicle,
  RouteAlternative,
  ShadowSceneResponse,
  TravelMode,
} from "../api/types";
import { colors, radius, shadow, spacing } from "../theme/tokens";
import { NavigationAvatar, navigationAvatarKind } from "./NavigationAvatar";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/bright";
const ISRAEL_CENTER: Coordinate = { latitude: 31.7683, longitude: 35.2137 };

export type MapDisplayMode = "2d" | "3d";

export interface NavizMapProps {
  routes: RouteAlternative[];
  selectedRouteId: string | null;
  userCoordinate: Coordinate | null;
  userHeadingDegrees: number | null;
  displayMode: MapDisplayMode;
  shadowScene: ShadowSceneResponse | null;
  mobilityVehicles: MobilityVehicle[];
  following: boolean;
  navigationActive: boolean;
  travelMode: TravelMode;
  onRecenter: () => void;
  onOverview: () => void;
  onDisplayModeChange: (mode: MapDisplayMode) => void;
  onMobilityVehiclePress: (vehicle: MobilityVehicle) => void;
}

function NavizMapComponent({
  routes,
  selectedRouteId,
  userCoordinate,
  userHeadingDegrees,
  displayMode,
  shadowScene,
  mobilityVehicles,
  following,
  navigationActive,
  travelMode,
  onRecenter,
  onOverview,
  onDisplayModeChange,
  onMobilityVehiclePress,
}: NavizMapProps) {
  const { t } = useTranslation();
  const selectedRoute =
    routes.find((route) => route.id === selectedRouteId) ?? routes[0] ?? null;
  const effectiveSelectedRouteId = selectedRoute?.id ?? null;
  const geometry = useMemo(
    () => (selectedRoute ? decodePolyline(selectedRoute.encoded_polyline) : []),
    [selectedRoute],
  );
  const routeLines = useMemo(
    () => buildRouteFeatureCollection(routes, effectiveSelectedRouteId),
    [effectiveSelectedRouteId, routes],
  );
  const selectedRouteLegs = useMemo(
    () => buildRouteLegFeatureCollection(selectedRoute, travelMode),
    [selectedRoute, travelMode],
  );
  const routeMarkers = useMemo(
    () => buildRouteMarkerFeatureCollection(selectedRoute),
    [selectedRoute],
  );
  const segments = useMemo<GeoJSON.FeatureCollection<GeoJSON.LineString>>(
    () => ({
      type: "FeatureCollection" as const,
      features:
        selectedRoute?.annotations
          .map((annotation) => ({
            type: "Feature" as const,
            properties: {
              classification: annotation.classification,
              selectedSide: annotation.selected_side,
            },
            geometry: {
              type: "LineString" as const,
              coordinates: geometry
                .slice(annotation.start_index, annotation.end_index + 1)
                .map(({ longitude, latitude }) => [longitude, latitude]),
            },
          }))
          .filter((feature) => feature.geometry.coordinates.length >= 2) ?? [],
    }),
    [geometry, selectedRoute?.annotations],
  );
  const crossings = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(
    () => ({
      type: "FeatureCollection" as const,
      features:
        selectedRoute?.annotations.flatMap((annotation) => {
          const coordinate = geometry[annotation.start_index];
          if (!annotation.crossing_kind || !coordinate) return [];
          return [
            {
              type: "Feature" as const,
              properties: { crossing: annotation.crossing_kind },
              geometry: {
                type: "Point" as const,
                coordinates: [coordinate.longitude, coordinate.latitude],
              },
            },
          ];
        }) ?? [],
    }),
    [geometry, selectedRoute?.annotations],
  );
  const mobilityPoints = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(
    () => ({
      type: "FeatureCollection" as const,
      features: mobilityVehicles.map((vehicle) => ({
        type: "Feature" as const,
        properties: {
          vehicleId: vehicle.id,
          provider: vehicle.provider,
          kind: vehicle.kind,
          battery: vehicle.battery_percent,
        },
        geometry: {
          type: "Point" as const,
          coordinates: [
            vehicle.coordinate.longitude,
            vehicle.coordinate.latitude,
          ],
        },
      })),
    }),
    [mobilityVehicles],
  );
  const userPoint = useMemo<GeoJSON.Feature<GeoJSON.Point> | null>(
    () =>
      userCoordinate
        ? {
            type: "Feature" as const,
            properties: {},
            geometry: {
              type: "Point" as const,
              coordinates: [userCoordinate.longitude, userCoordinate.latitude],
            },
          }
        : null,
    [userCoordinate],
  );
  const headingLine = useMemo(
    () => buildHeadingFeatureCollection(userCoordinate, userHeadingDegrees),
    [userCoordinate, userHeadingDegrees],
  );
  const routeBearing = useMemo(
    () => bearingNearCoordinate(geometry, userCoordinate),
    [geometry, userCoordinate],
  );
  const cameraBearing = navigationBearing(
    routeBearing,
    userHeadingDegrees,
    navigationActive,
  );
  const mapBearing = following
    ? cameraBearing
    : isFinite(routeBearing)
      ? routeBearing
      : 0;
  const navigationMarker = useMemo(
    () => navigationMarkerCoordinate(geometry, userCoordinate),
    [geometry, userCoordinate],
  );
  const markerRotationDegrees = navigationMarkerRotation(
    cameraBearing,
    following ? cameraBearing : displayMode === "3d" ? mapBearing : 0,
  );
  const navigationProfile = navigationCameraProfile(travelMode);
  const navigationTarget = useMemo(
    () => navigationCameraTarget(geometry, userCoordinate, travelMode),
    [geometry, travelMode, userCoordinate],
  );
  const lightingCoordinate = userCoordinate ?? geometry[0] ?? ISRAEL_CENTER;
  const light = useMemo(
    () =>
      solarStyleLight(
        shadowScene
          ? new Date(shadowScene.at)
          : selectedRoute
            ? new Date(selectedRoute.departure_at)
            : new Date(0),
        lightingCoordinate,
      ),
    [lightingCoordinate, selectedRoute, shadowScene],
  );
  const shadowPolygons = useMemo(
    () => buildShadowFeatureCollection(shadowScene, false),
    [shadowScene],
  );
  const highConfidenceShadowPolygons = useMemo(
    () => buildShadowFeatureCollection(shadowScene, true),
    [shadowScene],
  );
  const is3d = displayMode === "3d";
  return (
    <View style={styles.container} accessibilityLabel={t("accessibility.map")}>
      <Map
        style={styles.map}
        mapStyle={MAP_STYLE}
        light={light}
        preferredFramesPerSecond={is3d ? 45 : 60}
        attributionPosition={{ top: 64, right: 8 }}
        logoPosition={{ top: 64, left: 8 }}
      >
        {following && userCoordinate ? (
          <Camera
            center={[navigationTarget.longitude, navigationTarget.latitude]}
            zoom={
              navigationActive
                ? is3d
                  ? navigationProfile.zoom3d
                  : navigationProfile.zoom2d
                : is3d
                  ? 15.7
                  : 14.7
            }
            bearing={navigationActive ? cameraBearing : 0}
            pitch={is3d ? (navigationActive ? navigationProfile.pitch : 48) : 0}
            padding={{ top: 112, right: 32, bottom: 186, left: 32 }}
            duration={420}
          />
        ) : selectedRoute ? (
          <Camera
            bounds={selectedRoute.bbox}
            padding={{ top: 104, right: 36, bottom: 300, left: 36 }}
            bearing={is3d ? routeBearing : 0}
            pitch={is3d ? 50 : 0}
            duration={600}
          />
        ) : (
          <Camera
            pitch={is3d ? 45 : 0}
            initialViewState={{
              center: userCoordinate
                ? [userCoordinate.longitude, userCoordinate.latitude]
                : [ISRAEL_CENTER.longitude, ISRAEL_CENTER.latitude],
              zoom: userCoordinate ? 13.5 : 7.2,
              pitch: is3d ? 45 : 0,
            }}
          />
        )}

        <GeoJSONSource
          key="naviz-building-shadows"
          id="naviz-building-shadows"
          data={shadowPolygons}
        >
          <Layer
            key="naviz-building-shadow-fill"
            id="naviz-building-shadow-fill"
            type="fill"
            paint={{
              "fill-color": "#26364D",
              "fill-opacity": is3d ? 0.2 : 0,
              "fill-outline-color": "rgba(30, 41, 59, 0.22)",
            }}
          />
        </GeoJSONSource>
        <GeoJSONSource
          key="naviz-high-confidence-shadows"
          id="naviz-high-confidence-shadows"
          data={highConfidenceShadowPolygons}
        >
          <Layer
            key="naviz-high-confidence-shadow-fill"
            id="naviz-high-confidence-shadow-fill"
            type="fill"
            paint={{
              "fill-color": "#111827",
              "fill-opacity": is3d ? 0.22 : 0,
            }}
          />
        </GeoJSONSource>

        <Layer
          key="naviz-3d-buildings"
          id="naviz-3d-buildings"
          type="fill-extrusion"
          source="openmaptiles"
          source-layer="building"
          minzoom={14.5}
          filter={[
            "all",
            ["has", "render_height"],
            ["has", "render_min_height"],
          ]}
          paint={{
            "fill-extrusion-base": ["get", "render_min_height"],
            "fill-extrusion-height": ["get", "render_height"],
            "fill-extrusion-color": [
              "interpolate",
              ["linear"],
              ["get", "render_height"],
              0,
              "#F4F7FA",
              24,
              "#DCE3EB",
              80,
              "#B9C5D3",
              180,
              "#8C9AAA",
            ],
            "fill-extrusion-opacity": is3d ? 0.82 : 0,
            "fill-extrusion-vertical-gradient": true,
          }}
        />

        {routeLines.features.length > 0 ? (
          <GeoJSONSource
            key="route-alternatives"
            id="route-alternatives"
            data={routeLines}
          >
            <Layer
              key="route-alternative-borders"
              id="route-alternative-borders"
              type="line"
              filter={["==", ["get", "selected"], false]}
              paint={{
                "line-color": colors.surface,
                "line-width": 8,
                "line-opacity": 0.62,
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
            <Layer
              key="route-alternative-lines"
              id="route-alternative-lines"
              type="line"
              filter={["==", ["get", "selected"], false]}
              paint={{
                "line-color": "#64748B",
                "line-width": 4,
                "line-opacity": 0.62,
                "line-dasharray": [2, 1.5],
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
          </GeoJSONSource>
        ) : null}

        {selectedRouteLegs.features.length > 0 ? (
          <GeoJSONSource
            key="selected-route-legs"
            id="selected-route-legs"
            data={selectedRouteLegs}
          >
            <Layer
              key="selected-route-glow"
              id="selected-route-glow"
              type="line"
              paint={{
                "line-color": ["get", "color"],
                "line-width": is3d ? 18 : 12,
                "line-opacity": is3d ? 0.2 : 0,
                "line-blur": 5,
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
            <Layer
              key="selected-route-border"
              id="selected-route-border"
              type="line"
              paint={{
                "line-color": colors.surface,
                "line-width": is3d ? 12 : 11,
                "line-opacity": 0.96,
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
            <Layer
              key="selected-route-lines"
              id="selected-route-lines"
              type="line"
              filter={["!=", ["get", "mode"], "transit"]}
              paint={{
                "line-color": ["get", "color"],
                "line-width": is3d ? 7.5 : 7,
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
            <Layer
              key="selected-route-transit-lines"
              id="selected-route-transit-lines"
              type="line"
              filter={["==", ["get", "mode"], "transit"]}
              paint={{
                "line-color": ["get", "color"],
                "line-width": is3d ? 8 : 7,
                "line-dasharray": [2.2, 0.8],
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
          </GeoJSONSource>
        ) : null}

        {selectedRoute && geometry.length >= 2 ? (
          <>
            <GeoJSONSource
              key="route-segments"
              id="route-segments"
              data={segments}
            >
              <Layer
                key="route-shade-lines"
                id="route-shade-lines"
                type="line"
                filter={["==", ["get", "classification"], "shade"]}
                paint={{ "line-color": colors.shade, "line-width": 7 }}
                layout={{ "line-cap": "round" }}
              />
              <Layer
                key="route-mixed-lines"
                id="route-mixed-lines"
                type="line"
                filter={["==", ["get", "classification"], "mixed"]}
                paint={{
                  "line-color": colors.mixed,
                  "line-width": 7,
                  "line-dasharray": [2, 1],
                }}
                layout={{ "line-cap": "round" }}
              />
              <Layer
                key="route-sun-lines"
                id="route-sun-lines"
                type="line"
                filter={["==", ["get", "classification"], "sun"]}
                paint={{
                  "line-color": colors.sun,
                  "line-width": 7,
                  "line-dasharray": [0.5, 1.5],
                }}
                layout={{ "line-cap": "round" }}
              />
            </GeoJSONSource>
            <GeoJSONSource
              key="route-crossings"
              id="route-crossings"
              data={crossings}
            >
              <Layer
                key="route-crossing-points"
                id="route-crossing-points"
                type="circle"
                paint={{
                  "circle-color": colors.surface,
                  "circle-radius": 5,
                  "circle-stroke-color": colors.ink,
                  "circle-stroke-width": 2,
                }}
              />
            </GeoJSONSource>
          </>
        ) : null}

        {routeMarkers.features.length > 0 ? (
          <GeoJSONSource
            key="route-markers"
            id="route-markers"
            data={routeMarkers}
          >
            <Layer
              key="route-handoff-markers"
              id="route-handoff-markers"
              type="circle"
              filter={["==", ["get", "kind"], "handoff"]}
              paint={{
                "circle-color": colors.surface,
                "circle-radius": 7,
                "circle-stroke-color": ["get", "color"],
                "circle-stroke-width": 3,
              }}
            />
            <Layer
              key="route-destination-marker"
              id="route-destination-marker"
              type="circle"
              filter={["==", ["get", "kind"], "destination"]}
              paint={{
                "circle-color": colors.ink,
                "circle-radius": 8,
                "circle-stroke-color": colors.surface,
                "circle-stroke-width": 3,
              }}
            />
          </GeoJSONSource>
        ) : null}

        {mobilityVehicles.length > 0 ? (
          <GeoJSONSource
            key="mobility-vehicles"
            id="mobility-vehicles"
            data={mobilityPoints}
            onPress={(event) => {
              const vehicleId =
                event.nativeEvent.features[0]?.properties?.vehicleId;
              const vehicle = mobilityVehicles.find(
                (item) => item.id === vehicleId,
              );
              if (vehicle) onMobilityVehiclePress(vehicle);
            }}
          >
            <Layer
              key="mobility-vehicle-points"
              id="mobility-vehicle-points"
              type="circle"
              paint={{
                "circle-color": colors.primary,
                "circle-radius": 7,
                "circle-stroke-color": colors.surface,
                "circle-stroke-width": 3,
              }}
            />
          </GeoJSONSource>
        ) : null}

        {navigationActive && navigationMarker ? (
          <Marker
            key="naviz-navigation-avatar"
            id="naviz-navigation-avatar"
            lngLat={[navigationMarker.longitude, navigationMarker.latitude]}
            anchor="center"
            pointerEvents="none"
          >
            <NavigationAvatar
              mode={travelMode}
              displayMode={displayMode}
              rotationDegrees={markerRotationDegrees}
              accessibilityLabel={t("navigation.positionMarker", {
                mode: t(`mode.${travelMode}`),
              })}
            />
          </Marker>
        ) : userPoint ? (
          <>
            {headingLine.features.length > 0 ? (
              <GeoJSONSource
                key="naviz-user-heading"
                id="naviz-user-heading"
                data={headingLine}
              >
                <Layer
                  key="naviz-user-heading-line"
                  id="naviz-user-heading-line"
                  type="line"
                  paint={{
                    "line-color": colors.primaryDark,
                    "line-width": 5,
                    "line-opacity": 0.9,
                  }}
                  layout={{ "line-cap": "round" }}
                />
              </GeoJSONSource>
            ) : null}
            <GeoJSONSource
              key="naviz-user-location"
              id="naviz-user-location"
              data={userPoint}
            >
              <Layer
                key="naviz-user-location-halo"
                id="naviz-user-location-halo"
                type="circle"
                paint={{
                  "circle-color": "rgba(91, 75, 219, 0.18)",
                  "circle-radius": 15,
                  "circle-stroke-width": 0,
                }}
              />
              <Layer
                key="naviz-user-location-puck"
                id="naviz-user-location-puck"
                type="circle"
                paint={{
                  "circle-color": colors.primary,
                  "circle-radius": 7.5,
                  "circle-stroke-color": colors.surface,
                  "circle-stroke-width": 3,
                }}
              />
            </GeoJSONSource>
          </>
        ) : null}
      </Map>

      <View
        style={[
          styles.mapControls,
          navigationActive && styles.mapControlsWhileNavigating,
        ]}
      >
        <MapModeToggle value={displayMode} onChange={onDisplayModeChange} />
        {selectedRoute && !following ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("overview")}
            style={styles.mapButton}
            onPress={onOverview}
          >
            <Text style={styles.mapButtonText}>▱</Text>
          </Pressable>
        ) : null}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("recenter")}
          style={styles.mapButton}
          onPress={onRecenter}
        >
          <Text style={styles.mapButtonText}>◎</Text>
        </Pressable>
      </View>
    </View>
  );
}

export function MapModeToggle({
  value,
  onChange,
}: {
  value: MapDisplayMode;
  onChange: (value: MapDisplayMode) => void;
}) {
  const { t } = useTranslation();
  const nextValue: MapDisplayMode = value === "3d" ? "2d" : "3d";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={nextValue === "3d" ? t("map3d") : t("map2d")}
      accessibilityHint={t("mapDisplayMode")}
      accessibilityState={{ selected: value === "3d" }}
      onPress={() => onChange(nextValue)}
      style={styles.mapButton}
    >
      <Text style={styles.mapModeButtonText}>{nextValue.toUpperCase()}</Text>
    </Pressable>
  );
}

export function buildRouteFeatureCollection(
  routes: RouteAlternative[],
  selectedRouteId: string | null,
): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  return {
    type: "FeatureCollection",
    features: routes.flatMap((route) => {
      const coordinates = decodePolyline(route.encoded_polyline).map(
        ({ longitude, latitude }) => [longitude, latitude],
      );
      if (coordinates.length < 2) return [];
      return [
        {
          type: "Feature" as const,
          properties: {
            routeId: route.id,
            selected: route.id === selectedRouteId,
          },
          geometry: { type: "LineString" as const, coordinates },
        },
      ];
    }),
  };
}

const ROUTE_COLORS: Record<TravelMode, string> = {
  walk: "#5B4BDB",
  bike: "#0F9D76",
  scooter: "#0284C7",
  car: "#2563EB",
  motorcycle: "#7C3AED",
  truck: "#334155",
  transit: "#E11D48",
  bike_transit: "#0F9D76",
  scooter_transit: "#0284C7",
  rental_transit: "#7C3AED",
};

export function buildRouteLegFeatureCollection(
  route: RouteAlternative | null,
  fallbackMode: TravelMode = "walk",
): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  if (!route) return { type: "FeatureCollection", features: [] };
  const legs = route.legs.length
    ? route.legs.map((leg) => ({
        mode: leg.mode,
        polyline: leg.encoded_polyline,
      }))
    : [{ mode: fallbackMode, polyline: route.encoded_polyline }];
  return {
    type: "FeatureCollection",
    features: legs.flatMap((leg, index) => {
      const coordinates = decodePolyline(leg.polyline).map(
        ({ longitude, latitude }) => [longitude, latitude],
      );
      if (coordinates.length < 2) return [];
      return [
        {
          type: "Feature" as const,
          properties: {
            index,
            mode: leg.mode,
            color: ROUTE_COLORS[leg.mode],
          },
          geometry: { type: "LineString" as const, coordinates },
        },
      ];
    }),
  };
}

export function buildRouteMarkerFeatureCollection(
  route: RouteAlternative | null,
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  if (!route) return { type: "FeatureCollection", features: [] };
  const legs = route.legs.flatMap((leg) => {
    const geometry = decodePolyline(leg.encoded_polyline);
    const coordinate = geometry.at(-1);
    return coordinate ? [{ coordinate, mode: leg.mode }] : [];
  });
  const routeEnd = decodePolyline(route.encoded_polyline).at(-1);
  const markerLegs = legs.length
    ? legs
    : routeEnd
      ? [{ coordinate: routeEnd, mode: "walk" as TravelMode }]
      : [];
  return {
    type: "FeatureCollection",
    features: markerLegs.map(({ coordinate, mode }, index) => ({
      type: "Feature" as const,
      properties: {
        kind: index === markerLegs.length - 1 ? "destination" : "handoff",
        color: ROUTE_COLORS[mode],
      },
      geometry: {
        type: "Point" as const,
        coordinates: [coordinate.longitude, coordinate.latitude],
      },
    })),
  };
}

export function buildHeadingFeatureCollection(
  coordinate: Coordinate | null,
  headingDegrees: number | null,
): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  if (!coordinate || headingDegrees === null || headingDegrees < 0) {
    return { type: "FeatureCollection", features: [] };
  }
  const heading = degreesToRadians(normalizeDegrees(headingDegrees));
  const distanceM = 22;
  const latitudeDelta = (distanceM * Math.cos(heading)) / 111_320;
  const longitudeScale = Math.max(
    0.1,
    Math.cos(degreesToRadians(coordinate.latitude)),
  );
  const longitudeDelta =
    (distanceM * Math.sin(heading)) / (111_320 * longitudeScale);
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: [
            [coordinate.longitude, coordinate.latitude],
            [
              coordinate.longitude + longitudeDelta,
              coordinate.latitude + latitudeDelta,
            ],
          ],
        },
      },
    ],
  };
}

export type NavigationMarkerKind =
  "person" | "two_wheeler" | "car" | "truck" | "transit";

export function navigationMarkerKind(mode: TravelMode): NavigationMarkerKind {
  return navigationAvatarKind(mode);
}

export function navigationMarkerRotation(
  headingDegrees: number,
  mapBearingDegrees: number,
): number {
  return normalizeSignedDegrees(headingDegrees - mapBearingDegrees);
}

export function navigationBearing(
  routeBearingDegrees: number,
  gpsHeadingDegrees: number | null,
  navigationActive: boolean,
): number {
  const routeBearingDegreesNormalized = normalizeDegrees(routeBearingDegrees);
  if (gpsHeadingDegrees === null || gpsHeadingDegrees < 0) {
    return routeBearingDegreesNormalized;
  }
  const gpsHeadingDegreesNormalized = normalizeDegrees(gpsHeadingDegrees);
  if (!navigationActive) return gpsHeadingDegreesNormalized;

  // The matched route supplies a stable forward course at walking speed, while
  // stopped, and in urban canyons where a compass heading oscillates. Rerouting
  // updates this course as soon as the user genuinely leaves the route.
  return routeBearingDegreesNormalized;
}

export function navigationMarkerCoordinate(
  geometry: Coordinate[],
  userCoordinate: Coordinate | null,
  maximumSnapDistanceM = 45,
): Coordinate | null {
  if (!userCoordinate || geometry.length < 2) return userCoordinate;
  const longitudeScale = Math.max(
    0.1,
    Math.cos(degreesToRadians(userCoordinate.latitude)),
  );
  let bestCoordinate = userCoordinate;
  let bestDistanceM = Number.POSITIVE_INFINITY;

  for (let index = 0; index < geometry.length - 1; index += 1) {
    const start = geometry[index];
    const end = geometry[index + 1];
    if (!start || !end) continue;
    const startX =
      (start.longitude - userCoordinate.longitude) * longitudeScale;
    const startY = start.latitude - userCoordinate.latitude;
    const endX = (end.longitude - userCoordinate.longitude) * longitudeScale;
    const endY = end.latitude - userCoordinate.latitude;
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    const lengthSquared = deltaX * deltaX + deltaY * deltaY;
    const ratio =
      lengthSquared <= Number.EPSILON
        ? 0
        : clamp(-(startX * deltaX + startY * deltaY) / lengthSquared, 0, 1);
    const candidate: Coordinate = {
      latitude: start.latitude + (end.latitude - start.latitude) * ratio,
      longitude: start.longitude + (end.longitude - start.longitude) * ratio,
    };
    const distanceM = distanceMeters(userCoordinate, candidate);
    if (distanceM < bestDistanceM) {
      bestDistanceM = distanceM;
      bestCoordinate = candidate;
    }
  }

  return bestDistanceM <= maximumSnapDistanceM
    ? bestCoordinate
    : userCoordinate;
}

export interface NavigationCameraProfile {
  zoom2d: number;
  zoom3d: number;
  pitch: number;
  lookAheadM: number;
}

export function navigationCameraProfile(
  mode: TravelMode,
): NavigationCameraProfile {
  if (mode === "walk") {
    return { zoom2d: 18, zoom3d: 17.95, pitch: 55, lookAheadM: 70 };
  }
  if (mode === "bike" || mode === "scooter") {
    return { zoom2d: 17.5, zoom3d: 17.5, pitch: 54, lookAheadM: 90 };
  }
  if (mode === "transit" || mode.endsWith("_transit")) {
    return { zoom2d: 16.6, zoom3d: 16.9, pitch: 50, lookAheadM: 160 };
  }
  // Keep the vehicle visible above the bottom navigation card. A longer
  // look-ahead pushed the geographic marker underneath the HUD on short first
  // maneuvers, particularly just before a turn.
  return { zoom2d: 17.2, zoom3d: 17.05, pitch: 54, lookAheadM: 95 };
}

export function navigationCameraTarget(
  geometry: Coordinate[],
  userCoordinate: Coordinate | null,
  mode: TravelMode,
): Coordinate {
  if (!userCoordinate || geometry.length < 2) {
    return userCoordinate ?? geometry[0] ?? ISRAEL_CENTER;
  }
  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  geometry.forEach((coordinate, index) => {
    const distance = distanceMeters(userCoordinate, coordinate);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });
  const lookAheadM = navigationCameraProfile(mode).lookAheadM;
  let travelledM = 0;
  let target = geometry[nearestIndex] ?? userCoordinate;
  for (let index = nearestIndex; index < geometry.length - 1; index += 1) {
    const current = geometry[index];
    const next = geometry[index + 1];
    if (!current || !next) break;
    const segmentM = distanceMeters(current, next);
    if (segmentM <= 0) continue;
    if (travelledM + segmentM >= lookAheadM) {
      const ratio = clamp((lookAheadM - travelledM) / segmentM, 0, 1);
      return {
        latitude: current.latitude + (next.latitude - current.latitude) * ratio,
        longitude:
          current.longitude + (next.longitude - current.longitude) * ratio,
      };
    }
    travelledM += segmentM;
    target = next;
  }
  return target;
}

export function buildShadowFeatureCollection(
  scene: ShadowSceneResponse | null,
  highConfidence: boolean,
): GeoJSON.FeatureCollection<GeoJSON.Polygon> {
  const polygons = highConfidence
    ? scene?.high_confidence_shadows
    : scene?.shadows;
  return {
    type: "FeatureCollection",
    features:
      polygons?.map((polygon, index) => ({
        type: "Feature" as const,
        properties: { confidence: highConfidence ? "high" : "modeled", index },
        geometry: {
          type: "Polygon" as const,
          coordinates: polygon.rings.map((ring) =>
            ring.map((point) => [point.longitude, point.latitude]),
          ),
        },
      })) ?? [],
  };
}

export function solarStyleLight(
  at: Date,
  coordinate: Coordinate,
): LightSpecification {
  const millisecondsPerDay = 86_400_000;
  const julianDay = at.getTime() / millisecondsPerDay + 2_440_587.5;
  const daysSinceEpoch = julianDay - 2_451_545;
  const meanLongitude = normalizeDegrees(280.46 + 0.9856474 * daysSinceEpoch);
  const meanAnomaly = normalizeDegrees(357.528 + 0.9856003 * daysSinceEpoch);
  const anomalyRadians = degreesToRadians(meanAnomaly);
  const eclipticLongitude = normalizeDegrees(
    meanLongitude +
      1.915 * Math.sin(anomalyRadians) +
      0.02 * Math.sin(2 * anomalyRadians),
  );
  const obliquity = 23.439 - 0.0000004 * daysSinceEpoch;
  const eclipticRadians = degreesToRadians(eclipticLongitude);
  const obliquityRadians = degreesToRadians(obliquity);
  const rightAscension = normalizeDegrees(
    radiansToDegrees(
      Math.atan2(
        Math.cos(obliquityRadians) * Math.sin(eclipticRadians),
        Math.cos(eclipticRadians),
      ),
    ),
  );
  const declination = Math.asin(
    Math.sin(obliquityRadians) * Math.sin(eclipticRadians),
  );
  const siderealTime = normalizeDegrees(
    280.46061837 +
      360.98564736629 * (julianDay - 2_451_545) +
      coordinate.longitude,
  );
  const hourAngle = degreesToRadians(
    normalizeSignedDegrees(siderealTime - rightAscension),
  );
  const latitude = degreesToRadians(coordinate.latitude);
  const elevation = radiansToDegrees(
    Math.asin(
      Math.sin(latitude) * Math.sin(declination) +
        Math.cos(latitude) * Math.cos(declination) * Math.cos(hourAngle),
    ),
  );
  const azimuth = normalizeDegrees(
    radiansToDegrees(
      Math.atan2(
        Math.sin(hourAngle),
        Math.cos(hourAngle) * Math.sin(latitude) -
          Math.tan(declination) * Math.cos(latitude),
      ),
    ) + 180,
  );
  const polarAngle = clamp(90 - elevation, 15, 85);
  const daylight = elevation > 0;
  return {
    anchor: "map",
    position: [1.5, azimuth, polarAngle],
    color: daylight ? (elevation < 12 ? "#FFD5A3" : "#FFF8E7") : "#DCE6FF",
    intensity: daylight ? 0.55 : 0.25,
  };
}

export function bearingNearCoordinate(
  geometry: Coordinate[],
  currentCoordinate: Coordinate | null,
): number {
  let startIndex = 0;
  if (currentCoordinate) {
    let nearestDistance = Number.POSITIVE_INFINITY;
    geometry.forEach((coordinate, index) => {
      const distance = distanceMeters(currentCoordinate, coordinate);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        startIndex = index;
      }
    });
  }
  const first = geometry[startIndex] ?? geometry[0];
  const second = geometry
    .slice(startIndex + 1)
    .find(
      (coordinate) =>
        first &&
        (coordinate.latitude !== first.latitude ||
          coordinate.longitude !== first.longitude),
    );
  if (!first || !second) return 0;
  const latitude1 = degreesToRadians(first.latitude);
  const latitude2 = degreesToRadians(second.latitude);
  const longitudeDelta = degreesToRadians(second.longitude - first.longitude);
  const y = Math.sin(longitudeDelta) * Math.cos(latitude2);
  const x =
    Math.cos(latitude1) * Math.sin(latitude2) -
    Math.sin(latitude1) * Math.cos(latitude2) * Math.cos(longitudeDelta);
  return normalizeDegrees(radiansToDegrees(Math.atan2(y, x)));
}

function degreesToRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function radiansToDegrees(value: number): number {
  return (value * 180) / Math.PI;
}

function normalizeDegrees(value: number): number {
  return ((value % 360) + 360) % 360;
}

function normalizeSignedDegrees(value: number): number {
  return ((value + 540) % 360) - 180;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export const NavizMap = memo(NavizMapComponent);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#E5E7EB" },
  map: { flex: 1 },
  rowReverse: { flexDirection: "row-reverse" },
  mapControls: {
    position: "absolute",
    right: spacing.md,
    top: 112,
    gap: spacing.sm,
  },
  mapControlsWhileNavigating: { top: 172 },
  mapButton: {
    width: 48,
    height: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    ...shadow,
  },
  mapButtonText: { color: colors.primaryDark, fontSize: 24, fontWeight: "800" },
  mapModeButtonText: {
    color: colors.primaryDark,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 0.4,
  },
});
