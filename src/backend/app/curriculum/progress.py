"""Where a learner stands on each unit, and which unit to study next.

Nothing here is stored: it is recomputed from the word bank (lemmas, and the tense of every form the
learner has met), guided lessons they logged, and their practice answers. Deleting a session or
quiz therefore updates progress with no extra bookkeeping.

- exposure: the learner has met the unit's material: a guided lesson for it, two or more
  unambiguous forms in a tense the unit is about (Unit.drilled_tenses), or about half its key words.
- mastery: a recency-weighted score over answers that test the unit (practice/skills.py weights).
- unlocked: every prerequisite has been started (or the unit itself has). Not mastered: the teachability research does not
  support strict gates, and a learner should be able to move on and come back.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from ..practice.skills import _score
from .syllabus import Syllabus, Unit

WINDOW = 30
MIN_ANSWERS = 5
SOLID = 0.8
WEAK = 0.7
# A tense counts as met once the learner has logged this many different unambiguous forms in it.
# One is not enough: the analyzer can read a form two ways ("eres" is also a subjunctive of erar).
MIN_FORMS_FOR_TENSE = 2


@dataclass
class UnitStatus:
    unit: Unit
    status: str = "new"  # new | started | practicing | solid
    unlocked: bool = True
    lessons: int = 0
    words_known: int = 0
    tenses_met: list[str] = field(default_factory=list)
    answers: int = 0
    score: float | None = None

    @property
    def exposed(self) -> bool:
        return self.status != "new"


@dataclass
class _Learner:
    lemmas: set[str]
    tenses: set[str]
    lessons: dict[str, int]
    evidence: list[tuple[str, str | None, str | None, str | None, str]]  # outcome, tense, token, unit_id, skill


def _load(conn: sqlite3.Connection, user_id: int) -> _Learner:
    lemmas = {r[0] for r in conn.execute(
        "SELECT l.lemma FROM bank_entries e JOIN lexemes l ON l.id = e.lexeme_id WHERE e.user_id = ? AND e.kind = 'WORD'",
        (user_id,))}
    forms_by_tense: dict[str, set[str]] = defaultdict(set)
    for (analysis,) in conn.execute(
        "SELECT f.analysis_json FROM bank_forms f JOIN bank_entries e ON e.id = f.bank_entry_id WHERE e.user_id = ?",
        (user_id,),
    ):
        data = json.loads(analysis)
        words = data.get("words") or [data]  # phrases store their analysed words
        for w in words:
            lemmas.add(w.get("lemma") or "")
            readings = {f["tense"] for f in w.get("forms", []) if f.get("tense")}
            if len(readings) == 1 and not w.get("alternatives"):
                forms_by_tense[readings.pop()].add(w.get("surface") or "")
    tenses = {t for t, forms in forms_by_tense.items() if len(forms) >= MIN_FORMS_FOR_TENSE}
    lessons: dict[str, int] = defaultdict(int)
    for r in conn.execute(
        "SELECT unit_id, COUNT(*) FROM study_sessions WHERE user_id = ? AND unit_id IS NOT NULL GROUP BY unit_id", (user_id,)
    ):
        lessons[r[0]] = r[1]
    evidence = []
    for r in conn.execute(
        "SELECT ce.outcome, i.answer_json, i.skill, c.token, a.unit_id FROM concept_evidence ce"
        " JOIN assessment_items i ON i.id = ce.assessment_item_id JOIN assessments a ON a.id = i.assessment_id"
        " JOIN concepts c ON c.id = ce.concept_id"
        " WHERE a.user_id = ? AND ce.evidence_type = 'ASSESSMENT' AND ce.outcome IN ('HIT', 'PARTIAL', 'MISS')"
        " ORDER BY ce.id DESC",
        (user_id,),
    ):
        key = json.loads(r["answer_json"]) if r["answer_json"] else {}
        evidence.append((r["outcome"], key.get("tense"), r["token"], r["unit_id"], r["skill"]))
    lemmas.discard("")
    return _Learner(lemmas, tenses, dict(lessons), evidence)


def _words_to_start(unit: Unit) -> int:
    """Key words a learner must already know for a unit to count as started: half, at least two
    (one shared word like ser says little), and never more than the unit has."""
    return min(len(unit.lemmas), max(2, -(-len(unit.lemmas) // 2)))


def _tests_unit(unit: Unit, tense: str | None, token: str | None, unit_id: str | None, skill: str) -> bool:
    if unit_id == unit.id:
        return True
    if tense and tense in unit.drilled_tenses and skill == "GRAMMAR":
        return True
    if token in unit.lemmas:
        return not unit.tenses or tense is None or tense in unit.tenses
    return False


def unit_statuses(conn: sqlite3.Connection, user_id: int, syllabus: Syllabus) -> list[UnitStatus]:
    learner = _load(conn, user_id)
    out: dict[str, UnitStatus] = {}
    for unit in syllabus.units:
        s = UnitStatus(unit=unit)
        s.lessons = learner.lessons.get(unit.id, 0)
        s.words_known = len(set(unit.lemmas) & learner.lemmas)
        s.tenses_met = [t for t in unit.drilled_tenses if t in learner.tenses]
        outcomes = [o for o, t, tok, uid, sk in learner.evidence if _tests_unit(unit, t, tok, uid, sk)][:WINDOW]
        s.answers = len(outcomes)
        s.score = round(_score(outcomes), 3) if len(outcomes) >= MIN_ANSWERS else None
        if s.score is not None and s.score >= SOLID:
            s.status = "solid"
        elif s.answers:
            s.status = "practicing"
        elif s.lessons or s.tenses_met or (unit.lemmas and s.words_known >= _words_to_start(unit)):
            s.status = "started"
        # A unit the learner is already working on is never locked, whatever its prerequisites.
        s.unlocked = s.exposed or all(out[p].exposed for p in unit.prereqs)
        out[unit.id] = s
    return list(out.values())


@dataclass
class Suggestion:
    status: UnitStatus
    reason: str


def suggest(statuses: list[UnitStatus]) -> Suggestion | None:
    """The earliest weak unit first (foundations before later units); otherwise the earliest unlocked
    unit that isn't solid yet."""
    weak = [s for s in statuses if s.unlocked and s.score is not None and s.score < WEAK]
    if weak:
        s = min(weak, key=lambda x: x.unit.n)
        return Suggestion(s, f"You get about {round(s.score * 100)}% of questions on this unit right. "
                             "A lesson and some practice should lift that.")
    for s in statuses:
        if not s.unlocked or s.status == "solid":
            continue
        if s.status == "practicing":
            more = MIN_ANSWERS - s.answers
            return Suggestion(s, "Keep practising this unit" + (f": {more} more answers will show how solid it is."
                                                               if more > 0 else " to make it solid."))
        if s.status == "started":
            if s.lessons:
                return Suggestion(s, "You've read this lesson. Practise it next.")
            met = []
            if s.tenses_met:
                met.append("forms in this unit's tense")
            if s.words_known:
                met.append(f"{s.words_known} of its key words")
            return Suggestion(s, f"You've already met {' and '.join(met)} in your own study.")
        return Suggestion(s, "The next unit in the syllabus." if s.unit.n > 1 else "Start here.")
    return None
