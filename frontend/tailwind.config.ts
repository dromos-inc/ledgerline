import type { Config } from "tailwindcss";

// Editorial, dense, keyboard-first aesthetic. Function over form (PRD §5).
// No rounded pills, no brand gradients. Type-driven information hierarchy.
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        // A restrained palette. Keyboard-driven tools don't need many colors.
        ink: {
          50: "#f8f8f7",
          100: "#ebebe8",
          200: "#d8d8d4",
          300: "#b5b5ae",
          400: "#8a8a80",
          500: "#5c5c53",
          600: "#3d3d37",
          700: "#2a2a25",
          800: "#1a1a17",
          900: "#0f0f0d",
        },
        accent: {
          DEFAULT: "#d97757", // terracotta — the "post" button
          hover: "#c5674a",
        },
        danger: "#b3261e",
        success: "#2e7d32",
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.125rem" }],
        base: ["0.875rem", { lineHeight: "1.25rem" }],
        lg: ["1rem", { lineHeight: "1.375rem" }],
        xl: ["1.125rem", { lineHeight: "1.5rem" }],
        "2xl": ["1.375rem", { lineHeight: "1.75rem" }],
        "3xl": ["1.75rem", { lineHeight: "2rem" }],
      },
    },
  },
  plugins: [],
};

export default config;
