"""Boss battles (docs/ROADMAP.md Phase 5): one per rank, gating the rank-up.

Reaching a rank's XP unlocks its boss. The battle has a stage per skill (listening, reading, grammar,
writing), each built from different words in the learner's bank. Passing every stage, and the whole,
grants the rank. Failing starts a short cooldown and puts every missed word back in the review queue.
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone

from .. import db, rules
from ..lexicon.verbs import VerbData
from .compose import NeedsModel, NotEnoughMaterial, choose_items, save
from .context import load_entries

VALUE = {"HIT": 1.0, "PARTIAL": 0.5, "MISS": 0.0}

# The writing stage is a small real-life task, not "use X in a sentence".
SCENARIOS = [
    "You are texting a friend you haven't seen in a while.",
    "You are telling a coworker about your weekend.",
    "You are leaving a voice note for your family about your plans.",
    "You are writing a short message to a new neighbour.",
    "You are describing your day to a language partner.",
]


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def held_rank_index(conn: sqlite3.Connection, user_id: int, total_xp: int) -> int:
    """The highest rank whose boss is passed, climbing in order. A rank once won is kept even if XP later
    drops below its threshold (a deleted study session takes its XP back, not the battle)."""
    passed = {r[0] for r in conn.execute("SELECT rank_name FROM boss_passes WHERE user_id = ?", (user_id,))}
    index = 0
    while index + 1 < len(rules.RANKS) and rules.RANKS[index + 1][1] in passed:
        index += 1
    return index


def state(conn: sqlite3.Connection, user_id: int, total_xp: int, now: datetime) -> dict:
    held = held_rank_index(conn, user_id, total_xp)
    nxt = rules.RANKS[held + 1] if held + 1 < len(rules.RANKS) else None
    out = {"held_index": held, "rank": None, "status": "NONE", "cooldown_until": None,
           "attempt_id": None, "assessment_id": None, "words_needed": 0, "last_result": None}
    if nxt is None or total_xp < nxt[0]:
        return out
    out["rank"] = nxt[1]
    attempt = conn.execute(
        "SELECT * FROM boss_attempts WHERE user_id = ? AND rank_name = ? ORDER BY id DESC LIMIT 1", (user_id, nxt[1])
    ).fetchone()
    if attempt and attempt["stage_results_json"]:
        out["last_result"] = {"status": attempt["status"], **json.loads(attempt["stage_results_json"])}
    if attempt and attempt["status"] == "IN_PROGRESS":
        out.update(status="IN_PROGRESS", attempt_id=attempt["id"], assessment_id=attempt["assessment_id"])
        return out
    if attempt and attempt["cooldown_until"] and _ts(attempt["cooldown_until"]) > now:
        out.update(status="COOLDOWN", cooldown_until=attempt["cooldown_until"])
        return out
    words, verbs = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN l.pos = 'VERB' THEN 1 ELSE 0 END) FROM bank_entries e"
        " LEFT JOIN lexemes l ON l.id = e.lexeme_id WHERE e.user_id = ? AND COALESCE(l.pos, '') != 'FUNCTION'",
        (user_id,),
    ).fetchone()
    need = max(rules.BOSS_MIN_ENTRIES - (words or 0), rules.BOSS_MIN_VERBS - (verbs or 0), 0)
    out.update(status="NEEDS_WORDS" if need else "READY", words_needed=need)
    return out


def start(conn: sqlite3.Connection, verbs: VerbData, user_id: int, total_xp: int, *, listening: bool,
          model_ok: bool, now: datetime | None = None, rng: random.Random | None = None) -> int:
    """Begin (or resume) the boss battle for the next rank. Returns the attempt id."""
    now = now or datetime.now(timezone.utc)
    rng = rng or random.Random()
    st = state(conn, user_id, total_xp, now)
    if st["status"] == "IN_PROGRESS":
        return st["attempt_id"]
    if st["status"] != "READY":
        raise NotEnoughMaterial({
            "NONE": "No boss battle is open: reach the next rank's XP first.",
            "COOLDOWN": "The boss is resting. Practise your missed words and try again later.",
            "NEEDS_WORDS": f"Log {st['words_needed']} more words before this boss battle.",
        }[st["status"]])
    if not model_ok:
        raise NeedsModel("Boss battles need the local model for their writing stage, which is unavailable right now.")

    entries = load_entries(conn, verbs, user_id)
    remaining = list(entries)
    items, stages, skipped = [], [], []
    for key, label, types, count in rules.BOSS_STAGES:
        if key == "LISTENING" and not listening:
            skipped.append({"key": key, "label": label, "reason": "no Spanish voice on this device"})
            continue
        # Different words per stage where possible, so one known word can't carry the battle.
        built = choose_items(remaining, n=count, focus="MIXED", listening=listening, allow_write=True, now=now,
                             rng=rng, only=set(types))
        if len(built) < count:
            built = choose_items(entries, n=count, focus="MIXED", listening=listening, allow_write=True, now=now,
                                 rng=rng, only=set(types))
        if not built:
            skipped.append({"key": key, "label": label, "reason": "not enough material yet"})
            continue
        for item in built:
            if item.item_type == "WRITE":
                item.prompt = f"{rng.choice(SCENARIOS)} {item.prompt.replace('Write one Spanish sentence', 'Write one or two Spanish sentences')}"
        used = {i.entry.id for i in built}
        remaining = [e for e in remaining if e.id not in used]
        items += built
        stages += [key] * len(built)
    if len(set(stages)) < 2:
        raise NotEnoughMaterial("Not enough variety in your word bank for a boss battle yet. Keep logging words.")

    with conn:
        attempt_id = conn.execute(
            "INSERT INTO boss_attempts (user_id, rank_name, status, stage_results_json, started_at)"
            " VALUES (?, ?, 'IN_PROGRESS', ?, ?)",
            (user_id, st["rank"], json.dumps({"skipped": skipped}), db.utc_timestamp(now)),
        ).lastrowid
    assessment_id = save(conn, user_id, items, kind="BOSS", focus="BOSS", boss_attempt_id=attempt_id, stages=stages)
    with conn:
        conn.execute("UPDATE boss_attempts SET assessment_id = ? WHERE id = ?", (assessment_id, attempt_id))
    return attempt_id


def resolve(conn: sqlite3.Connection, assessment_id: int, now: datetime) -> None:
    """Score each stage, decide pass or fail. Runs inside the grading transaction."""
    attempt = conn.execute("SELECT * FROM boss_attempts WHERE assessment_id = ?", (assessment_id,)).fetchone()
    if attempt is None or attempt["status"] != "IN_PROGRESS":
        return
    labels = {key: label for key, label, _, _ in rules.BOSS_STAGES}
    per_stage: dict[str, list[float]] = {}
    missed: list[int] = []
    for item in conn.execute(
        "SELECT stage, feedback_json, bank_entry_id FROM assessment_items WHERE assessment_id = ? ORDER BY id",
        (assessment_id,),
    ):
        outcomes = [e["outcome"] for e in json.loads(item["feedback_json"])["evidence"]]
        value = min(VALUE[o] for o in outcomes)
        per_stage.setdefault(item["stage"], []).append(value)
        if value < 1 and item["bank_entry_id"]:
            missed.append(item["bank_entry_id"])
    stages = []
    for key, values in per_stage.items():
        score = sum(values) / len(values)
        stages.append({"key": key, "label": labels.get(key, key), "score": round(score, 3),
                       "correct": sum(v == 1 for v in values), "total": len(values),
                       "passed": score >= rules.BOSS_STAGE_PASS})
    all_values = [v for values in per_stage.values() for v in values]
    overall = sum(all_values) / len(all_values) if all_values else 0
    passed = all(s["passed"] for s in stages) and overall >= rules.BOSS_OVERALL_PASS
    previous = json.loads(attempt["stage_results_json"] or "{}")
    result = {"stages": stages, "overall": round(overall, 3), "skipped": previous.get("skipped", []),
              "stage_pass": rules.BOSS_STAGE_PASS, "overall_pass": rules.BOSS_OVERALL_PASS}
    cooldown = None if passed else db.utc_timestamp(now + timedelta(hours=rules.BOSS_COOLDOWN_HOURS))
    conn.execute(
        "UPDATE boss_attempts SET status = ?, stage_results_json = ?, finished_at = ?, cooldown_until = ? WHERE id = ?",
        ("PASSED" if passed else "FAILED", json.dumps(result), db.utc_timestamp(now), cooldown, attempt["id"]),
    )
    if passed:
        conn.execute("INSERT OR IGNORE INTO boss_passes (user_id, rank_name, attempt_id) VALUES (?, ?, ?)",
                     (attempt["user_id"], attempt["rank_name"], attempt["id"]))
    else:
        # Remediation: everything missed is due now, so warm-ups and quizzes go straight back to it.
        for entry_id in missed:
            conn.execute("UPDATE bank_entries SET due_at = ? WHERE id = ?", (db.utc_timestamp(now), entry_id))
