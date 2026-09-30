import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--color-ink)", muted: "var(--color-muted)", page: "var(--color-page)",
        panel: "var(--color-panel)", pitch: "var(--color-pitch)", accent: "var(--color-accent)",
        sky: "var(--color-sky)", alert: "var(--color-alert)", line: "var(--color-line)",
      },
      fontFamily: { sans: ["var(--font-ui)"], display: ["var(--font-display)"] },
      fontSize: { xs: "var(--text-xs)", sm: "var(--text-sm)", base: "var(--text-base)", lg: "var(--text-lg)", xl: "var(--text-xl)", "2xl": "var(--text-2xl)", "3xl": "var(--text-3xl)" },
      spacing: { 1: "var(--space-1)", 2: "var(--space-2)", 3: "var(--space-3)", 4: "var(--space-4)", 6: "var(--space-6)", 8: "var(--space-8)" },
      transitionDuration: { fast: "var(--motion-fast)", standard: "var(--motion-standard)", emphasis: "var(--motion-emphasis)" },
      transitionTimingFunction: { standard: "var(--ease-standard)", enter: "var(--ease-enter)" },
    },
  },
  plugins: [],
};

export default config;
