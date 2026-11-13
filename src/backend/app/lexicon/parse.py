"""Read what the learner actually typed into a term box before analysing it.

People write terms the way they write notes:

    phrase: pero queriendo volver a la última vez - but, wanting to go back to the last time
    extrañan = they miss
    te extraño (I miss you)

The Spanish is the term; a label ("phrase:") is dropped; the English after a separator is the
learner's own meaning for it. English words are never turned into Spanish word-bank entries.
"""

import re
from dataclasses import dataclass, field

from .analyze import normalize, tokens
from .english import SPANISH_MARKS, is_english_word
from .grammar_terms import FUNCTION_WORDS
from .verbs import VerbData

_LABEL = re.compile(
    r"^\s*(?:phrase|word|words|verb|noun|adj(?:ective)?|expression|idiom|slang|term|frase|palabra|verbo|expresi[oó]n)"
    r"\s*[:\-–—]\s*",
    re.IGNORECASE,
)
# The first of these splits "Spanish <sep> English". A plain hyphen only counts with spaces around it,
# so "¿qué-tal?" style hyphenation is left alone.
_SEPARATORS = re.compile(r"\s+[-–—=|]\s+|\s*[=|→]\s*|\s+[–—]\s*|\s*[–—]\s+|:\s+")
_TRAILING_PAREN = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")

@dataclass
class ParsedTerm:
    spanish: str  # the term to learn ("" when there was nothing Spanish in it)
    meaning: str | None  # the learner's own English meaning, if they wrote one
    kind_hint: str | None  # 'PHRASE' / 'WORD' from a label like "phrase:"
    english: list[str] = field(default_factory=list)  # English-only words found in the Spanish part

    @property
    def is_english(self) -> bool:
        return not self.spanish


def _score(text: str, verbs: VerbData) -> int:
    """Positive when the text reads as Spanish, negative when it reads as English."""
    score = 0
    for w in tokens(text):
        if SPANISH_MARKS.search(w) or w in FUNCTION_WORDS or verbs.matches(w):
            score += 1
        elif is_english_word(w, verbs):
            score -= 1
    return score


def parse_term(text: str, verbs: VerbData) -> ParsedTerm:
    raw = " ".join(text.split())
    kind_hint = None
    label = _LABEL.match(raw)
    if label:
        word = label.group(0).strip(" :-–—").casefold()
        kind_hint = "PHRASE" if word in ("phrase", "expression", "idiom", "frase", "expresión", "expresion") else "WORD"
        raw = raw[label.end():]

    parts = [p.strip() for p in _SEPARATORS.split(raw, maxsplit=1) if p.strip()]
    if len(parts) == 1:
        paren = _TRAILING_PAREN.match(raw)
        if paren and _score(paren.group(2), verbs) < 0 <= _score(paren.group(1), verbs):
            parts = [paren.group(1), paren.group(2)]

    if len(parts) == 2:
        a, b = parts
        spanish, meaning = (a, b) if _score(a, verbs) >= _score(b, verbs) else (b, a)
    else:
        spanish, meaning = raw, None

    english = [w for w in tokens(spanish) if is_english_word(w, verbs)]
    if tokens(spanish) and len(english) == len(tokens(spanish)):
        # Nothing Spanish here at all ("the", "miss you"): keep it as the meaning, learn nothing from it.
        return ParsedTerm("", meaning or spanish, kind_hint, english)
    return ParsedTerm(spanish.strip(" ,;"), meaning.strip(" ,;") if meaning else None, kind_hint, english)


def term_key(parsed: ParsedTerm) -> str:
    return normalize(parsed.spanish)
