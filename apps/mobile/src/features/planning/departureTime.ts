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
  const sameDay = israelDateKey(selected) === israelDateKey(now);
  return new Intl.DateTimeFormat(locale === "he" ? "he-IL" : "en-IL", {
    timeZone: "Asia/Jerusalem",
    ...(sameDay
      ? {}
      : { weekday: "short" as const, day: "numeric" as const, month: "short" as const }),
    hour: "2-digit",
    minute: "2-digit",
  }).format(selected);
}

function israelDateKey(value: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Jerusalem",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(value);
}
