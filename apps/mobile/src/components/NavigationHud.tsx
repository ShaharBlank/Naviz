import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { RouteAlternative } from "../api/types";
import { formatDistance, formatDuration, maneuverText } from "../features/navigation/presenters";
import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  route: RouteAlternative;
  maneuverIndex: number;
  rtl: boolean;
  recalculating: boolean;
  arrived: boolean;
  onStop: () => void;
}

export function NavigationHud(props: Props) {
  const { t } = useTranslation();
  const maneuver = props.route.maneuvers[props.maneuverIndex];
  const next = props.route.maneuvers[props.maneuverIndex + 1];
  return (
    <>
      <View style={styles.instruction} accessibilityLiveRegion="polite">
        <View style={styles.turnIcon}>
          <Text style={styles.turnIconText}>{iconFor(maneuver?.modifier)}</Text>
        </View>
        <View style={styles.instructionText}>
          <Text style={[styles.distance, props.rtl && styles.rtl]}>
            {maneuver ? `${Math.round(maneuver.distance_m)} m` : ""}
          </Text>
          <Text style={[styles.primary, props.rtl && styles.rtl]} numberOfLines={2}>
            {props.arrived
              ? t("status.arrived")
              : props.recalculating
                ? t("status.recalculating")
                : maneuverText(maneuver, (key, values) => String(t(key, values ?? {})))}
          </Text>
          {next ? (
            <Text style={[styles.next, props.rtl && styles.rtl]} numberOfLines={1}>
              {maneuverText(next, (key, values) => String(t(key, values ?? {})))}
            </Text>
          ) : null}
        </View>
      </View>
      <View style={styles.bottomBar}>
        <View>
          <Text style={styles.eta}>
            {new Date(props.route.arrival_at).toLocaleTimeString([], {
              hour: "2-digit", minute: "2-digit",
            })}
          </Text>
          <Text style={styles.summary}>
            {t("metrics.minutes", { value: formatDuration(props.route.metrics.duration_s) })} · {" "}
            {t("metrics.kilometers", { value: formatDistance(props.route.metrics.distance_m) })}
          </Text>
        </View>
        <Pressable style={styles.stopButton} onPress={props.onStop} accessibilityRole="button">
          <Text style={styles.stopText}>×</Text>
          <Text style={styles.stopLabel}>{t("stop")}</Text>
        </Pressable>
      </View>
    </>
  );
}

function iconFor(modifier?: string | null): string {
  if (modifier?.includes("left")) return "↰";
  if (modifier?.includes("right")) return "↱";
  if (modifier === "uturn") return "↶";
  if (modifier === "arrive") return "●";
  return "↑";
}

const styles = StyleSheet.create({
  instruction: {
    position: "absolute", top: spacing.lg, left: spacing.md, right: spacing.md,
    minHeight: 112, borderRadius: radius.lg, backgroundColor: colors.ink,
    flexDirection: "row", alignItems: "center", padding: spacing.lg, ...shadow,
  },
  turnIcon: {
    width: 68, height: 68, borderRadius: radius.md, backgroundColor: colors.primary,
    alignItems: "center", justifyContent: "center", marginRight: spacing.lg,
  },
  turnIconText: { color: colors.surface, fontSize: 40, fontWeight: "800" },
  instructionText: { flex: 1 },
  distance: { color: "#C7D2FE", fontSize: 14, fontWeight: "800" },
  primary: { color: colors.surface, fontSize: 20, fontWeight: "900", lineHeight: 25 },
  next: { color: "#CBD5E1", fontSize: 12, marginTop: spacing.xs },
  rtl: { textAlign: "right", writingDirection: "rtl" },
  bottomBar: {
    position: "absolute", left: spacing.md, right: spacing.md, bottom: spacing.lg,
    minHeight: 92, borderRadius: radius.lg, backgroundColor: colors.surface,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    padding: spacing.lg, ...shadow,
  },
  eta: { color: colors.ink, fontSize: 28, fontWeight: "900" },
  summary: { color: colors.muted, fontSize: 13, marginTop: spacing.xs },
  stopButton: { minWidth: 70, minHeight: 56, alignItems: "center", justifyContent: "center" },
  stopText: { color: colors.danger, fontSize: 28, lineHeight: 28 },
  stopLabel: { color: colors.danger, fontSize: 11, fontWeight: "700" },
});
