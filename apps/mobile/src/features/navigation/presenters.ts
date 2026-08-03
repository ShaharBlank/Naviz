import type { Maneuver, RouteAlternative } from "../../api/types";

export function routeLabelKey(labelKey: string): string {
  return labelKey.startsWith("route.") ? labelKey : `route.${labelKey}`;
}

export function formatDuration(seconds: number): number {
  return Math.max(1, Math.round(seconds / 60));
}

export function formatDistance(meters: number): number {
  return Math.round((meters / 1_000) * 10) / 10;
}

export function maneuverText(
  maneuver: Maneuver | undefined,
  translate: (key: string, values?: Record<string, string>) => string,
): string {
  if (!maneuver) return "";
  if (maneuver.instruction_key === "navigation.arrive") return translate("navigation.arrive");
  const modifier = maneuver.modifier
    ? translate(`navigation.${maneuver.modifier}`)
    : translate("navigation.straight");
  return translate(maneuver.instruction_key, {
    modifier,
    street: maneuver.street_name ?? "",
  });
}

export function secondaryMetrics(route: RouteAlternative): string[] {
  const result: string[] = [];
  if (route.metrics.shade_fraction != null) {
    result.push(`${Math.round(route.metrics.shade_fraction * 100)}% shade`);
  }
  if (route.metrics.signals_avoided) result.push(`${route.metrics.signals_avoided} fewer lights`);
  if (route.metrics.transfers) result.push(`${route.metrics.transfers} transfers`);
  return result;
}
