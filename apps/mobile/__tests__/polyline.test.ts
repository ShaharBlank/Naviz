import {
  decodePolyline,
  encodePolyline,
  shadowWindowPolyline,
} from "../src/api/polyline";

describe("decodePolyline", () => {
  it("decodes the canonical polyline example", () => {
    const points = decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", 5);
    expect(points).toHaveLength(3);
    expect(points[0]?.latitude).toBeCloseTo(38.5, 5);
    expect(points[0]?.longitude).toBeCloseTo(-120.2, 5);
    expect(points[2]?.latitude).toBeCloseTo(43.252, 5);
  });

  it("round-trips polyline6 geometry", () => {
    const coordinates = [
      { latitude: 32.0733, longitude: 34.7799 },
      { latitude: 32.0741, longitude: 34.7812 },
      { latitude: 32.0775, longitude: 34.7749 },
    ];
    expect(decodePolyline(encodePolyline(coordinates))).toEqual(coordinates);
  });

  it("limits a long shadow scene to the current route window", () => {
    const coordinates = Array.from({ length: 101 }, (_, index) => ({
      latitude: 32 + index * 0.001,
      longitude: 34.78,
    }));
    const window = decodePolyline(
      shadowWindowPolyline(encodePolyline(coordinates), coordinates[50]!, 500),
    );

    expect(window.length).toBeGreaterThan(2);
    expect(window.length).toBeLessThan(coordinates.length);
    expect(window).toContainEqual(coordinates[50]);
  });
});
