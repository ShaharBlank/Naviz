import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  message: string;
  tone?: "info" | "warning" | "error";
  actionLabel?: string;
  onAction?: () => void;
  rtl?: boolean;
}

export function StatusBanner({ message, tone = "info", actionLabel, onAction, rtl }: Props) {
  return (
    <View
      accessibilityLiveRegion="polite"
      style={[styles.banner, tone === "warning" && styles.warning, tone === "error" && styles.error]}
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
    position: "absolute", left: spacing.md, right: spacing.md, bottom: 290,
    minHeight: 54, borderRadius: radius.md, backgroundColor: colors.ink,
    flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, ...shadow,
  },
  warning: { backgroundColor: "#92400E" },
  error: { backgroundColor: colors.danger },
  message: { flex: 1, color: colors.surface, fontWeight: "700" },
  rtl: { textAlign: "right", writingDirection: "rtl" },
  action: { minHeight: 44, paddingHorizontal: spacing.md, justifyContent: "center" },
  actionText: { color: colors.surface, textDecorationLine: "underline", fontWeight: "800" },
});

