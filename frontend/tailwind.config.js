/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#54AB34",
          dark: "#438A29",
          light: "#EDF7E9",
        },
        brand: {
          DEFAULT: "#0055A5",
          dark: "#004484",
          light: "#E6F0F8",
        },
        navy: {
          DEFAULT: "#0B1F3A",
          light: "#152D50",
          muted: "#1E3A5F",
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
        },
        danger: {
          DEFAULT: "#EF3E2D",
          dark: "#C43225",
          light: "#FDECEA",
        },
        warning: {
          DEFAULT: "#F26715",
          dark: "#C45210",
          light: "#FEF0E8",
        },
        caution: {
          DEFAULT: "#FFBE00",
          dark: "#CC9800",
          light: "#FFF8E0",
        },
        info: {
          DEFAULT: "#0055A5",
          light: "#E6F0F8",
          border: "#93C5FD",
        },
      },
      fontFamily: {
        sans: ["Raleway", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11, 31, 58, 0.04), 0 4px 16px rgba(11, 31, 58, 0.06)",
        "card-hover": "0 4px 8px rgba(11, 31, 58, 0.06), 0 12px 28px rgba(11, 31, 58, 0.1)",
        nav: "0 4px 24px rgba(11, 31, 58, 0.18)",
        map: "0 8px 32px rgba(11, 31, 58, 0.12)",
        glow: "0 0 0 3px rgba(84, 171, 52, 0.18)",
      },
      borderRadius: {
        xl: "0.875rem",
      },
      animation: {
        shimmer: "shimmer 1.4s ease-in-out infinite",
        "fade-in": "fadeIn 0.35s ease-out",
        "slide-up": "slideUp 0.35s ease-out",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      backgroundImage: {
        "app-gradient": "linear-gradient(180deg, #F4F6F9 0%, #EEF2F7 100%)",
        "nav-gradient": "linear-gradient(135deg, #071525 0%, #0B1F3A 38%, #152D50 72%, #0B1F3A 100%)",
        "kpi-accent": "linear-gradient(135deg, rgba(84,171,52,0.08) 0%, rgba(255,255,255,0) 60%)",
        "kpi-brand": "linear-gradient(135deg, rgba(0,85,165,0.06) 0%, rgba(255,255,255,0) 60%)",
      },
    },
  },
  plugins: [],
};
