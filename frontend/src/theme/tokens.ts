/** 4ct-inspired design tokens — single source of truth for the Sreality Platform UI.
 *  Dominant green (accent), secondary navy (brand), white surfaces, controlled grays. */
export const tokens = {
  color: {
    accent: {
      DEFAULT: "#54AB34",
      dark: "#438A29",
      light: "#EDF7E9",
      glow: "rgba(84, 171, 52, 0.22)",
    },
    brand: {
      DEFAULT: "#0055A5",
      dark: "#004484",
      light: "#E6F0F8",
      navy: "#0B1F3A",
      navyLight: "#152D50",
    },
    ink: {
      DEFAULT: "#414042",
      muted: "#6B7280",
      faint: "#CBD5E1",
    },
    surface: {
      DEFAULT: "#FFFFFF",
      muted: "#F4F6F9",
      elevated: "#FFFFFF",
      border: "#E2E8F0",
      borderStrong: "#CBD5E1",
    },
    danger: { DEFAULT: "#EF3E2D", dark: "#C43225", light: "#FDECEA" },
    warning: { DEFAULT: "#F26715", dark: "#C45210", light: "#FEF0E8" },
    caution: { DEFAULT: "#FFBE00", dark: "#CC9800", light: "#FFF8E0" },
    info: { DEFAULT: "#0055A5", light: "#E6F0F8", border: "#93C5FD" },
  },
  radius: {
    sm: "0.375rem",
    md: "0.5rem",
    lg: "0.75rem",
    xl: "1rem",
  },
  shadow: {
    card: "0 1px 2px rgba(11, 31, 58, 0.04), 0 4px 16px rgba(11, 31, 58, 0.06)",
    cardHover: "0 4px 8px rgba(11, 31, 58, 0.06), 0 12px 28px rgba(11, 31, 58, 0.1)",
    nav: "0 4px 24px rgba(11, 31, 58, 0.18)",
    map: "0 8px 32px rgba(11, 31, 58, 0.12)",
  },
  motion: {
    fast: "150ms",
    base: "220ms",
    slow: "320ms",
  },
} as const;

export type BannerVariant = "info" | "success" | "warning" | "error" | "neutral";
