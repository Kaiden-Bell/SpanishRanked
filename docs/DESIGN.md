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
  - the nav: Dashboard, Study, Quiz, Words, History
  - a footer with "Signed in as" and Sign out
- **Below 960px:** the rail becomes a top bar. Brand and Sign out sit on the first row, and the nav takes its own full-width row, spread edge to edge with tighter padding, so all five items fit a 360px phone without scrolling.
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
- Quiz (`Assessment.tsx` → `QuizRunner`; also used by the warm-up and boss battles):
  - **The start screen** has a "Practise" select (Mixed, Vocabulary, Grammar, Reading, Listening, Writing, Sentence practice).
  - **Answering** shows one `.q-card` per screen, headed by `.q-progress` (count and skill, or the boss stage) and `.q-steps` segments.
  - **Inputs** (`Question.tsx`):
    - `.q-option` buttons for choices; clicking one answers it
    - a text field with an `.accent-bar` (á é í ó ú ñ ü ¿ ¡); gaps render inline in `.q-cloze`
    - `.tile` buttons for word order
    - ▶ Play and Slowly buttons for listening
  - **After each answer** a `.q-result` card shows the outcome pill, your answer and the explanation, with focus on Next.
  - **Results** use `.quiz-item` cards with a skill caption, the outcome pill, the question context and a link to the word.
  - **Outcome pills:** `hit` is solid olive, `partial` is outlined, `miss` uses `--bad`. They are always worded ("Correct", "Partly right", "Missed"), never shown by colour alone.
- Dashboard additions:
  - **`.recap-card`** ("Since last time") sits above the grid, with word chips (`.tag-link`) that open the word. While the warm-up is pending it holds the view's one primary button, and Start Study Session drops to outline.
  - **The skill profile** shows real bars once a skill has 8 answers, and the Vocabulary and Grammar rows sit below a hairline.
  - **The rank card** gains a `.boss-callout` when a boss battle is open.
- Settings (`Settings.tsx`), opened from the Settings button next to Sign out (in the rail, or in the top bar on phones), so the main nav stays at five items. The page is a stack of cards:
  - **Practice:** quiz and warm-up length, listening on or off, and the Spanish voice and speed. Voice and speed are saved on the device, the rest on the server.
  - **Motion:** a `.seg` with "Follow my device" and "Always reduce".
  - **Account:** change the password, and sign out other devices.
  - **Reset all data:** a `.danger` card. Its `.btn.danger-btn` stays disabled until the password is entered and RESET is typed.
  - "Always reduce" sets `data-motion="reduce"` on `<html>`, which index.css treats like `prefers-reduced-motion`.
- Boss (`Boss.tsx`): an intro card listing the stages and the pass rules, then the runner. The result card is `.boss-result.won` / `.lost`, with a `.boss-stages` table. Every stage is labelled "Passed" or "Not yet" in words.
- Word bank (`WordBank.tsx`):
  - **The list** uses `.bank-row` buttons in a hairline list. Each row shows the headword in the display font, the translation (clamped to two lines), a meta line with the part of speech and the forms seen, and a `.strength` pill.
  - **Strength pills** are always worded: "Not tested yet", "Needs practice" (`--bad` outline), "Learning", "Strong" (filled).
  - **The detail page** is a `2fr / 1fr` `.word-grid` with:
    - main column: the form you met (who and when), the conjugation table, and sentences
    - side column: your translation, meanings, linked phrases or words, and your history
  - **The conjugation table** (`.conj`) sits in a horizontally scrollable `.conj-scroll` so the page itself never scrolls sideways. Forms the learner has logged are `<mark>`ed with an olive outline. The table shows the main tenses and persons by default, with a toggle for all of them.
  - Source attribution sits in `.foot` under the page.
- `.notice.warn` is the dashboard banner when the model or grammar checker is offline. It is advisory: the dashboard works without it.
- `.card` and `.panel` are translucent surfaces. `.notice` is the save confirmation, `.error` the error box, `.empty` the dashed empty state, and `.tags` and `.sentences` are used in History entries.

## Rules

- No kicker or eyebrow above headings. No progress rings or sparklines. No rows of icon cards.
- Ship no placeholders. Features that aren't built (challenges, speaking) get no nav item or button. "Quick Assessment" is the secondary dashboard CTA now that quizzes exist.
- Skills read "Not yet assessed" until there is real assessment data. Never show an invented CEFR level.
- Rank is an activity rank, not a proficiency claim.
- Keep the focus ring visible (2px accent). `prefers-reduced-motion` turns off all transitions and animations.
