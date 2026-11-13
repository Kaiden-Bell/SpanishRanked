"""Checking one answered item without the model, and recording answers one at a time."""

import json
import sqlite3
from datetime import datetime

from .. import db
from . import check


def evaluate(item: sqlite3.Row, response: str) -> dict:
    """The same shape the model grader produces: {"feedback", "evidence"}, plus the answer to show."""
    key = json.loads(item["answer_json"])
    token = json.loads(item["expected_criteria_json"])["concepts"][0]["token"]
    kind, accept, display = key["check"], key["accept"], key["display"]
    note = None
    if kind == "choice":
        outcome = check.choice(response, accept)
    elif kind == "order":
        outcome, note = check.order(response, accept[0])
    elif kind == "dictation":
        outcome, note = check.dictation(response, accept[0])
    else:
        outcome, note = check.typed(response, accept)

    explain = key.get("explain")
    if outcome == "HIT":
        feedback = "Correct." if note != "accents" else f"Correct. Mind the accents: “{display}”."
    elif outcome == "PARTIAL" and note == "accents":
        feedback = f"Almost: only the accents are off. It is “{display}”."
    elif outcome == "PARTIAL":
        feedback = f"Close: you got {note}. It was “{display}”."
    elif item["item_type"] == "TRANSLATION_TF":
        feedback = f"It is {display.lower()}."
    else:
        feedback = f"The answer is “{display}”."
    if explain and (outcome != "HIT" or item["skill"] == "GRAMMAR"):
        feedback = f"{feedback} {explain}"
    return {
        "feedback": feedback,
        "evidence": [{"concept_token": token, "outcome": outcome,
                      "issue": "none" if outcome == "HIT" else (note or "wrong")}],
        "answer": display,
    }


class Closed(Exception):
    """The quiz no longer takes answers."""


def answer_item(conn: sqlite3.Connection, user_id: int, assessment_id: int, item_id: int, text: str,
                now: datetime, fingerprint) -> bool:
    """Save one answer (checking it at once unless the model grades it). Returns True when that was
    the last unanswered item, after moving the quiz to SUBMITTED."""
    row = conn.execute("SELECT status FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user_id)).fetchone()
    if row is None:
        raise LookupError("Quiz not found.")
    if row["status"] != "GENERATED":
        raise Closed("This quiz was already submitted.")
    item = conn.execute(
        "SELECT * FROM assessment_items WHERE id = ? AND assessment_id = ?", (item_id, assessment_id)
    ).fetchone()
    if item is None:
        raise LookupError("That question is not part of this quiz.")
    if item["response_text"] is not None:
        raise Closed("That question was already answered.")
    feedback = None if item["item_type"] == "WRITE" else evaluate(item, text)
    with conn:
        updated = conn.execute(
            "UPDATE assessment_items SET response_text = ?, answered_at = ?, feedback_json = ?"
            " WHERE id = ? AND response_text IS NULL",
            (text, db.utc_timestamp(now), json.dumps(feedback, ensure_ascii=False) if feedback else None, item_id),
        ).rowcount
        if updated != 1:
            raise Closed("That question was already answered.")
        items = conn.execute(
            "SELECT prompt, response_text FROM assessment_items WHERE assessment_id = ? ORDER BY id", (assessment_id,)
        ).fetchall()
        if any(i["response_text"] is None for i in items):
            return False
        conn.execute(
            "UPDATE assessments SET status = 'SUBMITTED', submitted_at = ?, fingerprint = ?"
            " WHERE id = ? AND status = 'GENERATED'",
            (db.utc_timestamp(now), fingerprint([(i["prompt"], i["response_text"]) for i in items]), assessment_id),
        )
    return True
