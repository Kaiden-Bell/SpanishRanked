"""Which entries a quiz practises, and when each comes back (Leitner boxes).

Material comes from the whole bank, not just the latest session: words that are due (oldest first),
words answered wrongly, and fresh words from recent sessions, so old material keeps returning.
"""

import random
import sqlite3
from datetime import datetime, timedelta

from .. import db
from .context import EntryCtx

# Days until the next review, by box. A miss sends the entry back to box 1, due again right away.
INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 32}
MAX_BOX = 6


def pick(entries: list[EntryCtx], now: datetime, n: int, rng: random.Random, *, recent_first: int = 2) -> list[EntryCtx]:
    """Up to n entries, most useful first. Never repeats an entry. Function words are context, not targets."""
    stamp = db.utc_timestamp(now)
    usable = [e for e in entries if not e.is_function_word]
    due = sorted((e for e in usable if e.due_at is None or e.due_at <= stamp), key=lambda e: e.due_at or "")
    weak = [e for e in due if e.last_outcome in ("MISS", "PARTIAL")]
    fresh = sorted((e for e in usable if e.tested == 0), key=lambda e: e.last_seen_at or e.created_at, reverse=True)

    chosen: list[EntryCtx] = []

    def take(group, limit):
        for e in group:
            if len(chosen) >= n or limit <= 0:
                return
            if e not in chosen:
                chosen.append(e)
                limit -= 1

    take(weak, max(1, n // 2))
    take(fresh, recent_first)
    take(due, n)
    # Nothing left due: extra practice on anything, least practised first.
    take(sorted(usable, key=lambda e: (e.box, rng.random())), n)
    return chosen


def schedule(conn: sqlite3.Connection, entry_id: int, outcome: str, now: datetime) -> None:
    """Move an entry between boxes after an answer. Call inside the grading transaction."""
    row = conn.execute("SELECT box FROM bank_entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        return
    box = row["box"]
    if outcome == "HIT":
        box = min(MAX_BOX, box + 1)
        due = now + timedelta(days=INTERVAL_DAYS[box])
    elif outcome == "PARTIAL":
        box = max(1, box)
        due = now + timedelta(days=1)
    else:
        box = 1
        due = now  # straight back into the next warm-up or quiz
    column = {"HIT": "hits", "PARTIAL": "partials", "MISS": "misses"}[outcome]
    conn.execute(
        f"UPDATE bank_entries SET box = ?, due_at = ?, last_tested_at = ?, last_outcome = ?, {column} = {column} + 1"
        " WHERE id = ?",
        (box, db.utc_timestamp(due), db.utc_timestamp(now), outcome, entry_id),
    )
