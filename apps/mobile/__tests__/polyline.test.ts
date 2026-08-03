import { decodePolyline } from "../src/api/polyline";

describe("decodePolyline", () => {
  it("decodes the canonical polyline example", () => {
    const points = decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", 5);
    expect(points).toHaveLength(3);
    expect(points[0]?.latitude).toBeCloseTo(38.5, 5);
    expect(points[0]?.longitude).toBeCloseTo(-120.2, 5);
    expect(points[2]?.latitude).toBeCloseTo(43.252, 5);
  });
});

