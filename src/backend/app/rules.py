"""Progression constants (MVP_DESIGN.md §7). Provisional balancing values, not validated with learners.

XP amounts live here, never in model output.
"""

# Completed study session: base + 1 XP per SESSION_MINUTES_PER_BONUS_XP minutes, total capped.
SESSION_BASE_XP = 15
SESSION_MINUTES_PER_BONUS_XP = 2
SESSION_XP_CAP = 45

# Used by the assessment milestone: XP per correct answer, none for incorrect.
QUIZ_XP_PER_CORRECT = 3

# Most XP that can be awarded per local calendar day, per source (after the streak multiplier).
DAILY_XP_CAP = {"STUDY_SESSION": 100, "ASSESSMENT": 30}

# (minimum total XP, name), ascending.
RANKS = [
    (0, "Pre-Learner I"),
    (120, "Pre-Learner II"),
    (300, "Pre-Learner III"),
    (550, "Learner I"),
    (900, "Learner II"),
    (1300, "Learner III"),
]

# (minimum consecutive days including the action being rewarded, multiplier), descending.
STREAK_MULTIPLIERS = [(30, 1.20), (14, 1.15), (7, 1.10), (3, 1.05), (1, 1.00)]
