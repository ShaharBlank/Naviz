import { ProgressTracker } from "../src/features/navigation/progressTracker";

const route = [
  { latitude: 32.0733, longitude: 34.7799 },
  { latitude: 32.0776, longitude: 34.7749 },
  { latitude: 32.0819, longitude: 34.7806 },
];

describe("ProgressTracker", () => {
  it("uses three-fix hysteresis before declaring off-route", () => {
    const tracker = new ProgressTracker(route);
    const far = {
      coordinate: { latitude: 32.12, longitude: 34.84 },
      accuracyM: 5,
      headingDegrees: 0,
    };
    expect(tracker.update(far).offRoute).toBe(false);
    expect(tracker.update(far).offRoute).toBe(false);
    expect(tracker.update(far).offRoute).toBe(true);
  });

  it("recognizes arrival near the final point", () => {
    const tracker = new ProgressTracker(route);
    expect(
      tracker.update({ coordinate: route[2]!, accuracyM: 5, headingDegrees: null }).arrived,
    ).toBe(true);
  });
});

