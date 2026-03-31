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
        primary: {
          DEFAULT: "#1e293b",
        },
        accent: {
          DEFAULT: "#f59e0b",
        },
      },
    },
  },
  plugins: [],
};
