import DateTimePicker, {
  DateTimePickerAndroid,
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { formatDepartureTime, sanitizeFutureDeparture } from "../features/planning/departureTime";
import { colors, radius, shadow, spacing } from "../theme/tokens";

interface Props {
  value: Date | null;
  locale: "he" | "en";
  onChange: (value: Date | null) => void;
}

export function DepartureTimeControl({ value, locale, onChange }: Props) {
  const { t } = useTranslation();
  const [iosVisible, setIosVisible] = useState(false);
  const [draft, setDraft] = useState(() => initialPickerValue(value));
  const rtl = locale === "he";
  const label = value ? formatDepartureTime(value, locale) : t("departure.now");

  const commit = (selected: Date) => onChange(sanitizeFutureDeparture(selected));
  const open = () => {
    const initial = initialPickerValue(value);
    setDraft(initial);
    if (Platform.OS === "android") {
      openAndroidDateTime(initial, commit);
      return;
    }
    setIosVisible(true);
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("departure.change")}
        accessibilityValue={{ text: label }}
        onPress={open}
        style={[styles.control, rtl && styles.rowReverse]}
      >
        <Text style={styles.icon}>◷</Text>
        <View style={styles.labelGroup}>
          <Text style={[styles.eyebrow, rtl && styles.rtlText]}>
            {t("departure.label")}
          </Text>
          <Text style={[styles.label, rtl && styles.rtlText]} numberOfLines={1}>
            {label}
          </Text>
        </View>
      </Pressable>

      {Platform.OS === "ios" ? (
        <Modal
          visible={iosVisible}
          transparent
          animationType="fade"
          onRequestClose={() => setIosVisible(false)}
        >
          <Pressable style={styles.backdrop} onPress={() => setIosVisible(false)}>
            <Pressable style={styles.sheet} onPress={() => undefined}>
              <Text style={[styles.title, rtl && styles.rtlText]}>
                {t("departure.choose")}
              </Text>
              <DateTimePicker
                value={draft}
                mode="datetime"
                display="inline"
                minimumDate={new Date()}
                locale={locale === "he" ? "he-IL" : "en-IL"}
                onChange={(_event, selected) => {
                  if (selected) setDraft(selected);
                }}
              />
              <View style={[styles.actions, rtl && styles.rowReverse]}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    onChange(null);
                    setIosVisible(false);
                  }}
                  style={styles.secondaryButton}
                >
                  <Text style={styles.secondaryText}>{t("departure.now")}</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    commit(draft);
                    setIosVisible(false);
                  }}
                  style={styles.primaryButton}
                >
                  <Text style={styles.primaryText}>{t("departure.done")}</Text>
                </Pressable>
              </View>
            </Pressable>
          </Pressable>
        </Modal>
      ) : null}
    </>
  );
}

function initialPickerValue(value: Date | null): Date {
  if (value && value.getTime() > Date.now()) return value;
  return new Date(Date.now() + 30 * 60_000);
}

function openAndroidDateTime(initial: Date, commit: (value: Date) => void) {
  DateTimePickerAndroid.open({
    value: initial,
    mode: "date",
    minimumDate: new Date(),
    onChange: (dateEvent: DateTimePickerEvent, selectedDate?: Date) => {
      if (dateEvent.type !== "set" || !selectedDate) return;
      DateTimePickerAndroid.open({
        value: initial,
        mode: "time",
        is24Hour: true,
        onChange: (timeEvent: DateTimePickerEvent, selectedTime?: Date) => {
          if (timeEvent.type !== "set" || !selectedTime) return;
          const combined = new Date(selectedDate);
          combined.setHours(selectedTime.getHours(), selectedTime.getMinutes(), 0, 0);
          commit(combined);
        },
      });
    },
  });
}

const styles = StyleSheet.create({
  control: {
    minHeight: 56,
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowReverse: { flexDirection: "row-reverse" },
  rtlText: { textAlign: "right", writingDirection: "rtl" },
  icon: { color: colors.primary, fontSize: 21, fontWeight: "900" },
  labelGroup: { flex: 1, minWidth: 0 },
  eyebrow: { color: colors.muted, fontSize: 10, fontWeight: "800" },
  label: { color: colors.ink, fontSize: 13, fontWeight: "900", marginTop: 1 },
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(15, 23, 42, 0.28)",
  },
  sheet: {
    backgroundColor: colors.surface,
    padding: spacing.lg,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    ...shadow,
  },
  title: { color: colors.ink, fontSize: 18, fontWeight: "900" },
  actions: { flexDirection: "row", justifyContent: "flex-end", gap: spacing.sm },
  secondaryButton: { minHeight: 48, paddingHorizontal: spacing.lg, justifyContent: "center" },
  secondaryText: { color: colors.primary, fontWeight: "900" },
  primaryButton: {
    minHeight: 48,
    paddingHorizontal: spacing.xl,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    justifyContent: "center",
  },
  primaryText: { color: colors.surface, fontWeight: "900" },
});
