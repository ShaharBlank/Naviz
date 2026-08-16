import { useTranslation } from "react-i18next";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { RouteAlternative } from "../api/types";
import {
  formatDistance,
  formatDuration,
  formatTelAvivTime,
  routeLabelKey,
} from "../features/navigation/presenters";
import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  routes: RouteAlternative[];
  selectedRouteId: string | null;
  onSelect: (route: RouteAlternative) => void;
  onStart: () => void;
  onBack: () => void;
  rtl: boolean;
}

export function RouteCards({ routes, selectedRouteId, onSelect, onStart, onBack, rtl }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.container}>
      <View style={[styles.header, rtl && styles.rowReverse]}>
        <Pressable accessibilityRole="button" onPress={onBack} style={styles.backButton}>
          <Text style={styles.backIcon}>{rtl ? "→" : "←"}</Text>
        </Pressable>
        <Text style={[styles.headerTitle, rtl && styles.rtl]}>{t("planRoute")}</Text>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        snapToInterval={310}
        decelerationRate="fast"
        contentContainerStyle={rtl ? styles.rowReverse : undefined}
      >
        {routes.map((route) => {
          const selected = route.id === selectedRouteId;
          const duration = t("metrics.minutes", { value: formatDuration(route.metrics.duration_s) });
          const distance = t("metrics.kilometers", { value: formatDistance(route.metrics.distance_m) });
          const arrival = formatTelAvivTime(route.arrival_at, rtl ? "he" : "en");
          const fallback = route.fallback_reason
            ? t(`fallback.${route.fallback_reason}`, { defaultValue: "" })
            : "";
          const transitLeg = route.legs.find((leg) => leg.mode === "transit" && leg.transit);
          return (
            <Pressable
              key={route.id}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={t("accessibility.routeCard", {
                name: t(routeLabelKey(route.label_key)), duration, distance,
              })}
              onPress={() => onSelect(route)}
              style={[styles.card, selected && styles.cardSelected]}
            >
              <View style={[styles.headingRow, rtl && styles.rowReverse]}>
                <Text style={[styles.name, rtl && styles.rtl]}>
                  {t(routeLabelKey(route.label_key))}
                </Text>
                <View style={styles.confidence}>
                  <Text style={styles.confidenceText}>
                    {t(`confidence.${route.quality.confidence}`)}
                  </Text>
                </View>
              </View>
              <View style={[styles.primaryMetrics, rtl && styles.rowReverse]}>
                <Text style={styles.duration}>{duration}</Text>
                <Text style={styles.distance}>{distance}</Text>
              </View>
              <Text style={[styles.arrival, rtl && styles.rtl]}>
                {t("metrics.arrival", { value: arrival })}
              </Text>
              {transitLeg?.transit ? (
                <View style={[styles.transitSummary, rtl && styles.rowReverse]}>
                  <View style={styles.transitBadge}>
                    <Text style={styles.transitBadgeText}>
                      {transitLeg.transit.route_short_name || "●"}
                    </Text>
                  </View>
                  <View style={styles.transitCopy}>
                    <Text style={[styles.transitHeadsign, rtl && styles.rtl]} numberOfLines={1}>
                      {transitLeg.transit.headsign || transitLeg.to_name}
                    </Text>
                    <Text style={[styles.transitTime, rtl && styles.rtl]} numberOfLines={1}>
                      {t("metrics.transitDeparture", {
                        value: formatTelAvivTime(
                          transitLeg.transit.departure_at,
                          rtl ? "he" : "en",
                        ),
                      })}
                    </Text>
                    {transitLeg.transit.vehicle_rule_source?.includes("folded-vehicle") ? (
                      <Text style={[styles.vehicleRule, rtl && styles.rtl]} numberOfLines={1}>
                        {t("metrics.foldBeforeBoarding")}
                      </Text>
                    ) : null}
                  </View>
                </View>
              ) : null}
              <View style={[styles.metricRow, rtl && styles.rowReverse]}>
                {route.metrics.shade_fraction != null ? (
                  <Metric
                    color={colors.shade}
                    text={t("metrics.shade", { value: Math.round(route.metrics.shade_fraction * 100) })}
                  />
                ) : null}
                {route.metrics.signals_avoided ? (
                  <Metric
                    color={colors.mixed}
                    text={t("metrics.signalsAvoided", { value: route.metrics.signals_avoided })}
                  />
                ) : route.metrics.traffic_signals != null ? (
                  <Metric
                    color={colors.mixed}
                    text={t("metrics.signals", { value: route.metrics.traffic_signals })}
                  />
                ) : null}
                {transitLeg ? (
                  <Metric
                    color={colors.transit}
                    text={t("metrics.transfers", { value: route.metrics.transfers })}
                  />
                ) : null}
                {transitLeg && route.metrics.walking_distance_m > 0 ? (
                  <Metric
                    color={colors.muted}
                    text={t("metrics.walking", {
                      value: formatDistance(route.metrics.walking_distance_m),
                    })}
                  />
                ) : null}
              </View>
              {fallback ? (
                <Text style={[styles.note, rtl && styles.rtl]} numberOfLines={2}>
                  {fallback}
                </Text>
              ) : null}
              {transitLeg ? (
                <Pressable
                  accessibilityRole="link"
                  onPress={() => void Linking.openURL("https://transitous.org/sources/")}
                  style={styles.sourceLink}
                >
                  <Text style={[styles.sourceText, rtl && styles.rtl]}>
                    {t("metrics.transitSource")}
                  </Text>
                </Pressable>
              ) : null}
            </Pressable>
          );
        })}
      </ScrollView>
      <Pressable style={styles.startButton} onPress={onStart} accessibilityRole="button">
        <Text style={styles.startText}>{t("start")}</Text>
      </Pressable>
    </View>
  );
}

function Metric({ color, text }: { color: string; text: string }) {
  return (
    <View style={styles.metric}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.metricText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    padding: spacing.md,
    ...shadow,
  },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  rowReverse: { flexDirection: "row-reverse" },
  backButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  backIcon: { color: colors.primaryDark, fontSize: 25, fontWeight: "800" },
  headerTitle: { flex: 1, color: colors.ink, fontSize: 17, fontWeight: "900" },
  card: {
    width: 298,
    minHeight: 172,
    marginHorizontal: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 2,
    borderColor: "transparent",
  },
  cardSelected: { borderColor: colors.primary, backgroundColor: "#F5F3FF" },
  headingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 6 },
  name: { fontSize: 17, fontWeight: "900", color: colors.ink, flex: 1 },
  rtl: { textAlign: "right", writingDirection: "rtl" },
  confidence: {
    borderRadius: radius.pill,
    backgroundColor: "#DCFCE7",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  confidenceText: { color: colors.success, fontSize: 10, fontWeight: "800" },
  primaryMetrics: { flexDirection: "row", gap: spacing.md, alignItems: "baseline", marginTop: spacing.sm },
  duration: { fontSize: 27, fontWeight: "900", color: colors.primaryDark },
  distance: { fontSize: 14, color: colors.muted },
  arrival: { color: colors.muted, fontSize: 12, marginTop: 2 },
  transitSummary: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  transitBadge: {
    minWidth: 34,
    minHeight: 28,
    borderRadius: radius.sm,
    backgroundColor: colors.transit,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
  },
  transitBadgeText: { color: colors.surface, fontSize: 12, fontWeight: "900" },
  transitCopy: { flex: 1, minWidth: 0 },
  transitHeadsign: { color: colors.ink, fontSize: 12, fontWeight: "800" },
  transitTime: { color: colors.muted, fontSize: 10, marginTop: 1 },
  vehicleRule: { color: colors.primaryDark, fontSize: 10, fontWeight: "800", marginTop: 1 },
  metricRow: { flexDirection: "row", gap: spacing.md, flexWrap: "wrap", marginTop: spacing.sm },
  metric: { flexDirection: "row", gap: spacing.xs, alignItems: "center" },
  dot: { width: 8, height: 8, borderRadius: 4 },
  metricText: { fontSize: 12, fontWeight: "700", color: colors.ink },
  note: { fontSize: 11, lineHeight: 15, color: colors.muted, marginTop: spacing.sm },
  sourceLink: { minHeight: 44, justifyContent: "center", alignSelf: "stretch" },
  sourceText: { color: colors.primary, fontSize: 11, fontWeight: "700" },
  startButton: {
    minHeight: 54,
    marginTop: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  startText: { color: colors.surface, fontSize: 18, fontWeight: "900" },
});
