from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app import db, progression as pg
from app.progression import Award, award_xp, rank_for, session_base_xp, streak_multiplier, streak_state

UTC = ZoneInfo("UTC")
TOKYO = ZoneInfo("Asia/Tokyo")


def at(day, hour=12, minute=0):
    return datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc) + timedelta(days=day)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "t.db")
    db.migrate(connection)
    connection.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'owner', 'x')")
    connection.commit()
    yield connection
    connection.close()


_next_id = iter(range(1, 10_000))


def award(conn, base, when, source="STUDY_SESSION", tz=UTC, source_id=None):
    with conn:
        return award_xp(conn, 1, source, source_id or next(_next_id), base, when, tz)


# ---- the numbers you specified ----------------------------------------------------------------

@pytest.mark.parametrize(
    "minutes, expected",
    [(1, 15), (2, 16), (3, 16), (30, 30), (59, 44), (60, 45), (61, 45), (600, 45)],
)
def test_session_xp_is_15_plus_one_per_two_minutes_capped_at_45(minutes, expected):
    assert session_base_xp(minutes) == expected


@pytest.mark.parametrize(
    "days, expected",
    [(0, 1.0), (1, 1.0), (2, 1.0), (3, 1.05), (6, 1.05), (7, 1.10), (13, 1.10),
     (14, 1.15), (29, 1.15), (30, 1.20), (365, 1.20)],
)
def test_streak_multiplier_tiers(days, expected):
    assert streak_multiplier(days) == expected


@pytest.mark.parametrize(
    "xp, rank, next_rank",
    [(0, "Pre-Learner I", "Pre-Learner II"), (119, "Pre-Learner I", "Pre-Learner II"),
     (120, "Pre-Learner II", "Pre-Learner III"), (299, "Pre-Learner II", "Pre-Learner III"),
     (300, "Pre-Learner III", "Learner I"), (549, "Pre-Learner III", "Learner I"),
     (550, "Learner I", "Learner II"), (899, "Learner I", "Learner II"),
     (900, "Learner II", "Learner III"), (1299, "Learner II", "Learner III"),
     (1300, "Learner III", None), (99_999, "Learner III", None)],
)
def test_rank_thresholds(xp, rank, next_rank):
    current, following = rank_for(xp)
    assert current[1] == rank
    assert (following[1] if following else None) == next_rank


def test_thirty_minute_session_earns_30_xp_before_any_streak_bonus(conn):
    result = award(conn, session_base_xp(30), at(0))
    assert (result.base_xp, result.multiplier, result.awarded_xp, result.capped) == (30, 1.0, 30, False)


# ---- ledger rules -----------------------------------------------------------------------------

def test_same_source_cannot_be_paid_twice(conn):
    first = award(conn, 30, at(0), source_id=7)
    again = award(conn, 30, at(0, 13), source_id=7)
    assert again.already_awarded and again.awarded_xp == first.awarded_xp
    assert pg.total_xp(conn, 1) == 30


def test_study_xp_is_capped_at_100_per_day_but_the_session_is_still_recorded(conn):
    amounts = [award(conn, 30, at(0, hour)).awarded_xp for hour in (8, 9, 10, 11, 12)]
    assert amounts == [30, 30, 30, 10, 0]
    assert pg.total_xp(conn, 1) == 100
    assert conn.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == 5
    assert award(conn, 30, at(0, 13)).capped is True


def test_the_cap_resets_the_next_day(conn):
    for hour in (8, 9, 10, 11):
        award(conn, 30, at(0, hour))
    assert award(conn, 30, at(1)).awarded_xp == 30


def test_quiz_cap_is_30_and_separate_from_the_study_cap(conn):
    for hour in (8, 9, 10):
        award(conn, 30, at(0, hour))  # 90 study XP
    quiz = [award(conn, 18, at(0, hour), source="ASSESSMENT").awarded_xp for hour in (13, 14)]
    assert quiz == [18, 12]
    assert award(conn, 15, at(0, 15)).awarded_xp == 10  # study cap unaffected by quiz XP


def test_the_cap_applies_after_the_streak_bonus(conn):
    for day in range(7):  # reach the 1.10x tier
        award(conn, 15, at(day))
    amounts = [award(conn, 45, at(7, hour)).awarded_xp for hour in (8, 9, 10)]
    assert amounts == [50, 50, 0]  # 45 * 1.10 = 49.5 -> 50 each, then capped at 100


def test_a_capped_session_still_extends_the_streak(conn):
    for hour in (8, 9, 10, 11):
        award(conn, 30, at(0, hour))
    award(conn, 30, at(1, 8))
    award(conn, 30, at(1, 9))
    award(conn, 30, at(1, 10))
    award(conn, 30, at(1, 11))
    award(conn, 30, at(2, 8))
    assert streak_state(pg.active_days(conn, 1), date(2026, 1, 3)).current == 3


# ---- streaks ----------------------------------------------------------------------------------

def test_multiplier_follows_consecutive_days_including_the_rewarded_action(conn):
    seen = [(day + 1, award(conn, 30, at(day)).multiplier) for day in range(8)]
    assert dict(seen) == {1: 1.0, 2: 1.0, 3: 1.05, 4: 1.05, 5: 1.05, 6: 1.05, 7: 1.10, 8: 1.10}


def test_rounding_is_half_up(conn):
    award(conn, 30, at(0)); award(conn, 30, at(1))
    assert award(conn, 30, at(2)).awarded_xp == 32  # 31.5 -> 32
    assert pg._scale(15, 1.05) == 16  # 15.75


def test_a_second_action_on_the_same_day_does_not_extend_the_streak(conn):
    award(conn, 20, at(0, 8)); award(conn, 20, at(1, 8))
    same_day = award(conn, 20, at(1, 20))
    assert same_day.multiplier == 1.0  # still day 2
    assert streak_state(pg.active_days(conn, 1), date(2026, 1, 2)).current == 2


def test_a_missed_day_ends_the_streak_but_keeps_earned_xp(conn):
    for day in range(3):
        award(conn, 30, at(day))
    before = pg.total_xp(conn, 1)
    after_gap = award(conn, 30, at(5))  # skipped days 4 and 5
    assert after_gap.multiplier == 1.0
    assert pg.total_xp(conn, 1) == before + 30


def test_streak_state_cases():
    d = lambda n: date(2026, 1, n)
    assert streak_state(set(), d(10)) == pg.StreakState(0, False, 1)
    assert streak_state({d(10)}, d(10)) == pg.StreakState(1, True, 1)
    assert streak_state({d(8), d(9)}, d(10)) == pg.StreakState(2, False, 3)  # alive until today ends
    assert streak_state({d(7), d(8)}, d(10)) == pg.StreakState(0, False, 1)  # yesterday missed
    assert streak_state({d(7), d(9), d(10)}, d(10)) == pg.StreakState(2, True, 2)  # gap breaks the run


def test_days_are_decided_by_the_configured_timezone(conn):
    # 23:30 and 00:30 UTC: one hour apart, but the same day in Tokyo and different days in UTC.
    award(conn, 30, at(0, 23, 30), tz=TOKYO)
    award(conn, 30, at(1, 0, 30), tz=TOKYO)
    dates = [r[0] for r in conn.execute("SELECT local_date FROM xp_events ORDER BY id")]
    assert dates == ["2026-01-02", "2026-01-02"]
    other = award(conn, 30, at(0, 23, 30), tz=UTC, source_id=999)
    assert conn.execute("SELECT local_date FROM xp_events WHERE source_id = 999").fetchone()[0] == "2026-01-01"
    assert other.awarded_xp == 30


def test_local_date_is_stored_so_a_timezone_change_cannot_rewrite_history(conn):
    award(conn, 30, at(0, 23, 30), tz=TOKYO)
    assert pg.active_days(conn, 1) == {date(2026, 1, 2)}
    assert pg.progress(conn, 1, at(0, 23, 45), UTC)["total_xp"] == 30


# ---- backfill ---------------------------------------------------------------------------------

def test_sessions_saved_before_xp_existed_are_awarded_once_in_order(conn):
    for n, minutes in enumerate((30, 60, 10)):
        stamp = db.utc_timestamp(at(n))
        conn.execute(
            "INSERT INTO study_sessions (user_id, language_code, mode, activity_type, duration_minutes,"
            " context_text, created_at, completed_at) VALUES (1, 'es', 'SELF_STUDY', 'READING', ?, 'x', ?, ?)",
            (minutes, stamp, stamp),
        )
    conn.commit()
    assert pg.award_missing_sessions(conn, UTC) == 3
    rows = [tuple(r) for r in conn.execute("SELECT awarded_xp, multiplier FROM xp_events ORDER BY source_id")]
    assert rows == [(30, 1.0), (45, 1.0), (21, 1.05)]  # 10 min = 20 base, day 3 streak: 20 * 1.05
    assert pg.award_missing_sessions(conn, UTC) == 0  # idempotent
    assert conn.execute("SELECT COUNT(*) FROM xp_events").fetchone()[0] == 3
