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
  searchTarget: "destination" as const,
  query: "",
  onQueryChange: jest.fn(),
  onClear: jest.fn(),
  results: [],
  recent: [rabin],
  favorites: [],
  selectedDestination: null,
  selectedOrigin: null,
  departureAt: null,
  routeTimeMode: "depart_at" as const,
  onSelect: jest.fn(),
  onSearchTargetChange: jest.fn(),
  onDepartureChange: jest.fn(),
  onToggleFavorite: jest.fn(),
  mode: "walk" as const,
  onModeChange: jest.fn(),
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
  it("shows English LTR recents and opens starting-point search", async () => {
    await i18n.changeLanguage("en");
    const screen = render(<SearchPanel {...defaults} locale="en" />);
    expect(screen.getByText("Recent destinations")).toBeTruthy();
    expect(screen.getByText("Rabin Square")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("Change starting point"));
    expect(defaults.onSearchTargetChange).toHaveBeenCalledWith("origin");
  });

  it("lets the traveler restore current location as the starting point", async () => {
    await i18n.changeLanguage("en");
    const screen = render(
      <SearchPanel {...defaults} locale="en" searchTarget="origin" />,
    );
    expect(screen.getByLabelText("Where from?")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("Start from my location"));
    expect(defaults.onUseCurrentLocation).toHaveBeenCalled();
  });

  it("shows whether the selected future time is a departure or arrival", async () => {
    await i18n.changeLanguage("en");
    const screen = render(
      <SearchPanel
        {...defaults}
        locale="en"
        departureAt={new Date("2030-09-15T11:15:00+03:00")}
        routeTimeMode="arrive_by"
      />,
    );
    expect(screen.getByText("Arrive")).toBeTruthy();
    expect(screen.getByLabelText("Change trip time")).toBeTruthy();
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
    expect(screen.getByText("השוואת מסלולים")).toBeTruthy();
    expect(screen.queryByText(i18n.t("tagline"))).toBeNull();
    expect(screen.queryByText(i18n.t("allRoutesCalculated"))).toBeNull();
    expect(screen.queryByText("צל מאוזן")).toBeNull();
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
      />,
    );
    expect(screen.getByLabelText("Change travel mode")).toBeTruthy();
    expect(screen.getByText("Bike + transit")).toBeTruthy();
    expect(screen.queryByText("More travel modes")).toBeNull();
  });

  it("shows rich search metadata and distance without confidence jargon", async () => {
    await i18n.changeLanguage("en");
    const restaurant: Place = {
      id: "prozdor",
      name: "Prozdor",
      name_he: "הפרוזדור",
      subtitle: "Mendele Mokher Sfarim Street 6, Tel Aviv-Yafo",
      coordinate: { latitude: 32.0789, longitude: 34.7741 },
      category: "restaurant",
      confidence: "medium",
    };
    const screen = render(
      <SearchPanel
        {...defaults}
        locale="en"
        query="Prozdor"
        results={[restaurant]}
        proximity={{ latitude: 32.09, longitude: 34.78 }}
      />,
    );

    expect(screen.getByText("Restaurant")).toBeTruthy();
    expect(screen.getByText(/km$/)).toBeTruthy();
    expect(screen.getByText(restaurant.subtitle!)).toBeTruthy();
    expect(screen.queryByText("Medium confidence")).toBeNull();
  });
});
