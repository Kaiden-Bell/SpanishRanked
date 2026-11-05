# Design: Alhambra Dusk

The Language AI frontend (`src/frontend/spanish-ranked/`) uses the **Alhambra Dusk** direction: a quiet study sanctuary. A daily Spanish scene frames a few modules and nothing else. It is deliberately not a metric-tile SaaS dashboard.

Source of truth is the shipped CSS: `src/index.css` (tokens, base, controls) and `src/App.css` (shell, scene, views). This file records the system; if they disagree, fix this file.

## Tokens

Dark only (`color-scheme: dark`). There is no light theme.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#11140f` | Page background (green-black) |
| `--rail-bg` | `#0e110c` | Left rail |
| `--surface` | `#181c14` | Cards and panels (at 86% with `backdrop-filter: blur(10px)`) |
| `--field` | `#151911` | Inputs |
| `--ink` / `--ink-2` / `--ink-3` | `#ece6d6` / `#bdb9a8` / `#8f8d7e` | Text: primary, secondary, captions. `--ink-3` on `--bg` is about 5.4:1 contrast, which passes AA. |
| `--accent` / `--accent-hover` / `--accent-ink` | `#a9ae6e` / `#bcc17f` / `#12150e` | Olive: primary buttons, bar fills, focus ring |
| `--nav-active` | `#5a6038` | Current nav item |
| `--line` / `--line-strong` | bone at 12% / 28% | Hairlines and control borders |
| `--good` / `--bad` | `#a9ae6e` / `#e0a08a` | Status |
| `--radius` / `--radius-card` | `6px` / `10px` | Controls / cards |
| `--rail` | `15.5rem` | Rail width |
| `--ease-out` | `cubic-bezier(.16,1,.3,1)` | All motion |

## Type

- **Display:** Libre Caslon Text, at 400, 400 italic and 700. Used for headings, the greeting, the italic sub-line, recent-session terms and the Spanish sentences in History.
- **UI:** Albert Sans, at 400, 500 and 600. Used for everything else.
- Both fonts are self-hosted through `@fontsource` and imported in `main.tsx`. The app makes no requests to Google Fonts or any other third party, which PRODUCT.md requires.
- Card section labels (`.card-head h2`) are uppercase UI font, tracked `.12em`. They are the only tracked uppercase apart from the brand subtitle.

## Layout

- **Shell:** a sticky full-height left rail containing:
  - the brand: "Language AI" with "LEARN SPANISH" under it
  - the nav: Dashboard, Study, History
  - a footer with "Signed in as" and Sign out
- **Below 960px:** the rail becomes a top bar. Brand and Sign out sit on the first row, and the nav takes its own full-width row so no item is hidden.
- **Content:** `.view` is capped at 76rem and has a fluid side gutter.
- **Dashboard:** a greeting hero, then a `1.5fr / 1fr` grid:
  - first row: rank card and streak card
  - second row: skill profile and recent sessions
  - below 960px it becomes one column

## Scene banner

- `Scene.tsx` shows one of five scenes per calendar day: Granada, Barcelona, Salamanca, Cantabria and Sevilla.
- It is 26rem tall on the dashboard and sign-in, and 9rem on the other views. Over the scene sit a warm radial highlight, a left fade and a bottom fade to `--bg`, plus SVG grain.
- **Photos:** each scene loads `public/scenes/<id>.webp` if the file exists. Without it, the scene's three-colour tint gradient shows instead.
- **Caption:** the top-right caption and the `role="img"` label appear only once a real photo has loaded, so the UI never describes an image that isn't there.
- **Photo spec:**
  - 2560×1100 px WebP at quality ~80, under ~300 KB
  - dusk or golden-hour light, with muted greens and ochres
  - keep the left third calm, because the headline sits over it; put the subject right of centre
  - no people, text or watermarks
- **Credit:** add a `credit` string to the scene's entry in `SCENES` in `Scene.tsx` once a photo exists. Every shipped photo must be the owner's own or properly licensed.

## Components

- `.btn`: the default style is an outline. `.btn.primary` is the solid olive button, with only one per view. `.btn.ghost` is used in the rail.
- All controls are at least 44px tall.
- `.field` wraps a label `<span>` and its control. Other form building blocks:
  - `fieldset.group` for repeated inputs
  - `.row2` for side-by-side fields, which stack below 760px
  - `.seg` for a two-way choice, using `aria-pressed`
- `.bar > .fill` is driven by `--w` (0–1) and animates with scaleX only. `.empty-track` is a dashed line for a skill that hasn't been measured.
- `.card` and `.panel` are translucent surfaces. `.notice` is the save confirmation, `.error` the error box, `.empty` the dashed empty state, and `.tags` and `.sentences` are used in History entries.

## Rules

- No kicker or eyebrow above headings. No progress rings or sparklines. No rows of icon cards.
- Ship no placeholders. Features that aren't built (assessments, vocabulary, challenges) get no nav item or button. "Quick Assessment" returns as the secondary CTA once assessments exist.
- Skills read "Not yet assessed" until there is real assessment data. Never show an invented CEFR level.
- Rank is an activity rank, not a proficiency claim.
- Keep the focus ring visible (2px accent). `prefers-reduced-motion` turns off all transitions and animations.
