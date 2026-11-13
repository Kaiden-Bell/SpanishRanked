"""Skill profile from real answers only (docs/ROADMAP.md Phase 4).

Each skill is scored from its own evidence: Reading from reading questions, Listening from listening
questions, Writing from typed and free-sentence answers. A recency-weighted mean of the last answers
(HIT 1, PARTIAL 0.5, MISS 0). Below MIN_ANSWERS a skill is "Not yet assessed". Speaking has no
questions yet, so it always is. No CEFR level is claimed.
"""

import json
import sqlite3
from collections import defaultdict

from ..lexicon.grammar_terms import TENSES

WINDOW = 30
MIN_ANSWERS = 8
DECAY = 0.95
VALUE = {"HIT": 1.0, "PARTIAL": 0.5, "MISS": 0.0}

SKILLS = [("READING", "Reading"), ("LISTENING", "Listening"), ("WRITING", "Writing"), ("SPEAKING", "Speaking")]
AREAS = [("VOCABULARY", "Vocabulary"), ("GRAMMAR", "Grammar")]


def _score(outcomes: list[str]) -> float | None:
    """outcomes newest first."""
    if not outcomes:
        return None
    weights = [DECAY**i for i in range(len(outcomes))]
    return sum(w * VALUE[o] for w, o in zip(weights, outcomes)) / sum(weights)


def _summary(key: str, label: str, outcomes: list[str]) -> dict:
    recent, before = outcomes[:WINDOW], outcomes[WINDOW:WINDOW * 2]
    assessed = len(recent) >= MIN_ANSWERS
    score = _score(recent) if assessed else None
    trend = None
    if assessed and len(before) >= MIN_ANSWERS:
        trend = round(score - _score(before), 3)
    return {"key": key, "label": label, "status": "ASSESSED" if assessed else "NOT_ASSESSED",
            "score": round(score, 3) if score is not None else None, "answers": len(outcomes),
            "answers_needed": max(0, MIN_ANSWERS - len(outcomes)), "trend": trend}


def profile(conn: sqlite3.Connection, user_id: int) -> dict:
    rows = conn.execute(
        "SELECT ce.outcome, ce.modality, i.skill, i.item_type, i.answer_json, c.token"
        " FROM concept_evidence ce JOIN assessment_items i ON i.id = ce.assessment_item_id"
        " JOIN assessments a ON a.id = i.assessment_id JOIN concepts c ON c.id = ce.concept_id"
        " WHERE a.user_id = ? AND ce.evidence_type = 'ASSESSMENT' ORDER BY ce.id DESC",
        (user_id,),
    ).fetchall()
    by_modality, by_area = defaultdict(list), defaultdict(list)
    tenses, words = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in rows:
        by_modality[r["modality"]].append(r["outcome"])
        area = "GRAMMAR" if r["skill"] == "GRAMMAR" else "VOCABULARY" if r["skill"] in ("VOCABULARY", "COMPREHENSION") else None
        if area:
            by_area[area].append(r["outcome"])
        key = json.loads(r["answer_json"]) if r["answer_json"] else {}
        if area == "GRAMMAR" and key.get("tense") in TENSES:
            t = tenses[key["tense"]]
            t[0] += r["outcome"] == "HIT"
            t[1] += 1
        if area == "VOCABULARY":
            w = words[r["token"]]
            w[0] += r["outcome"] == "HIT"
            w[1] += 1

    def weakest(table, label):
        ranked = sorted(((v[0] / v[1], -v[1], k) for k, v in table.items() if v[1] >= 2 and v[0] < v[1]))
        return [{"label": label(k), "correct": table[k][0], "total": table[k][1]} for _, _, k in ranked[:3]]

    areas = []
    for key, label in AREAS:
        s = _summary(key, label, by_area[key])
        s["weakest"] = weakest(tenses, lambda k: TENSES[k]["label"]) if key == "GRAMMAR" else weakest(words, str)
        areas.append(s)
    return {"skills": [_summary(k, label, by_modality[k]) for k, label in SKILLS], "areas": areas,
            "min_answers": MIN_ANSWERS}
