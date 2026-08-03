import { useMutation, useQuery } from "@tanstack/react-query";
import { useMachine } from "@xstate/react";
import * as Haptics from "expo-haptics";
import * as Location from "expo-location";
import * as Speech from "expo-speech";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ApiError, getDataStatus, planRoute, reroute, searchPlaces } from "../src/api/client";
import { decodePolyline } from "../src/api/polyline";
import type { Coordinate, RoutePlanRequest } from "../src/api/types";
import { NavigationHud } from "../src/components/NavigationHud";
import { NavizMap } from "../src/components/NavizMap";
import { RouteCards } from "../src/components/RouteCards";
import { SearchPanel } from "../src/components/SearchPanel";
import { StatusBanner } from "../src/components/StatusBanner";
import {
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

const DEMO_ORIGIN: Coordinate = { latitude: 32.0733, longitude: 34.7799 };

export default function HomeScreen() {
  const { t } = useTranslation();
  const [state, send] = useMachine(navigationMachine);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [origin, setOrigin] = useState<Coordinate>(DEMO_ORIGIN);
  const [userCoordinate, setUserCoordinate] = useState<Coordinate | null>(null);
  const [following, setFollowing] = useState(false);
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

  useEffect(() => {
    void Location.getForegroundPermissionsAsync().then(async (permission) => {
      if (permission.status !== "granted") return;
      const location = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const coordinate = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      };
      setOrigin(coordinate);
      setUserCoordinate(coordinate);
    });
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
    queryKey: ["places", debouncedQuery, locale, origin],
    queryFn: () => searchPlaces(debouncedQuery, locale, origin),
    enabled: debouncedQuery.length > 0 && state.matches("idle"),
  });

  const buildRequest = useCallback(
    (currentOrigin = origin): RoutePlanRequest => ({
      origin: currentOrigin,
      destination: state.context.destination!.coordinate,
      depart_at: new Date().toISOString(),
      locale,
      mode,
      preference,
      vehicle: { kind: vehicleKind, can_fold: vehicleKind === "folding_bike" },
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
    [locale, mode, origin, preference, state.context.destination, vehicleKind],
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
      setOfflineContinuation(false);
    },
    onError: (error) => {
      send({ type: "FAIL", message: readableError(error) });
    },
  });

  const selectedRoute = useMemo(
    () =>
      state.context.routes.find((route) => route.id === state.context.selectedRouteId) ??
      state.context.routes[0] ??
      null,
    [state.context.routes, state.context.selectedRouteId],
  );

  const rerouteMutation = useMutation({
    mutationFn: async ({ coordinate, location }: { coordinate: Coordinate; location: Location.LocationObject }) => {
      if (!selectedRoute || !state.context.destination) throw new Error("No active route");
      const request = buildRequest(coordinate);
      const { origin: _origin, ...remaining } = request;
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
        tracker.current = new ProgressTracker(decodePolyline(route.encoded_polyline));
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
      send({ type: "REROUTE_UNAVAILABLE", message: readableError(error) });
    },
  });

  const mutateReroute = rerouteMutation.mutate;
  const navigating = state.matches("navigating");
  const recalculating = state.matches("recalculating");
  const offline = state.matches("offline");

  useEffect(() => {
    if (!navigating && !recalculating && !offline) return;
    let subscription: Location.LocationSubscription | null = null;
    void Location.watchPositionAsync(
      {
        accuracy: Location.Accuracy.BestForNavigation,
        distanceInterval: 5,
        timeInterval: 2_000,
      },
      (location) => {
        const coordinate = {
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
        };
        setUserCoordinate(coordinate);
        const progress = tracker.current?.update({
          coordinate,
          accuracyM: location.coords.accuracy ?? 15,
          headingDegrees: location.coords.heading,
        });
        if (!progress || !selectedRoute) return;
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
          );
          if (message) Speech.speak(message, { language: locale === "he" ? "he-IL" : "en-US" });
          void Haptics.selectionAsync();
        }
        if (progress.arrived) {
          send({ type: "ARRIVE" });
          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          Speech.speak(t("status.arrived"), { language: locale === "he" ? "he-IL" : "en-US" });
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
    ).then((value) => {
      subscription = value;
    });
    return () => subscription?.remove();
  }, [locale, mutateReroute, navigating, offline, recalculating, selectedRoute, send, t]);

  const plan = () => {
    if (!state.context.destination) {
      Alert.alert(t("error.title"), t("error.noDestination"));
      return;
    }
    send({ type: "PLAN" });
    routeMutation.mutate(buildRequest());
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
    const points = decodePolyline(selectedRoute.encoded_polyline);
    tracker.current = points.length >= 2 ? new ProgressTracker(points) : null;
    lastSpokenManeuver.current = -1;
    await startBackgroundNavigation();
    setFollowing(true);
    send({ type: "START" });
  };

  const stop = async () => {
    Speech.stop();
    await stopBackgroundNavigation();
    await clearCachedRoute();
    setFollowing(false);
    tracker.current = null;
    send({ type: "STOP" });
  };

  const planning = state.matches("planning");
  const active = navigating || recalculating || offline || state.matches("arrived");

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <View style={styles.container}>
        <NavizMap route={selectedRoute} userCoordinate={userCoordinate} following={following} />
        {state.matches("idle") || planning || state.matches("error") ? (
          <SearchPanel
            query={query}
            onQueryChange={setQuery}
            results={search.data?.results ?? []}
            recent={recent}
            favorites={favorites}
            selectedDestination={state.context.destination}
            onSelect={(destination) => {
              send({ type: "DESTINATION_SELECTED", destination });
              setQuery(rtl ? (destination.name_he ?? destination.name) : destination.name);
              addRecent(destination);
            }}
            mode={mode}
            onModeChange={setMode}
            preference={preference}
            onPreferenceChange={setPreference}
            onPlan={plan}
            onCancel={cancelPlanning}
            searching={search.isFetching}
            planning={planning}
            locale={locale}
            onLocaleToggle={() => setLocale(locale === "he" ? "en" : "he")}
            onToggleFavorite={toggleFavorite}
          />
        ) : null}
        {(state.matches("preview") || state.matches("permissionDenied")) && selectedRoute ? (
          <RouteCards
            routes={state.context.routes}
            selectedRouteId={state.context.selectedRouteId}
            onSelect={(route) => send({ type: "SELECT_ROUTE", routeId: route.id })}
            onStart={() => void start()}
            rtl={rtl}
          />
        ) : null}
        {active && selectedRoute ? (
          <NavigationHud
            route={selectedRoute}
            maneuverIndex={state.context.maneuverIndex}
            rtl={rtl}
            recalculating={state.matches("recalculating")}
            arrived={state.matches("arrived")}
            onStop={() => void stop()}
          />
        ) : null}
        {state.context.engineWarming ? (
          <StatusBanner message={t("status.warming")} tone="warning" rtl={rtl} />
        ) : null}
        {offlineContinuation ? (
          <StatusBanner message={t("status.offline")} tone="warning" rtl={rtl} />
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
            onAction={plan}
            rtl={rtl}
          />
        ) : null}
        {!active && !state.context.engineWarming ? (
          <StatusBanner message={t("status.demo")} tone="warning" rtl={rtl} />
        ) : null}
      </View>
    </SafeAreaView>
  );
}

function readableError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unable to calculate a route";
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#111827" },
  container: { flex: 1 },
});
