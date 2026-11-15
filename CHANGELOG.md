# Changelog

## 1.0.0 (2026-11-15)

The first release. Everything below is new since the Level 1 prototype. Design notes: [docs/ROADMAP.md](docs/ROADMAP.md), [docs/GUIDED_STUDY.md](docs/GUIDED_STUDY.md) and [docs/MVP_DESIGN.md](docs/MVP_DESIGN.md).

### Study

- **Study log.** Record what you studied: duration, activity, context, the words you met and sentences you wrote. XP, daily caps, streaks and ranks.
- **Word bank.** Every logged term is filed under its dictionary form, with:
  - its meaning
  - who and when for the form you met
  - the full conjugation table (about 9,700 verbs, built in)
  - example sentences
  - your own translation
  - your history with it

  Phrases keep their own entries. You can also add words by hand, search by any conjugated form, and delete a session logged by mistake.
- **Guided study.** An optional path of 48 units, from greetings to the subjunctive. Lessons come from *¡Chévere!* (CC BY 4.0), and you can add your own content packs. Each unit has a form to log it and a quiz on its words and tenses.
- **Lesson audio.** Each Spanish line of a lesson can be heard in the browser's Spanish voice. Select any text and press **Hear** to listen to it.

### Practice

- **Quizzes built from your words**, scheduled with Leitner boxes. There are eight question types, most checked instantly by code:
  - meaning
  - who and when
  - conjugation
  - cloze
  - sentence meaning
  - word order
  - listening
  - a free sentence graded by the local model

  You can focus on one skill or do Sentence practice.
- **Background grading.** A quiz with free sentences comes back at once and is graded on a worker. A toast tells you when it's done.
- **Daily recap and warm-up.** "Since last time", plus a 5-question warm-up that works without the model.
- **Skill profile.** Reading, Listening and Writing are each scored from their own answers. Vocabulary and Grammar show your weakest words and tenses.
- **Boss battles.** Each rank-up needs a boss win, with four stages: listening, reading, grammar and writing.
- **Progress recap.** After every quiz: XP, skills and rank, before and after.

### App

- **Themes.** One theme per rank, unlocked by the rank you hold.
- **Settings:**
  - quiz length
  - listening questions
  - Spanish voice and speed on each device
  - reduced motion
  - password
  - reset all data
- **Self-hosted with Docker Compose**: the app, LanguageTool and Ollama (optional). It keeps working when LanguageTool or the model is down.
- **Pinned sidecar images:** `erikvl87/languagetool:6.8` and `ollama/ollama:0.40.14`.
- **Licence:** the code is licensed under the GNU AGPL-3.0. The lesson content keeps its own CC licences.
