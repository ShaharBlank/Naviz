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
});
