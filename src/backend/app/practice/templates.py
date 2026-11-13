"""Question templates. Each builder turns one word-bank entry into one question, or returns None when
the entry lacks what that question needs (no meaning, not a verb, no example sentence...).

Questions are built from verified data only: the verb tables, dictionary glosses, real example
sentences and the learner's own sentences. Nothing here calls the model. The answer key stays on
the server (answer_json) until the item is answered.
"""

import random
import re
from dataclasses import dataclass

from ..lexicon.analyze import tokens
from ..lexicon.grammar_terms import CORE_TENSES, DRILL_PERSONS, PERSONS, TENSES, describe_form
from ..lexicon.verbs import cells_for
from .check import normalize, plain
from .context import EntryCtx, Example, short_gloss

# Distractors when the learner's own bank is still small. Common words, glossed.
FALLBACK = [
    ("casa", "house", "Noun"), ("perro", "dog", "Noun"), ("agua", "water", "Noun"), ("libro", "book", "Noun"),
    ("ciudad", "city", "Noun"), ("trabajo", "work, job", "Noun"), ("amigo", "friend", "Noun"),
    ("tiempo", "time; weather", "Noun"), ("comer", "to eat", "Verb"), ("dormir", "to sleep", "Verb"),
    ("hablar", "to speak", "Verb"), ("vivir", "to live", "Verb"), ("salir", "to go out, to leave", "Verb"),
    ("buscar", "to look for", "Verb"), ("olvidar", "to forget", "Verb"), ("ganar", "to win, to earn", "Verb"),
    ("pequeño", "small", "Adjective"), ("feliz", "happy", "Adjective"), ("cansado", "tired", "Adjective"),
    ("siempre", "always", "Adverb"), ("nunca", "never", "Adverb"), ("lejos", "far away", "Adverb"),
]

OPTIONS = 4


@dataclass
class Item:
    item_type: str
    modality: str  # READING / WRITING / LISTENING
    skill: str  # VOCABULARY / GRAMMAR / COMPREHENSION / LISTENING / WRITING
    prompt: str
    payload: dict  # what the client needs to render the question; never the answer
    answer: dict  # server only: {"check", "accept", "display", "explain"}
    entry: EntryCtx


class Pool:
    """All entries plus fallbacks, for distractors."""

    def __init__(self, entries: list[EntryCtx]):
        self.entries = entries

    def glosses(self, exclude: EntryCtx, kind: str) -> list[str]:
        own = [short_gloss(e.translation) for e in self.entries
               if e.id != exclude.id and e.kind == kind and e.translation]
        fallback = [g for _, g, _ in FALLBACK] if kind == "WORD" else []
        return [g for g in own + fallback if g]

    def headwords(self, exclude: EntryCtx, kind: str = "WORD") -> list[str]:
        own = [e.headword for e in self.entries if e.id != exclude.id and e.kind == kind and not e.is_function_word]
        return own + ([w for w, _, _ in FALLBACK] if kind == "WORD" else [])

    def translations(self, exclude: Example) -> list[str]:
        out = []
        for e in self.entries:
            for x in e.examples:
                if x.en and x.es != exclude.es:
                    out.append(x.en)
        return out


def _options(correct: str, distractors: list[str], rng: random.Random, k: int = OPTIONS) -> list[str] | None:
    seen = {normalize(correct)}
    pool = []
    for d in rng.sample(distractors, len(distractors)):
        key = normalize(d)
        if key and key not in seen:
            seen.add(key)
            pool.append(d)
        if len(pool) == k - 1:
            break
    if len(pool) < 2:
        return None
    options = pool + [correct]
    rng.shuffle(options)
    return options


def _q(text: str) -> str:
    return f"“{text}”"


def _cell_label(tense: str, person: str) -> str:
    return f"{PERSONS[person]['who']} · {TENSES[tense]['label']}"


def _explain_form(entry: EntryCtx, form: str) -> str | None:
    cells = [c for c in cells_for(entry.table, entry.headword, form.casefold()) if c.person in PERSONS]
    if not cells:
        return None
    readings = ", ".join(dict.fromkeys(describe_form(c.tense, c.person)["summary"] for c in cells))
    return f"{form} = {readings} of {entry.headword}."


def _find(sentence: str, word: str) -> tuple[str, str, str] | None:
    """Split a sentence around the first whole-word match: (before, the word as written, after)."""
    m = re.search(rf"(?<!\w){re.escape(word)}(?!\w)", sentence, re.IGNORECASE)
    if not m:
        return None
    return sentence[: m.start()], m.group(0), sentence[m.end():]


# ---------------------------------------------------------------- vocabulary


def meaning_mc(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    gloss = short_gloss(e.translation, 80 if e.kind == "PHRASE" else 60)
    if not gloss or e.is_function_word:
        return None
    options = _options(gloss, pool.glosses(e, e.kind), rng)
    if not options:
        return None
    return Item("MEANING_MC", "READING", "VOCABULARY", f"What does {_q(e.headword)} mean?",
                {"input": "choice", "options": options, "spanish": e.headword},
                {"check": "choice", "accept": [gloss], "display": gloss,
                 "explain": f"{e.headword} means {_q(e.translation)}."}, e)


def reverse_mc(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    gloss = short_gloss(e.translation)
    if e.kind != "WORD" or not gloss or e.is_function_word:
        return None
    options = _options(e.headword, pool.headwords(e), rng)
    if not options:
        return None
    return Item("REVERSE_MC", "READING", "VOCABULARY", f"Which Spanish word means {_q(gloss)}?",
                {"input": "choice", "options": options, "options_lang": "es"},
                {"check": "choice", "accept": [e.headword], "display": e.headword,
                 "explain": f"{e.headword} means {_q(e.translation)}."}, e)


# ---------------------------------------------------------------- grammar


def _verb_target(e: EntryCtx, rng: random.Random) -> tuple[str, str, str] | None:
    """(form, tense, person) to ask about: a form the learner met if it is a plain finite form,
    otherwise a core-tense form from the table."""
    for form, analysis in rng.sample(e.forms, len(e.forms)):
        for f in analysis.get("forms", []):
            if f["tense"] in CORE_TENSES and f["person"] in DRILL_PERSONS and not analysis.get("clitics"):
                return form, f["tense"], f["person"]
    tense = rng.choice(["pres", "pret", "impf", "fut"])
    person = rng.choice(DRILL_PERSONS)
    cell = e.table["tenses"].get(tense, {}).get(person)
    return (cell[0], tense, person) if cell else None


def form_id(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    if not e.is_verb:
        return None
    target = _verb_target(e, rng)
    if not target:
        return None
    form, tense, person = target
    valid = {(c.tense, c.person) for c in cells_for(e.table, e.headword, form.casefold())}
    correct = _cell_label(tense, person)
    distractors = [_cell_label(tense, p) for p in DRILL_PERSONS if (tense, p) not in valid]
    distractors += [_cell_label(t, person) for t in CORE_TENSES[:5] if (t, person) not in valid]
    accept = [_cell_label(t, p) for t, p in valid if t in TENSES and p in PERSONS]
    options = _options(correct, distractors, rng)
    if not options:
        return None
    return Item("FORM_ID", "READING", "GRAMMAR",
                f"{_q(form)} is a form of {_q(e.headword)}. Who is doing it, and when?",
                {"input": "choice", "options": options, "spanish": form},
                {"check": "choice", "accept": accept, "display": correct, "explain": _explain_form(e, form),
                 "tense": tense}, e)


def conjugate(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    if not e.is_verb:
        return None
    seen = {(f["tense"], f["person"]) for _, a in e.forms for f in a.get("forms", [])}
    tenses = list(dict.fromkeys([t for t, _ in seen if t in CORE_TENSES] + ["pres", "pret"]))
    tense = rng.choice(tenses)
    people = [p for p in DRILL_PERSONS if (tense, p) not in seen] or list(DRILL_PERSONS)
    person = rng.choice(people)
    accept = e.table["tenses"].get(tense, {}).get(person)
    if not accept:
        return None
    gloss = short_gloss(e.translation)
    return Item("CONJUGATE", "WRITING", "GRAMMAR",
                f"Write {_q(e.headword)}{f' ({gloss})' if gloss else ''} for {PERSONS[person]['label']} "
                f"({PERSONS[person]['who']}), {TENSES[tense]['label']}.",
                {"input": "text", "hint": TENSES[tense]["when"]},
                {"check": "typed", "accept": accept, "display": accept[0], "tense": tense,
                 "explain": f"{e.headword} · {PERSONS[person]['label']} · {TENSES[tense]['label']}: {accept[0]}."}, e)


def cloze(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    if e.is_function_word:
        return None
    if e.kind == "PHRASE":
        content = [w for w in e.phrase_words if w.get("pos") != "FUNCTION"]
        if len(e.phrase_words) < 2 or not content:
            return None
        word = rng.choice(content)
        split = _find(e.headword, word["surface"])
        if not split:
            return None
        hint = word["lemma"] if word.get("pos") == "VERB" else None
        if not hint and not e.translation:
            return None
        before, answer, after = split
        readings = [describe_form(f["tense"], f["person"])["summary"] for f in word.get("forms", [])
                    if f.get("person") in PERSONS]
        explain = (f"{answer} = {', '.join(dict.fromkeys(readings))} of {word['lemma']}, in “{e.headword}”."
                   if readings else f"The phrase is “{e.headword}”.")
        return Item("CLOZE", "WRITING", "GRAMMAR" if hint else "VOCABULARY", "Fill in the missing word.",
                    {"input": "text", "cloze": {"before": before, "after": after}, "hint": hint,
                     "translation": e.translation},
                    {"check": "typed", "accept": [answer], "display": answer, "explain": explain}, e)

    forms = e.all_forms() if e.is_verb else {e.headword, f"{e.headword}s", f"{e.headword}es", *(f for f, _ in e.forms)}
    candidates = []
    for x in e.examples:
        for t in tokens(x.es):
            # For a verb the hint is the infinitive, so blanking the infinitive itself would give it away.
            if t in forms and (not e.is_verb or t != e.headword):
                candidates.append((x, t))
                break
    if not candidates:
        return None
    x, word = rng.choice(candidates)
    split = _find(x.es, word)
    if not split:
        return None
    before, answer, after = split
    tense = None
    if e.is_verb:
        hint, skill, explain = e.headword, "GRAMMAR", _explain_form(e, answer)
        cells = [c for c in cells_for(e.table, e.headword, answer.casefold()) if c.tense in TENSES]
        tense = cells[0].tense if cells else None
    else:
        hint, skill, explain = short_gloss(e.translation), "VOCABULARY", None
        if not hint:
            return None
    return Item("CLOZE", "WRITING", skill, "Fill in the missing word.",
                {"input": "text", "cloze": {"before": before, "after": after}, "hint": hint, "translation": x.en},
                {"check": "typed", "accept": [answer], "display": answer, "explain": explain or f"The sentence is “{x.es}”.",
                 "tense": tense}, e)


def scramble(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    if e.kind == "PHRASE":
        source, translation = e.headword, e.translation
    else:
        usable = [x for x in e.examples if 3 <= len(tokens(x.es)) <= 7]
        if not usable:
            return None
        x = rng.choice(usable)
        source, translation = x.es, x.en
    words = tokens(source)
    if len(words) < 3 or len(set(words)) < 2:
        return None
    tiles = words[:]
    for _ in range(6):
        rng.shuffle(tiles)
        if tiles != words:
            break
    if tiles == words:
        return None
    return Item("SCRAMBLE", "WRITING", "GRAMMAR", "Put the words in order.",
                {"input": "order", "tiles": tiles, "translation": translation},
                {"check": "order", "accept": [" ".join(words)], "display": source, "explain": None}, e)


# ---------------------------------------------------------------- comprehension


def _translated(e: EntryCtx) -> list[Example]:
    return [x for x in e.examples if x.en and x.source != "LEARNER"]


def sentence_meaning(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    examples = _translated(e)
    if not examples:
        return None
    x = rng.choice(examples)
    options = _options(x.en, pool.translations(x), rng)
    if not options:
        return None
    return Item("SENTENCE_MEANING", "READING", "COMPREHENSION", "What does this sentence mean?",
                {"input": "choice", "options": options, "spanish": x.es},
                {"check": "choice", "accept": [x.en], "display": x.en, "explain": f"{x.es} = {x.en}"}, e)


def translation_tf(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    examples = _translated(e)
    if not examples:
        return None
    x = rng.choice(examples)
    others = [t for t in pool.translations(x) if normalize(t) != normalize(x.en)]
    truth = rng.random() < 0.5 or not others
    if not others:
        return None
    shown = x.en if truth else rng.choice(others)
    return Item("TRANSLATION_TF", "READING", "COMPREHENSION", f"True or false: this means {_q(shown)}",
                {"input": "choice", "options": ["True", "False"], "spanish": x.es},
                {"check": "choice", "accept": ["True" if truth else "False"], "display": "True" if truth else "False",
                 "explain": f"{x.es} = {x.en}"}, e)


# ---------------------------------------------------------------- listening


def listen_pick(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    if e.is_function_word:
        return None
    if e.is_verb:
        target = _verb_target(e, rng)
        if not target:
            return None
        form, tense, _ = target
        # Other persons of the same tense: hearing the ending is the skill.
        others = [f for p in DRILL_PERSONS for f in e.table["tenses"].get(tense, {}).get(p, [])]
        others += [f for t in ("pres", "pret", "impf") for f in e.table["tenses"].get(t, {}).get("3s", [])]
    else:
        form, others = e.headword, pool.headwords(e, e.kind)
    # Options must sound clearly different: no two may differ only by an accent (extraño / extrañó).
    heard = {plain(form)}
    distinct = []
    for o in rng.sample(others, len(others)):
        if plain(o) not in heard:
            heard.add(plain(o))
            distinct.append(o)
    options = _options(form, distinct, rng)
    if not options:
        return None
    return Item("LISTEN_PICK", "LISTENING", "LISTENING", "Listen, then choose what you heard.",
                {"input": "choice", "options": options, "options_lang": "es", "tts": form},
                {"check": "choice", "accept": [form], "display": form,
                 "explain": _explain_form(e, form) if e.is_verb else None}, e)


def dictation(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    usable = [x for x in e.examples if 2 <= len(tokens(x.es)) <= 8]
    if not usable:
        return None
    x = rng.choice(usable)
    return Item("DICTATION", "LISTENING", "LISTENING", "Listen, then type what you heard.",
                {"input": "text", "tts": x.es},
                {"check": "dictation", "accept": [x.es], "display": x.es,
                 "explain": f"It means {_q(x.en)}." if x.en else None}, e)


# ---------------------------------------------------------------- free writing (the model grades it)


def write(e: EntryCtx, pool: Pool, rng: random.Random) -> Item | None:
    # Never for a phrase: "use 'te extrañan mucho' in a sentence" is not a sensible task.
    if e.kind != "WORD" or e.is_function_word:
        return None
    gloss = short_gloss(e.translation)
    what = "a form of " if e.is_verb else ""
    return Item("WRITE", "WRITING", "WRITING",
                f"Write one Spanish sentence using {what}{_q(e.headword)}{f' ({gloss})' if gloss else ''}.",
                {"input": "text", "long": True},
                {"check": "model"}, e)


BUILDERS = {
    "MEANING_MC": meaning_mc,
    "REVERSE_MC": reverse_mc,
    "FORM_ID": form_id,
    "CONJUGATE": conjugate,
    "CLOZE": cloze,
    "SCRAMBLE": scramble,
    "SENTENCE_MEANING": sentence_meaning,
    "TRANSLATION_TF": translation_tf,
    "LISTEN_PICK": listen_pick,
    "DICTATION": dictation,
    "WRITE": write,
}
MODALITY = {"MEANING_MC": "READING", "REVERSE_MC": "READING", "FORM_ID": "READING", "CONJUGATE": "WRITING",
            "CLOZE": "WRITING", "SCRAMBLE": "WRITING", "SENTENCE_MEANING": "READING", "TRANSLATION_TF": "READING",
            "LISTEN_PICK": "LISTENING", "DICTATION": "LISTENING", "WRITE": "WRITING"}
LISTENING_TYPES = {"LISTEN_PICK", "DICTATION"}
