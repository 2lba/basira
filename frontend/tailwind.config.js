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
          subtle: "#1f1f1f",
          DEFAULT: "#2a2a2a",
        },
        fg: {
          DEFAULT: "#f5f5f5",
          secondary: "#a3a3a3",
          muted: "#525252",
        },
        accent: "#6366f1",
        success: "#10b981",
        warning: "#f59e0b",
        danger: "#ef4444",
        ai: "#8b5cf6",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
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
