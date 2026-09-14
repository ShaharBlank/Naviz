export function departureForRequest(
  selected: Date | null,
  now: Date = new Date(),
): Date {
  return selected && selected.getTime() > now.getTime() ? selected : now;
}

export function sanitizeFutureDeparture(
  selected: Date,
  now: Date = new Date(),
): Date | null {
  return selected.getTime() >= now.getTime() + 60_000 ? selected : null;
}

export function shadowDisplayTime(
  routeDepartureAt: string,
  navigationActive: boolean,
  now: Date = new Date(),
): Date {
  const selected = navigationActive ? now : new Date(routeDepartureAt);
  selected.setSeconds(0, 0);
  return selected;
}

export function formatDepartureTime(
  selected: Date,
  locale: "he" | "en",
  now: Date = new Date(),
): string {
  const sameDay =
    selected.getFullYear() === now.getFullYear() &&
    selected.getMonth() === now.getMonth() &&
    selected.getDate() === now.getDate();
  return new Intl.DateTimeFormat(locale === "he" ? "he-IL" : "en-IL", {
    ...(sameDay
      ? {}
      : { weekday: "short" as const, day: "numeric" as const, month: "short" as const }),
    hour: "2-digit",
    minute: "2-digit",
  }).format(selected);
}
