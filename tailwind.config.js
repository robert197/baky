/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#1e293b", light: "#334155" },
        secondary: { DEFAULT: "#475569" },
        accent: { DEFAULT: "#f59e0b", light: "#fbbf24" },
        success: { DEFAULT: "#10b981" },
        warning: { DEFAULT: "#f59e0b" },
        danger: { DEFAULT: "#f43f5e" },
        surface: { DEFAULT: "#f8fafc" },
        card: { DEFAULT: "#ffffff" },
        border: { DEFAULT: "#e2e8f0" },
        muted: { DEFAULT: "#94a3b8" },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [
    function ({ addUtilities }) {
      addUtilities({
        ".pb-safe": {
          "padding-bottom": "env(safe-area-inset-bottom)",
        },
      });
    },
  ],
};
