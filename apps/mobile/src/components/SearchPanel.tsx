import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import type { Place, RoutePreference, TravelMode } from "../api/types";
import { colors, radius, shadow, spacing } from "../theme/tokens";

export type LocationStatus = "idle" | "locating" | "ready" | "denied" | "unavailable";

interface Props {
  query: string;
  onQueryChange: (value: string) => void;
  onClear: () => void;
  results: Place[];
  recent: Place[];
  favorites: Place[];
  selectedDestination: Place | null;
  onSelect: (place: Place) => void;
  onToggleFavorite: (place: Place) => void;
  mode: TravelMode;
  onModeChange: (mode: TravelMode) => void;
  preference: RoutePreference;
  onPreferenceChange: (preference: RoutePreference) => void;
  onPlan: () => void;
  onCancel: () => void;
  onUseCurrentLocation: () => void;
  locationStatus: LocationStatus;
  searching: boolean;
  searchError: boolean;
  planning: boolean;
  locale: "he" | "en";
  onLocaleToggle: () => void;
}

const PRIMARY_MODES: TravelMode[] = ["walk", "car", "transit", "bike"];
const MORE_MODES: TravelMode[] = [
  "scooter",
  "motorcycle",
  "truck",
  "bike_transit",
  "scooter_transit",
  "rental_transit",
];
const MODE_ICONS: Record<TravelMode, string> = {
  walk: "🚶",
  bike: "🚲",
  scooter: "🛴",
  car: "🚗",
  motorcycle: "🏍",
  truck: "🚚",
  transit: "🚌",
  bike_transit: "🚲+",
  scooter_transit: "🛴+",
  rental_transit: "⇄",
};

function preferencesFor(mode: TravelMode): RoutePreference[] {
  if (mode === "walk") return ["fastest", "balanced_shade", "maximum_shade"];
  if (["car", "motorcycle", "truck"].includes(mode)) return ["fastest", "fewer_lights"];
  if (mode === "bike" || mode === "scooter") return ["fastest", "safer_streets"];
  return ["fastest", "fewer_transfers"];
}

export function SearchPanel(props: Props) {
  const { t } = useTranslation();
  const rtl = props.locale === "he";
  const [searchFocused, setSearchFocused] = useState(false);
  const [showMoreModes, setShowMoreModes] = useState(
    MORE_MODES.includes(props.mode),
  );
  const favoriteSelected = props.favorites.some(
    (place) => place.id === props.selectedDestination?.id,
  );
  const selectedLabel = props.selectedDestination
    ? rtl
      ? (props.selectedDestination.name_he ?? props.selectedDestination.name)
      : props.selectedDestination.name
    : "";
  const editingDestination = Boolean(
    props.selectedDestination && props.query.trim() !== selectedLabel.trim(),
  );
  const showSearchState =
    props.query.trim().length > 1 &&
    (!props.selectedDestination || editingDestination) &&
    !props.searching;

  return (
    <View style={[styles.panel, searchFocused && styles.panelWhileTyping]}>
      <View style={styles.handle} />
      <View style={[styles.brandRow, rtl && styles.rowReverse]}>
        <View style={styles.brandCopy}>
          <Text style={[styles.brand, rtl && styles.rtlText]}>{t("appName")}</Text>
          <Text style={[styles.tagline, rtl && styles.rtlText]} numberOfLines={1}>
            {t("tagline")}
          </Text>
        </View>
        <Pressable
          accessibilityRole="button"
          style={styles.languageButton}
          onPress={props.onLocaleToggle}
        >
          <Text style={styles.languageText}>{t("language")}</Text>
        </Pressable>
      </View>

      <View style={[styles.searchBox, rtl && styles.rowReverse]}>
        <Text style={styles.searchIcon}>⌕</Text>
        <TextInput
          accessibilityLabel={t("searchPlaceholder")}
          value={props.query}
          onChangeText={props.onQueryChange}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
          placeholder={t("searchPlaceholder")}
          placeholderTextColor={colors.muted}
          style={[styles.input, rtl && styles.rtlText]}
          returnKeyType="search"
          autoCorrect={false}
        />
        {props.searching ? <ActivityIndicator color={colors.primary} /> : null}
        {props.query.length > 0 && !props.searching ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("clear")}
            onPress={props.onClear}
            style={styles.inlineButton}
          >
            <Text style={styles.clearIcon}>×</Text>
          </Pressable>
        ) : null}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("currentLocation")}
          onPress={props.onUseCurrentLocation}
          disabled={props.locationStatus === "locating"}
          style={styles.inlineButton}
        >
          {props.locationStatus === "locating" ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : (
            <Text style={styles.locationIcon}>◎</Text>
          )}
        </Pressable>
      </View>

      <ScrollView
        style={styles.scrollArea}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {props.query.length > 0 &&
        (!props.selectedDestination || editingDestination) &&
        props.results.length > 0 ? (
          <PlaceRows places={props.results.slice(0, 6)} rtl={rtl} onSelect={props.onSelect} />
        ) : null}
        {showSearchState && props.results.length === 0 ? (
          <Text style={[styles.emptyText, rtl && styles.rtlText]}>
            {props.searchError ? t("error.code.network_error") : t("empty.search")}
          </Text>
        ) : null}
        {props.query.length === 0 && !props.selectedDestination && props.favorites.length > 0 ? (
          <PlaceSection
            title={t("favorites")}
            places={props.favorites}
            rtl={rtl}
            onSelect={props.onSelect}
          />
        ) : null}
        {props.query.length === 0 && !props.selectedDestination && props.recent.length > 0 ? (
          <PlaceSection
            title={t("recent")}
            places={props.recent}
            rtl={rtl}
            onSelect={props.onSelect}
          />
        ) : null}
        {props.query.length === 0 &&
        !props.selectedDestination &&
        props.recent.length === 0 &&
        props.favorites.length === 0 ? (
          <Text style={[styles.emptyText, rtl && styles.rtlText]}>{t("empty.start")}</Text>
        ) : null}

        {props.selectedDestination && !editingDestination ? (
          <View style={styles.routeControls}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={favoriteSelected ? t("removeFavorite") : t("saveFavorite")}
              style={[styles.favoriteButton, rtl && styles.rowReverse]}
              onPress={() => props.onToggleFavorite(props.selectedDestination!)}
            >
              <Text style={styles.favoriteIcon}>{favoriteSelected ? "★" : "☆"}</Text>
              <Text style={[styles.favoriteText, rtl && styles.rtlText]}>
                {favoriteSelected ? t("favorites") : t("saveFavorite")}
              </Text>
            </Pressable>

            <View style={[styles.primaryModeGrid, rtl && styles.rowReverse]}>
              {PRIMARY_MODES.map((mode) => (
                <ModeButton
                  key={mode}
                  mode={mode}
                  label={t(`mode.${mode}`)}
                  selected={props.mode === mode}
                  onPress={() => props.onModeChange(mode)}
                />
              ))}
            </View>
            {showMoreModes ? (
              <View style={[styles.moreModeGrid, rtl && styles.rowReverse]}>
                {MORE_MODES.map((mode) => (
                  <ModeButton
                    key={mode}
                    mode={mode}
                    label={t(`mode.${mode}`)}
                    selected={props.mode === mode}
                    onPress={() => props.onModeChange(mode)}
                    compact
                  />
                ))}
              </View>
            ) : null}
            <Pressable
              accessibilityRole="button"
              onPress={() => setShowMoreModes((value) => !value)}
              style={styles.moreButton}
            >
              <Text style={styles.moreButtonText}>
                {showMoreModes ? t("fewerModes") : t("moreModes")}
              </Text>
            </Pressable>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={[styles.chipRow, rtl && styles.rowReverse]}
            >
              {preferencesFor(props.mode).map((preference) => (
                <Chip
                  key={preference}
                  label={t(`preference.${preference}`)}
                  selected={props.preference === preference}
                  onPress={() => props.onPreferenceChange(preference)}
                />
              ))}
            </ScrollView>
            <Pressable
              accessibilityRole="button"
              style={({ pressed }) => [styles.planButton, pressed && styles.pressed]}
              onPress={props.planning ? props.onCancel : props.onPlan}
            >
              {props.planning ? <ActivityIndicator color={colors.surface} /> : null}
              <Text style={styles.planButtonText}>
                {props.planning ? t("cancel") : t("planRoute")}
              </Text>
            </Pressable>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

function PlaceSection({
  title,
  places,
  rtl,
  onSelect,
}: {
  title: string;
  places: Place[];
  rtl: boolean;
  onSelect: (place: Place) => void;
}) {
  return (
    <View>
      <Text style={[styles.sectionTitle, rtl && styles.rtlText]}>{title}</Text>
      <PlaceRows places={places.slice(0, 3)} rtl={rtl} onSelect={onSelect} />
    </View>
  );
}

function PlaceRows({
  places,
  rtl,
  onSelect,
}: {
  places: Place[];
  rtl: boolean;
  onSelect: (place: Place) => void;
}) {
  return (
    <View style={styles.results}>
      {places.map((place) => (
        <Pressable
          accessibilityRole="button"
          key={place.id}
          style={[styles.result, rtl && styles.rowReverse]}
          onPress={() => {
            Keyboard.dismiss();
            onSelect(place);
          }}
        >
          <View style={styles.resultIcon}><Text>⌖</Text></View>
          <View style={styles.resultText}>
            <Text style={[styles.resultName, rtl && styles.rtlText]}>
              {rtl ? (place.name_he ?? place.name) : place.name}
            </Text>
            {place.subtitle ? (
              <Text style={[styles.resultSubtitle, rtl && styles.rtlText]} numberOfLines={1}>
                {place.subtitle}
              </Text>
            ) : null}
          </View>
        </Pressable>
      ))}
    </View>
  );
}

function ModeButton({
  mode,
  label,
  selected,
  compact = false,
  onPress,
}: {
  mode: TravelMode;
  label: string;
  selected: boolean;
  compact?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.modeButton, compact && styles.modeButtonCompact, selected && styles.modeSelected]}
    >
      <Text style={styles.modeIcon}>{MODE_ICONS[mode]}</Text>
      <Text style={[styles.modeLabel, selected && styles.modeLabelSelected]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.chip, selected && styles.chipSelected]}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  panel: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    maxHeight: "72%",
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    ...shadow,
  },
  panelWhileTyping: {
    top: spacing.md,
    bottom: undefined,
    maxHeight: "56%",
  },
  handle: {
    width: 42,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.border,
    alignSelf: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  brandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  rowReverse: { flexDirection: "row-reverse" },
  brandCopy: { flex: 1 },
  brand: { fontSize: 24, lineHeight: 28, fontWeight: "900", color: colors.ink },
  tagline: { fontSize: 12, color: colors.muted, marginTop: 1 },
  rtlText: { textAlign: "right", writingDirection: "rtl" },
  languageButton: { minHeight: 44, paddingHorizontal: spacing.md, justifyContent: "center" },
  languageText: { color: colors.primary, fontWeight: "800" },
  searchBox: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceElevated,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchIcon: { fontSize: 24, color: colors.primary, marginHorizontal: spacing.xs },
  input: { flex: 1, minHeight: 50, fontSize: 17, color: colors.ink, paddingHorizontal: spacing.sm },
  inlineButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  clearIcon: { fontSize: 24, color: colors.muted },
  locationIcon: { fontSize: 25, color: colors.primary, fontWeight: "800" },
  scrollArea: { flexGrow: 0 },
  results: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  sectionTitle: { color: colors.muted, fontSize: 12, fontWeight: "800", marginTop: spacing.md },
  result: { flexDirection: "row", alignItems: "center", minHeight: 60, paddingVertical: spacing.sm },
  resultIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#EEF2FF",
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: spacing.sm,
  },
  resultText: { flex: 1, minWidth: 0 },
  resultName: { color: colors.ink, fontSize: 15, fontWeight: "800" },
  resultSubtitle: { color: colors.muted, fontSize: 12, marginTop: 2 },
  emptyText: { color: colors.muted, fontSize: 13, lineHeight: 19, paddingVertical: spacing.lg },
  routeControls: { paddingTop: spacing.sm },
  favoriteButton: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: spacing.sm },
  favoriteIcon: { color: colors.primary, fontSize: 22 },
  favoriteText: { color: colors.primaryDark, fontWeight: "700" },
  primaryModeGrid: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs },
  moreModeGrid: { flexDirection: "row", gap: spacing.sm, flexWrap: "wrap", marginTop: spacing.sm },
  modeButton: {
    flex: 1,
    minWidth: 68,
    minHeight: 64,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  modeButtonCompact: { flexGrow: 0, width: "31%" },
  modeSelected: { backgroundColor: "#EEF2FF", borderColor: colors.primary },
  modeIcon: { fontSize: 20 },
  modeLabel: { color: colors.ink, fontSize: 11, fontWeight: "700", marginTop: 2 },
  modeLabelSelected: { color: colors.primaryDark },
  moreButton: { minHeight: 44, justifyContent: "center", alignItems: "center" },
  moreButtonText: { color: colors.primary, fontSize: 13, fontWeight: "800" },
  chipRow: { gap: spacing.sm, paddingBottom: spacing.sm },
  chip: {
    minHeight: 44,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  chipSelected: { backgroundColor: "#EEF2FF", borderColor: colors.primary },
  chipText: { color: colors.ink, fontWeight: "600" },
  chipTextSelected: { color: colors.primaryDark },
  planButton: {
    minHeight: 54,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  planButtonText: { color: colors.surface, fontSize: 17, fontWeight: "900" },
  pressed: { opacity: 0.82 },
});
