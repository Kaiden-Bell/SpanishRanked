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
DAILY_XP_CAP = {"STUDY_SESSION": 100, "ASSESSMENT": 30, "WARMUP": 15, "BOSS": 60}

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

# Questions in one mixed quiz (docs/ROADMAP.md Phase 2). At most one is a free sentence graded by the
# model; the rest are built and checked by code.
QUIZ_ITEMS = 5
# Sentence practice: every question is a free sentence, graded by the model (the Level 1 quiz).
SENTENCE_QUIZ_ITEMS = 3

# Daily warm-up (Phase 3). Provisional. Only the first warm-up of a local day pays; later ones are
# practice and still count toward the streak.
WARMUP_ITEMS = 5
WARMUP_COMPLETION_XP = 5
WARMUP_XP_PER_CORRECT = 2


def warmup_base_xp(correct: int, first_today: bool) -> int:
    return WARMUP_COMPLETION_XP + correct * WARMUP_XP_PER_CORRECT if first_today else 0


# Boss battles (Phase 5). Provisional. Reaching a rank's XP unlocks its boss; passing it grants the rank.
BOSS_XP_PER_CORRECT = 4
# (stage, label, question types, items). Each stage tests a different skill.
BOSS_STAGES = [
    ("LISTENING", "Listening", ("LISTEN_PICK", "DICTATION"), 3),
    ("READING", "Reading", ("SENTENCE_MEANING", "TRANSLATION_TF", "MEANING_MC", "REVERSE_MC"), 3),
    ("GRAMMAR", "Grammar", ("FORM_ID", "CONJUGATE", "CLOZE", "SCRAMBLE"), 3),
    ("WRITING", "Writing", ("WRITE",), 1),
]
BOSS_STAGE_PASS = 0.6  # every stage needs at least this share (HIT 1, PARTIAL 0.5)
BOSS_OVERALL_PASS = 0.7
BOSS_COOLDOWN_HOURS = 6
BOSS_MIN_ENTRIES = 8  # words in the bank before a boss can be built
BOSS_MIN_VERBS = 2
