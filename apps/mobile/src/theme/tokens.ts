export const colors = {
  ink: "#111827",
  muted: "#667085",
  surface: "#FFFFFF",
  surfaceElevated: "#F8FAFC",
  border: "#E2E8F0",
  primary: "#5B4BDB",
  primaryDark: "#4034A8",
  shade: "#2563EB",
  mixed: "#14B8A6",
  sun: "#F59E0B",
  transit: "#7C3AED",
  danger: "#DC2626",
  success: "#16803C",
  scrim: "rgba(17, 24, 39, 0.18)",
} as const;

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const radius = { sm: 10, md: 16, lg: 24, pill: 999 } as const;

export const shadow = {
  shadowColor: "#111827",
  shadowOpacity: 0.16,
  shadowRadius: 14,
  shadowOffset: { width: 0, height: 6 },
  elevation: 8,
} as const;

