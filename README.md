# Language AI (SpanishRanked)

A self-hosted Spanish study tracker with short local-AI quizzes. Log what you studied, take a quick assessment built from your own words and sentences, get feedback and XP, and watch your rank and streak. Everything runs on your machine: no account, no cloud AI, no telemetry.

**Status:** Level 1 MVP, in release check. See [MVP_DESIGN.md](MVP_DESIGN.md) for scope, design and known limitations.

## What you need

- Docker with Compose v2.
- About **15 GB of disk**: the images are about 10 GB (the `ollama/ollama` image alone is 8.5 GB, LanguageTool 1.2 GB, the app 0.3 GB) plus the 4.7 GB `qwen2.5:7b` model. Measured on the development host.
- About **8 GB of free RAM** while a quiz is being graded. This is an estimate (the 4.7 GB model plus overhead), not a measurement; at idle the three containers use under 1 GB together (LanguageTool ~650 MB, the rest small).
- No GPU is required. Without one, expect roughly **12 s per graded answer** (about 40 s for a 3-question quiz) on an 8-core CPU.
- Internet is needed once, to pull images and the model. After that the app works offline.

## Install

```bash
git clone <this repo> && cd SpanishRanked
cp .env.example .env          # optional: set your timezone and bind address
docker compose --profile ollama up -d --build
docker compose exec ollama ollama pull qwen2.5:7b    # one time, about 4.7 GB
docker compose logs languageai | grep "First run"
```

The last command prints the one-time sign-in for the account named `owner`. It is shown **once**, in the logs of the first start. Open <http://127.0.0.1:8000>, sign in, and you will be asked to choose a new password straight away.

If you already run Ollama on the host, skip `--profile ollama` and the `pull`, and set `LANGUAGEAI_OLLAMA_URL=http://host.docker.internal:11434` in `.env`.

## Using it

1. **Start Study Session**: choose Self-Study or Guided Study (both use the same form in Level 1), then enter the duration, activity, context, 3–5 words or phrases, and 2–3 sentences you wrote.
2. **History** lists everything you logged.
3. **Quick Assessment** builds a short text quiz from your recent logged material. Answer, submit once, and read the feedback. XP is paid per correct answer, up to a daily cap.
4. The **Dashboard** shows rank, XP to the next rank, streak and recent activity.

If you have not logged anything yet, the app asks for a study session instead of making up a quiz.

## When something is down

The app keeps working when the helpers are not available (see [MVP_DESIGN.md](MVP_DESIGN.md) §5):

| Down | What you see |
| --- | --- |
| LanguageTool | Grading continues without grammar hints, and you are told. |
| The model (Ollama) | Study logging works. Quizzes say they are unavailable. If it goes down while grading, your answers are saved and you can retry. No XP is paid until grading succeeds. |

## Configuration

Set these in `.env` (see [.env.example](.env.example)).

| Variable | Default | Meaning |
| --- | --- | --- |
| `LANGUAGEAI_BIND_ADDR` | `127.0.0.1` | Address the UI is published on. |
| `LANGUAGEAI_TIMEZONE` | `UTC` | Where a day ends, for streaks and daily caps. |
| `LANGUAGEAI_OLLAMA_URL` | `http://ollama:11434` | Model server. |
| `LANGUAGEAI_LANGUAGETOOL_URL` | `http://languagetool:8010` | Grammar checker. |
| `LANGUAGEAI_MODEL` | `qwen2.5:7b` | Model name in Ollama. |

Also available to the app but not wired through compose: `LANGUAGEAI_SECURE_COOKIES=1` (set it if you serve over HTTPS), `LANGUAGEAI_SESSION_TTL_HOURS` (default 168), `LANGUAGEAI_LANGUAGETOOL_TIMEOUT` (3 s) and `LANGUAGEAI_MODEL_TIMEOUT` (120 s).

## Security notes

- The UI is published on `127.0.0.1` by default. Only widen it to a private network or VPN, and put HTTPS in front of it (and set `LANGUAGEAI_SECURE_COOKIES=1`) if you reach it over anything you do not fully trust. Do not expose it to the public internet.
- There is no default password. The first-run password is random and must be changed on first sign-in.
- **Forgot your password?** Issue a new one-time password and sign out all devices:

  ```bash
  docker compose exec -w /app/backend languageai python -m app.manage reset-owner-password
  ```

## Your data and backups

Everything is in the `languageai-data` volume (`/data/languageai.db`); models are in `ollama-models`. Recreating or rebuilding containers keeps both. `docker compose down -v` **deletes them**.

Take a consistent backup while the app is running (a plain file copy can miss the write-ahead log):

```bash
docker compose exec languageai python -c "
import sqlite3
src = sqlite3.connect('/data/languageai.db'); dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst); dst.close()"
docker compose cp languageai:/tmp/backup.db ./languageai-backup.db
```

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                      # backend tests
cd src/frontend/spanish-ranked && npm ci && npm run dev
```

Grading quality is measured with `eval/grading/run_grading_eval.py`; see [eval/grading/README.md](eval/grading/README.md). Post-MVP ideas live in [docs/backlog-learning.md](docs/backlog-learning.md) and [docs/backlog-scenes.md](docs/backlog-scenes.md).

## Known limitations (Level 1)

- Grading is not perfectly repeatable: in testing, about 1 answer in 74 was paid XP it should not have been. Rank is an activity rank, not a proficiency claim.
- Grading is slow on CPU-only hosts (see above).
- Single owner account only; no editing or deleting study sessions; no quiz history list.
- Writing shows "Not yet assessed" on the dashboard; per-skill results are planned for Level 2.
