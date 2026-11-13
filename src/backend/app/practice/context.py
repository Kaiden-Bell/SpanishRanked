"""Everything the question templates may use about each word-bank entry, loaded in one pass."""

import json
import re
import sqlite3
from dataclasses import dataclass, field

from ..lexicon import bank
from ..lexicon.analyze import tokens
from ..lexicon.verbs import VerbData

MAX_SENTENCE_WORDS = 12


@dataclass
class Example:
    es: str
    en: str | None  # None for the learner's own sentences
    source: str  # TATOEBA / WIKTIONARY / LEARNER


@dataclass
class EntryCtx:
    id: int
    concept_id: int
    token: str  # concept token: the lemma for words, the phrase for phrases
    kind: str  # WORD / PHRASE
    headword: str
    pos: str | None
    translation: str | None
    box: int
    due_at: str | None
    last_outcome: str | None
    tested: int
    created_at: str
    last_seen_at: str | None
    forms: list[tuple[str, dict]] = field(default_factory=list)  # (form, analysis_json)
    examples: list[Example] = field(default_factory=list)
    table: dict | None = None  # verb conjugation table
    phrase_words: list[dict] = field(default_factory=list)  # for phrases: the analysed words

    @property
    def is_verb(self) -> bool:
        return self.kind == "WORD" and self.table is not None

    @property
    def is_function_word(self) -> bool:
        return self.kind == "WORD" and self.pos in ("FUNCTION", "ENGLISH")

    def all_forms(self) -> set[str]:
        forms = {self.headword} | {f for f, _ in self.forms}
        if self.table:
            for cells in self.table["tenses"].values():
                for values in cells.values():
                    forms.update(values)
        return forms


def short_gloss(gloss: str | None, limit: int = 60) -> str | None:
    """'to talk; to speak; to communicate' -> 'to talk'. Keeps options short and comparable."""
    if not gloss:
        return None
    text = gloss.split(";")[0].strip()
    # "to miss (someone or something)" -> "to miss": the bracket is a usage note, not the meaning.
    bare = re.sub(r"\s*\([^)]*\)", "", text).strip()
    text = bare or text
    if len(text) > limit:
        text = text.split(",")[0].strip()
    return text[:limit].rstrip(" ,") or None


def load_entries(conn: sqlite3.Connection, verbs: VerbData, user_id: int) -> list[EntryCtx]:
    rows = conn.execute(f"{bank.ENTRY_SELECT} WHERE e.user_id = ? ORDER BY e.id", (user_id,)).fetchall()
    entries: list[EntryCtx] = []
    by_lexeme: dict[int, list[EntryCtx]] = {}
    for r in rows:
        e = EntryCtx(
            id=r["id"], concept_id=r["concept_id"], token=r["lemma"] if r["kind"] == "WORD" else r["phrase_text"],
            kind=r["kind"], headword=r["headword"], pos=r["pos"], translation=bank.translation(r),
            box=r["box"], due_at=r["due_at"], last_outcome=r["last_outcome"],
            tested=r["hits"] + r["partials"] + r["misses"], created_at=r["created_at"], last_seen_at=r["last_seen_at"],
        )
        if e.kind == "WORD" and e.pos == "VERB":
            e.table = verbs.table(e.headword)
        entries.append(e)
        if r["lexeme_id"]:
            by_lexeme.setdefault(r["lexeme_id"], []).append(e)

    by_id = {e.id: e for e in entries}
    for f in conn.execute(
        "SELECT f.bank_entry_id, f.form, f.analysis_json FROM bank_forms f JOIN bank_entries e ON e.id = f.bank_entry_id"
        " WHERE e.user_id = ? ORDER BY f.first_seen_at", (user_id,)
    ):
        e = by_id[f["bank_entry_id"]]
        analysis = json.loads(f["analysis_json"])
        if e.kind == "PHRASE":
            e.phrase_words = analysis.get("words", [])
        else:
            e.forms.append((f["form"], analysis))

    if by_lexeme:
        marks = ",".join("?" * len(by_lexeme))
        for x in conn.execute(
            f"SELECT lexeme_id, es_text, en_text, source FROM example_sentences WHERE lexeme_id IN ({marks})"
            " ORDER BY LENGTH(es_text)", list(by_lexeme)
        ):
            if len(tokens(x["es_text"])) <= MAX_SENTENCE_WORDS:
                for e in by_lexeme[x["lexeme_id"]]:
                    e.examples.append(Example(x["es_text"], x["en_text"], x["source"]))

    # The learner's own sentences, attached to every entry they use.
    own = [s["sentence_text"] for s in conn.execute(
        "SELECT st.sentence_text FROM study_sentences st JOIN study_sessions ss ON ss.id = st.study_session_id"
        " WHERE ss.user_id = ? ORDER BY st.id DESC", (user_id,))]
    for e in entries:
        if e.kind == "PHRASE":
            needle = f" {' '.join(tokens(e.headword))} "
            matches = [s for s in own if needle in f" {' '.join(tokens(s))} "]
        else:
            forms = e.all_forms()
            matches = [s for s in own if forms & set(tokens(s))]
        e.examples.extend(Example(s, None, "LEARNER") for s in matches[:5] if len(tokens(s)) <= MAX_SENTENCE_WORDS)
    return entries
