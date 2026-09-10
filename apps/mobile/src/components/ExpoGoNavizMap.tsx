import { memo, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";
import MapView, { Marker, Polygon, Polyline } from "react-native-maps";

import { decodePolyline } from "../api/polyline";
import type { Coordinate, TravelMode } from "../api/types";
import { colors, radius, shadow, spacing } from "../theme/tokens";
import type { NavizMapProps } from "./NavizMap";

const ISRAEL_CENTER: Coordinate = { latitude: 31.7683, longitude: 35.2137 };

function ExpoGoNavizMapComponent({
  routes,
  selectedRouteId,
  userCoordinate,
  userHeadingDegrees,
  displayMode,
  shadowScene,
  shadowLoading,
  mobilityVehicles,
  following,
  navigationActive,
  travelMode,
  onRecenter,
  onOverview,
  onDisplayModeChange,
  onShadowTimeShift,
  onShadowTimeReset,
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
          heading: navigationActive
            ? validHeading(userHeadingDegrees)
              ? userHeadingDegrees
              : routeBearing(selectedGeometry)
            : 0,
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
    userHeadingDegrees,
  ]);

  const shadowPolygons = shadowScene?.shadows ?? [];
  const verifiedShadowPolygons = shadowScene?.high_confidence_shadows ?? [];
  const avatarHeading = following && navigationActive
    ? 0
    : validHeading(userHeadingDegrees)
      ? userHeadingDegrees
      : routeBearing(selectedGeometry);

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
          .filter(({ route, coordinates }) =>
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
        {selectedLegs.length > 0
          ? selectedLegs.map((leg) => (
              <Polyline
                key={leg.id}
                coordinates={leg.coordinates}
                strokeColor={legColor(leg.mode)}
                strokeWidth={7}
                {...(leg.mode === "transit"
                  ? { lineDashPattern: [14, 5] }
                  : {})}
                lineCap="round"
                lineJoin="round"
              />
            ))
          : selectedGeometry.length >= 2
            ? (
                <Polyline
                  coordinates={selectedGeometry}
                  strokeColor={legColor(travelMode)}
                  strokeWidth={7}
                  lineCap="round"
                  lineJoin="round"
                />
              )
            : null}

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
          <Marker coordinate={selectedGeometry.at(-1)!} anchor={{ x: 0.5, y: 0.5 }}>
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

        {userCoordinate ? (
          <Marker
            coordinate={userCoordinate}
            anchor={{ x: 0.5, y: 0.5 }}
            flat
            rotation={avatarHeading}
            accessibilityLabel={
              rtl
                ? `המיקום שלך בניווט ${t(`mode.${travelMode}`)}`
                : `Your ${t(`mode.${travelMode}`)} navigation position`
            }
          >
            <NavigationAvatar mode={travelMode} active={navigationActive} />
          </Marker>
        ) : null}
      </MapView>

      {is3d && (shadowLoading || shadowScene?.available) ? (
        <View style={styles.shadowPanel}>
          <Text style={[styles.shadowLabel, rtl && styles.rtlText]} numberOfLines={2}>
            {shadowLoading
              ? t("shadow3d.loading")
              : t("shadow3d.scene", {
                  value: new Date(shadowScene!.at).toLocaleTimeString(
                    rtl ? "he-IL" : "en-IL",
                    { hour: "2-digit", minute: "2-digit" },
                  ),
                })}
          </Text>
          <View style={[styles.shadowButtons, rtl && styles.rowReverse]}>
            <SmallButton
              label="−15"
              accessibilityLabel={t("shadow3d.earlier")}
              onPress={() => onShadowTimeShift(-15)}
            />
            <SmallButton
              label={t("shadow3d.reset")}
              accessibilityLabel={t("shadow3d.resetTime")}
              onPress={onShadowTimeReset}
              wide
            />
            <SmallButton
              label="+15"
              accessibilityLabel={t("shadow3d.later")}
              onPress={() => onShadowTimeShift(15)}
            />
          </View>
        </View>
      ) : null}

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

function SmallButton({
  label,
  accessibilityLabel,
  onPress,
  wide = false,
}: {
  label: string;
  accessibilityLabel: string;
  onPress: () => void;
  wide?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={onPress}
      style={[styles.smallButton, wide && styles.smallButtonWide]}
    >
      <Text style={styles.smallButtonText} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

function NavigationAvatar({ mode, active }: { mode: TravelMode; active: boolean }) {
  const kind = avatarKind(mode);
  const color = legColor(mode);
  return (
    <View style={[styles.avatar, !active && styles.avatarIdle]}>
      <View style={[styles.avatarHalo, { borderColor: color }]} />
      <View style={[styles.avatarNose, { borderBottomColor: color }]} />
      {kind === "person" ? (
        <View style={styles.person}>
          <View style={[styles.personHead, { backgroundColor: color }]} />
          <View style={[styles.personBody, { backgroundColor: color }]} />
          <View style={styles.personLegs}>
            <View style={[styles.personLeg, { backgroundColor: color }]} />
            <View style={[styles.personLeg, { backgroundColor: color }]} />
          </View>
        </View>
      ) : kind === "two_wheeler" ? (
        <View style={styles.twoWheeler}>
          <View style={[styles.wheel, { borderColor: color }]} />
          <View style={[styles.twoWheelerBody, { backgroundColor: color }]} />
          <View style={[styles.wheel, { borderColor: color }]} />
        </View>
      ) : (
        <View
          style={[
            styles.vehicle,
            kind === "truck" && styles.truck,
            kind === "transit" && styles.transit,
            { backgroundColor: color },
          ]}
        >
          <View style={styles.windshield} />
          <View style={styles.headlights}>
            <View style={styles.headlight} />
            <View style={styles.headlight} />
          </View>
        </View>
      )}
    </View>
  );
}

function avatarKind(mode: TravelMode) {
  if (mode === "walk") return "person";
  if (mode === "bike" || mode === "scooter" || mode === "motorcycle") {
    return "two_wheeler";
  }
  if (mode === "truck") return "truck";
  if (mode === "transit" || mode.endsWith("_transit")) return "transit";
  return "car";
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

function validHeading(value: number | null): value is number {
  return value !== null && Number.isFinite(value) && value >= 0;
}

function routeBearing(geometry: Coordinate[]): number {
  const first = geometry[0];
  const second = geometry.find(
    (point, index) =>
      index > 0 &&
      first &&
      (point.latitude !== first.latitude || point.longitude !== first.longitude),
  );
  if (!first || !second) return 0;
  const lat1 = (first.latitude * Math.PI) / 180;
  const lat2 = (second.latitude * Math.PI) / 180;
  const deltaLongitude = ((second.longitude - first.longitude) * Math.PI) / 180;
  const y = Math.sin(deltaLongitude) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLongitude);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
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
  shadowPanel: {
    position: "absolute",
    top: 112,
    left: spacing.md,
    maxWidth: 236,
    padding: spacing.xs,
    gap: spacing.xs,
    borderRadius: radius.md,
    backgroundColor: "rgba(255,255,255,0.94)",
    ...shadow,
  },
  shadowLabel: {
    color: colors.ink,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: "800",
    paddingHorizontal: spacing.xs,
  },
  shadowButtons: { flexDirection: "row", gap: spacing.xs },
  smallButton: {
    minWidth: 48,
    minHeight: 44,
    paddingHorizontal: spacing.xs,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceElevated,
    alignItems: "center",
    justifyContent: "center",
  },
  smallButtonWide: { flex: 1 },
  smallButtonText: { color: colors.ink, fontSize: 11, fontWeight: "900" },
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
  avatar: { width: 54, height: 54, alignItems: "center", justifyContent: "center" },
  avatarIdle: { transform: [{ scale: 0.84 }] },
  avatarHalo: {
    position: "absolute",
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 3,
    backgroundColor: "rgba(255,255,255,0.92)",
    ...shadow,
  },
  avatarNose: {
    position: "absolute",
    top: -2,
    width: 0,
    height: 0,
    borderLeftWidth: 7,
    borderRightWidth: 7,
    borderBottomWidth: 12,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
  },
  person: { alignItems: "center", gap: 1 },
  personHead: { width: 9, height: 9, borderRadius: 5 },
  personBody: { width: 9, height: 14, borderRadius: 4 },
  personLegs: { flexDirection: "row", gap: 3 },
  personLeg: { width: 3, height: 8, borderRadius: 2 },
  twoWheeler: { alignItems: "center", gap: 1 },
  wheel: { width: 13, height: 13, borderRadius: 7, borderWidth: 3 },
  twoWheelerBody: { width: 5, height: 11, borderRadius: 3 },
  vehicle: {
    width: 22,
    height: 31,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: colors.surface,
    alignItems: "center",
    paddingTop: 4,
  },
  truck: { width: 25, height: 34, borderRadius: 5 },
  transit: { width: 26, height: 35, borderRadius: 6 },
  windshield: {
    width: 14,
    height: 7,
    borderRadius: 3,
    backgroundColor: "rgba(224,242,254,0.94)",
  },
  headlights: {
    position: "absolute",
    top: 1,
    left: 3,
    right: 3,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  headlight: { width: 4, height: 3, borderRadius: 2, backgroundColor: "#FEF08A" },
});
