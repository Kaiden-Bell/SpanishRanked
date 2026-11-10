# Level 2 build plan: Daily Recap and Daily Review v1

> **Status:** Planned. Not started. Work begins after the Level 1 release (Milestone E in `MVP_DESIGN.md` §11).  
> **Last updated:** November 10, 2026  
> **Covers:** milestones L2-M1 and L2-M2 of `LANGUAGE_AI_PRODUCT_ROADMAP.md` §13. The intended learner experience is in §4 of that document.

## 1. What the audit found

The repository was checked on November 10, 2026. All paths are under `src/backend/app/`.

| Capability | Status | Where |
| --- | --- | --- |
| Study sessions with 3 to 5 terms and 2 to 3 sentences | Built | `routes_sessions.py`; tables `study_sessions`, `study_terms`, `study_sentences` |
| Concepts a learner has encountered | Derivable, no new table | `study_terms` joined to `concepts` |
| Question generation from recent material | Built. Needs the local model | `assessment/generate.py`: `recent_material`, `generate_quiz` |
| Written-answer grading, HIT / PARTIAL / MISS per concept | Built. Needs the local model | `assessment/grade.py`: `grade_assessment` |
| Evidence per graded concept | Built | `concept_evidence`, written only in `grade.py` `_finalize` |
| XP ledger, one award per source, daily cap per source | Built | `progression.py` `award_xp`; `rules.py` `DAILY_XP_CAP` |
| No XP for an identical retake | Built | `fingerprint` in `grade.py` |
| List of past assessments | API only | `GET /api/assessments` in `routes_assessments.py`. No page. |
| Recap or review of any kind | Not built | |
| Multiple-choice or fill-in-the-blank questions | Not built | |

Three limits in the current code shape this plan:

1. **`xp_events` rejects a new source.** Its `source_type` CHECK allows only `STUDY_SESSION` and `ASSESSMENT`. SQLite cannot change a CHECK in place, so allowing `REVIEW` means rebuilding the table in a migration.
2. **The generator always writes exactly three questions.** `build_schema` in `generate.py` sets both the minimum and maximum to `rules.QUIZ_ITEMS`. A shorter review, or a second round for one missed concept, needs a variable count.
3. **Grading is slow.** About 12 seconds per answer on the development host, so about 40 seconds per three-question round. A review with a second round has two waits.

## 2. L2-M1: Daily Recap

**Goal:** on return, the learner sees what they recently studied and how they did, without starting anything.

**Scope:**

- One read-only endpoint, for example `GET /api/recap`.
- A Recap panel on the dashboard or its own page.

**Content, all from existing tables:**

- Recent sessions: date, activity, context note, and terms. Go back by session count, not by days, so a learner who missed a week still sees material. `recent_material` already does this for the last five sessions.
- For each recent concept: its latest graded outcome, if it has one. Otherwise it is listed as studied and not yet tested.
- Concepts whose latest outcome was MISS or PARTIAL, listed as needing practice.

**Rules:**

- No model call and no database migration.
- No improvement claims. The Recap states outcomes ("last answer: correct"). It does not say a concept improved, because nothing defines that yet.
- A learner with no sessions gets an empty state that offers a study session.
- Reading the Recap pays no XP and does not count toward the streak.

**Tests:**

- [ ] New user with no study history gets an honest empty state.
- [ ] Learner who missed several days still sees their most recent sessions.
- [ ] Learner can read the Recap without starting a review.
- [ ] A concept with no graded answer is shown as not yet tested.
- [ ] The Recap works with the model and LanguageTool both down.

## 3. L2-M2: Daily Review v1

**Goal:** an optional short review with a second round on missed concepts, clear results, and review XP.

**Accepted limits of v1** (from the roadmap, §3):

- The local model is required. When it is down, Review says it is unavailable and the Recap still works.
- Written answers only. Three questions in round 1.

### 3.1 Flow

1. **Start.** The learner starts a review. A review session is created.
2. **Round 1.** Generate questions with the existing generator and grade them with the existing pipeline.
3. **Round 2.** If any concept in round 1 was not a HIT, generate one new question per missed concept. The prompt must ask for a different sentence from round 1. Grade the same way.
4. **Close.** The session closes when round 2 is graded, when round 1 had no misses, or when the learner skips round 2.
5. **Results.** Show round 1 and round 2 separately, the feedback per answer, and the XP breakdown.

### 3.2 Reuse

- `generate_quiz` and `recent_material` for round 1.
- `save_answers` and `grade_assessment` for both rounds. Answers are saved before any model call, and a failed grading can be retried. Reviews inherit both behaviours.
- `award_xp` for the award. It already pays once per source and applies the cap for that source.
- The existing Quiz screen for answering and feedback.

### 3.3 Code changes

- **Generator:** accept a list of target concepts and a question count, in place of the fixed three. Round 2 passes the missed concepts.
- **Grading:** `_finalize` in `grade.py` pays quiz XP today. For an assessment that belongs to a review, it must write evidence and mark the round graded, and leave XP to the review session.
- **Review service and routes:** start a review, fetch its state, skip round 2, close.
- **Rules:** a `REVIEW` entry in `DAILY_XP_CAP` and the three review XP constants.
- **Frontend:** a Review entry point from the Recap, the two-round flow, and a results view.

### 3.4 Database migration (one, appended as the next schema version)

- **New table `review_sessions`:** owner, status, created and closed timestamps, and the stored XP breakdown (completion, first-try correct count, retry correct count).
- **`assessments`:** add a nullable `review_session_id` and a `round` number. Both stay empty for ordinary quizzes.
- **`xp_events`:** rebuild the table so `source_type` also allows `REVIEW`. Copy every existing row unchanged and recreate its indexes and its unique constraint.

`concept_evidence` does not change. Each evidence row already points at its question, and the question's assessment will carry the round.

### 3.5 XP

- One `xp_events` row per review session: `source_type = 'REVIEW'`, `source_id` = the review session.
- Base XP follows the formula in the roadmap, §4.2.
- Awarded once, when the session closes. A second close returns the original award.
- The streak multiplier and the `REVIEW` daily cap apply through `award_xp`, as they do for other sources.
- A review counts toward the streak in the same way a submitted assessment does.

### 3.6 Tests

- [ ] Incorrect first-round answer stays recorded after a correct retry.
- [ ] Round 2 asks only about concepts missed in round 1, with different questions.
- [ ] Round 2 is skipped when round 1 has no misses.
- [ ] First-try XP exceeds retry XP.
- [ ] A review produces exactly one XP event, and closing twice pays once.
- [ ] The review daily cap cannot be bypassed by repeated sessions.
- [ ] Review XP does not reduce the quiz cap, and quiz XP does not reduce the review cap.
- [ ] Ordinary quizzes pay exactly as before the migration.
- [ ] The migration keeps every existing XP row, and totals, ranks, and streaks are unchanged after it.
- [ ] Model down at start: Review reports unavailable and the Recap still loads.
- [ ] Model down during grading: answers are kept, the round can be retried, and no XP is paid until the session closes.
- [ ] Results show first-attempt and retry outcomes separately.

## 4. Decisions needed before L2-M2 starts

| Decision | Recommendation |
| --- | --- |
| Values for completion XP, first-try XP, retry XP, and the review daily cap | Set them together with the quiz values (3 XP per correct answer, cap 30) in view. |
| Can completion XP be earned more than once a day? | No. Pay it for the first closed review of the day only. |
| What happens to a review the learner abandons? | Close it automatically after 24 hours and award what was earned, without completion XP. |
| Do results include a corrected sentence? (`backlog-learning.md` item 2) | Decide after measuring the grading time it adds. It changes the grading contract in `MVP_DESIGN.md` §8. |
| Rule for deleted study sessions (`backlog-learning.md` item 4) | Keep the XP and mark the session deleted. The Recap then hides deleted sessions. Needed before deletion is built, not before L2-M1. |
| Does a second round with one question justify a model call of about 12 seconds? | Yes for v1. Revisit when templates exist. |

## 5. Out of scope for both milestones

These belong to L2-M3 or later in the roadmap:

- Multiple-choice and fill-in-the-blank questions, and the five-question target.
- Reviews that work without the model.
- Concept suggestions from free-text notes.
- The personal dictionary, self-reported familiarity, and the future-review queue.
- Skill estimates and improvement claims.
