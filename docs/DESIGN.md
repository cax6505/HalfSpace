# Product and visual design rules

## Visual direction

Use a dark broadcast-analyst aesthetic. Keep the pitch as the dominant visual anchor and let sequence movement, pressure, and space explain the data. Avoid default component-library styling: use restrained square-corner panels, fine separators, compact labels, and deliberate typography. Keep the interface dense enough for analysis while preserving readable touch targets.

## Tokens

The canonical CSS custom properties live in `apps/web/app/globals.css`; Tailwind semantic color, type, spacing, duration, and easing names map to those properties in `apps/web/tailwind.config.ts`.

- **Colors:** page `#111713`, panel `#19211b`, raised panel `#202a22`, line `#344238`, ink `#f4f2e9`, muted `#a7aa9f`, pitch `#285d41`, accent `#d7ff54`, away/team blue `#84d7ff`, alert `#ff987e`.
- **Type scale:** 12, 14, 16, 18, 22, 30, and responsive 32–56 px. Use the condensed display stack for short uppercase section heads and the UI sans stack for reading.
- **Spacing:** use an 8 px base. Named steps are 8, 16, 24, 32, 48, and 64 px. Align controls and panels to these steps; 4 px optical adjustments are allowed inside markers.
- **Motion:** fast 120 ms, standard 220 ms, emphasis 360 ms. Standard easing is `cubic-bezier(0.2, 0.7, 0.2, 1)`; entering emphasis is `cubic-bezier(0.16, 1, 0.3, 1)`. Playback follows sequence timestamps with `requestAnimationFrame` and updates React only at frame boundaries.

## Interaction and accessibility

- Provide a visible high contrast `:focus-visible` ring on every interactive control.
- Give SVG pitch and marker layers accessible names. Convey team identity by both color and labels or numbers.
- Use native buttons, selects, and range inputs with explicit labels. Support Space to play or pause, and left/right arrows to step when the sequence player has focus.
- Respect `prefers-reduced-motion`: do not autoplay or continuously play; allow manual frame selection and stepping.
- Use a canvas heatmap only as a visual layer and expose its highest activity zones in accessible text.
- Maintain readable contrast on text, controls, pitch markings, and overlays. Do not rely on color alone to communicate state.

Apply these rules to all new user-facing web work.
