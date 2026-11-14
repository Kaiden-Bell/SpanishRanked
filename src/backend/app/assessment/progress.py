"""What one graded quiz changed: XP toward the next rank, the skills it touched, a rank won.

Derived from the XP ledger, the evidence and the boss passes, never stored, so reopening an old quiz
shows what that quiz did then, not today's totals.
"""

import sqlite3

from .. import rules, themes
from ..practice import boss, skills


def _area(skill: str) -> str | None:
    if skill == "GRAMMAR":
        return "GRAMMAR"
    return "VOCABULARY" if skill in ("VOCABULARY", "COMPREHENSION") else None


def _held_before(conn: sqlite3.Connection, user_id: int, assessment_id: int, graded_at: str) -> tuple[int, str | None]:
    """(held rank index just before this quiz, rank this quiz's boss battle won or None)."""
    rows = conn.execute(
        "SELECT p.rank_name, p.passed_at, a.assessment_id FROM boss_passes p"
        " LEFT JOIN boss_attempts a ON a.id = p.attempt_id WHERE p.user_id = ?",
        (user_id,),
    ).fetchall()
    won = next((r["rank_name"] for r in rows if r["assessment_id"] == assessment_id), None)
    passed = {r["rank_name"] for r in rows if r["assessment_id"] != assessment_id and r["passed_at"] <= graded_at}
    return boss.held_index_from(passed), won


def quiz_progress(conn: sqlite3.Connection, user_id: int, assessment_id: int, source: str, graded_at: str) -> dict | None:
    event = conn.execute(
        "SELECT id, awarded_xp FROM xp_events WHERE user_id = ? AND source_type = ? AND source_id = ?",
        (user_id, source, assessment_id),
    ).fetchone()
    if event is None:
        return None
    before = conn.execute("SELECT COALESCE(SUM(awarded_xp), 0) FROM xp_events WHERE user_id = ? AND id < ?",
                          (user_id, event["id"])).fetchone()[0]
    after = before + event["awarded_xp"]

    held, won = _held_before(conn, user_id, assessment_id, graded_at)
    band_min, rank_name = rules.RANKS[held]
    following = rules.RANKS[held + 1] if held + 1 < len(rules.RANKS) else None
    rank_up = None
    if won:
        new_index = next(i for i, (_, name) in enumerate(rules.RANKS) if name == won)
        theme = themes.for_rank(new_index)
        rank_up = {"rank": won, "theme": {"id": theme.id, "label": theme.label} if theme else None}
    xp = {
        "before": before, "after": after, "gained": event["awarded_xp"],
        "rank": rank_name, "band_min": band_min,
        "band_max": following[0] if following else None,
        "next_rank": following[1] if following else None,
        # The XP for the next rank is there; its boss battle is what's left.
        "boss_ready": bool(following and not won and before < following[0] <= after),
    }

    ev = conn.execute(
        "SELECT MIN(ce.id), MAX(ce.id) FROM concept_evidence ce JOIN assessment_items i ON i.id = ce.assessment_item_id"
        " WHERE i.assessment_id = ?", (assessment_id,)).fetchone()
    touched_skills, touched_areas = set(), set()
    for r in conn.execute("SELECT modality, skill FROM assessment_items WHERE assessment_id = ?", (assessment_id,)):
        touched_skills.add(r["modality"])
        if _area(r["skill"]):
            touched_areas.add(_area(r["skill"]))
    changes = []
    if ev[0] is not None:
        then = skills.profile(conn, user_id, before_evidence_id=ev[0])
        now = skills.profile(conn, user_id, before_evidence_id=ev[1] + 1)
        for group, touched in (("skills", touched_skills), ("areas", touched_areas)):
            old = {s["key"]: s for s in then[group]}
            for s in now[group]:
                if s["key"] not in touched:
                    continue
                o = old[s["key"]]
                changes.append({
                    "key": s["key"], "label": s["label"], "kind": "SKILL" if group == "skills" else "AREA",
                    "before": {k: o[k] for k in ("status", "score", "answers_needed")},
                    "after": {k: s[k] for k in ("status", "score", "answers_needed")},
                })
    return {"xp": xp, "skills": changes, "rank_up": rank_up}
