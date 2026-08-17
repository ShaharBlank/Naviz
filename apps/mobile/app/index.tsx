import { useMutation, useQuery } from "@tanstack/react-query";
import { useMachine } from "@xstate/react";
import * as Haptics from "expo-haptics";
import * as Location from "expo-location";
import * as Speech from "expo-speech";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, Linking, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  ApiError,
  getDataStatus,
  getMobilityVehicles,
  planRoute,
  reroute,
  searchPlaces,
} from "../src/api/client";
import { decodePolyline } from "../src/api/polyline";
import type {
  Coordinate,
  MobilityVehicle,
  RoutePlanRequest,
} from "../src/api/types";
import { NavigationHud } from "../src/components/NavigationHud";
import { NavizMap } from "../src/components/NavizMap";
import { RouteCards } from "../src/components/RouteCards";
import {
  SearchPanel,
  type LocationStatus,
} from "../src/components/SearchPanel";
import { StatusBanner } from "../src/components/StatusBanner";
import {
  requestBackgroundNavigationPermission,
  requestNavigationPermission,
  startBackgroundNavigation,
  stopBackgroundNavigation,
} from "../src/features/navigation/backgroundLocation";
import { navigationMachine } from "../src/features/navigation/navigationMachine";
import { usePreferences } from "../src/features/navigation/preferencesStore";
import { maneuverText } from "../src/features/navigation/presenters";
import { ProgressTracker } from "../src/features/navigation/progressTracker";
import {
  cacheRoute,
  clearCachedRoute,
  loadCachedRoute,
} from "../src/features/navigation/routeCache";

const METRO_BBOX = { west: 34.69, south: 31.94, east: 34.93, north: 32.2 };
const TEL_AVIV_CENTER = { latitude: 32.0733, longitude: 34.7799 };

export default function HomeScreen() {
  const { t } = useTranslation();
  const [state, send] = useMachine(navigationMachine);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [origin, setOrigin] = useState<Coordinate | null>(null);
  const [userCoordinate, setUserCoordinate] = useState<Coordinate | null>(null);
  const [locationStatus, setLocationStatus] = useState<LocationStatus>("idle");
  const [following, setFollowing] = useState(false);
  const [muted, setMuted] = useState(false);
  const [backgroundEnabled, setBackgroundEnabled] = useState(true);
  const [remainingDistanceM, setRemainingDistanceM] = useState<number | null>(
    null,
  );
  const [progressFraction, setProgressFraction] = useState(0);
  const [offlineContinuation, setOfflineContinuation] = useState(false);
  const tracker = useRef<ProgressTracker | null>(null);
  const rerouting = useRef(false);
  const rerouteAfter = useRef(0);
  const lastSpokenManeuver = useRef(-1);
  const planningAbort = useRef<AbortController | null>(null);

  const {
    locale,
    mode,
    preference,
    vehicleKind,
    setLocale,
    setMode,
    setPreference,
    addRecent,
    recent,
    favorites,
    toggleFavorite,
  } = usePreferences();
  const rtl = locale === "he";

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 280);
    return () => clearTimeout(timer);
  }, [query]);

  const locateUser = useCallback(
    async (requestPermission: boolean): Promise<Coordinate | null> => {
      setLocationStatus("locating");
      try {
        let permission = await Location.getForegroundPermissionsAsync();
        if (permission.status !== "granted" && requestPermission) {
          permission = await Location.requestForegroundPermissionsAsync();
        }
        if (permission.status !== "granted") {
          setLocationStatus(requestPermission ? "denied" : "idle");
          return null;
        }
        const lastKnown = await Location.getLastKnownPositionAsync({
          maxAge: 60_000,
          requiredAccuracy: 200,
        });
        if (lastKnown)
          updateLocation(
            lastKnown,
            setOrigin,
            setUserCoordinate,
            setLocationStatus,
          );
        try {
          const current = await withTimeout(
            Location.getCurrentPositionAsync({
              accuracy: Location.Accuracy.High,
            }),
            12_000,
          );
          updateLocation(
            current,
            setOrigin,
            setUserCoordinate,
            setLocationStatus,
          );
          return toCoordinate(current);
        } catch {
          if (lastKnown) return toCoordinate(lastKnown);
          setLocationStatus("unavailable");
          return null;
        }
      } catch {
        setLocationStatus("unavailable");
        return null;
      }
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    void Location.getForegroundPermissionsAsync().then(async (permission) => {
      if (permission.status !== "granted") return;
      const lastKnown = await Location.getLastKnownPositionAsync({
        maxAge: 60_000,
        requiredAccuracy: 200,
      });
      if (!cancelled && lastKnown) {
        updateLocation(
          lastKnown,
          setOrigin,
          setUserCoordinate,
          setLocationStatus,
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void getDataStatus().catch(async () => {
      const route = await loadCachedRoute();
      if (!route) return;
      const coordinate = decodePolyline(route.encoded_polyline).at(-1);
      if (!coordinate) return;
      send({
        type: "RESTORE",
        route,
        destination: {
          id: `cached:${route.id}`,
          name: "Saved destination",
          name_he: "יעד שמור",
          subtitle: null,
          coordinate,
          category: "cached",
          confidence: "unknown",
        },
      });
      setQuery(locale === "he" ? "יעד שמור" : "Saved destination");
      setOfflineContinuation(true);
    });
  }, [locale, send]);

  const search = useQuery({
    queryKey: [
      "places",
      debouncedQuery,
      locale,
      origin?.latitude,
      origin?.longitude,
    ],
    queryFn: () => searchPlaces(debouncedQuery, locale, origin ?? undefined),
    enabled: debouncedQuery.length > 0 && state.matches("idle"),
    retry: 1,
  });

  const mobilityCenter = userCoordinate ?? origin ?? TEL_AVIV_CENTER;
  const mobility = useQuery({
    queryKey: [
      "mobility",
      mobilityCenter.latitude.toFixed(3),
      mobilityCenter.longitude.toFixed(3),
    ],
    queryFn: () => getMobilityVehicles(mobilityCenter),
    enabled: mode === "rental_transit",
    staleTime: 20_000,
    refetchInterval: 30_000,
    retry: 1,
  });

  const openMobilityVehicle = useCallback(
    async (vehicle: MobilityVehicle) => {
      if (!vehicle.deep_link) {
        Alert.alert(t("mobility.title"), t("mobility.noDeepLink"));
        return;
      }
      try {
        await Linking.openURL(vehicle.deep_link);
      } catch {
        Alert.alert(t("mobility.title"), t("mobility.openError"));
      }
    },
    [t],
  );

  const buildRequest = useCallback(
    (currentOrigin: Coordinate): RoutePlanRequest => ({
      origin: currentOrigin,
      destination: state.context.destination!.coordinate,
      depart_at: new Date().toISOString(),
      locale,
      mode,
      preference,
      include_comparisons: true,
      vehicle: {
        kind: vehicleKind,
        can_fold:
          vehicleKind === "folding_bike" || vehicleKind === "personal_scooter",
      },
      accessibility: {
        avoid_stairs: false,
        require_step_free: false,
        maximum_carry_distance_m: 500,
      },
      constraints: {
        maximum_time_detour_percent: null,
        maximum_distance_detour_percent: null,
        allow_low_confidence_crossings: false,
      },
    }),
    [locale, mode, preference, state.context.destination, vehicleKind],
  );

  const routeMutation = useMutation({
    mutationFn: async (request: RoutePlanRequest) => {
      const controller = new AbortController();
      planningAbort.current = controller;
      const warmingTimer = setTimeout(() => send({ type: "WARMING" }), 2_500);
      try {
        return await planRoute(request, controller.signal);
      } finally {
        clearTimeout(warmingTimer);
        if (planningAbort.current === controller) planningAbort.current = null;
      }
    },
    onSuccess: (response) => {
      send({ type: "ROUTES_READY", routes: response.routes });
      if (response.routes[0]) void cacheRoute(response.routes[0]);
      setRemainingDistanceM(response.routes[0]?.metrics.distance_m ?? null);
      setProgressFraction(0);
      setFollowing(false);
      setOfflineContinuation(false);
    },
    onError: (error) => {
      send({
        type: "FAIL",
        message: readableError(error, (key) => String(t(key))),
      });
    },
  });

  const selectedRoute = useMemo(
    () =>
      state.context.routes.find(
        (route) => route.id === state.context.selectedRouteId,
      ) ??
      state.context.routes[0] ??
      null,
    [state.context.routes, state.context.selectedRouteId],
  );

  const rerouteMutation = useMutation({
    mutationFn: async ({
      coordinate,
      location,
    }: {
      coordinate: Coordinate;
      location: Location.LocationObject;
    }) => {
      if (!selectedRoute || !state.context.destination)
        throw new Error("No active route");
      const request = buildRequest(coordinate);
      const {
        origin: _origin,
        include_comparisons: _includeComparisons,
        ...remaining
      } = request;
      return reroute({
        ...remaining,
        current_position: coordinate,
        original_route_id: selectedRoute.id,
        ...(location.coords.heading !== null
          ? { heading_degrees: location.coords.heading }
          : {}),
        ...(location.coords.accuracy !== null
          ? { accuracy_m: location.coords.accuracy }
          : {}),
      });
    },
    onSuccess: (response) => {
      const route = response.routes[0];
      if (route) {
        tracker.current = new ProgressTracker(
          decodePolyline(route.encoded_polyline),
        );
        setRemainingDistanceM(route.metrics.distance_m);
        setProgressFraction(0);
        void cacheRoute(route);
      }
      send({ type: "ROUTES_READY", routes: response.routes });
      rerouting.current = false;
      rerouteAfter.current = 0;
      setOfflineContinuation(false);
    },
    onError: (error) => {
      rerouting.current = false;
      rerouteAfter.current = Date.now() + 30_000;
      setOfflineContinuation(true);
      send({
        type: "REROUTE_UNAVAILABLE",
        message: readableError(error, (key) => String(t(key))),
      });
    },
  });

  const mutateReroute = rerouteMutation.mutate;
  const navigating = state.matches("navigating");
  const recalculating = state.matches("recalculating");
  const offline = state.matches("offline");

  useEffect(() => {
    if (!navigating && !recalculating && !offline) return;
    let cancelled = false;
    let subscription: Location.LocationSubscription | null = null;
    void Location.watchPositionAsync(
      {
        accuracy: Location.Accuracy.BestForNavigation,
        distanceInterval: 5,
        timeInterval: 2_000,
      },
      (location) => {
        const coordinate = toCoordinate(location);
        setUserCoordinate(coordinate);
        setOrigin(coordinate);
        setLocationStatus("ready");
        const progress = tracker.current?.update({
          coordinate,
          accuracyM: location.coords.accuracy ?? 15,
          headingDegrees: location.coords.heading,
        });
        if (!progress || !selectedRoute) return;
        setRemainingDistanceM(progress.remainingDistanceM);
        setProgressFraction(progress.progressFraction);
        const maneuverIndex = Math.max(
          0,
          selectedRoute.maneuvers.findLastIndex(
            (maneuver) => maneuver.geometry_index <= progress.geometryIndex,
          ),
        );
        send({ type: "ADVANCE", maneuverIndex });
        if (maneuverIndex !== lastSpokenManeuver.current) {
          lastSpokenManeuver.current = maneuverIndex;
          const message = maneuverText(
            selectedRoute.maneuvers[maneuverIndex],
            (key, values) => String(t(key, values ?? {})),
            locale === "en",
          );
          if (message && !muted) {
            Speech.speak(message, {
              language: locale === "he" ? "he-IL" : "en-US",
            });
          }
          void Haptics.selectionAsync();
        }
        if (progress.arrived) {
          send({ type: "ARRIVE" });
          void Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
          if (!muted) {
            Speech.speak(t("status.arrived"), {
              language: locale === "he" ? "he-IL" : "en-US",
            });
          }
          void stopBackgroundNavigation();
        } else if (
          progress.offRoute &&
          !rerouting.current &&
          Date.now() >= rerouteAfter.current
        ) {
          rerouting.current = true;
          send({ type: "OFF_ROUTE" });
          mutateReroute({ coordinate, location });
        }
      },
    )
      .then((value) => {
        if (cancelled) value.remove();
        else subscription = value;
      })
      .catch(() => setOfflineContinuation(true));
    return () => {
      cancelled = true;
      subscription?.remove();
    };
  }, [
    locale,
    muted,
    mutateReroute,
    navigating,
    offline,
    recalculating,
    selectedRoute,
    send,
    t,
  ]);

  const plan = async () => {
    if (!state.context.destination) {
      Alert.alert(t("error.title"), t("error.noDestination"));
      return;
    }
    // A route must start from a current fix. The map can keep displaying the
    // last known marker while idle, but it must never silently become the
    // origin of a later trip after the user has moved.
    const currentOrigin = await locateUser(true);
    if (!currentOrigin) {
      Alert.alert(t("error.title"), t("error.locationUnavailable"));
      return;
    }
    if (!insideMetroCoverage(currentOrigin)) {
      Alert.alert(t("error.title"), t("error.outsideCoverage"));
      return;
    }
    send({ type: "PLAN" });
    routeMutation.mutate(buildRequest(currentOrigin));
  };

  const cancelPlanning = () => {
    planningAbort.current?.abort();
    planningAbort.current = null;
    routeMutation.reset();
    send({ type: "STOP" });
  };

  const start = async () => {
    if (!selectedRoute) return;
    if (!(await requestNavigationPermission())) {
      send({ type: "PERMISSION_DENIED" });
      Alert.alert(t("error.title"), t("error.permission"));
      return;
    }
    const current = await locateUser(false);
    if (!current) {
      Alert.alert(t("error.title"), t("error.locationUnavailable"));
      return;
    }
    const points = decodePolyline(selectedRoute.encoded_polyline);
    tracker.current = points.length >= 2 ? new ProgressTracker(points) : null;
    lastSpokenManeuver.current = -1;
    setRemainingDistanceM(selectedRoute.metrics.distance_m);
    setProgressFraction(0);
    let backgroundGranted = false;
    try {
      backgroundGranted = await requestBackgroundNavigationPermission();
      if (backgroundGranted)
        backgroundGranted = await startBackgroundNavigation();
    } catch {
      backgroundGranted = false;
    }
    setBackgroundEnabled(backgroundGranted);
    setFollowing(true);
    send({ type: "START" });
  };

  const stop = async () => {
    Speech.stop();
    await stopBackgroundNavigation();
    await clearCachedRoute();
    setFollowing(false);
    setBackgroundEnabled(true);
    setRemainingDistanceM(null);
    setProgressFraction(0);
    tracker.current = null;
    send({ type: "STOP" });
  };

  const resetPreview = () => {
    setFollowing(false);
    setQuery("");
    setRemainingDistanceM(null);
    send({ type: "STOP" });
  };

  const centerOnUser = async () => {
    const coordinate = userCoordinate ?? (await locateUser(true));
    if (coordinate) setFollowing(true);
  };

  const planning = state.matches("planning");
  const active =
    navigating || recalculating || offline || state.matches("arrived");

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <View style={styles.container}>
        <NavizMap
          route={selectedRoute}
          userCoordinate={userCoordinate}
          mobilityVehicles={
            mode === "rental_transit" ? (mobility.data?.vehicles ?? []) : []
          }
          following={following}
          onRecenter={() => void centerOnUser()}
          onOverview={() => setFollowing(false)}
          onMobilityVehiclePress={(vehicle) =>
            void openMobilityVehicle(vehicle)
          }
        />
        {state.matches("idle") || planning || state.matches("error") ? (
          <SearchPanel
            query={query}
            onQueryChange={setQuery}
            onClear={() => setQuery("")}
            results={search.data?.results ?? []}
            recent={recent}
            favorites={favorites}
            selectedDestination={state.context.destination}
            onSelect={(destination) => {
              send({ type: "DESTINATION_SELECTED", destination });
              setQuery(
                rtl
                  ? (destination.name_he ?? destination.name)
                  : destination.name,
              );
              addRecent(destination);
            }}
            mode={mode}
            onModeChange={setMode}
            preference={preference}
            onPreferenceChange={setPreference}
            onPlan={() => void plan()}
            onCancel={cancelPlanning}
            onUseCurrentLocation={() => void centerOnUser()}
            locationStatus={locationStatus}
            searching={search.isFetching}
            searchError={search.isError}
            planning={planning}
            locale={locale}
            onLocaleToggle={() => setLocale(locale === "he" ? "en" : "he")}
            onToggleFavorite={toggleFavorite}
            mobilityCount={
              mode === "rental_transit" && mobility.isFetching && !mobility.data
                ? null
                : (mobility.data?.vehicles.length ?? 0)
            }
          />
        ) : null}
        {(state.matches("preview") || state.matches("permissionDenied")) &&
        selectedRoute ? (
          <RouteCards
            routes={state.context.routes}
            selectedRouteId={state.context.selectedRouteId}
            onSelect={(route) =>
              send({ type: "SELECT_ROUTE", routeId: route.id })
            }
            onStart={() => void start()}
            onBack={resetPreview}
            rtl={rtl}
          />
        ) : null}
        {active && selectedRoute ? (
          <NavigationHud
            route={selectedRoute}
            maneuverIndex={state.context.maneuverIndex}
            rtl={rtl}
            locale={locale}
            remainingDistanceM={remainingDistanceM}
            progressFraction={progressFraction}
            muted={muted}
            recalculating={state.matches("recalculating")}
            arrived={state.matches("arrived")}
            onToggleMute={() => {
              Speech.stop();
              setMuted((value) => !value);
            }}
            onStop={() => void stop()}
          />
        ) : null}
        {state.context.engineWarming ? (
          <StatusBanner
            message={t("status.warming")}
            tone="warning"
            rtl={rtl}
          />
        ) : null}
        {offlineContinuation ? (
          <StatusBanner
            message={t("status.offline")}
            tone="warning"
            rtl={rtl}
          />
        ) : null}
        {active && !backgroundEnabled && !offlineContinuation ? (
          <StatusBanner
            message={t("status.keepOpen")}
            tone="warning"
            rtl={rtl}
          />
        ) : null}
        {state.matches("permissionDenied") ? (
          <StatusBanner
            message={t("error.permission")}
            tone="error"
            actionLabel={t("retry")}
            onAction={() => send({ type: "RETRY" })}
            rtl={rtl}
          />
        ) : null}
        {state.matches("error") ? (
          <StatusBanner
            message={state.context.error ?? t("error.generic")}
            tone="error"
            actionLabel={t("retry")}
            onAction={() => void plan()}
            rtl={rtl}
          />
        ) : null}
      </View>
    </SafeAreaView>
  );
}

function readableError(
  error: unknown,
  translate: (key: string) => string,
): string {
  if (error instanceof ApiError) {
    const key = `error.code.${error.code}`;
    const translated = translate(key);
    return translated === key ? translate("error.generic") : translated;
  }
  return translate("error.generic");
}

function toCoordinate(location: Location.LocationObject): Coordinate {
  return {
    latitude: location.coords.latitude,
    longitude: location.coords.longitude,
  };
}

function updateLocation(
  location: Location.LocationObject,
  setOrigin: (value: Coordinate) => void,
  setUserCoordinate: (value: Coordinate) => void,
  setStatus: (value: LocationStatus) => void,
) {
  const coordinate = toCoordinate(location);
  setOrigin(coordinate);
  setUserCoordinate(coordinate);
  setStatus("ready");
}

function insideMetroCoverage(coordinate: Coordinate): boolean {
  return (
    coordinate.longitude >= METRO_BBOX.west &&
    coordinate.longitude <= METRO_BBOX.east &&
    coordinate.latitude >= METRO_BBOX.south &&
    coordinate.latitude <= METRO_BBOX.north
  );
}

async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timeout = setTimeout(
          () => reject(new Error("Location timeout")),
          timeoutMs,
        );
      }),
    ]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#111827" },
  container: { flex: 1 },
});
