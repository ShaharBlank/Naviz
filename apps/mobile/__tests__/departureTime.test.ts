import {
  departureForRequest,
  formatDepartureTime,
  routeTimeForRequest,
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

  it("sends exactly one planned-time mode", () => {
    const future = new Date("2026-09-15T11:15:00+03:00");
    expect(routeTimeForRequest("depart_at", future, now)).toEqual({
      depart_at: future.toISOString(),
    });
    expect(routeTimeForRequest("arrive_by", future, now)).toEqual({
      arrive_by: future.toISOString(),
    });
    expect(routeTimeForRequest("depart_at", null, now)).toEqual({
      depart_at: now.toISOString(),
    });
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
      formatDepartureTime(new Date("2026-09-15T11:15:00+03:00"), "en", now),
    ).toMatch(/11:15/);
    const anotherDay = formatDepartureTime(
      new Date("2026-09-16T12:00:00+03:00"),
      "en",
      now,
    );
    expect(anotherDay).toMatch(/16/);
    expect(anotherDay).toMatch(/12:00/);
    expect(anotherDay.length).toBeLessThan(18);
  });
});
