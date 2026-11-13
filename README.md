# Language AI (SpanishRanked)

A self-hosted Spanish study tracker. Log what you studied, and every word you log goes into a word bank: its meaning, the exact form you met (who and when), its full conjugation table and real example sentences. Then take short quizzes built from your own words, get feedback and XP, and watch your rank and streak. It runs on your machine: no account, no cloud AI, no telemetry. Word meanings and examples are looked up online (see [Online lookups](#online-lookups)).

**Status:** Level 1 MVP done; the Level 2 work is in progress. The word bank is built. See [ROADMAP.md](docs/ROADMAP.md) for what is coming and [MVP_DESIGN.md](docs/MVP_DESIGN.md) for the Level 1 design.

## What you need

- Docker with Compose v2.
- About **15 GB of disk**: the images are about 10 GB (the `ollama/ollama` image alone is 8.5 GB, LanguageTool 1.2 GB, the app 0.3 GB) plus the 4.7 GB `qwen2.5:7b` model. Measured on the development host.
- About **8 GB of free RAM** while a quiz is being graded. This is an estimate (the 4.7 GB model plus overhead), not a measurement; at idle the three containers use under 1 GB together (LanguageTool ~650 MB, the rest small).
- No GPU is required. Without one, expect roughly **12 s per graded answer** (about 40 s for a 3-question quiz) on an 8-core CPU.
- Internet is needed once, to pull images and the model. After that it is used only for word lookups, which you can turn off.

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
2. **Words** is your word bank. Search it, open a word to see what the form you met means, its conjugation table, examples and your history with it, and add your own translation. Each term you type in the study form shows a quick lookup as you type.
3. **History** lists everything you logged. Delete a session logged by mistake: its XP is taken back, and words that only it added leave the word bank. Quiz results stay.
4. **Quiz** builds five short questions from your word bank, mixing types:
   - meanings
   - who and when (which person and tense a form is)
   - conjugating
   - filling the gap in a real sentence
   - putting words in order
   - listening, through your browser's voice
   - one free sentence

   Most are checked instantly. Words you miss come back sooner (Leitner boxes). You can also practise one skill, or do "Sentence practice", where the local model grades free sentences.
5. The **Dashboard** has four parts:
   - **Since last time**, a recap with a 5-question **warm-up**. The first warm-up each day earns a little XP.
   - **Your rank and streak.**
   - **A skill profile**, scored separately for Reading, Listening and Writing from your own answers.
   - **Recent activity.**
6. **Boss battles.** When you have the XP for the next rank, its boss battle opens: a stage each for listening, reading, grammar and writing. Win it to take the rank. Lose, and your missed words go back into review; you can try again after a short rest.

7. **Settings**, next to Sign out, covers:
   - quiz and warm-up length
   - listening questions on or off
   - the Spanish voice and speed on this device
   - reduced motion
   - changing your password and signing out other devices
   - resetting all your data, which needs your password and typing RESET; your account and settings stay
If you have not logged anything yet, the app asks for a study session instead of making up a quiz.

## When something is down

The app keeps working when the helpers are not available (see [MVP_DESIGN.md](docs/MVP_DESIGN.md) §5):

| Down | What you see |
| --- | --- |
| LanguageTool | Grading continues without grammar hints, and you are told. |
| The model (Ollama) | Quizzes and warm-ups still work, without the free-sentence question. Sentence practice and boss battles say they are unavailable. If it goes down while grading a sentence, your answers are saved and you can retry. No XP is paid until grading succeeds. |

## Configuration

Set these in `.env` (see [.env.example](.env.example)).

| Variable | Default | Meaning |
| --- | --- | --- |
| `LANGUAGEAI_BIND_ADDR` | `127.0.0.1` | Address the UI is published on. |
| `LANGUAGEAI_TIMEZONE` | `UTC` | Where a day ends, for streaks and daily caps. |
| `LANGUAGEAI_OLLAMA_URL` | `http://ollama:11434` | Model server. |
| `LANGUAGEAI_LANGUAGETOOL_URL` | `http://languagetool:8010` | Grammar checker. |
| `LANGUAGEAI_MODEL` | `qwen2.5:7b` | Model name in Ollama. |
| `LANGUAGEAI_ONLINE_LOOKUPS` | `1` | Look up word meanings and examples online. `0` turns it off. |
| `LANGUAGEAI_LOOKUP_CONTACT` | empty | Your URL or email, added to the User-Agent of lookups as Wikimedia asks. Optional. |

Also available to the app but not wired through compose: `LANGUAGEAI_SECURE_COOKIES=1` (set it if you serve over HTTPS), `LANGUAGEAI_SESSION_TTL_HOURS` (default 168), `LANGUAGEAI_LANGUAGETOOL_TIMEOUT` (3 s) and `LANGUAGEAI_MODEL_TIMEOUT` (120 s).

## Online lookups

When you log a term, the app looks it up in [Wiktionary](https://en.wiktionary.org) (meanings), [Tatoeba](https://tatoeba.org) (example sentences) and, for whole phrases, [MyMemory](https://mymemory.translated.net) (machine translation). Only the Spanish word or phrase is sent. Every result is cached in your database, so each word is fetched once.

Conjugations and grammar analysis never go online: the verb tables (about 9,700 verbs, generated with [verbecc](https://github.com/bretttolbert/verbecc)) are built into the image.

If the lookups are off or unreachable, everything still works: an entry shows that its meaning is missing, and you can type your own translation.

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

Grading quality is measured with `eval/grading/run_grading_eval.py`; see [eval/grading/README.md](eval/grading/README.md). The post-MVP roadmap is in [docs/LANGUAGE_AI_PRODUCT_ROADMAP.md](docs/LANGUAGE_AI_PRODUCT_ROADMAP.md); smaller ideas live in [docs/backlog-learning.md](docs/backlog-learning.md) and [docs/backlog-scenes.md](docs/backlog-scenes.md).

## Known limitations (Level 1)

- Grading is not perfectly repeatable: in testing, about 1 answer in 74 was paid XP it should not have been. Rank is an activity rank, not a proficiency claim.
- Grading is slow on CPU-only hosts (see above).
- Single owner account only; no editing or deleting study sessions; no quiz history list.
- Writing shows "Not yet assessed" on the dashboard; per-skill results are planned for Level 2.
