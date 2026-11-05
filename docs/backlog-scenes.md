# Backlog: scene rotation and theming

Post-MVP nice-to-haves for the dashboard scene banner. None of this is required for Level 1.

## 1. Shuffle bag rotation

Replace the daily scene pick with a shuffle bag.

- Each visit shows a scene the browser hasn't shown yet, in random order.
- When every scene has been shown, the bag refills.
- Stored per browser in localStorage (per-viewer convenience only, which the design rules allow).
- Adding a photo means dropping the WebP in and adding one manifest entry.

**Prerequisites:** a `scenes.json` manifest (place, title, credit, source link, crop), a `npm run scenes` conversion script, and `scene-sources/` for the gitignored originals.

## 2. Per-location colour themes

Each scene sets its own accent palette, so the app's colours follow the photo.

- Scene data gets a `theme` block that overrides the accent tokens: `--accent`, `--accent-hover`, `--accent-ink`, `--nav-active`, `--selected`.
- Candidate themes: olive for Granada, sea blue for Cantabria, saffron or terracotta for Sevilla.
- Every theme must pass WCAG AA:
  - text on `--bg` at 4.5:1 or better
  - `--accent-ink` on `--accent` at 4.5:1 or better
  - focus ring visible against `--bg`
- Per-theme contrast checks belong in the build, so a bad palette fails before it ships.
- Keep the surfaces and text colours fixed. Only the accent family changes, so the app stays readable.
- Note: `DESIGN.md` describes one palette. If themes ship, update it to describe the base and the per-scene overrides.

**Decided:**
- The theme follows the scene on screen, so the whole app picks up the palette of the photo shown.
- The rail background changes with the theme, as well as the accents. Rail text and nav states must still pass AA against each rail colour, so the contrast check covers `--rail-bg` too.
- Surfaces, body text and the page background stay fixed. Only the accent family and `--rail-bg` change.
