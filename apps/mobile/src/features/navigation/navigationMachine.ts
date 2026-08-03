import { assign, setup } from "xstate";

import type { Place, RouteAlternative } from "../../api/types";

interface NavigationContext {
  destination: Place | null;
  routes: RouteAlternative[];
  selectedRouteId: string | null;
  maneuverIndex: number;
  error: string | null;
  engineWarming: boolean;
}

type NavigationEvent =
  | { type: "DESTINATION_SELECTED"; destination: Place }
  | { type: "RESTORE"; destination: Place; route: RouteAlternative }
  | { type: "PLAN" }
  | { type: "WARMING" }
  | { type: "ROUTES_READY"; routes: RouteAlternative[] }
  | { type: "SELECT_ROUTE"; routeId: string }
  | { type: "START" }
  | { type: "PERMISSION_DENIED" }
  | { type: "ADVANCE"; maneuverIndex: number }
  | { type: "OFF_ROUTE" }
  | { type: "REROUTE_UNAVAILABLE"; message: string }
  | { type: "ARRIVE" }
  | { type: "FAIL"; message: string }
  | { type: "RETRY" }
  | { type: "STOP" };

export const navigationMachine = setup({
  types: {
    context: {} as NavigationContext,
    events: {} as NavigationEvent,
  },
  actions: {
    setDestination: assign(({ event }) =>
      event.type === "DESTINATION_SELECTED"
        ? { destination: event.destination, routes: [], selectedRouteId: null, error: null }
        : {},
    ),
    setWarming: assign({ engineWarming: true }),
    restore: assign(({ event }) =>
      event.type === "RESTORE"
        ? {
            destination: event.destination,
            routes: [event.route],
            selectedRouteId: event.route.id,
            maneuverIndex: 0,
            error: null,
            engineWarming: false,
          }
        : {},
    ),
    setRoutes: assign(({ event }) =>
      event.type === "ROUTES_READY"
        ? {
            routes: event.routes,
            selectedRouteId: event.routes[0]?.id ?? null,
            maneuverIndex: 0,
            engineWarming: false,
            error: null,
          }
        : {},
    ),
    selectRoute: assign(({ event }) =>
      event.type === "SELECT_ROUTE" ? { selectedRouteId: event.routeId } : {},
    ),
    advance: assign(({ event }) =>
      event.type === "ADVANCE" ? { maneuverIndex: event.maneuverIndex } : {},
    ),
    setError: assign(({ event }) =>
      event.type === "FAIL" || event.type === "REROUTE_UNAVAILABLE"
        ? { error: event.message, engineWarming: false }
        : {},
    ),
    reset: assign({
      destination: null,
      routes: [],
      selectedRouteId: null,
      maneuverIndex: 0,
      error: null,
      engineWarming: false,
    }),
  },
}).createMachine({
  id: "navigation",
  initial: "idle",
  context: {
    destination: null,
    routes: [],
    selectedRouteId: null,
    maneuverIndex: 0,
    error: null,
    engineWarming: false,
  },
  states: {
    idle: {
      on: {
        DESTINATION_SELECTED: { actions: "setDestination" },
        RESTORE: { target: "preview", actions: "restore" },
        PLAN: "planning",
      },
    },
    planning: {
      initial: "requesting",
      states: {
        requesting: {},
        warming: {},
      },
      on: {
        WARMING: { target: ".warming", actions: "setWarming" },
        ROUTES_READY: { target: "preview", actions: "setRoutes" },
        FAIL: { target: "error", actions: "setError" },
        STOP: { target: "idle", actions: "reset" },
      },
    },
    preview: {
      on: {
        SELECT_ROUTE: { actions: "selectRoute" },
        START: "navigating",
        PERMISSION_DENIED: "permissionDenied",
        PLAN: "planning",
        STOP: { target: "idle", actions: "reset" },
      },
    },
    navigating: {
      on: {
        ADVANCE: { actions: "advance" },
        OFF_ROUTE: "recalculating",
        ARRIVE: "arrived",
        FAIL: { actions: "setError" },
        STOP: { target: "idle", actions: "reset" },
      },
    },
    recalculating: {
      on: {
        WARMING: { actions: "setWarming" },
        ROUTES_READY: { target: "navigating", actions: "setRoutes" },
        REROUTE_UNAVAILABLE: { target: "offline", actions: "setError" },
        FAIL: { target: "navigating", actions: "setError" },
        STOP: { target: "idle", actions: "reset" },
      },
    },
    offline: {
      on: {
        ADVANCE: { actions: "advance" },
        OFF_ROUTE: "recalculating",
        ARRIVE: "arrived",
        STOP: { target: "idle", actions: "reset" },
      },
    },
    permissionDenied: {
      on: {
        RETRY: "preview",
        STOP: { target: "idle", actions: "reset" },
      },
    },
    arrived: {
      on: { STOP: { target: "idle", actions: "reset" } },
    },
    error: {
      on: {
        RETRY: "planning",
        STOP: { target: "idle", actions: "reset" },
        DESTINATION_SELECTED: { target: "idle", actions: "setDestination" },
      },
    },
  },
});
