"""XP ledger, ranks and streaks (MVP_DESIGN.md §7).

The backend alone decides these. Every award is an append-only row in ``xp_events`` written in the
same transaction as the action that earned it; totals are always derived from that ledger.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from . import db, rules


@dataclass(frozen=True)
class Award:
    base_xp: int
    multiplier: float
    awarded_xp: int
    capped: bool  # the daily cap reduced this award
    already_awarded: bool = False


@dataclass(frozen=True)
class StreakState:
    current: int  # consecutive days ending today (or yesterday, if today has no action yet)
    active_today: bool
    next_length: int  # streak length the next rewarded action counts as


def session_base_xp(duration_minutes: int) -> int:
    bonus = duration_minutes // rules.SESSION_MINUTES_PER_BONUS_XP
    return min(rules.SESSION_XP_CAP, rules.SESSION_BASE_XP + bonus)


def streak_multiplier(length: int) -> float:
    for minimum, multiplier in rules.STREAK_MULTIPLIERS:
        if length >= minimum:
            return multiplier
    return 1.0


def _scale(base_xp: int, multiplier: float) -> int:
    """base * multiplier rounded half up, using decimal so 30 * 1.05 is exactly 31.5 -> 32."""
    return int((Decimal(base_xp) * Decimal(str(multiplier))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _run_ending(days: set[date], end: date) -> int:
    length = 0
    while end in days:
        length += 1
        end -= timedelta(days=1)
    return length


def streak_state(days: set[date], today: date) -> StreakState:
    """``days`` are the local dates with an eligible action. A missed day ends the streak."""
    if today in days:
        run = _run_ending(days, today)
        return StreakState(run, True, run)
    run = _run_ending(days, today - timedelta(days=1))
    return StreakState(run, False, run + 1)


def rank_for(total_xp: int) -> tuple[tuple[int, str], tuple[int, str] | None]:
    """Returns (current rank, next rank or None at the top); each is (min_xp, name)."""
    index = max(i for i, (minimum, _) in enumerate(rules.RANKS) if total_xp >= minimum)
    following = rules.RANKS[index + 1] if index + 1 < len(rules.RANKS) else None
    return rules.RANKS[index], following


def active_days(conn: sqlite3.Connection, user_id: int) -> set[date]:
    rows = conn.execute(
        "SELECT DISTINCT local_date FROM xp_events WHERE user_id = ? AND local_date != ''", (user_id,)
    )
    return {date.fromisoformat(r[0]) for r in rows}


def total_xp(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(awarded_xp), 0) FROM xp_events WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def xp_earned_on(conn: sqlite3.Connection, user_id: int, source_type: str, local_date: date) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(awarded_xp), 0) FROM xp_events"
        " WHERE user_id = ? AND source_type = ? AND local_date = ?",
        (user_id, source_type, local_date.isoformat()),
    ).fetchone()[0]


def existing_award(conn: sqlite3.Connection, user_id: int, source_type: str, source_id: int) -> Award | None:
    """The award already recorded for this action, if any."""
    row = conn.execute(
        "SELECT base_xp, multiplier, awarded_xp FROM xp_events WHERE user_id = ? AND source_type = ? AND source_id = ?",
        (user_id, source_type, source_id),
    ).fetchone()
    if row is None:
        return None
    raw = _scale(row["base_xp"], row["multiplier"])
    return Award(row["base_xp"], row["multiplier"], row["awarded_xp"], capped=row["awarded_xp"] < raw, already_awarded=True)


def award_xp(
    conn: sqlite3.Connection,
    user_id: int,
    source_type: str,
    source_id: int,
    base_xp: int,
    at: datetime,
    tz: ZoneInfo,
) -> Award:
    """Record the award for one completed action. Call inside the transaction that saved the action.

    Idempotent per (user, source_type, source_id): a repeat returns the original award and pays nothing.
    Even a fully capped action is recorded (with 0 XP) because it still counts toward the streak.
    """
    existing = existing_award(conn, user_id, source_type, source_id)
    if existing:
        return existing

    local_date = at.astimezone(tz).date()
    multiplier = streak_multiplier(streak_state(active_days(conn, user_id), local_date).next_length)
    raw = _scale(base_xp, multiplier)
    remaining = max(0, rules.DAILY_XP_CAP[source_type] - xp_earned_on(conn, user_id, source_type, local_date))
    awarded = min(raw, remaining)
    conn.execute(
        "INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp,"
        " local_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, source_type, source_id, base_xp, multiplier, awarded,
         local_date.isoformat(), db.utc_timestamp(at)),
    )
    return Award(base_xp, multiplier, awarded, capped=awarded < raw)


def award_missing_sessions(conn: sqlite3.Connection, tz: ZoneInfo) -> int:
    """Award study sessions saved before XP existed, oldest first so streaks build correctly.

    Safe to run on every start: sessions that already have an award are skipped.
    """
    rows = conn.execute(
        "SELECT s.id, s.user_id, s.duration_minutes, COALESCE(s.completed_at, s.created_at) AS at"
        " FROM study_sessions s WHERE NOT EXISTS (SELECT 1 FROM xp_events e WHERE e.user_id = s.user_id"
        " AND e.source_type = 'STUDY_SESSION' AND e.source_id = s.id) ORDER BY s.id"
    ).fetchall()
    for row in rows:
        at = datetime.strptime(row["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        with conn:
            award_xp(conn, row["user_id"], "STUDY_SESSION", row["id"], session_base_xp(row["duration_minutes"]), at, tz)
    return len(rows)


def progress(conn: sqlite3.Connection, user_id: int, now: datetime, tz: ZoneInfo) -> dict:
    today = now.astimezone(tz).date()
    total = total_xp(conn, user_id)
    (rank_min, rank_name), following = rank_for(total)
    streak = streak_state(active_days(conn, user_id), today)
    return {
        "total_xp": total,
        "rank": {"name": rank_name, "min_xp": rank_min},
        "next_rank": {"name": following[1], "min_xp": following[0]} if following else None,
        "xp_to_next": following[0] - total if following else None,
        "streak": {
            "current": streak.current,
            "active_today": streak.active_today,
            "next_multiplier": streak_multiplier(streak.next_length),
        },
        "today": {
            "date": today.isoformat(),
            "study_xp": xp_earned_on(conn, user_id, "STUDY_SESSION", today),
            "study_xp_cap": rules.DAILY_XP_CAP["STUDY_SESSION"],
        },
    }
