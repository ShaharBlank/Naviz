import * as SecureStore from "expo-secure-store";
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

import i18n from "../../i18n";
import type { Locale, Place, RoutePreference, TravelMode, VehicleKind } from "../../api/types";

const secureStorage: StateStorage = {
  getItem: (name) => SecureStore.getItemAsync(name),
  setItem: (name, value) => SecureStore.setItemAsync(name, value),
  removeItem: (name) => SecureStore.deleteItemAsync(name),
};

interface PreferencesState {
  locale: Locale;
  mode: TravelMode;
  preference: RoutePreference;
  vehicleKind: VehicleKind;
  recent: Place[];
  favorites: Place[];
  setLocale: (locale: Locale) => void;
  setMode: (mode: TravelMode) => void;
  setPreference: (preference: RoutePreference) => void;
  setVehicleKind: (kind: VehicleKind) => void;
  addRecent: (place: Place) => void;
  toggleFavorite: (place: Place) => void;
}

export const usePreferences = create<PreferencesState>()(
  persist(
    (set) => ({
      locale: i18n.language === "en" ? "en" : "he",
      mode: "walk",
      preference: "balanced_shade",
      vehicleKind: "none",
      recent: [],
      favorites: [],
      setLocale: (locale) => {
        void i18n.changeLanguage(locale);
        set({ locale });
      },
      setMode: (mode) =>
        set({
          mode,
          preference:
            mode === "walk"
              ? "balanced_shade"
              : ["car", "motorcycle", "truck"].includes(mode)
                ? "fastest"
                : mode.includes("transit") || mode === "transit"
                  ? "fewer_transfers"
                  : "safer_streets",
          vehicleKind:
            mode === "bike_transit"
              ? "folding_bike"
              : mode === "scooter_transit"
                ? "personal_scooter"
                : "none",
        }),
      setPreference: (preference) => set({ preference }),
      setVehicleKind: (vehicleKind) => set({ vehicleKind }),
      addRecent: (place) =>
        set((state) => ({
          recent: [place, ...state.recent.filter((item) => item.id !== place.id)].slice(0, 6),
        })),
      toggleFavorite: (place) =>
        set((state) => ({
          favorites: state.favorites.some((item) => item.id === place.id)
            ? state.favorites.filter((item) => item.id !== place.id)
            : [place, ...state.favorites].slice(0, 20),
        })),
    }),
    {
      name: "naviz-preferences-v1",
      storage: createJSONStorage(() => secureStorage),
      onRehydrateStorage: () => (state) => {
        if (state?.locale) void i18n.changeLanguage(state.locale);
      },
    },
  ),
);
