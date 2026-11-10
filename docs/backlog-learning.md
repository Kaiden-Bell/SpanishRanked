# Backlog: learning features (post-MVP)

Ideas raised after the Milestone D build. None of these is required for Level 1.

This file holds detail notes for smaller items. It does not set the order of work: `LANGUAGE_AI_PRODUCT_ROADMAP.md` §13 does. Each item below says where it sits against that roadmap.

## 1. Quiz history

**Roadmap:** build with Daily Review v1 (L2-M2). Review results need the same list, so build one history page that shows quizzes and reviews.

- List completed quizzes, newest first, with the score and XP for each.
- Open a past quiz to see the prompts, the learner's answers, feedback and results.
- The API already returns this (`GET /api/assessments`). Only the page is missing.
- Was item 3 of the Milestone D outstanding list in MVP_DESIGN.md §11; moved here by decision.

## 2. Corrected sentences and extra examples in feedback

**Roadmap:** the corrected sentence is a candidate for Daily Review v1 results (L2-M2), decision pending in `LEVEL2_RECAP_REVIEW_PLAN.md` §4. Example sentences are unscheduled.

Right now feedback is one or two sentences. Two additions:

- **Corrected sentence:** the learner's sentence rewritten correctly, shown next to their own answer.
- **Example sentences:** two or three further sentences using the same target words, at the same level.

Points to settle before building:

- **Trust:** both come from the model, so they are untrusted output. Show them as suggestions, never as a graded value, and keep the learner's original text visible.
- **Schema:** this changes the grading contract (MVP_DESIGN.md §8). Two new fields, validated like `feedback` is now, with length caps.
- **XP:** unchanged. Corrections and examples never affect outcomes or points.
- **Cost:** longer output means slower grading. On this CPU-only host, grading already takes about 35 seconds for three questions, so measure the increase before committing to it.
- **Quality check:** add reference cases for corrections to the grading eval (`eval/grading/cases.json`), since a wrong correction is worse than none.

## 3. Tenses, gathered automatically per word

Spanish needs tense work: the same verb changes form across the present, preterite, imperfect and subjunctive. Once a vocabulary bank exists:

- For each saved word, gather its conjugations across the common tenses.
- Use the bank as the source, not the model, so forms are checked rather than invented. The model could explain them, but should not generate them.
- Show them alongside the word in history and in quiz feedback.

**Depends on:** a vocabulary bank (a per-word record that persists across sessions). That is not in Level 1, and it is the first thing to design.

**Roadmap:** the vocabulary bank is the personal dictionary in L2-M3. This item follows it.

## 4. Edit and delete study sessions

**Roadmap:** unscheduled. The Daily Recap (L2-M1) reads study sessions, so the deletion rule below must be decided before deletion is built.

Study sessions cannot be changed or removed today.

- **Edit:** correct a typo or a term after saving.
- **Delete:** remove an entry logged by mistake.

Decisions needed first:

- **XP on delete:** PRODUCT.md says XP is never removed by a missed day, and §7 says XP comes from an append-only ledger. Deleting a session therefore needs a rule. Options:
  - (a) Keep the XP and mark the session as deleted. This is the safest, because it keeps the ledger honest.
  - (b) Reverse the XP with a compensating ledger entry, so totals and the daily cap stay correct.
  - (c) Let deletion remove the XP outright. This breaks the append-only rule and should be avoided.
- **Editing:** if a session is edited after its XP was awarded, does the award change? The simplest rule is that it does not. The original award stands and the text changes.
- **Concept evidence:** a deleted session may have produced evidence rows. Those need the same treatment as the XP.
- **Assessments:** quizzes are not sessions and should not be editable.
