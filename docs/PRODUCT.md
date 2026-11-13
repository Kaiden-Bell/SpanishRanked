# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Right now: a single owner-learner who self-hosts Language AI on their own machine and studies Spanish through material they already consume (shows, music, books, textbooks, conversation). They return regularly to log study, take short assessments, and watch rank, XP and streak grow.

Planned: the project will be open-sourced on GitHub so other self-hosters can run it and add the languages they are learning. Design for one learner per install today; do not build multi-user or hosted-service assumptions.

## Product Purpose
Language AI turns material a learner already consumes into recorded practice and short, personalized assessments. It does not replace books, videos or conversation. It runs one loop: study something, log what you learned, take a short assessment, get feedback and XP, see progress.

Level 1 succeeds when a user can complete that loop entirely on their own machine, with no account and no cloud AI provider.

## Positioning
Learning is tracked from whatever the learner already studies, with no fixed curriculum. The backend, not the language model, owns XP, rank and streaks. It is self-hosted, with no cloud AI and no external account; dictionary lookups are the only online calls.

## Operating Context
- One Docker container: React/TypeScript frontend, Python/FastAPI backend, SQLite on a persistent volume, local text-model inference, and LanguageTool as an advisory grammar checker.
- Single administrator login; password change forced on first login.
- Day boundaries for streaks and daily XP caps use one configured timezone.
- Minimum journey: empty dashboard, then Start Study Session (Self-Study or Guided Study, same form in Level 1), then History, then Quick Assessment, then feedback and updated XP/rank/streak.

## Capabilities and Constraints
- Primary CTA: Start Study Session. Secondary: Quick Assessment.
- Study log captures duration, activity type, context, 3-5 target words/phrases, and 2-3 learner-written sentences.
- Assessments are short, text-only, and generated only from the learner's own saved study history. With no history, offer a study session instead.
- Rank is an XP-based activity rank, not a certified proficiency claim. Ladder: Pre-Learner I, II, III, then Learner I, II, III. Thresholds are provisional (see `src/backend/app/rules.py`).
- Streaks are earned by completed study sessions or submitted assessments, never by opening the app. Missed days end the streak but never remove XP.
- Reading, Writing, Listening and Speaking are independent skills. Level 1 only evaluates written modalities. Skills not yet assessed must say "Not yet assessed", and no CEFR level is invented.
- Level 2 (docs/ROADMAP.md) added a word bank, code-built quizzes with listening through the browser's voice, a daily recap and warm-up, a real skill profile, and boss battles that gate rank-ups. Still excluded: placement tests, speaking assessment, PDF ingestion, Anki export, multi-user accounts and cloud hosting.
- Design concepts and prototypes may preview post-MVP features (Challenges, speaking, listening) as clearly locked or future, but the shipped Level 1 app should not carry placeholders that complicate it.
- Word meanings, example sentences and phrase translations are looked up online (Wiktionary, Tatoeba, MyMemory), cached locally, and can be turned off. Only the looked-up Spanish text is sent. Everything else, including conjugation and grammar analysis, is local. See `docs/ROADMAP.md`.

## Brand Commitments
Name: Language AI. Spanish is the first language. Authority for scope and rules: `MVP_DESIGN.md`. No other brand assets or voice rules have been confirmed.

## Evidence on Hand
- `MVP_DESIGN.md` (Level 1 design, data model, progression rules, AI assessment contract).
- Working backend and a basic frontend (login, dashboard, new session, history) in `src/`.
- No real learner data, testimonials, or photography assets exist yet. Do not fabricate them. Imagery in prototypes is placeholder only.

## Product Principles
1. Progress is evidence-based: never claim mastery or proficiency that was not demonstrated.
2. The learner's own material drives everything; no imposed curriculum.
3. Rewards are earned by real study, never by presence, and should never pressure.
4. The system is auditable and local: original inputs are kept, and the backend (not the model) decides XP.
5. Built to be forked: language-specific content must stay configurable so other learners can add their own languages.

## Accessibility & Inclusion
Target WCAG 2.1 AA: sufficient contrast, full keyboard operation, visible focus, and reduced-motion support. It must work on desktop and mobile web.
