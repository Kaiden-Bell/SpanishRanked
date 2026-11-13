# Roadmap: from study log to study tool

> **Status:** Phases 0–5 built (Nov 12, 2026). Provisional numbers (XP, thresholds, cooldown) are marked in `rules.py`.
> **Last updated:** November 12, 2026
> **Replaces:** `LANGUAGE_AI_PRODUCT_ROADMAP.md` and `LEVEL2_RECAP_REVIEW_PLAN.md`. `MVP_DESIGN.md` remains the record of Level 1.

## Why this changed

After a week of daily use, the owner found that the Level 1 app didn't help them improve:

- **Every quiz had the same format.** The model was told to "write one Spanish sentence using these terms", whatever the term was. A phrase taken from a song became "Use *[the whole phrase]* in a sentence".
- **Quizzes were slow and depended on the model.** Writing a quiz took one model call. Grading took one or two calls per answer, about 40 s for three questions on CPU. With the model down, there were no quizzes at all.
- **Words were never analysed.** `extrañan` was stored as the string "extrañan", with no infinitive, conjugation, translation or examples.
- **There was no reason to come back.** The app had no recap, no warm-up and no word bank.
- **The skill profile measured nothing.** Every piece of evidence was recorded as WRITING, so it couldn't tell reading from listening from writing.

## Decisions

| Area | Decision |
| --- | --- |
| Role of the AI model | It grades free writing only. Code builds and grades every other question type, instantly. |
| Word data | Hybrid. Lemmas and conjugations come from local data; meanings and examples from free web APIs, cached in SQLite. |
| Offline | No longer a goal. Online lookups are on by default, and the app still works when they fail. |
| Boss battles | They gate rank-ups. Ranks the learner already holds when bosses ship are kept. |
| Delivery | Five phases, each shippable on its own. |

## Phase 0: findings (dependency spike, Nov 12, 2026)

- **spaCy was dropped.** Its small Spanish model (`es_core_news_sm`, GPL-3.0) lemmatised `extrañan` correctly but failed on short sentences:
  - `extrañamos` came out as "extrañir" and `extrañaste` as "extrañastar"
  - `extrañé` was tagged as an adjective
  - `hablaríamos` was left as its own lemma

  It would also add about 300 MB of packages and a GPL dependency.
- **verbecc 2.1.0 (LGPL-3.0) is used at build time only.** `scripts/build_verb_data.py` turns it into `verbs.db`:
  - 9,689 verbs and every simple-tense form
  - built in about 48 s, about 30 MB
  - exact lookups, irregular verbs included: `fui` → ir/ser, `dijeron` → decir, `hablaríamos` → hablar
  - the runtime image needs neither verbecc nor scikit-learn
- **Wiktionary REST** (`/api/rest_v1/page/definition/{word}`, `es` section; CC BY-SA 4.0):
  - gives English glosses, example sentences with translations, and `form-of-definition-link` markers (maletas → maleta)
  - **Wikimedia refuses library traffic (HTTP 403) unless the User-Agent is policy-style**: `name/version (contact) library/version`. `LANGUAGEAI_LOOKUP_CONTACT` lets the self-hoster add their own URL or email; nothing personal is sent by default.
- **Tatoeba** (`api.tatoeba.org/unstable/sentences?lang=spa&q=…&trans:lang=eng&sort=words`; CC BY 2.0 FR):
  - The search is stemmed, so `extrañar` also returns `extraño` = "strange".
  - Results are therefore filtered: the sentence must contain a form of the verb, and the English must contain the gloss.
- **MyMemory** (`api.mymemory.translated.net/get`) translates phrases, which dictionaries don't list. Its output is labelled as machine translation.
- **Licences.** The repository has no LICENSE file yet, and one must be chosen before release. Attribution for Wiktionary, Tatoeba, MyMemory and verbecc is shown on every word page.

## Phase 1: Word bank (built)

Every logged term becomes a word-bank entry.

- **A word** is filed under its dictionary form, so `extrañan` and `extraño` are both filed under extrañar.
- **A phrase** keeps its own entry and links its content words. `te extrañan mucho` links extrañar and mucho; te is grammar context, not a word to learn.

Each entry shows:

- its meaning
- the form you met, with who and when: *ellos / ellas / ustedes · present: they / you all, now*
- the full conjugation table, with the forms you've met highlighted
- example sentences and your own sentences
- the sessions it came from
- your quiz results
- your own translation, if you add one

**Where the code is:**

- `app/lexicon/`, which holds:

  | File | Role |
  | --- | --- |
  | `analyze.py` | Local analysis |
  | `verbs.py` | Verb tables |
  | `sources.py` | Web APIs |
  | `cache.py` | Lookup cache |
  | `enrich.py` | Background worker |
  | `bank.py` | Entries |

- `routes_bank.py`
- migration V5 in `db.py`
- `WordBank.tsx`
- the lookup chip under each term in `NewSession.tsx`

**How it behaves:**

- Analysis is local and takes under 1 ms.
- Dictionary lookups run on a background worker after a session is saved.
- An entry that hasn't been looked up yet says so. Its conjugation table still shows, because it is local.
- Terms logged before the word bank existed are added at startup.
- A word-bank failure never loses a study session: it runs in a savepoint.

**What you type is parsed first** (`lexicon/parse.py`, added Nov 12, 2026, after real use):

- A label like `phrase:` or `word:` is dropped.
- English after a separator (`-`, `=`, `—`, `|`, or a trailing `(…)`) becomes your own translation:
  - for a phrase, of the phrase
  - for a word, of the form you met
- English words never become entries, and an English-only term adds nothing. The study form warns you when that happens.
- Each multi-word term in the study form has a "Keep as a phrase" toggle. Turn it off to save only the words.
- The Words page has two tabs, Words and Phrases.
- A phrase page reads the phrase word by word: each word's dictionary form and meaning, plus who and when for verbs, with links to the word pages.
- **Repair of older data:** migration V8 schedules a one-time re-read of every logged term (`bank.reparse_all`). It removes entries made from labels and English words, keeps practice history, and runs once at startup.

**Known limits:**

- A single word that is both a verb form and a noun (`casa`, `extraño`) is filed as the verb. Inside a phrase, `la casa` is corrected to the noun once Wiktionary confirms the noun exists.
- Enclitic forms are recognised for infinitives, gerunds and commands only.

## Phase 2: Question engine (built)

Quizzes are built from the whole word bank, scheduled with Leitner boxes (1/2/4/8/16/32 days). Each question type is tagged with a skill:

| Type | Skill | Graded by |
| --- | --- | --- |
| Meaning (multiple choice), both directions | Reading | code |
| "*extrañan*: who and when?" (multiple choice or true/false) | Reading (grammar) | code |
| Conjugate "extrañar · nosotros · preterite" | Writing (grammar) | code; an accent-only error counts as partly right |
| Fill in the blank (cloze) from a real sentence | Reading / Writing | code |
| Sentence meaning, multiple choice and true/false | Reading | code |
| Put the phrase in order | Writing (grammar) | code |
| Hear it and pick it; dictation (browser text-to-speech) | Listening | code |
| Free sentence (single words only, never a phrase) | Writing | model |

- A quiz has 5 items, with at most one item graded by the model. When the model is down, the quiz is built without that item.
- Items are answered one at a time with instant feedback.
- Migration V6 adds an `item_type` and modality to each item, and rebuilds `xp_events` so it also allows `WARMUP` and `BOSS` sources.

**How it behaves:**

- A quiz can focus on one skill: Mixed, Vocabulary, Grammar, Reading, Listening or Writing. "Sentence practice" is the Level 1 quiz, every item a free sentence graded by the model.
- Quizzes never pad: each entry gets at most one question, so a small bank gives a shorter quiz.
- The answer key stays on the server until the item is answered.
- Code-checked items use the same feedback shape as the model grader, so submit, retry and finalize didn't change.
- Evidence now records the real modality of each item.
- Listening uses the browser's own text-to-speech. Without a Spanish voice, the client asks for no listening questions.

**Where the code is:** `app/practice/`, which holds:

| File | Role |
| --- | --- |
| `context.py` | Entry data |
| `select.py` | Selection and Leitner boxes |
| `templates.py` | Question builders |
| `compose.py` | Composing a quiz |
| `check.py` | Code checking |
| `answer.py` | Answers one at a time |

The endpoint is `POST /api/assessments/{id}/answers`.

## Phase 3: Daily recap and warm-up (built)

- **`GET /api/recap`** covers:
  - sessions since your last active day, or the last 3 sessions if that is more
  - new words
  - weak words, and how many are due
  - the last quiz
- **The warm-up** is offered on the first visit of a day:
  - 5 items, built by code only, so it works when the model is down
  - only the first warm-up of the day pays XP, under its own daily cap
  - it counts toward the streak

## Phase 4: Skill tracker (built)

- Reading, Listening and Writing are each scored from their own evidence:
  - a recency-weighted mean of the last 30 answers
  - "Not yet assessed" below 8 answers
- Vocabulary and Grammar show your weakest words and tenses.
- Speaking stays "Not yet assessed". No CEFR level is claimed.

## Phase 5: Boss battles (built)

- Reaching a rank's XP unlocks its boss, and passing the boss grants the rank.
- **Stages:** Listening, Reading, Grammar, and Writing (a scenario graded by the model).
- **To pass:** at least 60% in every stage and at least 70% overall.
- **Failing:**
  - starts a 6 h cooldown
  - makes the missed words due right away
- All three numbers above are provisional.
- Ranks held when the migration runs are grandfathered.
- Each stage uses different words where possible.
- The writing stage is a small real-life scenario and needs the model, so with the model down the battle can't start.
- Without a Spanish voice, the listening stage is skipped and the result says so.
- **Where the code is:**
  - `app/practice/boss.py`
  - `routes_boss.py`
  - migration V7 (`boss_attempts`, `boss_passes`)
  - `Boss.tsx`
- `GET /api/progress` reports the rank held, not the rank reached by XP.

## Not built yet

- Speaking, with no microphone input. Speaking stays "Not yet assessed".
- Server-side text-to-speech, for browsers with no Spanish voice. Piper is a candidate.
- A history page for past quizzes and boss battles. Their results are in the API.
- Editing study sessions.
- Picking the reading (verb vs noun) of an ambiguous single word from the Words page.

## Deleting a study session (built, Nov 13, 2026)

Decision (owner): **a deleted session's XP is taken back.**

**What a delete removes:**

- the session, with its terms and sentences
- its `xp_events` row, so total XP, that day's cap and the streak recalculate
- the word-bank entries that only it had added, including phrases and their words

**What it keeps:**

- Quiz, warm-up and boss results, with their XP, because they were earned by answering.
- Ranks won in a boss battle. A held rank no longer needs its XP threshold, so a delete can't take back a battle.

Deleting and then logging the same session again can't earn its XP twice. The endpoint is `DELETE /api/study-sessions/{id}`; the History page asks for confirmation inline.
