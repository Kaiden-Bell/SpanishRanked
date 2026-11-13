"""Build a quiz from the word bank: pick entries, choose varied question types, save the attempt.

Instant and model-free. The only model-graded type is WRITE, and a quiz carries at most one of them
unless the learner asked for sentence practice.
"""

import json
import random
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from .. import rules
from ..lexicon.verbs import VerbData
from .context import load_entries
from .select import pick
from .templates import BUILDERS, LISTENING_TYPES, MODALITY, Item, Pool

FOCUS_TYPES: dict[str, set[str]] = {
    "MIXED": set(BUILDERS),
    "SENTENCES": {"WRITE"},  # the Level 1 quiz: free sentences, graded by the model
    "READING": {t for t, m in MODALITY.items() if m == "READING"},
    "LISTENING": set(LISTENING_TYPES),
    "WRITING": {"CONJUGATE", "CLOZE", "SCRAMBLE", "WRITE"},
    "VOCABULARY": {"MEANING_MC", "REVERSE_MC", "CLOZE"},
    "GRAMMAR": {"FORM_ID", "CONJUGATE", "CLOZE", "SCRAMBLE"},
}
MIN_ITEMS = 3


class NotEnoughMaterial(Exception):
    pass


class NeedsModel(Exception):
    """Sentence practice was asked for while the model is down."""


def choose_items(entries, *, n: int, focus: str, listening: bool, allow_write: bool, now: datetime,
                 rng: random.Random, only: set[str] | None = None) -> list[Item]:
    allowed = set(only) if only else set(FOCUS_TYPES[focus])
    if not listening:
        allowed -= LISTENING_TYPES
    if not allow_write:
        allowed.discard("WRITE")
    if not allowed:
        return []
    single = len(allowed) == 1
    max_per_type = n if single else 2
    max_write = n if focus == "SENTENCES" else 1

    pool = Pool(entries)
    used, by_modality, items, previous = Counter(), Counter(), [], None
    candidates = pick(entries, now, n * 3, rng)
    done: set[int] = set()
    # First pass keeps the quiz varied; the second lets entries that only fit an already-used type in,
    # so a small bank isn't turned away. Either way an entry gets at most one question: no padding.
    for strict in (True, False):
        for entry in candidates:
            if len(items) >= n:
                break
            if entry.id in done:
                continue
            limit = max_per_type if strict else n
            options = [t for t in allowed
                       if used[t] < (max_write if t == "WRITE" else limit) and (single or not strict or t != previous)]
            # Spread skills first, then types; shuffle breaks ties so quizzes differ.
            rng.shuffle(options)
            options.sort(key=lambda t: (by_modality[MODALITY[t]], used[t]))
            for t in options:
                item = BUILDERS[t](entry, pool, rng)
                if item:
                    items.append(item)
                    done.add(entry.id)
                    used[t] += 1
                    by_modality[item.modality] += 1
                    previous = t
                    break
    return items


def save(conn: sqlite3.Connection, user_id: int, items: list[Item], *, kind: str, focus: str,
         boss_attempt_id: int | None = None, stages: list[str | None] | None = None) -> int:
    with conn:
        assessment_id = conn.execute(
            "INSERT INTO assessments (user_id, language_code, status, kind, focus, boss_attempt_id)"
            " VALUES (?, 'es', 'GENERATED', ?, ?, ?)",
            (user_id, kind, focus, boss_attempt_id),
        ).lastrowid
        for i, item in enumerate(items):
            conn.execute(
                "INSERT INTO assessment_items (assessment_id, prompt, expected_criteria_json, item_type, modality,"
                " skill, stage, payload_json, answer_json, bank_entry_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    assessment_id, item.prompt,
                    json.dumps({"concepts": [{"id": item.entry.concept_id, "token": item.entry.token}]}, ensure_ascii=False),
                    item.item_type, item.modality, item.skill, stages[i] if stages else None,
                    json.dumps(item.payload, ensure_ascii=False), json.dumps(item.answer, ensure_ascii=False),
                    item.entry.id,
                ),
            )
    return assessment_id


def compose(conn: sqlite3.Connection, verbs: VerbData, user_id: int, *, kind: str = "QUICK", focus: str = "MIXED",
            listening: bool = True, model_ok: bool = True, n: int | None = None,
            rng: random.Random | None = None, now: datetime | None = None) -> int:
    rng = rng or random.Random()
    now = now or datetime.now(timezone.utc)
    if focus == "SENTENCES" and not model_ok:
        raise NeedsModel("Sentence practice needs the local model, which is unavailable right now.")
    n = n or (rules.SENTENCE_QUIZ_ITEMS if focus == "SENTENCES" else rules.QUIZ_ITEMS)
    entries = load_entries(conn, verbs, user_id)
    items = choose_items(entries, n=n, focus=focus, listening=listening,
                         allow_write=model_ok and kind == "QUICK", now=now, rng=rng)
    if len(items) < min(MIN_ITEMS, n):
        if not entries:
            raise NotEnoughMaterial("Log a study session first: quizzes are built from the words you have studied.")
        raise NotEnoughMaterial(
            "Not enough material for this kind of quiz yet. Log a few more words, or try a mixed quiz."
        )
    return save(conn, user_id, items, kind=kind, focus=focus)
