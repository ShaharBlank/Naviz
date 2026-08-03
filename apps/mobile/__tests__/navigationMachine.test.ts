import { createActor } from "xstate";

import type { Place, RouteAlternative } from "../src/api/types";
import { navigationMachine } from "../src/features/navigation/navigationMachine";

const destination: Place = {
  id: "demo",
  name: "Rabin Square",
  name_he: "כיכר רבין",
  subtitle: null,
  coordinate: { latitude: 32.0819, longitude: 34.7806 },
  category: "landmark",
  confidence: "high",
};

const route = { id: "route-1", maneuvers: [] } as unknown as RouteAlternative;

describe("navigationMachine", () => {
  it("models preview, navigation, rerouting, and arrival explicitly", () => {
    const actor = createActor(navigationMachine).start();
    actor.send({ type: "DESTINATION_SELECTED", destination });
    actor.send({ type: "PLAN" });
    expect(actor.getSnapshot().matches("planning")).toBe(true);
    actor.send({ type: "ROUTES_READY", routes: [route] });
    expect(actor.getSnapshot().matches("preview")).toBe(true);
    actor.send({ type: "START" });
    actor.send({ type: "OFF_ROUTE" });
    expect(actor.getSnapshot().matches("recalculating")).toBe(true);
    actor.send({ type: "ROUTES_READY", routes: [route] });
    actor.send({ type: "ARRIVE" });
    expect(actor.getSnapshot().matches("arrived")).toBe(true);
  });

  it("stores honest engine-warming state", () => {
    const actor = createActor(navigationMachine).start();
    actor.send({ type: "PLAN" });
    actor.send({ type: "WARMING" });
    expect(actor.getSnapshot().context.engineWarming).toBe(true);
  });

  it("restores a cached route into preview while offline", () => {
    const actor = createActor(navigationMachine).start();
    actor.send({ type: "RESTORE", destination, route });
    expect(actor.getSnapshot().matches("preview")).toBe(true);
    expect(actor.getSnapshot().context.selectedRouteId).toBe("route-1");
  });

  it("keeps guidance available when rerouting is offline", () => {
    const actor = createActor(navigationMachine).start();
    actor.send({ type: "RESTORE", destination, route });
    actor.send({ type: "START" });
    actor.send({ type: "OFF_ROUTE" });
    actor.send({ type: "REROUTE_UNAVAILABLE", message: "Network unavailable" });
    expect(actor.getSnapshot().matches("offline")).toBe(true);
    actor.send({ type: "ADVANCE", maneuverIndex: 2 });
    expect(actor.getSnapshot().context.maneuverIndex).toBe(2);
  });

  it("models permission denial without discarding the preview", () => {
    const actor = createActor(navigationMachine).start();
    actor.send({ type: "RESTORE", destination, route });
    actor.send({ type: "PERMISSION_DENIED" });
    expect(actor.getSnapshot().matches("permissionDenied")).toBe(true);
    expect(actor.getSnapshot().context.routes).toEqual([route]);
  });
});
