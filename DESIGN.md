# Spanish Ranked

Personal Spanish learning tool with session recaps, progress evidence, and long-term XP progression.

**Owner:** Kaiden Bell  
**Design version:** 0.2  
**Updated:** 2026-10-10  
**Implementation status:** Planning. The checkboxes below describe work to build, not completed functionality.

## Start here today

Build **Phase 0 and the smallest working part of Phase 1**. A useful stopping point is one saved session that survives refresh and awards XP once after its recap is completed.

1. Create the React/TypeScript frontend and FastAPI backend.
2. Connect SQLite and add the first database migration.
3. Add a session form with activity, source text, and active minutes.
4. Save the session and load it again after refreshing the page.
5. Load a fixed recap for one reviewed sample passage and save its answers.
6. Add feedback review and a completion action that records one XP award.

Use a fixture provider for this first pass. Connect a real LLM in Phase 3 after session persistence and completion work reliably. The first text release becomes useful for regular study when Phase 4 is complete.

## 1 Product purpose

Spanish Ranked supports learning through music, lyric analysis, reels, books, and conversation. The learner chooses the material. The app turns notable sessions into a recap, specific feedback, a record of demonstrated ability, and a useful next task.

The core loop is:

1. Study or practice Spanish.
2. Record the session and enough context to assess it.
3. Complete a recap covering meaning, recall, and use.
4. Review feedback and attempt any required follow-up.
5. Receive XP and a recommendation for the next session.

### Required behavior

- A session earns no XP until its recap is complete.
- Incorrect answers can still earn effort XP. Correctness updates skill evidence separately.
- Every assessed session explains what was demonstrated, what required help, and what to practice next.
- Track words, phrases, and reusable sentence patterns in a personal bank.
- Support curriculum imports and a separate dictionary reference collection.
- Keep reading, listening, written production, and spoken production distinct.
- Allow English explanations when testing comprehension and mixed Spanish/English practice where appropriate.
- Provide feedback after each session while keeping major rank progression intentionally slow.
- Preserve session history and progress across restarts.

### Scope boundaries

The first useful release supports one learner, short pasted Spanish material, typed recaps, XP, a personal bank, curriculum topics, recommendations, and API cost tracking.

Audio assessment, major bosses, large dictionary imports, automated media ingestion, and a custom recommendation model are later work. A text-only release must show listening and speaking as unassessed.

## 2 Implementation phases

Each phase has an observable completion condition. Finish that condition before expanding the feature set. These are build steps, not calendar commitments.

| Phase | Deliverable | Depends on |
| --- | --- | --- |
| 0 | Running frontend, backend, and persistent database | Nothing |
| 1 | One complete stored session with recap and reliable XP | Phase 0 |
| 2 | Private homelab deployment with persistence and recovery | Phase 1 |
| 3 | Real LLM recaps, feedback, and enforced spending controls | Phase 1; deploy through Phase 2 when ready |
| 4 | Personal bank, curriculum imports, and next-task selection | Phase 3 |
| 5 | Delayed reviews, diagnostics, and progress comparisons | Phase 4 |
| 6 | Listening and spoken-response workflows | Phase 5 |
| 7 | Rank unlocks and boss encounters | Phase 5 for text bosses; Phase 6 for voice bosses |

### Phase 0 — Application foundation

**Goal:** Run the application locally and persist one record.

- [ ] Initialize the frontend and backend with pinned dependency versions.
- [ ] Add `GET /health` and a frontend connection check.
- [ ] Add configuration loading and a `.env.example` with placeholder values only.
- [ ] Connect SQLite, enable foreign-key enforcement, and introduce migrations.
- [ ] Create the initial `study_sessions` table.
- [ ] Document local startup commands in `README.md`.

**Done when:** The frontend can create and read a test session through the backend, and the record survives a backend restart.

### Phase 1 — Complete a session with fixed content

**Goal:** Prove the session lifecycle without needing paid model calls.

- [ ] Build session creation, session detail, and session history views.
- [ ] Validate activity, source context, and active minutes on the server.
- [ ] Add recap, response, assessment, and XP ledger tables.
- [ ] Create one reviewed sample passage with three fixed recap prompts and saved criteria.
- [ ] Add a fixture provider using that sample; label fixture feedback as development data.
- [ ] Save each submitted response and assistance event before evaluation.
- [ ] Display feedback, an explicit review acknowledgement, and any required follow-up.
- [ ] Implement session completion and the XP award in one database transaction.
- [ ] Return the existing result when a completion request is repeated.

**Done when:** A session can be resumed after refresh, incomplete recaps receive zero XP, a completed attempt can earn XP despite wrong answers, and repeated completion awards nothing extra.

**Boundary:** Fixture results do not establish real learner mastery. Other source material may be saved as a draft, but must not receive fabricated assessments from the sample fixture.

### Phase 2 — Make it available on the homelab

**Goal:** Keep the working session tool available whenever the learner returns.

- [ ] Add Dockerfiles and a Compose configuration with a persistent data volume.
- [ ] Serve the frontend and API through the same origin.
- [ ] Use the existing private homelab access route and reverse proxy.
- [ ] Add single-user authentication before deployment; keep credentials server-side.
- [ ] Configure secure session cookies and CSRF protection when using cookie authentication.
- [ ] Add health checks and ordinary application logs with useful error messages.
- [ ] Create a consistent SQLite backup and document the restore procedure.
- [ ] Restore a backup into a separate test instance.

**Done when:** The app is reachable through the intended private route, restarting or recreating containers preserves sessions and XP, and a restored backup reproduces the same data.

### Phase 3 — Add LLM feedback and spending controls

**Goal:** Assess new text sessions with traceable feedback and bounded cost.

- [ ] Define a provider interface with `generate_recap` and `evaluate_recap` operations.
- [ ] Keep the fixture provider and add one hosted API provider.
- [ ] Save prompts and criteria before presenting the recap.
- [ ] Validate structured evaluation output against the saved prompt and response IDs.
- [ ] Store model, prompt, and rubric versions with each assessment.
- [ ] Track input, output, cached usage, and any separately reported billed usage.
- [ ] Reserve estimated request cost before calling the model; reconcile after completion.
- [ ] Enforce a monthly application budget, request output limits, and a retry ceiling.
- [ ] Preserve pending sessions after timeouts, rate limits, and invalid output.
- [ ] Let the learner dispute an assessment without losing earned effort XP.
- [ ] Evaluate a small reviewed set containing correct, incorrect, ambiguous, and regionally valid Spanish answers.

**Done when:** A new excerpt produces a saved recap and evidence-linked feedback; provider failures preserve answers; invalid references cannot affect progress; budget exhaustion blocks new paid requests.

**Quality gate:** Required output fields are not proof of a good assessment. Review whether the corrections and outcomes are actually appropriate before relying on the selected model.

### Phase 4 — Personal bank and curriculum

**Goal:** Connect session feedback to an organized record of learning and a next task.

- [ ] Add personal entries for words, phrases, and patterns, including senses and sources.
- [ ] Support manual entry creation and optional acceptance of model suggestions.
- [ ] Add topics, learner goals, rubrics, topic-entry links, and prerequisite relationships.
- [ ] Seed a small set of everyday communication goals.
- [ ] Implement CSV bank imports and versioned JSON curriculum imports.
- [ ] Preview additions, conflicts, invalid references, and duplicate candidates before committing.
- [ ] Reject curriculum prerequisite cycles and unresolved rubric references.
- [ ] Link validated findings to existing topic and entry IDs.
- [ ] Implement deterministic next-task selection and show its reason.
- [ ] Preserve a manual choice to study other material.

**Done when:** An assessed session can update evidence for an entry or topic and produce a relevant next task. Imported entries begin as encountered, and a repeated import does not silently duplicate or overwrite records.

**First useful text release:** The learner can study their own material, complete a recap, receive feedback, earn XP, retain a personal bank, and return to a relevant recommendation.

### Phase 5 — Retention and progress diagnostics

**Goal:** Distinguish immediate success from ability demonstrated across days and contexts.

- [ ] Schedule delayed checks after accepted evidence is recorded.
- [ ] Revisit a target using fresh prompts rather than the same memorized question.
- [ ] Record hints, model answers, and other assistance per attempt.
- [ ] Add a short initial diagnostic using only the modalities currently supported.
- [ ] Show outcomes over comparable attempts with sample counts and dates.
- [ ] Rebuild progress summaries when an assessment is disputed or superseded.
- [ ] Add a configurable limit on review tasks so an old backlog does not consume every session.

**Done when:** The app can show that a target succeeded independently after a delay, distinguish supported from independent attempts, and explain why a review is due. A placement result sets task difficulty without inventing a certified CEFR level.

### Phase 6 — Listening and spoken responses

**Goal:** Address the learner's main difficulty with real spoken language.

- [ ] Choose a transcription and playback approach after testing cost and Spanish quality.
- [ ] Add short audio inputs and spoken-response recording.
- [ ] Store transcript visibility, replay count, playback speed, and assistance used.
- [ ] Separate the ability to understand a recording from the ability to answer in Spanish.
- [ ] Preserve or allow correction of uncertain transcripts before treating them as learner mistakes.
- [ ] Add fresh-speaker and fresh-wording checks for familiar expressions.
- [ ] Apply the same usage ledger and budget enforcement to paid audio operations.

**Done when:** The app can distinguish understanding with a transcript from understanding audio independently, and a transcription error does not automatically become a language error.

**Boundary:** Pronunciation evaluation needs suitable audio evidence and a tested evaluation method. A text transcript alone cannot justify it.

### Phase 7 — Bosses and long progression

**Goal:** Add demanding milestones around evidence the application can already collect.

- [ ] Define configurable rank thresholds and checkpoint requirements.
- [ ] Implement encounter definitions with a situation, required skills, allowed help, and passing criteria.
- [ ] Begin with text encounters; require Phase 6 before voice encounters.
- [ ] Save the encounter, rubric, and model versions for each attempt.
- [ ] Require a pass in every required skill rather than averaging away a weakness.
- [ ] Turn failed attempts into targeted practice recommendations.
- [ ] Show what remains before the next unlock and preserve earned XP after failure.
- [ ] Tune the grind using actual session patterns before setting permanent thresholds.

**Done when:** Eligibility can be explained from stored requirements, passing advances the configured rank once, and failure produces useful feedback without deleting XP.

**Optional work after the core loop:** Licensed dictionary datasets, richer media ingestion, semantic search, more scenarios, or a trained recommendation model. Each should solve an observed limitation.

## 3 Technical architecture

These are working defaults. Provider selection, dictionary source, Spanish variety, and final progression tuning remain open.

| Component | Initial choice | Responsibility |
| --- | --- | --- |
| Frontend | React and TypeScript | Session entry, recap, feedback, bank, goals, progress, usage |
| Backend | FastAPI | Validation, lifecycle, retrieval, model calls, progression |
| Persistence | SQLite with migrations | Durable sessions, evidence, imports, XP, usage |
| Model integration | Replaceable provider adapter | Generate prompts and propose assessments |
| Deployment | Docker Compose on the homelab | Private access, persistent storage, recovery |

Keep one backend application with ordinary modules. It owns all state changes. The LLM receives selected context and returns proposed content; it does not execute database operations or control XP.

### Suggested repository layout

Create only the files needed by the current phase.

| Path | Purpose |
| --- | --- |
| `DESIGN.md` | Product rules, architecture, phased checklist |
| `README.md` | Setup, run, backup, and restore instructions |
| `frontend/src/pages/` | Session, recap, feedback, bank, and progress views |
| `frontend/src/api/` | Typed calls to the application API |
| `backend/app/main.py` | Application entry point |
| `backend/app/routes/` | HTTP request and response handling |
| `backend/app/schemas/` | Validated input and output structures |
| `backend/app/models/` | Database records and relationships |
| `backend/app/services/` | Session completion, recommendations, imports, spending |
| `backend/app/providers/` | Fixture provider and hosted model adapter |
| `backend/migrations/` | Versioned schema changes |
| `backend/tests/` | Meaningful lifecycle and integration checks |
| `backend/fixtures/` | Reviewed sample material and evaluation cases |
| `compose.yaml` and `.env.example` | Deployment definition and documented settings |

API keys stay on the backend. Database files, credentials, and local recordings are excluded from source control.

## 4 Session lifecycle and completion

| State | Meaning | Next action |
| --- | --- | --- |
| `saved` | Source context and minutes are stored | Generate or load recap |
| `recap_ready` | Prompts and criteria are saved | Submit answers |
| `submitted` | Responses are durable; evaluation is pending | Evaluate or retry |
| `assessed` | A validated report is available | Review feedback and attempt required follow-up |
| `completed` | Recap requirements and XP award are committed | View report or begin another session |

Provider failures are recorded on request attempts; they do not erase the session or force it back to the beginning. A session can be resumed from its stored state.

### Completion rules

The completion endpoint checks that:

1. Every required prompt has a response or an explicit `dont_know` response.
2. A structurally valid assessment exists for the current primary response version.
3. The learner has acknowledged that assessment's feedback.
4. Any required guided follow-up has been attempted.
5. No XP award already exists for the session.

Proposed follow-up limit: at most one guided follow-up per recap in the initial release. Store that attempt against its parent assessment without replacing the primary response version. A wrong follow-up answer can still complete the effort requirement. An uncertain assessment records uncertainty and does not count as independent mastery; uncertainty alone does not require an endless loop of retesting.

Completion marks the session complete and inserts the XP ledger entry in one transaction. A unique constraint on the session's XP award prevents duplicate credit even if requests overlap. A repeated request returns the existing award.

Persist input before external calls. Use an idempotency key for submissions and reject reuse with a different payload. Save question sets once so retries do not silently produce a different test.

Allow one active model operation for a given session, operation type, and response version. Repeated evaluation requests return the existing result or pending operation instead of starting another paid call.

After a recap has responses, freeze its source, credited duration, and question version. Corrections create a new version or assessment and preserve the original history. Regrading never awards another set of XP.

## 5 Data model

All records use stable IDs and UTC timestamps. Display dates and review schedules in the learner's timezone. The first release has one learner profile.

| Record | Main fields | Introduced in |
| --- | --- | --- |
| `study_sessions` | `id`, activity, source text or description, optional URL, active minutes, target modality, state, timestamps | 0–1 |
| `recaps` | session ID, version, prompt set, server-side criteria, prompt version | 1 |
| `responses` | recap ID, response version, prompt ID, answer kind, text, assistance, idempotency key | 1 |
| `assessments` | response version, provider/model, rubric version, findings, feedback, validation/dispute status | 1; real provider in 3 |
| `xp_ledger` | unique session ID, amount, credited minutes, rule version, awarded timestamp | 1 |
| `api_requests` | operation, session ID, provider, model, usage, rate version, reserved/estimated cost, status | 3 |
| `bank_entries` | expression, type, sense, meaning, language, source, examples, regional notes | 4 |
| `topics` and `learner_goals` | stable topic ID, objective, rubric, active goal selection | 4 |
| `topic_entries` and `topic_prerequisites` | explicit many-to-many links between existing IDs | 4 |
| `evidence` | assessment and prompt IDs, entry or topic ID, modality, outcome, assistance, timestamp | 4 |
| `imports` | content hash, preview, decisions, schema version, commit status | 4 |
| `review_schedule` | entry or topic ID, modality, due date, interval, last evidence ID | 5 |
| `boss_attempts` | encounter ID/version, rubric/model versions, required-skill outcomes, result | 7 |

### Persistence rules

- Preserve attempts and assessments; derive progress summaries from accepted evidence.
- Disputed or superseded assessments do not contribute to current mastery summaries.
- Keep evidence tied to a particular modality and task target.
- Use database constraints for foreign keys, unique XP awards, and idempotency records.
- Store money using decimal arithmetic or integer microdollars.
- Back up the database consistently; copying only a live SQLite main file can omit active journal data. Use a supported backup operation or a clean shutdown snapshot.

## 6 Assessment and model contract

### Recap coverage

A default recap includes:

1. **Meaning:** Explain what the source or expression means.
2. **Recall:** Retrieve a useful expression without seeing the model answer.
3. **Transfer:** Use or interpret the target in a fresh situation.

The task's modality determines what can be assessed. An English explanation may demonstrate comprehension. A successful written answer cannot establish listening or pronunciation.

If the learner supplies only a description of their session, generate related practice and identify it as such. The app cannot verify the contents of an unseen reel, song, or conversation. A saved URL is source metadata until an ingestion feature actually retrieves usable content.

### Outcome values

| Value | Interpretation |
| --- | --- |
| `not_demonstrated` | This attempt does not establish the target ability |
| `with_support` | The target was achieved after recorded assistance |
| `independent` | The target was achieved without the specified assistance |
| `uncertain` | The attempt or assessment is too ambiguous for a reliable finding |
| `unassessed` | This attempt did not test the target skill |

Treat these as evidence labels. They are not permanent learner identities or a certified proficiency score.

### Provider operations

- `generate_recap(context)` returns prompts, target IDs, and expected criteria.
- `evaluate_recap(recap, responses, context)` returns findings, explanations, optional bank suggestions, and a proposed follow-up.

The backend assigns and validates canonical identifiers. It supplies only the source, relevant goals and bank entries, rubric, and compact progress summary. Full history and the entire dictionary are not necessary for every request.

Illustrative evaluation shape:

```json
{
  "schema_version": 1,
  "findings": [
    {
      "prompt_id": "q2",
      "response_id": "r2",
      "topic_id": "physical_states",
      "modality": "written_production",
      "outcome": "with_support",
      "evidence": {
        "response_quote": "Tengo frío.",
        "assistance_ids": ["hint_1"]
      },
      "explanation": "The response fits the situation after the supplied hint."
    }
  ],
  "feedback": {
    "demonstrated": ["Used the target phrase with support"],
    "practice_next": ["Use the pattern in a new situation without a hint"]
  },
  "bank_suggestions": [],
  "follow_up": null
}
```

The example assumes `q2`, `r2`, `physical_states`, and `hint_1` exist in the supplied context. Match quotes and assistance IDs to the stored response. Reject unknown references, unsupported modality claims, and malformed outcomes before updating evidence.

The LLM proposes language judgments. The application owns XP, budget enforcement, curriculum updates, and review scheduling. Treat imported or pasted text as source material rather than instructions for operating the application.

## 7 Application API

These routes belong to Spanish Ranked; the provider adapter has its own external API integration.

| Route | Purpose | Phase |
| --- | --- | --- |
| `GET /health` | Report application readiness | 0 |
| `POST /sessions` | Validate and create a saved session | 0–1 |
| `GET /sessions` | List recent sessions | 1 |
| `GET /sessions/{id}` | Resume a session or load its report | 1 |
| `POST /sessions/{id}/recap` | Create a saved recap or return the existing one | 1 |
| `POST /sessions/{id}/responses` | Persist answers and assistance | 1 |
| `POST /sessions/{id}/evaluate` | Evaluate the stored response version | 1 fixture; 3 real provider |
| `POST /sessions/{id}/complete` | Check completion and atomically award XP once | 1 |
| `GET /progress` | Return XP and available progress evidence | 1 onward |
| `GET /usage` | Return spend, reservations, and remaining budget | 3 |
| `POST /assessments/{id}/dispute` | Exclude a disputed finding from mastery updates | 3 |
| `GET /bank` and `POST /bank` | Search or add personal entries | 4 |
| `GET /topics` and `PUT /goals` | Inspect curriculum and select learner goals | 4 |
| `GET /next-task` | Return a recommendation with its supporting reason | 4 |
| `POST /imports/preview` | Validate an import without applying it | 4 |
| `POST /imports/{id}/commit` | Apply the reviewed import decisions once | 4 |

Use ordinary validation errors for malformed input, `409` for incompatible session state or idempotency reuse, and a structured application error for provider or budget failures. Include a machine-readable error code, a useful message, and whether retry is appropriate.

Example application error:

```json
{
  "code": "budget_exhausted",
  "message": "Your recap is saved. More evaluation requests are paused until the budget is available.",
  "retryable": false,
  "session_state": "submitted"
}
```

The `retryable` flag concerns automatic immediate retry. A manual retry may become appropriate after a budget change or reset.

## 8 Bank and curriculum design

### Three distinct collections

| Collection | What it contains | What adding an item means |
| --- | --- | --- |
| Dictionary | Reference words, senses, definitions, examples, regions | The information is available to look up |
| Personal bank | Expressions encountered or selected for practice | The expression has been encountered |
| Curriculum | Goals, prerequisites, rubrics, linked expressions | The app has a structured target to assess |

Adding an entry does not demonstrate mastery. Preserve Spanish accents, distinguish senses, and retain the exact inflected expression encountered even when a base form is available.

Track recognition, use, and later retention per modality. An entry can be understood independently in reading while remaining unassessed in speech.

### Personal bank CSV

Accept UTF-8 input. Required fields are `spanish`, `meaning`, and `entry_type`; the remaining fields are optional. Use semicolons inside a quoted `topic_ids` cell when assigning multiple topics. Missing sense labels require review when duplicate meanings are ambiguous.

```csv
spanish,meaning,entry_type,sense,topic_ids,source
"tengo frío","I feel cold","phrase","physical sensation","physical_states","personal notes"
"¿Cuánto cuesta?","How much does it cost?","phrase","asking a price","prices","conversation"
```

Normalize Unicode and whitespace for duplicate detection while preserving meaningful accents. Match expression, language, and sense. Present merge or skip choices rather than silently replacing existing meanings or evidence.

### Curriculum JSON

An import includes a schema version, topics, and optional rubric definitions. This example defines the rubric it references:

```json
{
  "schema_version": 1,
  "rubrics": [
    {
      "id": "needs_v1",
      "version": 1,
      "criteria": [
        "Interpret a basic physical need in context",
        "Express a basic physical need appropriately"
      ]
    }
  ],
  "topics": [
    {
      "id": "physical_states",
      "goal": "Understand and express a basic physical need",
      "prerequisites": [],
      "entry_ids": [],
      "rubric_id": "needs_v1"
    }
  ]
}
```

Validate references against the combined existing records and import contents. Reject prerequisite cycles. Preview changes, preserve import identity, and commit atomically. Imported topics do not replace active goals or rubrics without an explicit decision in the preview.

### Selecting the next task

Start with explainable rules:

1. Select a due review related to the current goal, within the configured review allowance.
2. Otherwise select a recent difficulty supported by accepted evidence.
3. Otherwise select the next relevant topic whose prerequisites are met.
4. If evidence is insufficient, offer a short diagnostic or let the learner select an entry topic.

Break ties using the oldest practice date. Show the reason and the supporting session. Keep the ability to choose another activity.

Proposed Phase 5 starting settings: a first check on a later day, longer intervals after independent success, and shorter intervals after supported or unsuccessful attempts. Keep those rules configurable and record their version. Tune them through use rather than presenting a particular interval as scientifically optimal.

Dictionary import adapters must preserve the source, license, attribution, sense, and regional information. Choose the dataset before writing the adapter; a generic dictionary is not automatically a beginner curriculum.

## 9 XP mastery and bosses

### Proposed XP defaults

- One XP per recorded active minute after completion.
- Up to 120 credited minutes per session initially.
- Active minutes must be a positive whole number; the server applies the cap.
- No correctness multiplier in the initial release.
- No XP loss for failed bosses or missed days.
- Background exposure has a separate log until its credit policy is decided.

Calculate the award on the backend and save the rule version with it. The frontend displays the result and never chooses the awarded amount.

### Evidence over time

Useful indicators include independent outcomes across comparable attempts, hints required, fresh-context success, delayed recall, sample counts, and evidence age. Show uncertain or unassessed skills directly.

Avoid combining different task difficulties into an unsupported fluency percentage. CEFR descriptions may help write goals, but application ranks are not CEFR certifications.

### Boss eligibility and results

A major boss requires its configured XP threshold and prerequisite checkpoints. Display remaining requirements explicitly. Keep rank thresholds as configuration and retain Bronze through SSL as a possible sequence.

Each encounter stores the situation, required skills, allowed assistance, grading criteria, and content version. Passing requires meeting each required skill criterion. Appropriate requests for clarification can count as successful interaction where the rubric permits them.

Failures create recommendations and preserve XP. Uncertain grading leaves the encounter result pending. Routine feedback and ordinary practice stay accessible regardless of rank.

## 10 Cost control and failure handling

Proposed initial budget: **$5 per month**, configurable. Select the model after testing its feedback quality on representative Spanish responses. Keep rates in versioned configuration instead of embedding prices throughout the code.

For every paid operation:

1. Bound the input and output and estimate the maximum permitted request cost.
2. Atomically reserve that amount against the monthly budget, including outstanding reservations.
3. Issue the request with the configured output limit.
4. Record reported usage and reconcile the reservation to estimated billed cost.
5. Retain the reservation if billing remains uncertain after a timeout; reconcile it before releasing it.

Log every attempt, including retries. Separate cached and uncached rates when relevant and account for billed reasoning or audio according to the selected provider's contract. Reconcile the app's estimates with the provider's usage reporting.

Proposed initial automatic retry ceiling: one retry for a transient failure, with backoff and a fresh budget check. Do not automatically retry authentication errors, exhausted budgets, or ambiguous in-flight requests that could duplicate a charge.

If the provider is unavailable, keep source material and answers saved. The report remains pending until it can be evaluated. Do not substitute fixture assessments for real learner results.

The earlier cost illustration was approximately $1.13 for thirty text sessions at 20,000 input and 5,000 output tokens each, using rates checked on 2026-10-09. It is a historical planning example, not a current quote or a budget guarantee. Verify the selected model's pricing before enabling paid calls; audio and additional requests are separate.

## 11 Checks that protect the core behavior

Implement these alongside the relevant phase. Focus on the rules that can lose data, double-charge, misrepresent learning, or award duplicate progress.

- [ ] Completing a session twice, including concurrently, creates one XP award.
- [ ] Empty or unfinished recaps cannot complete.
- [ ] Incorrect completed attempts can still receive effort XP.
- [ ] Refresh and backend restart preserve source, answers, feedback, and session state.
- [ ] Reused idempotency keys with different payloads are rejected.
- [ ] Failed or malformed model responses cannot overwrite valid assessments or update mastery.
- [ ] Findings reference the correct prompt, response, topic, and recorded assistance.
- [ ] Disputed or superseded evidence is excluded from progress summaries.
- [ ] Concurrent requests cannot bypass the budget reservation check.
- [ ] Imported entries are encountered, not mastered; duplicate commits are idempotent.
- [ ] Curriculum cycles and unknown references fail validation before any write.
- [ ] Restoring a backup recovers the same sessions and XP balance.
- [ ] Audio transcript errors can be corrected without recording a false learner failure.

## 12 Decisions to revisit

| Decision | Choose or tune by |
| --- | --- |
| API provider and model | Phase 3, after reviewing representative outputs |
| Spanish variety and treatment of regional expressions | Before relying on language judgments; make voice choices explicit in Phase 6 |
| Personal bank and dictionary sources | Phase 4 for personal imports; later for a large dataset |
| Review intervals and review allowance | Phase 5, using real sessions |
| Audio retention and transcription approach | Phase 6 |
| Rank thresholds and encounter retry rules | Phase 7 |
| Custom recommendation model | After collecting trustworthy outcomes and establishing a rule-based baseline |

## References

- [Council of Europe CEFR Companion Volume](https://rm.coe.int/cefr-companion-volume-with-new-descriptors-2020/16809ea0d4) — descriptors for communication goals and separate skill profiles.
- [The role of variable retrieval in effective learning](https://doi.org/10.1073/pnas.2413511121) — research informing delayed retrieval with varied contextual cues.
- [OpenAI model documentation and pricing example](https://developers.openai.com/api/docs/models/gpt-5.4-mini) — source for the dated cost illustration; verify current pricing when implementing.

This version expands the 2026-10-09 design into coding phases. It preserves the learning goals and makes implementation defaults explicit so they can be changed deliberately.
