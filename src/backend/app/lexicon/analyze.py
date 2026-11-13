"""Local, deterministic analysis of a term the learner typed. No network, a few milliseconds.

    analyze("extrañan")          -> WORD, extrañar, present · ellos/ellas/ustedes
    analyze("te extrañan mucho") -> PHRASE with words te (function), extrañar (verb), mucho

Verbs are recognised from the generated verb tables (exact forms, including irregulars). Other words
keep their surface form as the lemma until the dictionary lookup refines it (maletas -> maleta).
"""

import re
import unicodedata
from dataclasses import dataclass, field

from .english import is_english_word
from .grammar_terms import CLITICS, FUNCTION_WORDS
from .verbs import FormMatch, VerbData

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# A verb reading is implausible straight after these ("el viaje", "mi casa"). La/lo/los/las are left
# out on purpose: they are also object pronouns ("la extraño" = I miss her).
_DETERMINERS = frozenset(
    "el un una unos unas mi mis tu tus su sus nuestro nuestra nuestros nuestras vuestro vuestra "
    "este esta estos estas ese esa esos esas aquel aquella aquellos aquellas del al".split()
)
_ACCENTED = str.maketrans("áéíóú", "aeiou")


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def tokens(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


@dataclass
class WordAnalysis:
    surface: str
    lemma: str
    pos: str | None  # 'VERB', 'FUNCTION', 'ENGLISH', or None until the dictionary says
    forms: list[FormMatch] = field(default_factory=list)
    clitics: list[str] = field(default_factory=list)  # pronouns attached to the verb (extrañarte -> te)
    alternatives: list[str] = field(default_factory=list)  # other infinitives the form could belong to

    @property
    def is_content(self) -> bool:
        return self.pos not in ("FUNCTION", "ENGLISH")

    def to_json(self) -> dict:
        return {
            "surface": self.surface, "lemma": self.lemma, "pos": self.pos,
            "forms": [{"tense": f.tense, "person": f.person} for f in self.forms],
            "clitics": self.clitics, "alternatives": self.alternatives,
        }


@dataclass
class TermAnalysis:
    text: str
    kind: str  # 'WORD' | 'PHRASE'
    words: list[WordAnalysis]

    @property
    def content_words(self) -> list[WordAnalysis]:
        return [w for w in self.words if w.is_content]

    @property
    def head(self) -> WordAnalysis | None:
        """The word a single-word term is about."""
        return self.words[0] if self.kind == "WORD" and self.words else None


def _strip_clitics(word: str, verbs: VerbData) -> tuple[list[FormMatch], list[str]]:
    """extrañarte -> extrañar + te; dímelo -> di + me, lo. Only infinitives, gerunds and commands take them."""
    for n in (2, 1):
        for combo in _clitic_suffixes(word, n):
            base = word[: -len("".join(combo))]
            if len(base) < 2:
                continue
            for candidate in dict.fromkeys((base, base.translate(_ACCENTED))):
                found = [m for m in verbs.matches(candidate) if m.tense in ("inf", "ger", "imp_aff")]
                if found:
                    return found, list(combo)
    return [], []


def _clitic_suffixes(word: str, n: int):
    if n == 1:
        for c in CLITICS:
            if word.endswith(c):
                yield (c,)
        return
    for second in CLITICS:
        if word.endswith(second):
            for first in CLITICS:
                if word[: -len(second)].endswith(first):
                    yield (first, second)


def _analyze_word(word: str, previous: str | None, in_phrase: bool, verbs: VerbData) -> WordAnalysis:
    if in_phrase and word in FUNCTION_WORDS:
        return WordAnalysis(word, word, "FUNCTION")
    if is_english_word(word, verbs):
        return WordAnalysis(word, word, "ENGLISH")  # kept as context, never a word to learn
    matches = [] if previous in _DETERMINERS else verbs.matches(word)
    clitics: list[str] = []
    if not matches and previous not in _DETERMINERS and len(word) > 4:
        matches, clitics = _strip_clitics(word, verbs)
    if not matches:
        return WordAnalysis(word, word, "FUNCTION" if word in FUNCTION_WORDS else None)
    infinitives = list(dict.fromkeys(m.infinitive for m in matches))
    lemma = infinitives[0]
    return WordAnalysis(
        surface=word, lemma=lemma, pos="VERB",
        forms=[m for m in matches if m.infinitive == lemma],
        clitics=clitics, alternatives=infinitives[1:],
    )


def analyze(text: str, verbs: VerbData) -> TermAnalysis:
    words = tokens(text)
    kind = "PHRASE" if len(words) > 1 else "WORD"
    out, previous = [], None
    for word in words:
        out.append(_analyze_word(word, previous, kind == "PHRASE", verbs))
        previous = word
    return TermAnalysis(normalize(text), kind, out)


def strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
