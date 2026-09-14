import {
  departureForRequest,
  formatDepartureTime,
  sanitizeFutureDeparture,
  shadowDisplayTime,
} from "../src/features/planning/departureTime";

describe("departure and shade clocks", () => {
  const now = new Date("2026-09-15T10:00:37+03:00");

  it("uses now by default and preserves a future departure", () => {
    expect(departureForRequest(null, now)).toEqual(now);
    const future = new Date("2026-09-15T11:15:00+03:00");
    expect(departureForRequest(future, now)).toEqual(future);
  });

  it("treats past and accidental near-now choices as now", () => {
    expect(
      sanitizeFutureDeparture(new Date("2026-09-15T10:00:59+03:00"), now),
    ).toBeNull();
    expect(
      sanitizeFutureDeparture(new Date("2026-09-15T10:01:37+03:00"), now),
    ).not.toBeNull();
  });

  it("previews future shade but follows the live clock while navigating", () => {
    const future = "2026-09-15T13:45:29+03:00";
    expect(shadowDisplayTime(future, false, now).toISOString()).toBe(
      "2026-09-15T10:45:00.000Z",
    );
    expect(shadowDisplayTime(future, true, now).toISOString()).toBe(
      "2026-09-15T07:00:00.000Z",
    );
  });

  it("formats a concise localized time", () => {
    expect(
      formatDepartureTime(
        new Date("2026-09-15T11:15:00+03:00"),
        "en",
        now,
      ),
    ).toMatch(/11:15/);
  });
});
