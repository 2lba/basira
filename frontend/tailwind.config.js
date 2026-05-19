/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0a0a0a",
        surface: "#141414",
        border: {
          subtle: "#262626",
          DEFAULT: "#3f3f3f",
        },
        fg: {
          DEFAULT: "#fafafa",
          secondary: "#a3a3a3",
          muted: "#525252",
        },
        accent: {
          DEFAULT: "#06b6d4",
          hover: "#22d3ee",
        },
        success: "#10b981",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: [
          "Space Grotesk",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "8px",
        card: "12px",
      },
      maxWidth: {
        content: "1280px",
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
    },
  },
  plugins: [],
};
