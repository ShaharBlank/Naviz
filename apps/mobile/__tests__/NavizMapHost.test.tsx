import { isExpoGoRuntime } from "../src/components/NavizMapHost";

jest.mock("../src/components/ExpoGoNavizMap", () => ({
  ExpoGoNavizMap: () => null,
}));

jest.mock("../src/components/NavizMap", () => ({
  NavizMap: () => null,
}));

describe("Naviz map runtime selection", () => {
  it("selects the Expo Go-safe renderer only for Expo Go ownership", () => {
    expect(isExpoGoRuntime("expo")).toBe(true);
    expect(isExpoGoRuntime("standalone")).toBe(false);
    expect(isExpoGoRuntime("guest")).toBe(false);
    expect(isExpoGoRuntime(null)).toBe(false);
    expect(isExpoGoRuntime(undefined)).toBe(false);
  });
});
