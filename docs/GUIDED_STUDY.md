# Guided study

Guided study is an optional path through Spanish: 48 units in four stages, each pairing a short textbook lesson with practice built from the learner's own word bank. Self-study keeps working as before, and it counts toward guided progress.

## How it works

**The syllabus** is `src/backend/app/curriculum/units.json`. Each unit lists:
- the tenses it teaches, as ids from `lexicon/grammar_terms.py`
- its key words (lemmas)
- topic tags
- its prerequisites
- a confidence label for its position in the order

Unit ids (`u01` to `u48`) are stable. Content packs and stored sessions refer to them.

**Content packs** supply the lesson text (see [Content packs](#content-packs)). The bundled default is *¡Chévere!* (CC BY 4.0). A unit no installed pack covers still works: the learner can log their own study of it and practise its words.

**A guided lesson** is an ordinary study session with `mode = GUIDED_STUDY` and a `unit_id`. It reuses the existing pieces:
- the word bank
- XP
- History
- delete

The learner logs the words they want to keep and writes 2–3 sentences of their own using what the lesson taught.

**Unit practice** is a quiz built by `practice/compose.py: compose_unit`. It differs from a regular quiz in two ways:
- **Which entries.** It uses the learner's entries for the unit's key words. For a unit about a tense, it also uses any verb, drilled in that tense.
- **How many questions.** An entry can come back as up to three *different* question types. New material needs several retrievals in a session; regular quizzes keep one question per entry.

**Progress** is computed on every request (`curriculum/progress.py`), never stored, so deleting a session or quiz needs no cleanup. Each unit gets one of four statuses:

| Status | Meaning |
|---|---|
| new | Nothing yet. |
| started | The learner has done one of these: logged a guided lesson for the unit, logged at least two unambiguous forms in a tense the unit is about, or logged about half its key words. Self-study counts. |
| practising | Some answers test the unit. |
| solid | A recency-weighted score of 80% or more over at least 5 answers. |

Answers count toward a unit when one of these holds:
- the quiz was for that unit
- the question is about one of the unit's key words
- the question is a grammar drill in a tense the unit is *about* (`Unit.drilled_tenses`)

That last rule keeps a preterite drill from counting toward "the uses of *se*".

**Hearing a lesson.** Each Spanish line of a lesson gets a ▶ button, and any selected text can be heard with "Hear". This uses the browser's Spanish voice, the same one listening questions use, with the voice and speed chosen in Settings. A browser without one shows a hint instead.
- Which lines count as Spanish is a heuristic in `src/frontend/spanish-ranked/src/spanishText.ts`: Spanish and English function words, accents, `¿ ¡`, and typical endings.
- What is said leaves out the speaker label (`**Juana**:`), list numbers, and English glosses in brackets or italics (`la mochila (*backpack*)` says "la mochila").
- Packs need nothing extra for this. Writing Spanish lines with the gloss in brackets after them, as *¡Chévere!* does, gives the cleanest result.

**Unlocking** is soft. A unit opens once its prerequisites are *started*, not mastered, and a unit the learner is already working on is never locked.

**The suggestion** follows two rules:
1. If any unlocked unit scores below 70%, suggest the earliest such unit (foundations first).
2. Otherwise, suggest the earliest unlocked unit that isn't solid.

## Why the syllabus is ordered this way

The order comes from two sources:
- how well-regarded programs sequence Spanish: US first-year textbooks, the Instituto Cervantes *Plan Curricular*, and self-study methods
- second-language acquisition research on adult English-speaking learners

Where they agree, or where the research is solid, the order follows them. Elsewhere it is a judgment call, and each unit's `confidence` label says which:

| Label | Meaning |
|---|---|
| established | A replicated acquisition finding. |
| supported | Some acquisition evidence. |
| consensus | Programs agree; there is no acquisition data. |
| contested | Programs or studies disagree. |
| design | A judgment made here. |

The firm anchors:
- **Tenses:** present first, then the preterite, then the imperfect, and only then the contrast between them, which takes a long time. The subjunctive comes late and stays variable even for advanced learners.
- **Ser and estar:** learners use *ser* first and overuse it. *Estar* arrives in stages: first with the *-ndo* progressive, then for location, last with adjectives of condition. So *estar* gets its own units before the ser/estar contrast.
- **Gender:** gender errors persist, so nouns are learned with their article from unit 2 onward.
- **Object pronouns:** learners tend to read the first noun as the subject. Unit 16 teaches comprehension first: who did what to whom in *Lo ve María*.
- **Gustar:** it starts as a fixed phrase (unit 10), and the full analysis waits until indirect object pronouns are in place (unit 23).

The rest has no adult acquisition data, so its position is convention:
- *por*/*para*
- the present perfect (placed earlier in Spain)
- the future and the conditional

Six areas should keep coming back in later practice rather than being treated as finished:
- gender
- preterite vs imperfect
- *estar* + adjective
- clitic pronouns
- *gustar* agreement
- mood

What the learning research supports, in short:
- **Spacing and retrieval work.** The existing Leitner schedule needs no change; equal and expanding intervals perform about the same.
- **Explicit explanation beats implicit exposure** on the tests used.
- **Understanding first, then production.** Comprehension-based practice helps early understanding, and production practice helps later production.
- **Prompting before correcting.** Feedback that asks the learner to try again works better than simply restating the correct form.

That is why a lesson shows its sections in this order:
1. A short text that uses the target.
2. The rule.
3. The words.
4. Longer reading.

Practice then mixes recognition and production.

## Content packs

A pack is a folder:

```
manifest.json   {id, title, authors, copyright_holder, source_url, license: {code, url}, changes, retrieved}
sections.json   [{path, title, kind, module, source_url, license, extra_attribution}]
map.json        {"units": {"u19": ["m14/el-preterito.md", ...]}}
sections/**.md  the text
ATTRIBUTION.md  human-readable credits (optional, generated by importers)
```

- `kind` is one of `context`, `grammar`, `vocabulary`, `reading`, `culture`.
- Packs are loaded at startup from two places:
  - `src/backend/content/packs/`: bundled, and shipped in the image.
  - `<data dir>/packs/`: added by the owner. These never leave that machine, so a textbook you own can go here.
- A pack that fails validation is skipped and logged. Validation fails on a missing license, an unknown unit, or a section file that doesn't exist.

**Bundled packs must be CC BY or CC BY-SA.** NonCommercial terms complicate forks, and NoDerivatives forbids the conversion. A CC BY-SA section must stay in its own file and must never be merged into CC BY text.

### Writing an importer

Importers live in `src/backend/scripts/importers/` and run on a developer machine. They never run during the Docker build.

`pressbooks.py` is generic:
- it fetches a book through the public Pressbooks REST API
- it converts the HTML to Markdown with the standard library only
- it keeps text and drops images, audio, video and embedded exercises, whose licenses vary page by page

A book-specific module such as `chevere.py` decides:
- which pages to keep, and what kind each one is
- which pages carry license exceptions. Read every page's citation metadata; Lumen books keep it in `_candela_citation`.

```
python src/backend/scripts/importers/chevere.py fetch /tmp/chevere_raw
python src/backend/scripts/importers/chevere.py build /tmp/chevere_raw
```

`build` rewrites `sections/`, `sections.json`, `manifest.json` and `ATTRIBUTION.md`. `map.json` is written by hand and is left alone.

### The bundled pack

*¡Chévere! Introductory Spanish I & II* by Erica Brown, Alejandra Escudero, María Cristina Montoya and Elizabeth Small, © Lumen Learning, CC BY 4.0. Retrieved 2026-11-13 from the Lumen Learning edition (modules 1–23).

- It contains 172 text sections and covers 35 of the 48 units.
- Six sections adapt text from Wikibooks, Wikipedia or Athabasca University under CC BY-SA. They are marked per section and credited in `ATTRIBUTION.md`.
- It does not cover:
  - affirmative commands (unit 29)
  - the checkpoint (unit 36)
  - the subjunctive and hypotheticals (units 37–46)
  - unit 48

  Those lessons need to be written (license them CC BY 4.0 so they can sit beside *¡Chévere!*), or come from a user-installed pack.

## Not built yet

- Lessons for the uncovered units listed above.
- A frequency-based vocabulary track. The best open lemmatized list is CC BY-SA and needs hand correction before it can ship as a separate data file.
- Prompt-then-correct feedback: one retry with a hint before the answer is shown.
- Detectors for non-tense topics (*ser*/*estar*, *por*/*para*, gender agreement), so self-study can count toward those units.
- Choosing a preferred pack in Settings. Today the lesson view offers a picker when more than one pack covers a unit.
- A self-hosted voice (Piper) for browsers with no Spanish voice. It is planned for 1.1; see [ROADMAP.md](ROADMAP.md).
- Embeddings to match free-text session context to units, using Ollama's `/api/embed`, so the app image stays the same size.
