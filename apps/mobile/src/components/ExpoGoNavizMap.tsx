import { memo, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";
import MapView, { Marker, Polygon, Polyline } from "react-native-maps";

import { decodePolyline } from "../api/polyline";
import type { Coordinate, TravelMode } from "../api/types";
import { colors, radius, shadow, spacing } from "../theme/tokens";
import { NavigationAvatar } from "./NavigationAvatar";
import {
  bearingNearCoordinate,
  navigationBearing,
  navigationMarkerCoordinate,
  type NavizMapProps,
} from "./NavizMap";

const ISRAEL_CENTER: Coordinate = { latitude: 31.7683, longitude: 35.2137 };

function ExpoGoNavizMapComponent({
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
  const mapRef = useRef<MapView>(null);
  const { i18n, t } = useTranslation();
  const rtl = i18n.resolvedLanguage === "he";
  const is3d = displayMode === "3d";
  const selectedRoute =
    routes.find((route) => route.id === selectedRouteId) ?? routes[0] ?? null;
  const selectedGeometry = useMemo(
    () => (selectedRoute ? decodePolyline(selectedRoute.encoded_polyline) : []),
    [selectedRoute],
  );
  const matchedRouteBearing = bearingNearCoordinate(
    selectedGeometry,
    userCoordinate,
  );
  const navigationCourse = navigationBearing(
    matchedRouteBearing,
    userHeadingDegrees,
    navigationActive,
  );
  const routeGeometries = useMemo(
    () =>
      routes.map((route) => ({
        route,
        coordinates: decodePolyline(route.encoded_polyline),
      })),
    [routes],
  );
  const selectedLegs = useMemo(
    () =>
      selectedRoute?.legs
        .map((leg) => ({
          id: `${leg.mode}-${leg.from_name}-${leg.to_name}`,
          mode: leg.mode,
          coordinates: decodePolyline(leg.encoded_polyline),
        }))
        .filter((leg) => leg.coordinates.length >= 2) ?? [],
    [selectedRoute],
  );

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (following && userCoordinate) {
      map.animateCamera(
        {
          center: userCoordinate,
          heading: navigationActive ? navigationCourse : 0,
          pitch: is3d ? 55 : 0,
          zoom: navigationActive ? (is3d ? 17.4 : 16.7) : 15.2,
        },
        { duration: 450 },
      );
      return;
    }

    if (selectedGeometry.length >= 2) {
      map.fitToCoordinates(selectedGeometry, {
        animated: true,
        edgePadding: { top: 116, right: 44, bottom: 300, left: 44 },
      });
    }
  }, [
    following,
    is3d,
    navigationActive,
    selectedGeometry,
    userCoordinate,
    navigationCourse,
  ]);

  const shadowPolygons = shadowScene?.shadows ?? [];
  const verifiedShadowPolygons = shadowScene?.high_confidence_shadows ?? [];
  const avatarHeading = following && navigationActive ? 0 : navigationCourse;
  const avatarCoordinate = navigationMarkerCoordinate(
    selectedGeometry,
    userCoordinate,
  );

  return (
    <View style={styles.container} accessibilityLabel={t("accessibility.map")}>
      <MapView
        ref={mapRef}
        style={styles.map}
        initialRegion={{
          latitude: userCoordinate?.latitude ?? ISRAEL_CENTER.latitude,
          longitude: userCoordinate?.longitude ?? ISRAEL_CENTER.longitude,
          latitudeDelta: userCoordinate ? 0.08 : 4.6,
          longitudeDelta: userCoordinate ? 0.08 : 4.6,
        }}
        pitchEnabled
        rotateEnabled
        showsBuildings
        showsCompass={false}
        showsPointsOfInterests
        showsTraffic={isRoadMode(travelMode)}
        toolbarEnabled={false}
        loadingEnabled
      >
        {is3d
          ? shadowPolygons.map((polygon, index) => (
              <Polygon
                key={`shadow-${index}`}
                coordinates={polygon.rings[0] ?? []}
                holes={polygon.rings.slice(1)}
                fillColor="rgba(38, 54, 77, 0.20)"
                strokeColor="rgba(30, 41, 59, 0.22)"
                strokeWidth={1}
              />
            ))
          : null}
        {is3d
          ? verifiedShadowPolygons.map((polygon, index) => (
              <Polygon
                key={`verified-shadow-${index}`}
                coordinates={polygon.rings[0] ?? []}
                holes={polygon.rings.slice(1)}
                fillColor="rgba(17, 24, 39, 0.24)"
                strokeColor="rgba(17, 24, 39, 0.28)"
                strokeWidth={1}
              />
            ))
          : null}

        {routeGeometries
          .filter(
            ({ route, coordinates }) =>
              route.id !== selectedRoute?.id && coordinates.length >= 2,
          )
          .map(({ route, coordinates }) => (
            <Polyline
              key={`alternative-${route.id}`}
              coordinates={coordinates}
              strokeColor="rgba(100, 116, 139, 0.72)"
              strokeWidth={4}
              lineDashPattern={[10, 7]}
              lineCap="round"
              lineJoin="round"
            />
          ))}

        {selectedGeometry.length >= 2 ? (
          <Polyline
            coordinates={selectedGeometry}
            strokeColor="rgba(255,255,255,0.98)"
            strokeWidth={12}
            lineCap="round"
            lineJoin="round"
          />
        ) : null}
        {selectedLegs.length > 0 ? (
          selectedLegs.map((leg) => (
            <Polyline
              key={leg.id}
              coordinates={leg.coordinates}
              strokeColor={legColor(leg.mode)}
              strokeWidth={7}
              {...(leg.mode === "transit" ? { lineDashPattern: [14, 5] } : {})}
              lineCap="round"
              lineJoin="round"
            />
          ))
        ) : selectedGeometry.length >= 2 ? (
          <Polyline
            coordinates={selectedGeometry}
            strokeColor={legColor(travelMode)}
            strokeWidth={7}
            lineCap="round"
            lineJoin="round"
          />
        ) : null}

        {selectedRoute?.annotations.map((annotation, index) => {
          const coordinates = selectedGeometry.slice(
            annotation.start_index,
            annotation.end_index + 1,
          );
          if (coordinates.length < 2) return null;
          return (
            <Polyline
              key={`annotation-${index}`}
              coordinates={coordinates}
              strokeColor={annotationColor(annotation.classification)}
              strokeWidth={7}
              {...(annotation.classification === "mixed"
                ? { lineDashPattern: [8, 5] }
                : {})}
              lineCap="round"
            />
          );
        })}

        {selectedGeometry.at(-1) ? (
          <Marker
            coordinate={selectedGeometry.at(-1)!}
            anchor={{ x: 0.5, y: 0.5 }}
          >
            <View style={styles.destinationOuter}>
              <View style={styles.destinationInner} />
            </View>
          </Marker>
        ) : null}

        {mobilityVehicles.map((vehicle) => (
          <Marker
            key={vehicle.id}
            coordinate={vehicle.coordinate}
            onPress={() => onMobilityVehiclePress(vehicle)}
            accessibilityLabel={`${vehicle.provider} ${vehicle.kind}`}
          >
            <View style={styles.mobilityMarker}>
              <Text style={styles.mobilityMarkerText}>
                {vehicle.kind.includes("scooter") ? "S" : "B"}
              </Text>
            </View>
          </Marker>
        ))}

        {avatarCoordinate ? (
          <Marker
            coordinate={avatarCoordinate}
            anchor={is3d ? { x: 0.5, y: 0.82 } : { x: 0.5, y: 0.5 }}
            flat={!is3d}
            rotation={avatarHeading}
            accessibilityLabel={
              rtl
                ? `המיקום שלך בניווט ${t(`mode.${travelMode}`)}`
                : `Your ${t(`mode.${travelMode}`)} navigation position`
            }
          >
            <NavigationAvatar
              mode={travelMode}
              displayMode={displayMode}
              active={navigationActive}
            />
          </Marker>
        ) : null}
      </MapView>

      <View
        style={[
          styles.mapControls,
          navigationActive && styles.mapControlsWhileNavigating,
        ]}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("mapDisplayMode")}
          onPress={() => onDisplayModeChange(is3d ? "2d" : "3d")}
          style={styles.mapButton}
        >
          <Text style={styles.modeButtonText}>{is3d ? "2D" : "3D"}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("recenter")}
          onPress={onRecenter}
          style={styles.mapButton}
        >
          <Text style={styles.recenterText}>⌖</Text>
        </Pressable>
        {selectedRoute ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("overview")}
            onPress={onOverview}
            style={styles.mapButton}
          >
            <Text style={styles.overviewText}>▱</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function legColor(mode: TravelMode): string {
  if (mode === "walk") return colors.shade;
  if (mode === "bike" || mode === "scooter") return "#059669";
  if (mode === "transit" || mode.endsWith("_transit")) return "#D946EF";
  if (mode === "motorcycle") return "#7C3AED";
  if (mode === "truck") return "#EA580C";
  return colors.primary;
}

function annotationColor(classification: string): string {
  if (classification === "shade") return colors.shade;
  if (classification === "mixed") return colors.mixed;
  if (classification === "sun") return colors.sun;
  return "rgba(0,0,0,0)";
}

function isRoadMode(mode: TravelMode): boolean {
  return mode === "car" || mode === "motorcycle" || mode === "truck";
}

export const ExpoGoNavizMap = memo(ExpoGoNavizMapComponent);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#E5E7EB" },
  map: { flex: 1 },
  rtlText: { textAlign: "right", writingDirection: "rtl" },
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
  modeButtonText: {
    color: colors.primaryDark,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 0.4,
  },
  recenterText: { color: colors.primaryDark, fontSize: 28, fontWeight: "800" },
  overviewText: { color: colors.primaryDark, fontSize: 25, fontWeight: "800" },
  destinationOuter: {
    width: 23,
    height: 23,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    ...shadow,
  },
  destinationInner: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: "#DC2626",
  },
  mobilityMarker: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 2,
    borderColor: colors.surface,
    backgroundColor: "#059669",
    alignItems: "center",
    justifyContent: "center",
    ...shadow,
  },
  mobilityMarkerText: { color: colors.surface, fontWeight: "900" },
});
