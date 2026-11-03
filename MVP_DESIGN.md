# Language AI — Level 1 MVP Design

**Status:** Draft v0.1  
**Project type:** Open-source, self-hosted language-learning web application  
**Primary language for MVP:** Spanish  
**Last updated:** 2026-10-31

## 1. Purpose

Language AI helps learners turn material they already consume into recorded practice and short, personalized assessments. It does not try to replace books, videos, or conversations. Instead, it provides a repeatable loop:

**Study something → log what you learned → complete a short assessment → receive feedback and XP → view your progress.**

Level 1 is successful when a user can complete that loop entirely on their own machine, without an account or payment with a cloud AI provider.

## 2. Level 1 scope

### Included

- Deploy one application container with a web UI, Python backend, local SQLite database, and local text-inference capability.
- Run without cloud services or external API calls after installation and model provisioning.
- Secure initial administrator access; force a password change on first login.
- Show rank, total XP, XP needed for the next rank, current streak, and recent activity.
- Manually log **Self-Study** or **Guided Study** sessions. Both use the same log form in Level 1; Guided Study does *not* yet provide an automated curriculum.
- Collect duration, activity type, context, 3–5 target words/phrases, and 2–3 learner-written sentences.
- Persist the original study entries and create a basic history of concepts encountered.
- Generate short text-only assessments from the user's own recent logged material.
- Evaluate responses with structured AI output; the backend validates that output and determines XP.
- Store granular concept-level evidence with modality so later features can use it.
- Show the assessment outcome, brief explanations, and updated progress.

### Explicitly not included

Boss battles, placement tests, speaking or listening assessment, audio generation, automated textbook/PDF ingestion, Anki export, embeddings/vector search, multi-user accounts, a cloud-hosted service, advanced mastery predictions, timed fluency grading, sophisticated anti-cheat, and mobile-native apps.

These belong in the post-MVP backlog. Avoid implementing placeholders that complicate Level 1.

## 3. User stories and acceptance criteria

| ID | User story | Done when |
| --- | --- | --- |
| MVP-01 | As an owner, I can start Language AI locally. | One Docker service starts; dashboard and API are accessible; data survives container recreation. |
| MVP-02 | As an owner, I can sign in securely. | Initial credentials are unique per installation; first login requires setting a new password; protected routes reject anonymous requests. |
| MVP-03 | As a learner, I can log study. | A valid session saves duration, activity, context, 3–5 target terms, and 2–3 sentences. |
| MVP-04 | As a learner, I can review what I logged. | Session history displays stored inputs in chronological order. |
| MVP-05 | As a learner, I can test my learning. | A short quiz is generated only from relevant material in the learner's saved study history. |
| MVP-06 | As a learner, I can see how I performed. | The quiz shows feedback and saves the attempt, its answers, and concept evidence. |
| MVP-07 | As a learner, I can track progress. | XP, rank progress, and streak update after eligible completed actions and remain correct after refresh/restart. |
| MVP-08 | As a maintainer, I can run tests. | Authentication, session validation, XP rules, assessment parsing, and persistence have automated tests. |

## 4. Minimum user journey

1. Start the application using the documented single-container Docker deployment.
2. Open the browser dashboard, sign in using a unique installation credential, and change the password.
3. See an empty dashboard with **Start Study Session**.
4. Choose **Self-Study** or **Guided Study**, then enter the required session data.
5. Save and view the entry in **History**.
6. Select **Quick Assessment**. The application generates a short text-based quiz from logged material.
7. Answer the questions, submit once, review feedback, and see XP/rank/streak updates.

When no valid study history exists, the app offers a study-session action instead of generating an unrelated quiz.

## 5. Technical design

### Technology

- **Frontend:** React + TypeScript (Vite for development); built static assets served by the application container.
- **Backend:** Python + FastAPI for authentication, sessions, assessments, progress, and data access.
- **Database:** SQLite on a persistent Docker volume; enable foreign keys and use transactions.
- **AI:** A lightweight, locally executed, instruction-following text model with structured JSON output. The container must include a compatible inference runtime. Model choice is configurable rather than hardcoded into application logic.
- **Deployment:** One Docker service/container. No external LLM API, external database, or cloud account is required for normal use.

**Model distribution constraint:** Running fully offline is not the same as installing fully offline. The released image must either bundle compatible model weights or provide an explicitly documented one-time local provisioning step. Once provisioned, assessment generation must work without internet access. Document model size and RAM needs after benchmarking on the target homelab.

### Logical flow

```text
Browser (React)
      |
      v
FastAPI (same container)
      |-- Authentication + session cookie
      |-- Study session validation and persistence --> SQLite volume
      |-- XP, rank, and streak rules -------------> SQLite volume
      +-- Assessment orchestrator
                |-- Retrieve recent saved study content --> SQLite
                |-- Generate questions --> Local inference runtime
                |-- Validate generated JSON
                |-- Grade submitted answers --> Local inference runtime
                +-- Validate grading JSON, save evidence + award XP --> SQLite
```

The backend—not the language model—controls eligibility, XP, streaks, and rank state.

## 6. Data model (SQLite)

Keep schema small and preserve original input. Suggested core tables:

| Table | Essential fields | Purpose |
| --- | --- | --- |
| `users` | `id`, `username`, `password_hash`, `must_change_password`, `created_at` | Single-owner sign-in for MVP. |
| `study_sessions` | `id`, `user_id`, `language_code`, `mode`, `activity_type`, `duration_minutes`, `context_text`, `created_at`, `completed_at` | Original study entries and timing. |
| `study_terms` | `id`, `study_session_id`, `concept_id`, `original_text` | The 3–5 logged words/phrases. |
| `study_sentences` | `id`, `study_session_id`, `sentence_text` | The 2–3 learner-written sentences. |
| `assessments` | `id`, `user_id`, `language_code`, `status`, `created_at`, `submitted_at` | Quiz attempts and lifecycle. |
| `assessment_items` | `id`, `assessment_id`, `prompt`, `expected_criteria_json`, `response_text`, `feedback_json` | Persist prompts, answers, and assessment criteria. |
| `concepts` | `id`, `language_code`, `token`, `category` | Dictionary of encountered vocabulary/grammar topics. Unique on language + category + token. |
| `concept_evidence` | `id`, `concept_id`, `study_session_id` (nullable), `assessment_item_id` (nullable), `modality`, `evidence_type`, `outcome`, `assistance_level`, `response_time_ms` (nullable), `created_at` | Granular history for future adaptive learning. |
| `xp_events` | `id`, `user_id`, `source_type`, `source_id`, `base_xp`, `multiplier`, `awarded_xp`, `created_at` | Append-only history of XP awards; prevent double awards for the same eligible action. |

Use SQLite `INTEGER PRIMARY KEY` for IDs and `TEXT` for timestamp strings in UTC. Restrict enum-like values in application validation (and preferably with database `CHECK` constraints). Turn on `PRAGMA foreign_keys = ON` for each connection.

**Evidence model rule:** `concept_evidence` captures what happened, not a claim that a skill is mastered. `modality` supports `READING`, `WRITING`, `LISTENING`, `SPEAKING`; Level 1 only writes modalities it actually evaluates (primarily `READING` and `WRITING`). `evidence_type` distinguishes exposure/practice from assessment. `outcome` supports `HIT`, `PARTIAL`, `MISS`, and optionally `NOT_ASSESSED`. `assistance_level` supports `ASSISTED`, `UNASSISTED`, `UNKNOWN`. Self-reported study is not automatically treated as an independent mastery demonstration. For Level 1, no mastery-score calculation is required.

Store the original response and AI explanation so evidence can be audited and re-evaluated later. Each evidence record must trace back to a real session or assessment item; don't generate fake listening/speaking evidence from written text.

## 7. Progression rules (Level 1 only)

- Display a simple configurable ladder beginning with **Pre-Learner I, II, III** and **Learner I, II, III**.
- For MVP, rank is an **XP-based activity rank**, not a certified proficiency claim. Skill-gated promotions will be introduced later.
- Award XP for a completed, valid study log and a completed assessment; amounts are constants in backend configuration, not model-generated values.
- Count a completed study session or submitted assessment as an eligible daily action. Logging in or opening a page does not extend a streak.
- A calendar day counts at most once toward streak continuity in the user's configured timezone. Set one default timezone at setup; changing it should not rewrite past XP.
- Apply a modest capped streak multiplier to eligible new actions; missed days end the active streak but never remove earned XP.
- Assessments can be repeated as practice, but **the same assessment attempt cannot pay XP twice**. Add simple daily XP caps or diminishing returns for repeated assessment generation to avoid accidental farming.
- XP totals are derived from `xp_events`; save every award transactionally alongside the action that earned it.

**Values to tune during implementation:** base session XP, assessment XP, rank thresholds, multiplier cap, and daily assessment reward cap. These are configuration constants, not additional MVP features.

## 8. AI assessment contract

### Input

Retrieve a bounded set of recent study entries (context, terms, sentences). Clearly label these as learner-provided data. Ask the local model to create a small quiz based only on that material. If information is insufficient, ask for another study session rather than inventing unrelated topics.

### Output

Use structured JSON with a fixed schema for generated questions and grading responses. Conceptual grading shape:

```json
{
  "assessment_item_id": 12,
  "feedback": "The meaning is clear, but the verb form needs work.",
  "evidence": [
    {
      "concept_token": "poder",
      "modality": "WRITING",
      "outcome": "PARTIAL",
      "issue": "verb-conjugation"
    }
  ]
}
```

This is an example, not a finalized API schema. The backend must reject malformed, unsupported, or out-of-scope records and retry or report a clear error rather than awarding XP on unvalidated data. A valid JSON structure does not itself guarantee correct grading, so maintain a small set of reference examples/tests. Preserve original answers and feedback.

**Level 1 grading:** Short, low-stakes written practice. No per-word accuracy guarantee, conversational-fluency claim, or automatic promotion gating. The model provides feedback and concept observations; backend rules issue rewards.

## 9. Interface outline

1. **Setup/Login:** one-time credential enrollment or generated unique bootstrap credential; mandatory password change; normal login afterward.
2. **Dashboard:** current rank, XP bar/next threshold, streak, recent sessions, and quick actions.
3. **New Session:** study mode, activity type, duration, context, target terms, sentences, save confirmation.
4. **History:** list/details of prior study logs and completed assessments.
5. **Quick Assessment:** generated questions, typed answers, submit, feedback, earned XP.

Keep the UI responsive for laptop and phone browsers; no native app is needed.

## 10. Security, reliability, and local-first constraints

- Bind the service to localhost or a trusted private network by default; never expose it publicly by accident.
- Avoid a shared, hardcoded default password. Generate a unique bootstrap credential or require a one-time setup flow; enforce password change before normal use. Store only a modern password hash.
- Use authenticated sessions with secure cookie settings appropriate to HTTP localhost versus HTTPS remote access; add CSRF protection for cookie-authenticated state-changing requests.
- Treat study notes as untrusted input and do not let them override system instructions for the local model.
- Validate input sizes, timestamps, AI JSON schemas, and database references.
- Persist SQLite and model files in named volumes or documented mounted paths; restarting/recreating the container must not erase data.
- Document how to back up the SQLite file safely, including active write-ahead-log files if WAL mode is enabled.
- No telemetry, cloud API keys, or third-party analytics are required for the MVP.
- Record errors without logging passwords, session tokens, or private assessment responses unnecessarily.

## 11. Implementation plan

**Milestone A — Runnable shell:** Repository structure, Dockerfile / one-service Compose file, React build, FastAPI health route, SQLite volume, basic dashboard.

**Milestone B — Secure storage + study logs:** First-run auth, password reset on first login, session API, form validation, history page, migrations.

**Milestone C — Progression:** XP event ledger, rank display, streak calculation, unit tests for double-award prevention.

**Milestone D — Local AI assessment:** Model packaging/provisioning, quiz generation, response submission, structured grading, concept evidence persistence, assessment feedback UI.

**Milestone E — Release check:** Test full user journey offline, restart persistence, poor model output, malformed JSON, authentication protection, and basic mobile layout. Write an installation guide and sample configuration.

### Definition of Done

A new user can start one container, sign in securely, record a study session, complete a relevant text quiz, receive comprehensible feedback, gain XP, and still see the entire history after restarting the container—with no cloud inference required.

## 12. Future backlog (not Level 1 commitments)

- **Level 2:** Concept-by-modality analytics; exposure vs assisted/independent assessment; targeted review; spaced repetition/Anki export; more refined HIT/PARTIAL/MISS feedback; textbook curriculum ingestion.
- **Later:** Placement assessments; boss battles with reusable randomized scenarios and defined rubrics; controlled promotion attempts; remediation paths; speech/listening interaction; hesitation tracking with accessibility safeguards; advanced CEFR-aligned profiles; other languages; optional multi-user capabilities.

**Scope rule:** New ideas go into this backlog first. They enter Level 1 only if they are required to make the study → assessment → feedback → progress loop work.

## 13. Open decisions (safe to defer until implementation)

- Which small local model and inference runtime perform acceptably on the actual host?
- Are model weights packaged in the released image or provisioned once into a volume?
- What XP constants, rank thresholds, and streak caps feel reasonable after testing?
- What is the lowest-friction secure first-run bootstrap flow?
- Which fixed quiz formats give the most dependable feedback from the chosen model?

These decisions should not block work on the Docker shell, frontend, storage, or session forms.
