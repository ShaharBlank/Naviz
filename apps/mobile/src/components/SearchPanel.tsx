import { useEffect, useRef, useState } from "react";
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

import { distanceMeters } from "../api/polyline";
import type { Coordinate, Place, TravelMode } from "../api/types";
import type { RouteTimeMode } from "../features/planning/departureTime";
import { colors, radius, shadow, spacing } from "../theme/tokens";
import { DepartureTimeControl } from "./DepartureTimeControl";

export type LocationStatus =
  "idle" | "locating" | "ready" | "denied" | "unavailable";
export type SearchTarget = "origin" | "destination";

interface Props {
  query: string;
  onQueryChange: (value: string) => void;
  onClear: () => void;
  results: Place[];
  recent: Place[];
  favorites: Place[];
  searchTarget: SearchTarget;
  selectedOrigin: Place | null;
  selectedDestination: Place | null;
  departureAt: Date | null;
  routeTimeMode: RouteTimeMode;
  onSearchTargetChange: (target: SearchTarget) => void;
  onDepartureChange: (mode: RouteTimeMode, value: Date | null) => void;
  onSelect: (place: Place) => void;
  onToggleFavorite: (place: Place) => void;
  mode: TravelMode;
  onModeChange: (mode: TravelMode) => void;
  onPlan: () => void;
  onCancel: () => void;
  onUseCurrentLocation: () => void;
  locationStatus: LocationStatus;
  searching: boolean;
  searchError: boolean;
  planning: boolean;
  locale: "he" | "en";
  onLocaleToggle: () => void;
  mobilityCount?: number | null;
  proximity?: Coordinate | null | undefined;
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
const SEARCH_CATEGORIES = new Set([
  "address",
  "restaurant",
  "cafe",
  "nightlife",
  "transit",
  "government",
  "shopping",
  "hotel",
  "culture",
  "health",
  "education",
  "park",
  "outdoors",
  "parking",
  "fuel",
  "city",
  "district",
  "locality",
]);

export function SearchPanel(props: Props) {
  const { t } = useTranslation();
  const rtl = props.locale === "he";
  const [searchFocused, setSearchFocused] = useState(false);
  const searchInput = useRef<TextInput>(null);
  const [showMoreModes, setShowMoreModes] = useState(
    MORE_MODES.includes(props.mode),
  );
  const moreModesVisible = showMoreModes || MORE_MODES.includes(props.mode);
  const [collapsedDestinationId, setCollapsedDestinationId] = useState<
    string | null
  >(null);
  const modeSelectorExpanded =
    collapsedDestinationId !== props.selectedDestination?.id;

  const favoriteSelected = props.favorites.some(
    (place) => place.id === props.selectedDestination?.id,
  );
  const selectedSearchPlace =
    props.searchTarget === "origin"
      ? props.selectedOrigin
      : props.selectedDestination;
  const selectedLabel = selectedSearchPlace
    ? rtl
      ? (selectedSearchPlace.name_he ?? selectedSearchPlace.name)
      : selectedSearchPlace.name
    : "";
  const editingSelection = Boolean(
    selectedSearchPlace && props.query.trim() !== selectedLabel.trim(),
  );
  const editingDestination =
    props.searchTarget === "destination" && editingSelection;
  const showSearchState =
    props.query.trim().length > 1 &&
    (!selectedSearchPlace || editingSelection) &&
    !props.searching;

  useEffect(() => {
    if (props.searchTarget === "origin") searchInput.current?.focus();
  }, [props.searchTarget]);

  return (
    <View style={[styles.panel, searchFocused && styles.panelWhileTyping]}>
      <View style={styles.handle} />
      <View style={[styles.brandRow, rtl && styles.rowReverse]}>
        <Text style={[styles.brand, rtl && styles.rtlText]}>
          {t("appName")}
        </Text>
        <Pressable
          accessibilityRole="button"
          style={styles.languageButton}
          onPress={props.onLocaleToggle}
        >
          <Text style={styles.languageText}>{t("language")}</Text>
        </Pressable>
      </View>

      <View style={[styles.tripContextRow, rtl && styles.rowReverse]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("origin.change")}
          accessibilityState={{ selected: props.searchTarget === "origin" }}
          onPress={() => props.onSearchTargetChange("origin")}
          style={[
            styles.originControl,
            rtl && styles.rowReverse,
            props.searchTarget === "origin" && styles.contextControlSelected,
          ]}
        >
          <Text style={styles.originIcon}>
            {props.selectedOrigin ? "●" : "◎"}
          </Text>
          <View style={styles.contextLabelGroup}>
            <Text style={[styles.contextEyebrow, rtl && styles.rtlText]}>
              {t("origin.label")}
            </Text>
            <Text
              style={[styles.contextLabel, rtl && styles.rtlText]}
              numberOfLines={1}
            >
              {props.selectedOrigin
                ? rtl
                  ? (props.selectedOrigin.name_he ?? props.selectedOrigin.name)
                  : props.selectedOrigin.name
                : t("currentLocation")}
            </Text>
          </View>
        </Pressable>
        <DepartureTimeControl
          value={props.departureAt}
          mode={props.routeTimeMode}
          locale={props.locale}
          onChange={props.onDepartureChange}
        />
      </View>

      <View style={[styles.searchBox, rtl && styles.rowReverse]}>
        <Text style={styles.searchIcon}>
          {props.searchTarget === "origin" ? "●" : "⌕"}
        </Text>
        <TextInput
          ref={searchInput}
          accessibilityLabel={t(
            props.searchTarget === "origin"
              ? "originSearchPlaceholder"
              : "searchPlaceholder",
          )}
          value={props.query}
          onChangeText={props.onQueryChange}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
          placeholder={t(
            props.searchTarget === "origin"
              ? "originSearchPlaceholder"
              : "searchPlaceholder",
          )}
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
      </View>

      <ScrollView
        style={styles.scrollArea}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {props.searchTarget === "origin" ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("origin.useCurrent")}
            onPress={props.onUseCurrentLocation}
            disabled={props.locationStatus === "locating"}
            style={[styles.currentOriginRow, rtl && styles.rowReverse]}
          >
            {props.locationStatus === "locating" ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Text style={styles.currentOriginIcon}>◎</Text>
            )}
            <Text style={[styles.currentOriginLabel, rtl && styles.rtlText]}>
              {t("origin.useCurrent")}
            </Text>
          </Pressable>
        ) : null}
        {props.query.length > 0 &&
        (!selectedSearchPlace || editingSelection) &&
        props.results.length > 0 ? (
          <PlaceRows
            places={props.results.slice(0, 12)}
            rtl={rtl}
            proximity={props.proximity}
            onSelect={props.onSelect}
          />
        ) : null}
        {showSearchState && props.results.length === 0 ? (
          <Text style={[styles.emptyText, rtl && styles.rtlText]}>
            {props.searchError
              ? t("error.code.network_error")
              : t("empty.search")}
          </Text>
        ) : null}
        {props.query.length === 0 &&
        props.searchTarget === "destination" &&
        !props.selectedDestination &&
        props.favorites.length > 0 ? (
          <PlaceSection
            title={t("favorites")}
            places={props.favorites}
            rtl={rtl}
            proximity={props.proximity}
            onSelect={props.onSelect}
          />
        ) : null}
        {props.query.length === 0 &&
        props.searchTarget === "destination" &&
        !props.selectedDestination &&
        props.recent.length > 0 ? (
          <PlaceSection
            title={t("recent")}
            places={props.recent}
            rtl={rtl}
            proximity={props.proximity}
            onSelect={props.onSelect}
          />
        ) : null}
        {props.query.length === 0 &&
        props.searchTarget === "destination" &&
        !props.selectedDestination &&
        props.recent.length === 0 &&
        props.favorites.length === 0 ? (
          <Text style={[styles.emptyText, rtl && styles.rtlText]}>
            {t("empty.start")}
          </Text>
        ) : null}

        {props.selectedDestination &&
        props.searchTarget === "destination" &&
        !editingDestination ? (
          <View style={styles.routeControls}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={
                favoriteSelected ? t("removeFavorite") : t("saveFavorite")
              }
              style={[styles.favoriteButton, rtl && styles.rowReverse]}
              onPress={() => props.onToggleFavorite(props.selectedDestination!)}
            >
              <Text style={styles.favoriteIcon}>
                {favoriteSelected ? "★" : "☆"}
              </Text>
              <Text style={[styles.favoriteText, rtl && styles.rtlText]}>
                {favoriteSelected ? t("favorites") : t("saveFavorite")}
              </Text>
            </Pressable>

            <View style={[styles.transportHeader, rtl && styles.rowReverse]}>
              <Text style={[styles.transportTitle, rtl && styles.rtlText]}>
                {t("transportMode")}
              </Text>
              {modeSelectorExpanded ? (
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={t("collapseModes")}
                  accessibilityState={{ expanded: true }}
                  onPress={() =>
                    setCollapsedDestinationId(
                      props.selectedDestination?.id ?? null,
                    )
                  }
                  style={styles.transportHeaderButton}
                >
                  <Text style={styles.transportHeaderButtonText}>
                    {t("collapse")}
                  </Text>
                </Pressable>
              ) : null}
            </View>

            {modeSelectorExpanded ? (
              <>
                <View
                  style={[styles.primaryModeGrid, rtl && styles.rowReverse]}
                >
                  {PRIMARY_MODES.map((mode) => (
                    <ModeButton
                      key={mode}
                      mode={mode}
                      label={t(`mode.${mode}`)}
                      selected={props.mode === mode}
                      onPress={() => {
                        props.onModeChange(mode);
                        setCollapsedDestinationId(
                          props.selectedDestination?.id ?? null,
                        );
                      }}
                    />
                  ))}
                </View>
                {moreModesVisible ? (
                  <View style={[styles.moreModeGrid, rtl && styles.rowReverse]}>
                    {MORE_MODES.map((mode) => (
                      <ModeButton
                        key={mode}
                        mode={mode}
                        label={t(`mode.${mode}`)}
                        selected={props.mode === mode}
                        onPress={() => {
                          props.onModeChange(mode);
                          setCollapsedDestinationId(
                            props.selectedDestination?.id ?? null,
                          );
                        }}
                        compact
                      />
                    ))}
                  </View>
                ) : null}
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={
                    moreModesVisible ? t("fewerModes") : t("moreModes")
                  }
                  accessibilityState={{ expanded: moreModesVisible }}
                  onPress={() => setShowMoreModes(!moreModesVisible)}
                  style={styles.moreButton}
                >
                  <Text style={styles.moreButtonText}>
                    {moreModesVisible ? t("fewerModes") : t("moreModes")}
                  </Text>
                </Pressable>
              </>
            ) : (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t("changeMode")}
                accessibilityState={{ expanded: false }}
                onPress={() => setCollapsedDestinationId(null)}
                style={[styles.selectedModeSummary, rtl && styles.rowReverse]}
              >
                <Text style={styles.selectedModeIcon}>
                  {MODE_ICONS[props.mode]}
                </Text>
                <Text style={[styles.selectedModeLabel, rtl && styles.rtlText]}>
                  {t(`mode.${props.mode}`)}
                </Text>
                <Text style={styles.changeModeText}>{t("change")}</Text>
              </Pressable>
            )}

            {props.mode === "rental_transit" ? (
              <Text style={[styles.mobilityStatus, rtl && styles.rtlText]}>
                {props.mobilityCount === null
                  ? t("mobility.loading")
                  : t("mobility.available", { count: props.mobilityCount })}
              </Text>
            ) : null}
            <Pressable
              accessibilityRole="button"
              style={({ pressed }) => [
                styles.planButton,
                pressed && styles.pressed,
              ]}
              onPress={props.planning ? props.onCancel : props.onPlan}
            >
              {props.planning ? (
                <ActivityIndicator color={colors.surface} />
              ) : null}
              <Text style={styles.planButtonText}>
                {props.planning ? t("cancel") : t("routeComparison")}
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
  proximity,
  onSelect,
}: {
  title: string;
  places: Place[];
  rtl: boolean;
  proximity?: Coordinate | null | undefined;
  onSelect: (place: Place) => void;
}) {
  return (
    <View>
      <Text style={[styles.sectionTitle, rtl && styles.rtlText]}>{title}</Text>
      <PlaceRows
        places={places.slice(0, 3)}
        rtl={rtl}
        proximity={proximity}
        onSelect={onSelect}
      />
    </View>
  );
}

function PlaceRows({
  places,
  rtl,
  proximity,
  onSelect,
}: {
  places: Place[];
  rtl: boolean;
  proximity?: Coordinate | null | undefined;
  onSelect: (place: Place) => void;
}) {
  const { t } = useTranslation();
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
          <View style={styles.resultIcon}>
            <Text style={styles.resultIconText}>
              {placeIcon(place.category)}
            </Text>
          </View>
          <View style={styles.resultText}>
            <Text style={[styles.resultName, rtl && styles.rtlText]}>
              {rtl ? (place.name_he ?? place.name) : place.name}
            </Text>
            <View style={[styles.resultMeta, rtl && styles.rowReverse]}>
              <Text style={[styles.resultCategory, rtl && styles.rtlText]}>
                {t(`searchCategory.${normalizedCategory(place.category)}`)}
              </Text>
              {proximity ? (
                <Text style={styles.resultDistance}>
                  {formatPlaceDistance(
                    distanceMeters(proximity, place.coordinate),
                    t,
                  )}
                </Text>
              ) : null}
            </View>
            {place.subtitle ? (
              <Text
                style={[styles.resultSubtitle, rtl && styles.rtlText]}
                numberOfLines={2}
              >
                {place.subtitle}
              </Text>
            ) : null}
          </View>
        </Pressable>
      ))}
    </View>
  );
}

function normalizedCategory(category: string): string {
  const value = category.toLowerCase();
  if (value === "house" || value === "street") return "address";
  return SEARCH_CATEGORIES.has(value) ? value : "place";
}

function placeIcon(category: string): string {
  const value = normalizedCategory(category);
  if (value === "restaurant") return "♨";
  if (value === "cafe") return "☕";
  if (value === "transit") return "↔";
  if (value === "government") return "▦";
  if (value === "shopping") return "◇";
  if (value === "health") return "✚";
  if (value === "education" || value === "culture") return "▤";
  if (value === "park" || value === "outdoors") return "♧";
  if (value === "parking") return "P";
  if (value === "fuel") return "⛽";
  if (value === "hotel") return "⌂";
  return "⌖";
}

type Translate = ReturnType<typeof useTranslation>["t"];

function formatPlaceDistance(distance: number, t: Translate): string {
  if (distance < 1_000) {
    return t("metrics.meters", {
      value: Math.max(10, Math.round(distance / 10) * 10),
    });
  }
  return t("metrics.kilometers", {
    value: Math.round((distance / 1_000) * 10) / 10,
  });
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
      accessibilityLabel={label}
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[
        styles.modeButton,
        compact && styles.modeButtonCompact,
        selected && styles.modeSelected,
      ]}
    >
      <Text style={styles.modeIcon}>{MODE_ICONS[mode]}</Text>
      <Text
        style={[
          styles.modeLabel,
          compact && styles.modeLabelCompact,
          selected && styles.modeLabelSelected,
        ]}
      >
        {label}
      </Text>
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
  brandRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowReverse: { flexDirection: "row-reverse" },
  brand: { fontSize: 24, lineHeight: 28, fontWeight: "900", color: colors.ink },
  rtlText: { textAlign: "right", writingDirection: "rtl" },
  languageButton: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    justifyContent: "center",
  },
  languageText: { color: colors.primary, fontWeight: "800" },
  tripContextRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  originControl: {
    minHeight: 56,
    flex: 1.15,
    minWidth: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
  },
  contextControlSelected: {
    borderColor: colors.primary,
    backgroundColor: "#EEF2FF",
  },
  originIcon: { color: colors.primary, fontSize: 16, fontWeight: "900" },
  contextLabelGroup: { flex: 1, minWidth: 0 },
  contextEyebrow: { color: colors.muted, fontSize: 10, fontWeight: "800" },
  contextLabel: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: "900",
    marginTop: 1,
  },
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
  searchIcon: {
    fontSize: 24,
    color: colors.primary,
    marginHorizontal: spacing.xs,
  },
  input: {
    flex: 1,
    minHeight: 50,
    fontSize: 17,
    color: colors.ink,
    paddingHorizontal: spacing.sm,
  },
  inlineButton: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  clearIcon: { fontSize: 24, color: colors.muted },
  scrollArea: { flexGrow: 0 },
  currentOriginRow: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  currentOriginIcon: {
    color: colors.primary,
    fontSize: 24,
    fontWeight: "900",
  },
  currentOriginLabel: {
    flex: 1,
    color: colors.primaryDark,
    fontSize: 14,
    fontWeight: "900",
  },
  results: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  sectionTitle: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    marginTop: spacing.md,
  },
  result: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 60,
    paddingVertical: spacing.sm,
  },
  resultIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#EEF2FF",
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: spacing.sm,
  },
  resultIconText: {
    color: colors.primaryDark,
    fontSize: 17,
    fontWeight: "900",
  },
  resultText: { flex: 1, minWidth: 0 },
  resultName: { color: colors.ink, fontSize: 15, fontWeight: "900" },
  resultMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: 2,
  },
  resultCategory: { color: colors.primary, fontSize: 11, fontWeight: "800" },
  resultDistance: { color: colors.muted, fontSize: 11, fontWeight: "700" },
  resultSubtitle: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
    marginTop: 2,
  },
  emptyText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    paddingVertical: spacing.lg,
  },
  routeControls: { paddingTop: spacing.sm },
  favoriteButton: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  favoriteIcon: { color: colors.primary, fontSize: 22 },
  favoriteText: { color: colors.primaryDark, fontWeight: "700" },
  transportHeader: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  transportTitle: { color: colors.ink, fontSize: 14, fontWeight: "900" },
  transportHeaderButton: {
    minHeight: 44,
    paddingHorizontal: spacing.sm,
    justifyContent: "center",
  },
  transportHeaderButtonText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
  },
  primaryModeGrid: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  moreModeGrid: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
    marginTop: spacing.sm,
  },
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
  modeButtonCompact: {
    flexBasis: "46%",
    flexGrow: 1,
    minWidth: 120,
    minHeight: 76,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  modeSelected: { backgroundColor: "#EEF2FF", borderColor: colors.primary },
  modeIcon: { fontSize: 20 },
  modeLabel: {
    color: colors.ink,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: "700",
    marginTop: 2,
    textAlign: "center",
    flexShrink: 1,
  },
  modeLabelCompact: {
    width: "100%",
    minHeight: 30,
    textAlignVertical: "center",
  },
  modeLabelSelected: { color: colors.primaryDark },
  selectedModeSummary: {
    minHeight: 58,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: "#EEF2FF",
    borderWidth: 1,
    borderColor: colors.primary,
  },
  selectedModeIcon: { fontSize: 22 },
  selectedModeLabel: {
    flex: 1,
    color: colors.primaryDark,
    fontSize: 14,
    fontWeight: "900",
  },
  changeModeText: { color: colors.primary, fontSize: 12, fontWeight: "800" },
  moreButton: { minHeight: 44, justifyContent: "center", alignItems: "center" },
  moreButtonText: { color: colors.primary, fontSize: 13, fontWeight: "800" },
  mobilityStatus: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
    paddingBottom: spacing.sm,
  },
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
