# Milestone D plan: local AI assessment with independent, failure-tolerant services

## Context
Milestones A–C are done (shell, auth + study logs, XP/ranks/streaks). Milestone D adds quiz generation and grading via
LanguageTool (advisory hints) and Qwen2.5:7b (essential judge), with the backend alone deciding XP.

The design doc bundles everything into one container. On review, that makes failure handling awkward: Docker only restarts a
container when its main process exits, so a crashed LanguageTool inside the app container would go unnoticed. The two
dependencies also fail differently. LanguageTool is advisory, while Ollama is essential. This plan makes each service
independent, makes degradation explicit, and never loses a learner's answers. **Nothing is built until this plan is approved.**

## Decisions (confirmed with the user)
1. **Packaging: compose sidecars.** App, LanguageTool and (optionally) Ollama are separate services in one compose project.
   The definition of done changes from "one container" to "one compose project / one `docker compose up`"; MVP_DESIGN.md §5 and
   §11 need updating (needs the user's OK before editing).
2. **LanguageTool down or slow: grade without hints and warn the learner** that grammar hints were unavailable for this attempt.
3. **Model down or timed out at submission: save the answers, show "grading pending" with retry, award no XP until grading succeeds.**
   This uses the existing `SUBMITTED` / `FAILED` statuses in `assessments`.

Assumed, not yet confirmed: **PARTIAL pays 0 XP, HIT pays +3** (the user's table is binary; revisit after reviewing real grading).

## Architecture
- Backend talks to both services through small client "ports" (`GrammarChecker`, `LanguageModel`) configured by URL
  (`LANGUAGEAI_LANGUAGETOOL_URL`, `LANGUAGEAI_OLLAMA_URL`, model name). Tests use fakes; production uses HTTP clients.
- Reuse the working logic in `eval/grading/run_grading_eval.py` rather than rewriting it: `lt_check` and `lt_keep`
  (`/v2/check`, category filter), `format_hints` (the `<languagetool_hints>` block), `build_schema` and `call_ollama` (Ollama
  `/api/chat` with a JSON-schema `format`, temperature 0), `validate`, plus `eval/grading/concept_guidance.json`. Port them
  into backend modules. The backend then becomes the source of truth and the eval can import from it later.
- Compose: add a `languagetool` service (image `erikvl87/languagetool`, already healthy on the homelab at 650 MiB, internal
  network only). The app starts even if sidecars are absent (`depends_on ... required: false`).
- **Ollama reachability (needs a decision at build time):** on the homelab it is a systemd service bound to 127.0.0.1:11434
  with no GPU. Option (a), recommended for the homelab: `extra_hosts: host.docker.internal:host-gateway` plus
  `OLLAMA_HOST` set so the host listens on the docker bridge. Option (b): an `ollama` sidecar behind a compose profile with a
  model volume, which re-downloads 4.7 GB but is portable.

## Failure handling
| Event | Behaviour |
|---|---|
| LanguageTool timeout/down (3 s timeout) | Grade with the model alone; store checker findings as `{"status":"unavailable","reason":...}` (distinct from `{"status":"ok","matches":[]}`); show a warning to the learner. After 3 consecutive failures skip it for 60 s (in-process circuit breaker) so latency stays low. |
| Model down/timeout at generation | Clear "quizzes unavailable" message; nothing saved, no XP. Study logging keeps working. |
| Model down/timeout at grading | Answers saved in the same transaction, status `SUBMITTED`; respond "grading pending"; `POST /api/assessments/{id}/grade` retries. No XP until `GRADED`. |
| Malformed or out-of-scope model JSON | Validate against schema and scope; retry once; otherwise stay `SUBMITTED` with `grading_error`. Never award XP on unvalidated data. |
| Double submit / retry after success | Only `SUBMITTED -> GRADED` is allowed. `award_xp` is idempotent on `(user, ASSESSMENT, assessment_id)`. |
| Identical retake (same questions, same normalized answers) | A fingerprint stored on the assessment yields 0 additional XP. |

## Health model
- Keep `/api/health` as pure liveness (database only) and add a Docker `HEALTHCHECK` to it. A slow Ollama must never cause Docker
  to restart a healthy app.
- Add authenticated `GET /api/system/status` returning `database | languagetool | model` as `ok | degraded | down` with a
  timestamp, cached about 10 s. The dashboard shows a banner when the model is down ("Quizzes unavailable"). Uptime Kuma /
  Grafana on the homelab can watch the same endpoints.
- A short operator runbook (what to do for each row above) goes in the install guide (Milestone E).

## Data and code changes
- **Migration v4 (never edit v1–v3):** `assessments` gains `fingerprint`, `grading_error`, `graded_at`. Checker status is
  carried in the existing `checker_findings_json` envelope, so no new column is needed there.
- **New backend modules:** `clients/grammar.py` (LanguageTool client + breaker), `clients/model.py` (Ollama client),
  `assessment/generate.py`, `assessment/grade.py` (prompt building, validation, scoring), `routes_assessments.py`,
  `routes_system.py`.
- **Existing code to reuse:** `progression.award_xp` and `rules.DAILY_XP_CAP` / `rules.QUIZ_XP_PER_CORRECT` (already in place and
  tested), `deps.ready_user` / `get_db`, `routes_sessions._hydrate` for recent study material, `concepts` / `concept_evidence`
  tables.
- **Docs:** update MVP_DESIGN.md §5/§11 (compose project), §7/§8 (per-answer XP from model HIT outcomes, daily cap 30; LanguageTool
  still never moves XP).
- **Frontend:** Assessment screen (generate, answer, submit, feedback, XP earned), "grading pending" retry state, LanguageTool
  warning, dashboard status banner.

## Verification
1. **Unit/API tests with fakes (no 7B model needed):** inject timeouts, connection errors and malformed JSON for each client.
   Assert: answers are never lost, no XP without `GRADED`, one award per attempt, retake fingerprint pays 0, LanguageTool failure
   still grades with a warning, the circuit breaker opens and closes, and `/api/health` stays 200 while dependencies are down.
   Mutation-check the money paths as in Milestone C.
2. **Live failure drills on the homelab:** `docker compose stop languagetool` then submit (graded, warning shown); `systemctl stop
   ollama` then submit (saved as pending), start it and retry (graded, XP paid once); confirm the Docker health status of the
   app stays healthy throughout.
3. **Quality gate:** run `eval/grading/run_grading_eval.py` through the backend path and confirm the same bars (error detection ≥ 80%,
   false-error ≤ 10%, adversarial 100%, schema validity ≥ 95%, p95 ≤ 15 s).
