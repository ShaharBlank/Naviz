import { act, fireEvent, render } from "@testing-library/react-native";

import type { RouteAlternative } from "../src/api/types";
import { RouteCards } from "../src/components/RouteCards";
import i18n from "../src/i18n";

function route(
  id: string,
  labelKey: string,
  durationS: number,
  trafficSignals: number,
  signalsAvoided?: number,
): RouteAlternative {
  return {
    id,
    label_key: labelKey,
    encoded_polyline: "_p~iF~ps|U_ulLnnqC",
    bbox: [34.77, 32.07, 34.79, 32.09],
    departure_at: "2026-08-17T09:00:00+03:00",
    arrival_at: "2026-08-17T09:12:00+03:00",
    legs: [],
    maneuvers: [],
    annotations: [],
    metrics: {
      distance_m: 3_200,
      duration_s: durationS,
      walking_distance_m: 0,
      cycling_distance_m: 0,
      transfers: 0,
      traffic_signals: trafficSignals,
      signals_avoided: signalsAvoided ?? null,
      detour_time_percent: 0,
      detour_distance_percent: 0,
    },
    quality: {
      confidence: "high",
      scheduled_transit: false,
      realtime_transit: false,
      shade_sources: [],
      warnings: [],
      dataset_versions: { osm: "test" },
    },
    warnings: [],
    fallback_reason: null,
    expires_at: "2026-08-17T09:15:00+03:00",
  } as RouteAlternative;
}

describe("RouteCards comparison", () => {
  it("shows every calculated route type with total and avoided traffic lights", async () => {
    await i18n.changeLanguage("en");
    const onSelect = jest.fn();
    const fastest = route("fast", "route.fastest", 600, 12);
    const fewerLights = route("lights", "route.fewerLights", 720, 3, 9);
    const screen = render(
      <RouteCards
        routes={[fastest, fewerLights]}
        selectedRouteId={fastest.id}
        onSelect={onSelect}
        onStart={jest.fn()}
        onBack={jest.fn()}
        rtl={false}
      />,
    );

    expect(screen.getByText("Compare routes")).toBeTruthy();
    expect(screen.getByText("Fastest")).toBeTruthy();
    expect(screen.getByText("Fewer lights")).toBeTruthy();
    expect(screen.getByText("12 lights")).toBeTruthy();
    expect(screen.getByText("3 lights")).toBeTruthy();
    expect(screen.getByText("9 fewer lights")).toBeTruthy();
    expect(screen.getByText("+2 min vs fastest")).toBeTruthy();
    expect(screen.getByLabelText(/Fewer lights route.*3 lights/)).toBeTruthy();

    fireEvent.press(screen.getByText("Fewer lights"));
    expect(onSelect).toHaveBeenCalledWith(fewerLights);
  });

  it("blocks a transition ghost tap before enabling navigation", async () => {
    jest.useFakeTimers();
    const onStart = jest.fn();
    const fastest = route("fast", "route.fastest", 600, 4);
    const screen = render(
      <RouteCards
        routes={[fastest]}
        selectedRouteId={fastest.id}
        onSelect={jest.fn()}
        onStart={onStart}
        onBack={jest.fn()}
        rtl={false}
      />,
    );

    fireEvent.press(screen.getByText("Start"));
    expect(onStart).not.toHaveBeenCalled();
    act(() => jest.advanceTimersByTime(650));
    fireEvent.press(screen.getByText("Start"));
    expect(onStart).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });

  it("describes a zero-exposure route without claiming nighttime shade", async () => {
    await i18n.changeLanguage("en");
    const noSun = route("night", "route.fastest", 600, 0);
    noSun.metrics.shade_fraction = 1;
    noSun.metrics.sun_exposure_minutes = 0;
    const screen = render(
      <RouteCards
        routes={[noSun]}
        selectedRouteId={noSun.id}
        onSelect={jest.fn()}
        onStart={jest.fn()}
        onBack={jest.fn()}
        rtl={false}
      />,
    );

    expect(screen.getByText("No direct sun exposure")).toBeTruthy();
    expect(screen.queryByText("100% shade")).toBeNull();
  });

  it("does not clutter a single fastest result with a non-actionable fallback", async () => {
    await i18n.changeLanguage("en");
    const fastest = route("fast", "route.fastest", 600, 4);
    fastest.fallback_reason = "no_material_signal_reduction";
    const screen = render(
      <RouteCards
        routes={[fastest]}
        selectedRouteId={fastest.id}
        onSelect={jest.fn()}
        onStart={jest.fn()}
        onBack={jest.fn()}
        rtl={false}
      />,
    );

    expect(
      screen.queryByText(
        "Fastest route selected; alternatives did not avoid enough lights.",
      ),
    ).toBeNull();
  });
});
