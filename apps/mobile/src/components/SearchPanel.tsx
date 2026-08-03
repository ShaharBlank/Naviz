import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import type { Place, RoutePreference, TravelMode } from "../api/types";
import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  query: string;
  onQueryChange: (value: string) => void;
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
  searching: boolean;
  planning: boolean;
  locale: "he" | "en";
  onLocaleToggle: () => void;
}

const MODES: TravelMode[] = [
  "walk",
  "bike",
  "scooter",
  "car",
  "motorcycle",
  "truck",
  "transit",
  "bike_transit",
  "scooter_transit",
  "rental_transit",
];

function preferencesFor(mode: TravelMode): RoutePreference[] {
  if (mode === "walk") return ["fastest", "balanced_shade", "maximum_shade"];
  if (["car", "motorcycle", "truck"].includes(mode)) return ["fastest", "fewer_lights"];
  if (mode === "bike" || mode === "scooter") return ["fastest", "safer_streets"];
  return ["fastest", "fewer_transfers"];
}

export function SearchPanel(props: Props) {
  const { t } = useTranslation();
  const rtl = props.locale === "he";
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
  return (
    <View style={styles.panel}>
      <View style={styles.brandRow}>
        <View>
          <Text style={[styles.brand, rtl && styles.rtlText]}>{t("appName")}</Text>
          <Text style={[styles.tagline, rtl && styles.rtlText]}>{t("tagline")}</Text>
        </View>
        <Pressable
          accessibilityRole="button"
          style={styles.languageButton}
          onPress={props.onLocaleToggle}
        >
          <Text style={styles.languageText}>{t("language")}</Text>
        </Pressable>
      </View>
      <View style={styles.searchBox}>
        <Text style={styles.searchIcon}>⌕</Text>
        <TextInput
          accessibilityLabel={t("searchPlaceholder")}
          value={props.query}
          onChangeText={props.onQueryChange}
          placeholder={t("searchPlaceholder")}
          placeholderTextColor={colors.muted}
          style={[styles.input, rtl && styles.rtlText]}
          returnKeyType="search"
        />
        {props.searching ? <ActivityIndicator color={colors.primary} /> : null}
      </View>
      {props.query.length > 0 &&
      (!props.selectedDestination || editingDestination) &&
      props.results.length > 0 ? (
        <PlaceRows places={props.results.slice(0, 5)} rtl={rtl} onSelect={props.onSelect} />
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
      {props.selectedDestination && !editingDestination ? (
        <>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={favoriteSelected ? t("removeFavorite") : t("saveFavorite")}
            style={styles.favoriteButton}
            onPress={() => props.onToggleFavorite(props.selectedDestination!)}
          >
            <Text style={styles.favoriteText}>
              {favoriteSelected ? `★ ${t("favorites")}` : `☆ ${t("saveFavorite")}`}
            </Text>
          </Pressable>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipRow}
          >
            {MODES.map((mode) => (
              <Chip
                key={mode}
                label={t(`mode.${mode}`)}
                selected={props.mode === mode}
                onPress={() => props.onModeChange(mode)}
              />
            ))}
          </ScrollView>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipRow}
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
        </>
      ) : null}
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
        <Pressable key={place.id} style={styles.result} onPress={() => onSelect(place)}>
          <View style={styles.resultIcon}><Text>⌖</Text></View>
          <View style={styles.resultText}>
            <Text style={[styles.resultName, rtl && styles.rtlText]}>
              {rtl ? (place.name_he ?? place.name) : place.name}
            </Text>
            <Text style={[styles.resultSubtitle, rtl && styles.rtlText]} numberOfLines={1}>
              {place.subtitle}
            </Text>
          </View>
        </Pressable>
      ))}
    </View>
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
    position: "absolute", top: spacing.lg, left: spacing.md, right: spacing.md,
    maxHeight: "82%", borderRadius: radius.lg, backgroundColor: colors.surface,
    padding: spacing.lg, ...shadow,
  },
  brandRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  brand: { fontSize: 26, lineHeight: 31, fontWeight: "900", color: colors.ink },
  tagline: { fontSize: 13, color: colors.muted, marginTop: 1 },
  rtlText: { textAlign: "right", writingDirection: "rtl" },
  languageButton: { minHeight: 44, paddingHorizontal: spacing.md, justifyContent: "center" },
  languageText: { color: colors.primary, fontWeight: "700" },
  searchBox: {
    minHeight: 52, flexDirection: "row", alignItems: "center", marginTop: spacing.md,
    borderRadius: radius.md, backgroundColor: colors.surfaceElevated, paddingHorizontal: spacing.md,
  },
  searchIcon: { fontSize: 24, color: colors.primary, marginRight: spacing.sm },
  input: { flex: 1, minHeight: 48, fontSize: 17, color: colors.ink },
  results: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  sectionTitle: { color: colors.muted, fontSize: 12, fontWeight: "800", marginTop: spacing.md },
  result: { flexDirection: "row", alignItems: "center", minHeight: 58, paddingVertical: spacing.sm },
  resultIcon: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: "#EEF2FF",
    alignItems: "center", justifyContent: "center", marginRight: spacing.md,
  },
  resultText: { flex: 1 },
  resultName: { color: colors.ink, fontSize: 15, fontWeight: "700" },
  resultSubtitle: { color: colors.muted, fontSize: 12, marginTop: 2 },
  favoriteButton: { minHeight: 44, justifyContent: "center", alignItems: "flex-start" },
  favoriteText: { color: colors.primaryDark, fontWeight: "700" },
  chipRow: { gap: spacing.sm, paddingVertical: spacing.sm },
  chip: {
    minHeight: 44, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border,
    paddingHorizontal: spacing.lg, alignItems: "center", justifyContent: "center",
  },
  chipSelected: { backgroundColor: "#EEF2FF", borderColor: colors.primary },
  chipText: { color: colors.ink, fontWeight: "600" },
  chipTextSelected: { color: colors.primaryDark },
  planButton: {
    minHeight: 52, borderRadius: radius.md, backgroundColor: colors.primary,
    flexDirection: "row", gap: spacing.sm, alignItems: "center", justifyContent: "center",
  },
  planButtonText: { color: colors.surface, fontSize: 17, fontWeight: "800" },
  pressed: { opacity: 0.82 },
});
