"""Fill word-bank entries with dictionary data from the online sources, in the background.

Every lookup goes through the cache, and a source being down only leaves an entry 'unavailable'
(retried later). Nothing here is needed for the app to work; it makes entries richer.
"""

import json
import logging
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from .. import db
from . import bank
from .analyze import analyze, tokens
from .cache import cached, peek
from .grammar_terms import describe_form
from .parse import parse_term
from .sources import LexiconSources
from .verbs import VerbData

log = logging.getLogger(__name__)

MAX_EXAMPLES = 8
MAX_POS_BLOCKS = 4
_GLOSS_HEAD = re.compile(r"^(?:to |a |an |the )?([a-z][a-z'-]+)", re.I)


def _set_status(conn, lexeme_id: int, status: str) -> None:
    with conn:
        conn.execute("UPDATE lexemes SET enrich_status = ?, enriched_at = ? WHERE id = ?",
                     (status, db.utc_timestamp(), lexeme_id))


def _gloss_heads(entries: list[dict]) -> set[str]:
    heads = set()
    for entry in entries:
        for sense in entry["senses"][:3]:
            for part in re.split(r"[;,]", sense["gloss"]):
                m = _GLOSS_HEAD.match(part.strip())
                if m and len(m.group(1)) > 2:
                    heads.add(m.group(1).casefold())
    return heads


def _uses(sentence: str, lemma: str, is_verb: bool, verbs: VerbData) -> bool:
    words = tokens(sentence)
    if is_verb:
        return any(lemma in verbs.infinitives_for(w) for w in words)
    return any(w in (lemma, f"{lemma}s", f"{lemma}es") for w in words)


def pick_examples(candidates: list[dict], lemma: str, is_verb: bool, verbs: VerbData, heads: set[str]) -> list[dict]:
    """Sentences that really use the word, preferring ones whose translation contains its meaning
    (so 'Extraño.' = 'Strange.' doesn't illustrate extrañar = to miss)."""
    usable = [c for c in candidates if _uses(c["es"], lemma, is_verb, verbs) and len(c["es"]) <= 120]

    def matches_meaning(c):
        english = c["en"].casefold()
        return any(h in english for h in heads)

    good = [c for c in usable if matches_meaning(c)]
    chosen = good if len(good) >= 3 or not heads else good + [c for c in usable if c not in good]
    seen, out = set(), []
    for c in sorted(chosen, key=lambda c: (not matches_meaning(c), len(c["es"]))):
        key = " ".join(tokens(c["es"]))  # 'Te extrañé.' and '¡Te extrañé!' are the same example
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out[:MAX_EXAMPLES]


def enrich_lexeme(conn: sqlite3.Connection, sources: LexiconSources, verbs: VerbData, lexeme_id: int) -> None:
    lex = conn.execute("SELECT * FROM lexemes WHERE id = ?", (lexeme_id,)).fetchone()
    if lex is None or lex["redirect_lexeme_id"]:
        return
    if not sources.enabled:
        _set_status(conn, lexeme_id, "offline")
        return
    lemma, is_verb = lex["lemma"], lex["pos"] == "VERB"
    status, body = cached(conn, "WIKTIONARY", lemma, lambda: sources.wiktionary(lemma))
    if status == "error":
        _set_status(conn, lexeme_id, "unavailable")
        return
    entries = (body or {}).get("entries", [])
    real = [e for e in entries if not e["form_of"]]
    if is_verb:
        real = [e for e in real if e["pos"].casefold() == "verb"] or real
    targets = [t for e in entries for t in e["form_of"] if t != lemma]
    if not is_verb and not real and targets:
        with conn:
            bank.redirect_lexeme(conn, lexeme_id, targets[0].casefold(), None)
        return

    candidates = [
        {"es": ex["es"], "en": ex["en"], "source": "WIKTIONARY", "ref": None}
        for e in real for s in e["senses"] for ex in s["examples"]
    ]
    t_status, t_body = cached(conn, "TATOEBA", lemma, lambda: sources.tatoeba(lemma))
    for sentence in t_body or []:
        candidates.append({"es": sentence["es"], "en": sentence["en"], "source": "TATOEBA", "ref": str(sentence["id"])})
    examples = pick_examples(candidates, lemma, is_verb, verbs, _gloss_heads(real))

    pos = "VERB" if is_verb else (real[0]["pos"] if real else lex["pos"])
    final = "ok" if real or examples else ("unavailable" if t_status == "error" else "not_found")
    with conn:
        conn.execute(
            "UPDATE lexemes SET senses_json = ?, pos = ?, enrich_status = ?, enriched_at = ? WHERE id = ?",
            (json.dumps(real[:MAX_POS_BLOCKS], ensure_ascii=False), pos, final, db.utc_timestamp(), lexeme_id),
        )
        for ex in examples:
            conn.execute(
                "INSERT OR IGNORE INTO example_sentences (lexeme_id, es_text, en_text, source, source_ref)"
                " VALUES (?, ?, ?, ?, ?)",
                (lexeme_id, ex["es"], ex["en"], ex["source"], ex["ref"]),
            )


def _recheck_nouns(conn, sources: LexiconSources, entry: sqlite3.Row) -> None:
    """'la casa': the analyzer read casa as casar (he marries) because 'la' is also a pronoun. When the
    dictionary has a noun of that exact spelling, the phrase word is re-pointed to the noun."""
    row = conn.execute("SELECT analysis_json FROM bank_forms WHERE bank_entry_id = ? AND form = ?",
                       (entry["id"], entry["phrase_text"])).fetchone()
    if row is None:
        return
    words = json.loads(row["analysis_json"]).get("words", [])
    for previous, word in zip([None, *words], words):
        if word["pos"] != "VERB" or not previous or previous["surface"] not in ("la", "las", "los", "lo", "una", "un"):
            continue
        if not all(f["tense"] in ("pres", "imp_aff") and f["person"] in ("3s", "3p", "tu") for f in word["forms"]):
            continue
        status, body = cached(conn, "WIKTIONARY", word["surface"], lambda w=word["surface"]: sources.wiktionary(w))
        nouns = [e for e in (body or {}).get("entries", []) if e["pos"].casefold() == "noun" and not e["form_of"]]
        if status != "ok" or not nouns:
            continue
        with conn:
            _move_phrase_word(conn, entry, word["surface"], word["lemma"])


def _move_phrase_word(conn, phrase: sqlite3.Row, surface: str, wrong_lemma: str) -> None:
    wrong = conn.execute(
        "SELECT e.id FROM bank_entries e JOIN lexemes l ON l.id = e.lexeme_id WHERE e.user_id = ? AND l.lemma = ?",
        (phrase["user_id"], wrong_lemma)).fetchone()
    noun_lexeme = bank.ensure_lexeme(conn, surface, "Noun")
    target = bank.ensure_word_entry(conn, phrase["user_id"], noun_lexeme, phrase["created_at"])
    # The phrase's own concept, and the logged terms that contain the phrase.
    concepts = [phrase["concept_id"]] + [r["concept_id"] for r in conn.execute(
        "SELECT concept_id FROM bank_entry_concepts WHERE bank_entry_id = ? AND role = 'TERM'", (phrase["id"],))]
    for c in concepts:
        conn.execute("INSERT OR IGNORE INTO bank_entry_concepts (bank_entry_id, concept_id, role) VALUES (?, ?, 'IN_PHRASE')",
                     (target, c))
    conn.execute("INSERT OR IGNORE INTO bank_forms (bank_entry_id, form, analysis_json) VALUES (?, ?, ?)",
                 (target, surface, json.dumps({"surface": surface, "lemma": surface, "pos": "Noun", "forms": []})))
    # The phrase's own record of its words must say noun too, or questions about it would explain casa as casar.
    row = conn.execute("SELECT analysis_json FROM bank_forms WHERE bank_entry_id = ? AND form = ?",
                       (phrase["id"], phrase["phrase_text"])).fetchone()
    if row:
        analysis = json.loads(row["analysis_json"])
        for w in analysis.get("words", []):
            if w["surface"] == surface:
                w.update(lemma=surface, pos="Noun", forms=[], alternatives=[wrong_lemma])
        conn.execute("UPDATE bank_forms SET analysis_json = ? WHERE bank_entry_id = ? AND form = ?",
                     (json.dumps(analysis, ensure_ascii=False), phrase["id"], phrase["phrase_text"]))
    if wrong is None:
        return
    for c in concepts:
        conn.execute("DELETE FROM bank_entry_concepts WHERE bank_entry_id = ? AND concept_id = ? AND role = 'IN_PHRASE'",
                     (wrong["id"], c))
    still_used = conn.execute("SELECT 1 FROM bank_entry_concepts WHERE bank_entry_id = ?", (wrong["id"],)).fetchone()
    if still_used:
        conn.execute("DELETE FROM bank_forms WHERE bank_entry_id = ? AND form = ?", (wrong["id"], surface))
    else:
        conn.execute("DELETE FROM bank_entries WHERE id = ?", (wrong["id"],))


def enrich_phrase(conn: sqlite3.Connection, sources: LexiconSources, entry_id: int) -> None:
    entry = conn.execute("SELECT * FROM bank_entries WHERE id = ?", (entry_id,)).fetchone()
    if entry is None:
        return
    if not sources.enabled:
        with conn:
            conn.execute("UPDATE bank_entries SET translation_status = 'offline' WHERE id = ?", (entry_id,))
        return
    _recheck_nouns(conn, sources, entry)
    status, body = cached(conn, "MYMEMORY", entry["phrase_text"], lambda: sources.translate(entry["phrase_text"]))
    final = {"ok": "ok", "missing": "not_found", "error": "unavailable"}[status]
    with conn:
        conn.execute("UPDATE bank_entries SET auto_translation = ?, translation_status = ? WHERE id = ?",
                     (body if status == "ok" else entry["auto_translation"], final, entry_id))


def preview(conn: sqlite3.Connection, sources: LexiconSources, verbs: VerbData, text: str) -> dict:
    """What a term means, for the study form, before it is saved. Uses the cache; fetches if allowed."""
    parsed = parse_term(text, verbs)
    if parsed.is_english:
        return {"kind": "WORD", "text": "", "translation": None, "words": [], "meaning": parsed.meaning,
                "english_only": True, "english": parsed.english}
    analysis = analyze(parsed.spanish, verbs)

    def gloss_for(word: str, depth: int = 0) -> str | None:
        fetch = (lambda: sources.wiktionary(word)) if sources.enabled else None
        status, body = cached(conn, "WIKTIONARY", word, fetch) if fetch else peek(conn, "WIKTIONARY", word)
        for e in (body or {}).get("entries", []):
            if not e["form_of"] and e["senses"]:
                return e["senses"][0]["gloss"]
        targets = [t for e in (body or {}).get("entries", []) for t in e["form_of"]]
        return gloss_for(targets[0].casefold(), depth + 1) if targets and targets[0] != word and depth == 0 else None

    words = []
    for w in analysis.content_words[:3]:
        words.append({
            "surface": w.surface, "lemma": w.lemma, "pos": w.pos,
            "translation": gloss_for(w.lemma),
            "forms": [describe_form(f.tense, f.person) for f in w.forms][:3],
        })
    phrase_translation = None
    if analysis.kind == "PHRASE":
        if sources.enabled:
            status, body = cached(conn, "MYMEMORY", analysis.text, lambda: sources.translate(analysis.text))
        else:
            status, body = peek(conn, "MYMEMORY", analysis.text)
        phrase_translation = body if status == "ok" else None
    return {"kind": analysis.kind, "text": analysis.text, "translation": phrase_translation, "words": words,
            "meaning": parsed.meaning, "english_only": False, "english": parsed.english}


class Enricher:
    """One background worker. kick() after saving terms; inline=True runs synchronously (tests)."""

    def __init__(self, db_path: Path, sources: LexiconSources, verbs: VerbData, *, inline: bool = False):
        self._db_path, self.sources, self.verbs, self.inline = db_path, sources, verbs, inline
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._run_lock = threading.Lock()

    def start(self) -> None:
        if self.inline or self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="word-enricher", daemon=True)
        self._thread.start()
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def kick(self) -> None:
        if self.inline:
            self.run_pending()
        else:
            self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=600)  # also retry 'unavailable' entries every 10 minutes
            self._wake.clear()
            if self._stop.is_set():
                return
            try:
                self.retry_unavailable()
                self.run_pending()
            except Exception:  # never let the worker die; the next kick retries
                log.exception("word enrichment failed")

    def retry_unavailable(self) -> None:
        with closing(db.connect(self._db_path)) as conn, conn:
            conn.execute("UPDATE lexemes SET enrich_status = 'pending' WHERE enrich_status = 'unavailable'"
                         " AND (enriched_at IS NULL OR enriched_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-30 minutes'))")
            conn.execute("UPDATE bank_entries SET translation_status = 'pending' WHERE translation_status = 'unavailable'")

    def run_pending(self, limit: int = 500) -> int:
        done = 0
        with self._run_lock, closing(db.connect(self._db_path)) as conn:
            while done < limit and not self._stop.is_set():
                # Phrases first: checking them can re-point a misread word ('la casa') before it is looked up.
                phrase = conn.execute("SELECT id FROM bank_entries WHERE kind = 'PHRASE' AND translation_status = 'pending'"
                                      " ORDER BY id LIMIT 1").fetchone()
                if phrase:
                    enrich_phrase(conn, self.sources, phrase["id"])
                    conn.execute("UPDATE bank_entries SET translation_status = 'unavailable' WHERE id = ? AND translation_status = 'pending'",
                                 (phrase["id"],))
                    conn.commit()
                    done += 1
                    continue
                lex = conn.execute("SELECT id FROM lexemes WHERE enrich_status = 'pending' AND redirect_lexeme_id IS NULL"
                                   " ORDER BY id LIMIT 1").fetchone()
                if lex:
                    enrich_lexeme(conn, self.sources, self.verbs, lex["id"])
                    conn.execute("UPDATE lexemes SET enrich_status = 'unavailable' WHERE id = ? AND enrich_status = 'pending'",
                                 (lex["id"],))  # guarantees progress even if something above returned early
                    conn.commit()
                    done += 1
                    continue
                break
        return done


def reset_offline(conn: sqlite3.Connection) -> None:
    """At startup with lookups enabled: retry everything that was skipped while they were off."""
    with conn:
        conn.execute("UPDATE lexemes SET enrich_status = 'pending' WHERE enrich_status IN ('offline', 'unavailable')")
        conn.execute("UPDATE bank_entries SET translation_status = 'pending' WHERE translation_status IN ('offline', 'unavailable')")
