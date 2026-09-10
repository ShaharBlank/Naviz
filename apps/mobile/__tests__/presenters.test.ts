import {
  formatIsraelTime,
  formatNavigationDistance,
} from "../src/features/navigation/presenters";

describe("formatIsraelTime", () => {
  it("uses the explicit Jerusalem timezone regardless of the device timezone", () => {
    expect(formatIsraelTime("2026-08-06T13:34:00Z", "en")).toBe("16:34");
    expect(formatIsraelTime("2026-08-06T13:34:00Z", "he")).toBe("16:34");
  });
});

describe("formatNavigationDistance", () => {
  it("keeps sub-kilometre progress in metres", () => {
    expect(formatNavigationDistance(63)).toEqual({
      key: "metrics.meters",
      value: 60,
    });
    expect(formatNavigationDistance(1_250)).toEqual({
      key: "metrics.kilometers",
      value: 1.3,
    });
  });
});
