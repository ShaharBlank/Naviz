import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  message: string;
  tone?: "info" | "warning" | "error";
  actionLabel?: string;
  onAction?: () => void;
  rtl?: boolean;
  navigation?: boolean;
}

export function StatusBanner({
  message,
  tone = "info",
  actionLabel,
  onAction,
  rtl,
  navigation = false,
}: Props) {
  return (
    <View
      accessibilityLiveRegion="polite"
      style={[
        styles.banner,
        navigation && styles.navigationBanner,
        tone === "warning" && styles.warning,
        tone === "error" && styles.error,
      ]}
    >
      <Text style={[styles.message, rtl && styles.rtl]}>{message}</Text>
      {actionLabel && onAction ? (
        <Pressable onPress={onAction} style={styles.action} accessibilityRole="button">
          <Text style={styles.actionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    position: "absolute",
    top: 70,
    left: spacing.md,
    right: spacing.md,
    minHeight: 44,
    borderRadius: radius.pill,
    backgroundColor: "rgba(17, 24, 39, 0.94)",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    ...shadow,
  },
  navigationBanner: { top: 118 },
  warning: { backgroundColor: "rgba(146, 64, 14, 0.94)" },
  error: { backgroundColor: "rgba(185, 28, 28, 0.95)" },
  message: { flex: 1, color: colors.surface, fontSize: 12, fontWeight: "700" },
  rtl: { textAlign: "right", writingDirection: "rtl" },
  action: { minHeight: 44, paddingHorizontal: spacing.md, justifyContent: "center" },
  actionText: { color: colors.surface, fontWeight: "900" },
});
