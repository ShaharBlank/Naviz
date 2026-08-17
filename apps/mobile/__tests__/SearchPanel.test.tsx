import { fireEvent, render } from "@testing-library/react-native";

import type { Place } from "../src/api/types";
import { SearchPanel } from "../src/components/SearchPanel";
import i18n from "../src/i18n";

const rabin: Place = {
  id: "rabin",
  name: "Rabin Square",
  name_he: "כיכר רבין",
  subtitle: "Tel Aviv-Yafo",
  coordinate: { latitude: 32.0808, longitude: 34.7806 },
  category: "landmark",
  confidence: "high",
};

const defaults = {
  query: "",
  onQueryChange: jest.fn(),
  onClear: jest.fn(),
  results: [],
  recent: [rabin],
  favorites: [],
  selectedDestination: null,
  onSelect: jest.fn(),
  onToggleFavorite: jest.fn(),
  mode: "walk" as const,
  onModeChange: jest.fn(),
  preference: "balanced_shade" as const,
  onPreferenceChange: jest.fn(),
  onPlan: jest.fn(),
  onCancel: jest.fn(),
  onUseCurrentLocation: jest.fn(),
  locationStatus: "ready" as const,
  searching: false,
  searchError: false,
  planning: false,
  onLocaleToggle: jest.fn(),
};

describe("SearchPanel localization and controls", () => {
  it("shows English LTR recents and a current-location control", async () => {
    await i18n.changeLanguage("en");
    const screen = render(<SearchPanel {...defaults} locale="en" />);
    expect(screen.getByText("Recent destinations")).toBeTruthy();
    expect(screen.getByText("Rabin Square")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("Current location"));
    expect(defaults.onUseCurrentLocation).toHaveBeenCalled();
  });

  it("shows correct Hebrew RTL destination controls", async () => {
    await i18n.changeLanguage("he");
    const screen = render(
      <SearchPanel
        {...defaults}
        locale="he"
        query="כיכר רבין"
        selectedDestination={rabin}
      />,
    );
    expect(screen.getByLabelText("שמירה למועדפים")).toBeTruthy();
    expect(screen.getByText("צל מאוזן")).toBeTruthy();
  });

  it("shows live shared-vehicle availability for rental transit", async () => {
    await i18n.changeLanguage("en");
    const screen = render(
      <SearchPanel
        {...defaults}
        locale="en"
        query="Rabin Square"
        selectedDestination={rabin}
        mode="rental_transit"
        preference="fewer_transfers"
        mobilityCount={12}
      />,
    );

    expect(
      screen.getByText(
        "12 vehicles nearby · tap a map dot to open the operator app",
      ),
    ).toBeTruthy();
  });

  it("distinguishes live vehicles from rental itinerary support", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("fallback.rental_availability_unavailable")).toBe(
      "Shared vehicles are nearby, but this route currently uses public transit only.",
    );

    await i18n.changeLanguage("he");
    expect(i18n.t("fallback.rental_availability_unavailable")).toBe(
      "כלים שיתופיים זמינים בקרבת מקום, אך המסלול הזה משתמש כרגע בתחבורה ציבורית בלבד.",
    );
  });

  it("wraps combined-mode names and collapses after a mode is selected", async () => {
    await i18n.changeLanguage("en");
    const screen = render(
      <SearchPanel
        {...defaults}
        locale="en"
        query="Rabin Square"
        selectedDestination={rabin}
      />,
    );

    fireEvent.press(screen.getByText("More travel modes"));
    const combinedMode = screen.getByText("Bike + transit");
    expect(combinedMode.props.numberOfLines).toBeUndefined();
    fireEvent.press(combinedMode);
    expect(defaults.onModeChange).toHaveBeenLastCalledWith("bike_transit");

    screen.rerender(
      <SearchPanel
        {...defaults}
        locale="en"
        query="Rabin Square"
        selectedDestination={rabin}
        mode="bike_transit"
        preference="fewer_transfers"
      />,
    );
    expect(screen.getByLabelText("Change travel mode")).toBeTruthy();
    expect(screen.getByText("Bike + transit")).toBeTruthy();
    expect(screen.queryByText("More travel modes")).toBeNull();
  });
});
