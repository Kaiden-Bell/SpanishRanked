"""The learner's word bank: turning logged terms into entries, and reading entries back.

Writes here run inside the caller's transaction (session save, startup backfill), and make no
network calls. Dictionary data arrives later through enrich.py.
"""

import json
import sqlite3
from datetime import datetime, timezone

from .. import db
from .analyze import TermAnalysis, WordAnalysis, analyze, tokens
from .parse import parse_term
from .grammar_terms import CORE_TENSES, FUNCTION_GLOSS, PERSONS, TENSES, describe_form
from .sources import ATTRIBUTION
from .verbs import VerbData

LANGUAGE = "es"
LEMMA_CATEGORY = "LEMMA"  # concepts owned by word entries
TERM_CATEGORY = "VOCABULARY"  # concepts created from typed study terms (Level 1)


# ---------------------------------------------------------------- writes


def _concept(conn: sqlite3.Connection, category: str, token: str) -> int:
    conn.execute("INSERT OR IGNORE INTO concepts (language_code, token, category) VALUES (?, ?, ?)",
                 (LANGUAGE, token, category))
    return conn.execute("SELECT id FROM concepts WHERE language_code = ? AND category = ? AND token = ?",
                        (LANGUAGE, category, token)).fetchone()["id"]


def ensure_lexeme(conn: sqlite3.Connection, lemma: str, pos: str | None) -> int:
    conn.execute("INSERT OR IGNORE INTO lexemes (language_code, lemma, pos) VALUES (?, ?, ?)", (LANGUAGE, lemma, pos))
    row = conn.execute("SELECT id, pos, redirect_lexeme_id FROM lexemes WHERE language_code = ? AND lemma = ?",
                       (LANGUAGE, lemma)).fetchone()
    if row["redirect_lexeme_id"]:
        return row["redirect_lexeme_id"]
    if pos == "VERB" and row["pos"] != "VERB":
        conn.execute("UPDATE lexemes SET pos = 'VERB' WHERE id = ?", (row["id"],))
    return row["id"]


def ensure_word_entry(conn: sqlite3.Connection, user_id: int, lexeme_id: int, now: str) -> int:
    lemma = conn.execute("SELECT lemma FROM lexemes WHERE id = ?", (lexeme_id,)).fetchone()["lemma"]
    concept_id = _concept(conn, LEMMA_CATEGORY, lemma)
    conn.execute(
        "INSERT OR IGNORE INTO bank_entries (user_id, concept_id, kind, lexeme_id, due_at, created_at)"
        " VALUES (?, ?, 'WORD', ?, ?, ?)",
        (user_id, concept_id, lexeme_id, now, now),
    )
    return conn.execute("SELECT id FROM bank_entries WHERE user_id = ? AND concept_id = ?",
                        (user_id, concept_id)).fetchone()["id"]


def _phrase_entry(conn: sqlite3.Connection, user_id: int, concept_id: int, text: str, now: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO bank_entries (user_id, concept_id, kind, phrase_text, due_at, created_at)"
        " VALUES (?, ?, 'PHRASE', ?, ?, ?)",
        (user_id, concept_id, text, now, now),
    )
    return conn.execute("SELECT id FROM bank_entries WHERE user_id = ? AND concept_id = ?",
                        (user_id, concept_id)).fetchone()["id"]


def _link(conn, entry_id: int, concept_id: int, role: str) -> None:
    conn.execute("INSERT OR IGNORE INTO bank_entry_concepts (bank_entry_id, concept_id, role) VALUES (?, ?, ?)",
                 (entry_id, concept_id, role))


def _form(conn, entry_id: int, form: str, analysis: dict, now: str) -> None:
    conn.execute("INSERT OR IGNORE INTO bank_forms (bank_entry_id, form, analysis_json, first_seen_at) VALUES (?, ?, ?, ?)",
                 (entry_id, form, json.dumps(analysis, ensure_ascii=False), now))


def _word(conn, user_id: int, word: WordAnalysis, now: str) -> int:
    entry_id = ensure_word_entry(conn, user_id, ensure_lexeme(conn, word.lemma, word.pos), now)
    _form(conn, entry_id, word.surface, word.to_json(), now)
    return entry_id


PHRASE_CATEGORY = "PHRASE"  # concepts owned by phrase entries (the Spanish phrase, normalised)


def _set_meaning(conn, entry_id: int, meaning: str | None) -> None:
    if meaning:
        conn.execute("UPDATE bank_entries SET user_translation = COALESCE(user_translation, ?) WHERE id = ?",
                     (meaning[:200], entry_id))


def ingest_term(conn: sqlite3.Connection, verbs: VerbData, user_id: int, concept_id: int, text: str,
                now: str | None = None, *, keep_phrase: bool = True) -> list[int]:
    """Add one logged term to the bank. Returns entry ids.

    The typed text is parsed first (parse.py): a label like "phrase:" is dropped, an English meaning
    after a dash becomes the learner's translation, and English words never become entries. A phrase
    gets its own entry plus one per content word; with keep_phrase=False only the words are kept.
    """
    now = now or db.utc_timestamp()
    parsed = parse_term(text, verbs)
    if parsed.is_english:
        return []
    analysis: TermAnalysis = analyze(parsed.spanish, verbs)
    if not analysis.content_words:
        if analysis.kind == "WORD" and analysis.words and analysis.words[0].pos != "ENGLISH":
            pass  # a single function word the learner chose to study ("pero"): keep it
        elif analysis.kind == "WORD" or not analysis.words:
            return []
    if analysis.kind == "WORD":
        head = analysis.head
        entry_id = ensure_word_entry(conn, user_id, ensure_lexeme(conn, head.lemma, head.pos), now)
        form = head.to_json()
        if parsed.meaning:
            form["meaning"] = parsed.meaning
        _form(conn, entry_id, head.surface, form, now)
        _link(conn, entry_id, concept_id, "TERM")
        if head.surface == head.lemma:
            _set_meaning(conn, entry_id, parsed.meaning)  # the meaning of the dictionary form itself
        return [entry_id]

    ids: list[int] = []
    if keep_phrase:
        phrase_concept = _concept(conn, PHRASE_CATEGORY, analysis.text)
        phrase_id = _phrase_entry(conn, user_id, phrase_concept, analysis.text, now)
        _link(conn, phrase_id, concept_id, "TERM")
        _form(conn, phrase_id, analysis.text, {"words": [w.to_json() for w in analysis.words]}, now)
        _set_meaning(conn, phrase_id, parsed.meaning)
        ids.append(phrase_id)
    for word in analysis.content_words:
        entry_id = _word(conn, user_id, word, now)
        # Words of a kept phrase are linked through it; on their own they are the term.
        _link(conn, entry_id, phrase_concept if keep_phrase else concept_id, "IN_PHRASE" if keep_phrase else "TERM")
        if keep_phrase:
            _link(conn, entry_id, concept_id, "IN_PHRASE")
        ids.append(entry_id)
    return ids


def ingest_missing(conn: sqlite3.Connection, verbs: VerbData) -> int:
    """Backfill: every logged term that isn't in the bank yet (terms saved before it existed)."""
    rows = conn.execute(
        "SELECT ss.user_id, st.concept_id, st.original_text, ss.created_at FROM study_terms st"
        " JOIN study_sessions ss ON ss.id = st.study_session_id"
        " WHERE NOT EXISTS (SELECT 1 FROM bank_entry_concepts b WHERE b.concept_id = st.concept_id)"
        " ORDER BY st.id"
    ).fetchall()
    with conn:
        for r in rows:
            ingest_term(conn, verbs, r["user_id"], r["concept_id"], r["original_text"], r["created_at"])
    return len(rows)


def reparse_all(conn: sqlite3.Connection, verbs: VerbData) -> int:
    """One-time repair after term parsing arrived: re-read every logged term, so labels, English
    meanings and English words typed into term boxes stop being word-bank entries. Practice history
    is kept: word entries are the same rows, a re-created phrase inherits the counts of the one it
    replaces, and only untested, now-unused entries are removed. Returns how many terms were read."""
    changed = 0
    with conn:
        terms = conn.execute(
            "SELECT DISTINCT ss.user_id, st.concept_id, st.original_text, ss.created_at FROM study_terms st"
            " JOIN study_sessions ss ON ss.id = st.study_session_id ORDER BY st.id"
        ).fetchall()
        for t in terms:
            # Every term, not only the ones that read differently now: older phrases also move to the
            # current shape (a phrase owns its own concept), so logging one again can't duplicate it.
            old = [r["bank_entry_id"] for r in conn.execute(
                "SELECT bank_entry_id FROM bank_entry_concepts WHERE concept_id = ?", (t["concept_id"],))]
            old_kinds = {r["id"]: r["kind"] for r in conn.execute(
                f"SELECT id, kind FROM bank_entries WHERE id IN ({','.join('?' * len(old))})", old)} if old else {}
            conn.execute("DELETE FROM bank_entry_concepts WHERE concept_id = ?", (t["concept_id"],))
            new = ingest_term(conn, verbs, t["user_id"], t["concept_id"], t["original_text"], t["created_at"])
            new_phrase = next((i for i in new if conn.execute(
                "SELECT kind FROM bank_entries WHERE id = ?", (i,)).fetchone()["kind"] == "PHRASE"), None)
            for entry_id, kind in old_kinds.items():
                if entry_id in new:
                    continue
                if kind == "PHRASE" and new_phrase:
                    _merge_stats(conn, new_phrase, entry_id)
            changed += 1
        # Entries nothing points at any more (the English words, the raw "phrase: ... - ..." entries).
        conn.execute(
            "DELETE FROM bank_entries WHERE NOT EXISTS (SELECT 1 FROM bank_entry_concepts b WHERE b.bank_entry_id = bank_entries.id)"
            " AND hits + partials + misses = 0"
        )
        # Phrase entries that lost their links but had practice history were merged above; drop them too.
        conn.execute(
            "DELETE FROM bank_entries WHERE kind = 'PHRASE' AND NOT EXISTS"
            " (SELECT 1 FROM bank_entry_concepts b WHERE b.bank_entry_id = bank_entries.id)"
        )
    return changed


def forget_terms(conn: sqlite3.Connection, user_id: int, concept_ids: list[int]) -> int:
    """A deleted session's terms leave the bank, unless another session logged them too. Phrases those
    terms made go with them, and so does any word nothing else points at. Runs inside the caller's
    transaction. Returns how many entries were removed."""
    if not concept_ids:
        return 0
    marks = ",".join("?" * len(concept_ids))
    still_logged = {r[0] for r in conn.execute(
        f"SELECT DISTINCT st.concept_id FROM study_terms st JOIN study_sessions ss ON ss.id = st.study_session_id"
        f" WHERE ss.user_id = ? AND st.concept_id IN ({marks})", (user_id, *concept_ids))}
    gone = [c for c in concept_ids if c not in still_logged]
    if not gone:
        return 0
    marks = ",".join("?" * len(gone))
    mine = "bank_entry_id IN (SELECT id FROM bank_entries WHERE user_id = ?)"
    conn.execute(f"DELETE FROM bank_entry_concepts WHERE concept_id IN ({marks}) AND {mine}", (*gone, user_id))
    # A phrase no logged term points at any more: unlink its words from it, then drop it.
    orphans = conn.execute(
        "SELECT id, concept_id FROM bank_entries e WHERE user_id = ? AND kind = 'PHRASE' AND NOT EXISTS"
        " (SELECT 1 FROM bank_entry_concepts b WHERE b.bank_entry_id = e.id AND b.role = 'TERM')", (user_id,)
    ).fetchall()
    for o in orphans:
        conn.execute(f"DELETE FROM bank_entry_concepts WHERE concept_id = ? AND {mine}", (o["concept_id"], user_id))
    removed = conn.execute(
        "DELETE FROM bank_entries WHERE user_id = ? AND NOT EXISTS"
        " (SELECT 1 FROM bank_entry_concepts b WHERE b.bank_entry_id = bank_entries.id)", (user_id,)
    ).rowcount
    return removed


def redirect_lexeme(conn: sqlite3.Connection, from_id: int, to_lemma: str, pos: str | None) -> int:
    """maletas turned out to be a form of maleta: move every bank entry over and remember the redirect."""
    to_id = ensure_lexeme(conn, to_lemma, pos)
    if to_id == from_id:
        return to_id
    for entry in conn.execute("SELECT id, user_id, created_at FROM bank_entries WHERE lexeme_id = ?", (from_id,)).fetchall():
        target = ensure_word_entry(conn, entry["user_id"], to_id, entry["created_at"])
        for table, key in (("bank_entry_concepts", "concept_id"), ("bank_forms", "form")):
            conn.execute(
                f"UPDATE OR IGNORE {table} SET bank_entry_id = ? WHERE bank_entry_id = ?", (target, entry["id"])
            )
        _merge_stats(conn, target, entry["id"])
        conn.execute("DELETE FROM bank_entries WHERE id = ?", (entry["id"],))
    conn.execute("UPDATE lexemes SET redirect_lexeme_id = ?, enrich_status = 'ok' WHERE id = ?", (to_id, from_id))
    return to_id


def _merge_stats(conn, target: int, source: int) -> None:
    conn.execute(
        "UPDATE bank_entries SET hits = bank_entries.hits + s.hits, partials = bank_entries.partials + s.partials,"
        " misses = bank_entries.misses + s.misses,"
        " created_at = MIN(bank_entries.created_at, s.created_at),"
        " user_translation = COALESCE(bank_entries.user_translation, s.user_translation),"
        " note = COALESCE(bank_entries.note, s.note)"
        " FROM (SELECT hits, partials, misses, created_at, user_translation, note FROM bank_entries WHERE id = ?) AS s"
        " WHERE bank_entries.id = ?",
        (source, target),
    )


# ---------------------------------------------------------------- reads


def strength(row: sqlite3.Row) -> str:
    if row["hits"] + row["partials"] + row["misses"] == 0:
        return "new"
    if row["last_outcome"] in ("MISS", "PARTIAL"):
        return "weak"
    return "strong" if row["box"] >= 4 else "learning"


def senses(row: sqlite3.Row) -> list[dict]:
    return json.loads(row["senses_json"]) if row["senses_json"] else []


def translation(row: sqlite3.Row) -> str | None:
    if row["user_translation"]:
        return row["user_translation"]
    if row["kind"] == "PHRASE":
        return row["auto_translation"]
    for entry in senses(row):
        if entry.get("senses"):
            return entry["senses"][0]["gloss"]
    return None


def lookup_status(row: sqlite3.Row) -> str:
    return row["translation_status"] if row["kind"] == "PHRASE" else (row["enrich_status"] or "pending")


ENTRY_SELECT = (
    "SELECT e.*, l.lemma, l.pos, l.senses_json, l.enrich_status,"
    " COALESCE(l.lemma, e.phrase_text) AS headword,"
    " (SELECT COUNT(DISTINCT st.study_session_id) FROM bank_entry_concepts b"
    "    JOIN study_terms st ON st.concept_id = b.concept_id WHERE b.bank_entry_id = e.id) AS sessions_count,"
    " (SELECT MAX(ss.created_at) FROM bank_entry_concepts b JOIN study_terms st ON st.concept_id = b.concept_id"
    "    JOIN study_sessions ss ON ss.id = st.study_session_id WHERE b.bank_entry_id = e.id) AS last_seen_at"
    " FROM bank_entries e LEFT JOIN lexemes l ON l.id = e.lexeme_id"
)


def summary(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    forms = [r["form"] for r in conn.execute(
        "SELECT form FROM bank_forms WHERE bank_entry_id = ? ORDER BY first_seen_at, form", (row["id"],))]
    return {
        "id": row["id"], "kind": row["kind"], "headword": row["headword"], "pos": row["pos"],
        "translation": translation(row), "lookup_status": lookup_status(row),
        "forms_seen": [f for f in forms if f != row["headword"]] if row["kind"] == "WORD" else [],
        "strength": strength(row), "sessions_count": row["sessions_count"],
        "created_at": row["created_at"], "last_seen_at": row["last_seen_at"],
        "due_at": row["due_at"],
    }


def list_entries(conn: sqlite3.Connection, user_id: int, q: str = "", kind: str | None = None,
                 sort: str = "recent", limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
    where, args = ["e.user_id = ?"], [user_id]
    if kind:
        where.append("e.kind = ?")
        args.append(kind)
    if q.strip():
        like = f"%{q.strip().casefold()}%"
        where.append(
            "(LOWER(COALESCE(l.lemma, e.phrase_text)) LIKE ? OR LOWER(COALESCE(e.user_translation, '')) LIKE ?"
            " OR LOWER(COALESCE(e.auto_translation, '')) LIKE ? OR LOWER(COALESCE(l.senses_json, '')) LIKE ?"
            " OR EXISTS (SELECT 1 FROM bank_forms f WHERE f.bank_entry_id = e.id AND f.form LIKE ?))"
        )
        args += [like] * 5
    order = {
        "recent": "last_seen_at DESC, e.id DESC",
        "alpha": "headword COLLATE NOCASE",
        "weak": "CASE WHEN e.last_outcome IN ('MISS','PARTIAL') THEN 0 WHEN e.last_outcome IS NULL THEN 1 ELSE 2 END, e.box, e.id DESC",
    }.get(sort, "last_seen_at DESC, e.id DESC")
    clause = " WHERE " + " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM bank_entries e LEFT JOIN lexemes l ON l.id = e.lexeme_id{clause}", args
    ).fetchone()[0]
    rows = conn.execute(f"{ENTRY_SELECT}{clause} ORDER BY {order} LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
    return total, [summary(conn, r) for r in rows]


def counts(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    out = {"WORD": 0, "PHRASE": 0}
    for r in conn.execute("SELECT kind, COUNT(*) AS n FROM bank_entries WHERE user_id = ? GROUP BY kind", (user_id,)):
        out[r["kind"]] = r["n"]
    return out


def get_entry_row(conn: sqlite3.Connection, user_id: int, entry_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{ENTRY_SELECT} WHERE e.id = ? AND e.user_id = ?", (entry_id, user_id)).fetchone()


def conjugation_table(verbs: VerbData, infinitive: str, seen: set[str]) -> dict | None:
    table = verbs.table(infinitive)
    if not table:
        return None
    rows = []
    for key in TENSES:
        cells = table["tenses"].get(key)
        if not cells:
            continue
        rows.append({
            "tense": key, "label": TENSES[key]["label"], "mood": TENSES[key]["mood"], "when": TENSES[key]["when"],
            "core": key in CORE_TENSES,
            "cells": {p: cells.get(p, []) for p in PERSONS},
        })
    return {
        "infinitive": infinitive,
        "persons": [{"key": k, "label": v["label"], "who": v["who"]} for k, v in PERSONS.items()],
        "rows": rows, "gerund": table.get("ger", []), "participle": table.get("part", []),
        "seen": sorted(seen),
    }


def _all_forms(verbs: VerbData, row: sqlite3.Row, seen: list[str]) -> set[str]:
    forms = set(seen)
    if row["kind"] == "WORD":
        forms.add(row["lemma"])
        table = verbs.table(row["lemma"]) if row["pos"] == "VERB" else None
        if table:
            for cells in table["tenses"].values():
                for values in cells.values():
                    forms.update(values)
            forms.update(table.get("ger", []) + table.get("part", []))
    return forms


def detail(conn: sqlite3.Connection, verbs: VerbData, user_id: int, entry_id: int) -> dict | None:
    row = get_entry_row(conn, user_id, entry_id)
    if row is None:
        return None
    out = summary(conn, row)
    form_rows = conn.execute("SELECT form, analysis_json FROM bank_forms WHERE bank_entry_id = ? ORDER BY first_seen_at",
                             (entry_id,)).fetchall()
    forms = []
    for f in form_rows:
        analysis = json.loads(f["analysis_json"])
        if row["kind"] == "PHRASE":
            continue
        forms.append({
            "form": f["form"],
            "meaning": analysis.get("meaning"),
            "analyses": [describe_form(m["tense"], m["person"]) for m in analysis.get("forms", [])],
            "clitics": analysis.get("clitics", []),
            "also": analysis.get("alternatives", []),
        })
    seen = [f["form"] for f in form_rows]
    out["forms"] = forms
    out["senses"] = senses(row) if row["kind"] == "WORD" else []
    out["user_translation"] = row["user_translation"]
    out["note"] = row["note"]
    out["auto_translation"] = row["auto_translation"]
    out["conjugation"] = (conjugation_table(verbs, row["lemma"], set(seen))
                          if row["kind"] == "WORD" and row["pos"] == "VERB" else None)
    out["examples"] = [dict(r) for r in conn.execute(
        "SELECT es_text AS es, en_text AS en, source FROM example_sentences WHERE lexeme_id = ?"
        " ORDER BY LENGTH(es_text), id LIMIT 10", (row["lexeme_id"],))] if row["kind"] == "WORD" else []

    # The learner's own sentences that use this word or phrase.
    forms_set = _all_forms(verbs, row, seen)
    mine = []
    for s in conn.execute(
        "SELECT st.sentence_text, ss.id AS session_id, ss.created_at FROM study_sentences st"
        " JOIN study_sessions ss ON ss.id = st.study_session_id WHERE ss.user_id = ? ORDER BY ss.id DESC",
        (user_id,),
    ):
        text = s["sentence_text"]
        words = tokens(text)
        if row["kind"] == "PHRASE":
            hit = f" {' '.join(tokens(row['phrase_text']))} " in f" {' '.join(words)} "
        else:
            hit = bool(forms_set & set(words))
        if hit:
            mine.append(dict(s))
        if len(mine) >= 10:
            break
    out["your_sentences"] = mine

    out["sessions"] = [dict(r) for r in conn.execute(
        "SELECT DISTINCT ss.id, ss.created_at, ss.activity_type, ss.context_text FROM bank_entry_concepts b"
        " JOIN study_terms st ON st.concept_id = b.concept_id JOIN study_sessions ss ON ss.id = st.study_session_id"
        " WHERE b.bank_entry_id = ? AND ss.user_id = ? ORDER BY ss.id DESC LIMIT 20", (entry_id, user_id))]

    out["breakdown"] = _breakdown(conn, user_id, form_rows, row) if row["kind"] == "PHRASE" else []

    if row["kind"] == "PHRASE":
        related = conn.execute(
            f"{ENTRY_SELECT} WHERE e.user_id = ? AND e.kind = 'WORD' AND e.id IN ("
            " SELECT bank_entry_id FROM bank_entry_concepts WHERE concept_id = ? AND role = 'IN_PHRASE')",
            (user_id, row["concept_id"]),
        ).fetchall()
        out["words"] = [summary(conn, r) for r in related]
        out["phrases"] = []
    else:
        related = conn.execute(
            f"{ENTRY_SELECT} WHERE e.user_id = ? AND e.kind = 'PHRASE' AND e.concept_id IN ("
            " SELECT concept_id FROM bank_entry_concepts WHERE bank_entry_id = ? AND role = 'IN_PHRASE')",
            (user_id, entry_id),
        ).fetchall()
        out["phrases"] = [summary(conn, r) for r in related]
        out["words"] = []

    out["results"] = [dict(r) for r in conn.execute(
        "SELECT ce.outcome, ce.modality, ce.created_at FROM concept_evidence ce"
        " WHERE ce.evidence_type = 'ASSESSMENT' AND (ce.concept_id = ? OR ce.concept_id IN ("
        "   SELECT concept_id FROM bank_entry_concepts WHERE bank_entry_id = ? AND role = 'TERM'))"
        " ORDER BY ce.id DESC LIMIT 20", (row["concept_id"], entry_id))]
    out["stats"] = {"hits": row["hits"], "partials": row["partials"], "misses": row["misses"], "box": row["box"]}

    sources = []
    if out["senses"]:
        sources.append(ATTRIBUTION["WIKTIONARY"])
    if any(e["source"] == "TATOEBA" for e in out["examples"]):
        sources.append(ATTRIBUTION["TATOEBA"])
    if row["kind"] == "PHRASE" and row["auto_translation"] and not row["user_translation"]:
        sources.append(ATTRIBUTION["MYMEMORY"])  # only when the machine translation is the one shown
    if row["kind"] == "PHRASE" and any(w["entry_id"] and w["translation"] for w in out["breakdown"]):
        sources.append(ATTRIBUTION["WIKTIONARY"])
    if out["conjugation"]:
        sources.append("Conjugations generated with verbecc (LGPL-3.0)")
    out["attribution"] = sources
    return out


def _breakdown(conn: sqlite3.Connection, user_id: int, form_rows, row) -> list[dict]:
    """The phrase read word by word: each word's dictionary form, meaning and, for verbs, who and when.
    This is what makes a phrase page as useful as a word page."""
    words = []
    for f in form_rows:
        if f["form"] == row["phrase_text"]:
            words = json.loads(f["analysis_json"]).get("words", [])
    out = []
    for w in words:
        item = {"surface": w["surface"], "lemma": w["lemma"], "pos": w["pos"], "entry_id": None,
                "translation": None, "readings": []}
        if w["pos"] == "FUNCTION":
            item["translation"] = FUNCTION_GLOSS.get(w["surface"])
        elif w["pos"] != "ENGLISH":
            # Follow a dictionary redirect: "última" is filed under "último".
            lemma = conn.execute(
                "SELECT COALESCE(r.lemma, l.lemma) FROM lexemes l LEFT JOIN lexemes r ON r.id = l.redirect_lexeme_id"
                " WHERE l.language_code = ? AND l.lemma = ?", (LANGUAGE, w["lemma"])).fetchone()
            item["lemma"] = lemma[0] if lemma else w["lemma"]
            entry = conn.execute(
                f"{ENTRY_SELECT} WHERE e.user_id = ? AND e.kind = 'WORD' AND l.lemma = ?", (user_id, item["lemma"])
            ).fetchone()
            if entry:
                item["entry_id"] = entry["id"]
                item["translation"] = translation(entry)
                item["pos"] = entry["pos"] or w["pos"]
            item["readings"] = [describe_form(m["tense"], m["person"]) for m in w.get("forms", [])]
        out.append(item)
    return out


def now_ts() -> str:
    return db.utc_timestamp(datetime.now(timezone.utc))
