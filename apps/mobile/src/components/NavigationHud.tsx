import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { RouteAlternative } from "../api/types";
import {
  formatDuration,
  formatIsraelTime,
  formatNavigationDistance,
  maneuverText,
} from "../features/navigation/presenters";
import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  route: RouteAlternative;
  maneuverIndex: number;
  rtl: boolean;
  locale: "he" | "en";
  remainingDistanceM: number | null;
  progressFraction: number;
  muted: boolean;
  recalculating: boolean;
  arrived: boolean;
  onToggleMute: () => void;
  onStop: () => void;
}

export function NavigationHud(props: Props) {
  const { t } = useTranslation();
  const maneuver = props.route.maneuvers[props.maneuverIndex];
  const next = props.route.maneuvers[props.maneuverIndex + 1];
  const remainingDistance = props.remainingDistanceM ?? props.route.metrics.distance_m;
  const remainingDuration = Math.max(
    0,
    props.route.metrics.duration_s * (1 - Math.min(1, Math.max(0, props.progressFraction))),
  );
  const arrival = formatIsraelTime(props.route.arrival_at, props.locale);
  const navigationDistance = formatNavigationDistance(remainingDistance);
  return (
    <>
      <View
        style={[styles.instruction, props.rtl && styles.rowReverse]}
        accessibilityLiveRegion="polite"
      >
        <View style={styles.turnIcon}>
          <Text style={styles.turnIconText}>{iconFor(maneuver?.modifier)}</Text>
        </View>
        <View style={styles.instructionText}>
          <Text style={[styles.distance, props.rtl && styles.rtl]}>
            {maneuver ? formatManeuverDistance(maneuver.distance_m) : ""}
          </Text>
          <Text style={[styles.primary, props.rtl && styles.rtl]} numberOfLines={2}>
            {props.arrived
              ? t("status.arrived")
              : props.recalculating
                ? t("status.recalculating")
                : maneuverText(
                    maneuver,
                    (key, values) => String(t(key, values ?? {})),
                    props.locale === "en",
                  )}
          </Text>
          {next ? (
            <Text style={[styles.next, props.rtl && styles.rtl]} numberOfLines={1}>
              {maneuverText(
                next,
                (key, values) => String(t(key, values ?? {})),
                props.locale === "en",
              )}
            </Text>
          ) : null}
        </View>
      </View>
      <View style={[styles.bottomBar, props.rtl && styles.rowReverse]}>
        <View style={styles.tripSummary}>
          <Text style={[styles.eta, props.rtl && styles.rtl]}>{arrival}</Text>
          <Text style={[styles.summary, props.rtl && styles.rtl]}>
            {t("metrics.minutes", { value: formatDuration(remainingDuration) })} ·{" "}
            {t(navigationDistance.key, { value: navigationDistance.value })}
          </Text>
        </View>
        <View style={[styles.actions, props.rtl && styles.rowReverse]}>
          <Pressable
            style={styles.actionButton}
            onPress={props.onToggleMute}
            accessibilityRole="button"
            accessibilityLabel={props.muted ? t("unmute") : t("mute")}
          >
            <Text style={styles.actionIcon}>{props.muted ? "🔇" : "🔊"}</Text>
          </Pressable>
          <Pressable
            style={styles.stopButton}
            onPress={props.onStop}
            accessibilityRole="button"
            accessibilityLabel={t("stop")}
          >
            <Text style={styles.stopText}>×</Text>
          </Pressable>
        </View>
      </View>
    </>
  );
}

function formatManeuverDistance(distanceM: number): string {
  if (distanceM < 1_000) return `${Math.max(10, Math.round(distanceM / 10) * 10)} m`;
  return `${Math.round((distanceM / 1_000) * 10) / 10} km`;
}

function iconFor(modifier?: string | null): string {
  if (modifier === "board") return "🚌";
  if (modifier?.includes("left")) return "↰";
  if (modifier?.includes("right")) return "↱";
  if (modifier === "uturn") return "↶";
  if (modifier === "arrive") return "●";
  return "↑";
}

const styles = StyleSheet.create({
  instruction: {
    position: "absolute",
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    minHeight: 96,
    borderRadius: radius.lg,
    backgroundColor: colors.ink,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    ...shadow,
  },
  rowReverse: { flexDirection: "row-reverse" },
  turnIcon: {
    width: 58,
    height: 58,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: spacing.sm,
  },
  turnIconText: { color: colors.surface, fontSize: 34, fontWeight: "800" },
  instructionText: { flex: 1, minWidth: 0 },
  distance: { color: "#C7D2FE", fontSize: 14, fontWeight: "800" },
  primary: {
    color: colors.surface,
    fontSize: 19,
    fontWeight: "900",
    lineHeight: 23,
  },
  next: { color: "#CBD5E1", fontSize: 12, marginTop: spacing.xs },
  rtl: { textAlign: "right", writingDirection: "rtl" },
  bottomBar: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    minHeight: 78,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    ...shadow,
  },
  tripSummary: { flex: 1, paddingHorizontal: spacing.xs },
  eta: { color: colors.ink, fontSize: 24, fontWeight: "900" },
  summary: { color: colors.muted, fontSize: 13, marginTop: spacing.xs },
  actions: { flexDirection: "row", alignItems: "center" },
  actionButton: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },
  actionIcon: { fontSize: 20 },
  stopButton: {
    width: 48,
    height: 48,
    borderRadius: radius.pill,
    backgroundColor: "#FEF2F2",
    alignItems: "center",
    justifyContent: "center",
  },
  stopText: { color: colors.danger, fontSize: 30, lineHeight: 32 },
});
