import { formatTelAvivTime } from "../src/features/navigation/presenters";

describe("formatTelAvivTime", () => {
  it("uses the explicit Jerusalem timezone regardless of the device timezone", () => {
    expect(formatTelAvivTime("2026-08-06T13:34:00Z", "en")).toBe("16:34");
    expect(formatTelAvivTime("2026-08-06T13:34:00Z", "he")).toBe("16:34");
  });
});
