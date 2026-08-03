import { useTranslation } from "react-i18next";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { RouteAlternative } from "../api/types";
import { formatDistance, formatDuration, routeLabelKey } from "../features/navigation/presenters";
import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  routes: RouteAlternative[];
  selectedRouteId: string | null;
  onSelect: (route: RouteAlternative) => void;
  onStart: () => void;
  rtl: boolean;
}

export function RouteCards({ routes, selectedRouteId, onSelect, onStart, rtl }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} snapToInterval={306}>
        {routes.map((route) => {
          const selected = route.id === selectedRouteId;
          const duration = t("metrics.minutes", { value: formatDuration(route.metrics.duration_s) });
          const distance = t("metrics.kilometers", { value: formatDistance(route.metrics.distance_m) });
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
              <View style={styles.headingRow}>
                <Text style={[styles.name, rtl && styles.rtl]}>{t(routeLabelKey(route.label_key))}</Text>
                <View style={[styles.confidence, route.quality.confidence === "low" && styles.low]}>
                  <Text style={styles.confidenceText}>{route.quality.confidence}</Text>
                </View>
              </View>
              <View style={styles.primaryMetrics}>
                <Text style={styles.duration}>{duration}</Text>
                <Text style={styles.distance}>{distance}</Text>
              </View>
              <View style={styles.metricRow}>
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
                ) : null}
                {route.metrics.transfers ? (
                  <Metric
                    color={colors.transit}
                    text={t("metrics.transfers", { value: route.metrics.transfers })}
                  />
                ) : null}
              </View>
              {route.warnings?.[0] ? (
                <Text style={[styles.warning, rtl && styles.rtl]} numberOfLines={2}>
                  {route.warnings[0]}
                </Text>
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
  container: { position: "absolute", left: spacing.md, right: spacing.md, bottom: spacing.lg },
  card: {
    width: 294, minHeight: 154, marginRight: spacing.md, padding: spacing.lg,
    borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 2,
    borderColor: "transparent", ...shadow,
  },
  cardSelected: { borderColor: colors.primary },
  headingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  name: { fontSize: 17, fontWeight: "800", color: colors.ink, flex: 1 },
  rtl: { textAlign: "right", writingDirection: "rtl" },
  confidence: {
    borderRadius: radius.pill, backgroundColor: "#DCFCE7", paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  low: { backgroundColor: "#FEF3C7" },
  confidenceText: { color: colors.muted, fontSize: 10, textTransform: "uppercase" },
  primaryMetrics: { flexDirection: "row", gap: spacing.md, alignItems: "baseline", marginTop: spacing.sm },
  duration: { fontSize: 26, fontWeight: "900", color: colors.primaryDark },
  distance: { fontSize: 14, color: colors.muted },
  metricRow: { flexDirection: "row", gap: spacing.md, flexWrap: "wrap", marginTop: spacing.sm },
  metric: { flexDirection: "row", gap: spacing.xs, alignItems: "center" },
  dot: { width: 8, height: 8, borderRadius: 4 },
  metricText: { fontSize: 12, fontWeight: "600", color: colors.ink },
  warning: { fontSize: 11, color: colors.muted, marginTop: spacing.sm },
  startButton: {
    minHeight: 54, marginTop: spacing.md, borderRadius: radius.md, backgroundColor: colors.primary,
    alignItems: "center", justifyContent: "center", ...shadow,
  },
  startText: { color: colors.surface, fontSize: 18, fontWeight: "900" },
});
