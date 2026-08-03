import { render } from "@testing-library/react-native";

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
  searching: false,
  planning: false,
  onLocaleToggle: jest.fn(),
};

describe("SearchPanel localization", () => {
  it("shows English LTR recents", async () => {
    await i18n.changeLanguage("en");
    const screen = render(<SearchPanel {...defaults} locale="en" />);
    expect(screen.getByText("Recent destinations")).toBeTruthy();
    expect(screen.getByText("Rabin Square")).toBeTruthy();
  });

  it("shows Hebrew RTL destination controls", async () => {
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
