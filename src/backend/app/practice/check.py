"""Deterministic answer checking. Instant, and needs no model.

Outcomes use the grading vocabulary: HIT (correct), PARTIAL (right word, wrong accents), MISS.
"""

import re
import unicodedata

_PUNCT = re.compile(r"[¿?¡!.,;:\"'«»()\-–—…]")


def normalize(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", unicodedata.normalize("NFC", text).casefold()).split())


def plain(text: str) -> str:
    """Without accents. ñ counts as an accent here: 'extranan' for 'extrañan' is a spelling slip."""
    return "".join(ch for ch in unicodedata.normalize("NFD", normalize(text)) if unicodedata.category(ch) != "Mn")


def typed(answer: str, accepted: list[str]) -> tuple[str, str | None]:
    """(outcome, note). Exact match ignoring case and punctuation is a HIT; accents-only is PARTIAL."""
    given = normalize(answer)
    if any(given == normalize(a) for a in accepted):
        return "HIT", None
    if given and any(plain(answer) == plain(a) for a in accepted):
        return "PARTIAL", "accents"
    return "MISS", None


def choice(answer: str, correct: list[str]) -> str:
    return "HIT" if normalize(answer) in {normalize(c) for c in correct} else "MISS"


def order(answer: str, expected: str) -> tuple[str, str | None]:
    if normalize(answer) == normalize(expected):
        return "HIT", None
    return "MISS", None


def _lcs(a: list[str], b: list[str]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def dictation(answer: str, expected: str) -> tuple[str, str | None]:
    """Word-level match. Accents are forgiven in dictation (you can't hear a missing tilde on 'tu')."""
    want, got = plain(expected).split(), plain(answer).split()
    if not want:
        return "MISS", None
    score = _lcs(want, got) / max(len(want), len(got))
    if score >= 0.999:
        return ("HIT", None) if normalize(answer) == normalize(expected) else ("HIT", "accents")
    if score >= 0.6:
        return "PARTIAL", f"{round(score * 100)}% of the words"
    return "MISS", None
