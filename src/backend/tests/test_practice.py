"""Question engine units: checking, scheduling and the templates (no HTTP)."""

import random
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.lexicon.verbs import VerbData
from app.practice import check, templates
from app.practice.compose import choose_items
from app.practice.context import EntryCtx, Example, short_gloss
from app.practice.select import pick, schedule

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def verbs(verb_data_path):
    return VerbData(verb_data_path)


def entry(id, headword, kind="WORD", pos=None, translation=None, verbs=None, forms=(), examples=(), **kw):
    e = EntryCtx(id=id, concept_id=id, token=headword, kind=kind, headword=headword, pos=pos,
                 translation=translation, box=kw.get("box", 0), due_at=kw.get("due_at"),
                 last_outcome=kw.get("last_outcome"), tested=kw.get("tested", 0),
                 created_at=kw.get("created_at", "2026-11-01T00:00:00Z"), last_seen_at=kw.get("last_seen_at"))
    if verbs and pos == "VERB":
        e.table = verbs.table(headword)
    e.forms = list(forms)
    e.examples = list(examples)
    e.phrase_words = kw.get("phrase_words", [])
    return e


def extranar(verbs):
    return entry(1, "extrañar", pos="VERB", translation="to miss (someone or something)", verbs=verbs,
                 forms=[("extrañan", {"forms": [{"tense": "pres", "person": "3p"}], "clitics": []})],
                 examples=[Example("Te extrañé.", "I missed you.", "TATOEBA"),
                           Example("Extrañan Boston.", "They miss Boston.", "TATOEBA"),
                           Example("Mis padres me extrañan mucho.", None, "LEARNER")])


def bank(verbs):
    return [
        extranar(verbs),
        entry(2, "maleta", pos="Noun", translation="suitcase", examples=[Example("Necesito la maleta.", "I need the suitcase.", "TATOEBA")]),
        entry(3, "hablar", pos="VERB", translation="to talk; to speak", verbs=verbs),
        entry(4, "te extrañan mucho", kind="PHRASE", translation="They miss you a lot.",
              phrase_words=[{"surface": "te", "lemma": "te", "pos": "FUNCTION"},
                            {"surface": "extrañan", "lemma": "extrañar", "pos": "VERB"},
                            {"surface": "mucho", "lemma": "mucho", "pos": None}]),
        entry(5, "y", pos="FUNCTION"),
    ]


# ---------------------------------------------------------------- checking


@pytest.mark.parametrize("answer,outcome", [
    ("extrañábamos", "HIT"), ("Extrañábamos.", "HIT"), ("extranabamos", "PARTIAL"), ("extrañamos", "MISS"), ("", "MISS"),
])
def test_typed_answers(answer, outcome):
    assert check.typed(answer, ["extrañábamos"])[0] == outcome


def test_word_order_and_dictation():
    assert check.order("te extrañan mucho", "te extrañan mucho")[0] == "HIT"
    assert check.order("extrañan te mucho", "te extrañan mucho")[0] == "MISS"
    assert check.dictation("te extrane", "Te extrañé.") == ("HIT", "accents")
    assert check.dictation("mis padres me extrañan", "Mis padres me extrañan mucho.")[0] == "PARTIAL"
    assert check.dictation("hola", "Mis padres me extrañan mucho.")[0] == "MISS"


def test_short_gloss():
    assert short_gloss("to talk; to speak; to communicate") == "to talk"
    assert short_gloss("to miss (someone or something)") == "to miss"
    assert short_gloss("(informal) hi") == "hi"
    assert short_gloss(None) is None


# ---------------------------------------------------------------- scheduling


def test_pick_prefers_weak_then_fresh_then_oldest_due_and_skips_function_words(verbs):
    stamp = lambda d: db.utc_timestamp(NOW - timedelta(days=d))  # noqa: E731
    entries = [
        entry(1, "viejo", due_at=stamp(30), tested=3, box=2),  # old and due
        entry(2, "debil", due_at=stamp(1), tested=2, last_outcome="MISS", box=1),
        entry(3, "nuevo", due_at=stamp(0), tested=0, last_seen_at=stamp(0)),
        entry(4, "fuerte", due_at=db.utc_timestamp(NOW + timedelta(days=9)), tested=5, box=5),  # not due
        entry(5, "y", pos="FUNCTION", due_at=stamp(40)),
    ]
    chosen = [e.headword for e in pick(entries, NOW, 3, random.Random(1))]
    assert chosen == ["debil", "nuevo", "viejo"]
    assert "y" not in [e.headword for e in pick(entries, NOW, 10, random.Random(1))]


def test_schedule_moves_entries_between_boxes(tmp_path):
    conn = db.connect(tmp_path / "s.db")
    db.migrate(conn)
    conn.execute("INSERT INTO users (username, password_hash) VALUES ('owner', 'x')")
    conn.execute("INSERT INTO concepts (language_code, token, category) VALUES ('es', 'x', 'LEMMA')")
    conn.execute("INSERT INTO lexemes (language_code, lemma) VALUES ('es', 'x')")
    conn.execute("INSERT INTO bank_entries (user_id, concept_id, kind, lexeme_id) VALUES (1, 1, 'WORD', 1)")
    row = lambda: conn.execute("SELECT box, due_at, hits, misses, last_outcome FROM bank_entries").fetchone()  # noqa: E731
    schedule(conn, 1, "HIT", NOW)
    schedule(conn, 1, "HIT", NOW)
    assert row()["box"] == 2 and row()["due_at"] == db.utc_timestamp(NOW + timedelta(days=2))
    schedule(conn, 1, "MISS", NOW)
    assert (row()["box"], row()["due_at"], row()["misses"], row()["last_outcome"]) == (1, db.utc_timestamp(NOW), 1, "MISS")


# ---------------------------------------------------------------- templates


def build(name, e, entries, seed=0):
    return templates.BUILDERS[name](e, templates.Pool(entries), random.Random(seed))


def test_form_id_asks_who_and_when_and_never_offers_a_second_right_answer(verbs):
    entries = bank(verbs)
    item = build("FORM_ID", entries[0], entries)
    assert item.payload["spanish"] == "extrañan" and "they / you all · present" in item.payload["options"]
    hablamos = entry(9, "hablar", pos="VERB", translation="to talk", verbs=verbs,
                     forms=[("hablamos", {"forms": [{"tense": "pres", "person": "nos"}], "clitics": []})])
    for seed in range(10):
        item = build("FORM_ID", hablamos, entries + [hablamos], seed)
        assert "we · preterite" not in [o for o in item.payload["options"] if o not in item.answer["accept"]]
        assert sum(o in item.answer["accept"] for o in item.payload["options"]) == 1


def test_conjugate_asks_for_a_new_person_and_accepts_the_table_form(verbs):
    entries = bank(verbs)
    item = build("CONJUGATE", entries[0], entries)
    assert item.modality == "WRITING" and item.skill == "GRAMMAR"
    assert "extrañar" in item.prompt and item.answer["accept"][0].startswith("extrañ")


def test_cloze_blanks_a_conjugated_form_and_hints_the_infinitive(verbs):
    entries = bank(verbs)
    for seed in range(6):
        item = build("CLOZE", entries[0], entries, seed)
        assert item.payload["hint"] == "extrañar"
        gap = item.answer["accept"][0]
        assert gap.casefold() != "extrañar" and gap not in item.payload["cloze"]["before"] + item.payload["cloze"]["after"]
    phrase = build("CLOZE", entries[3], entries)
    assert phrase.payload["translation"] == "They miss you a lot."
    assert phrase.answer["accept"][0] in ("extrañan", "mucho")


def test_meaning_and_sentence_questions_include_the_right_answer_once(verbs):
    entries = bank(verbs)
    item = build("MEANING_MC", entries[1], entries)
    assert item.payload["options"].count("suitcase") == 1 and len(item.payload["options"]) == 4
    item = build("SENTENCE_MEANING", entries[0], entries)
    assert item.answer["accept"][0] in item.payload["options"]
    tf = build("TRANSLATION_TF", entries[0], entries)
    assert tf.payload["options"] == ["True", "False"] and tf.answer["accept"][0] in ("True", "False")


def test_listening_options_sound_different(verbs):
    entries = bank(verbs)
    for seed in range(8):
        item = build("LISTEN_PICK", entries[0], entries, seed)
        plain = [check.plain(o) for o in item.payload["options"]]
        assert len(plain) == len(set(plain)) and item.payload["tts"] in item.payload["options"]


def test_scramble_shuffles_and_phrases_never_get_free_writing(verbs):
    entries = bank(verbs)
    item = build("SCRAMBLE", entries[3], entries)
    assert sorted(item.payload["tiles"]) == sorted(["te", "extrañan", "mucho"])
    assert item.payload["tiles"] != ["te", "extrañan", "mucho"]
    assert build("WRITE", entries[3], entries) is None
    assert build("WRITE", entries[4], entries) is None  # function word
    assert "a form of “extrañar” (to miss)." in build("WRITE", entries[0], entries).prompt


def test_missing_data_means_no_question_not_a_bad_one(verbs):
    bare = entry(7, "palabra")  # no meaning, no examples, not a verb
    entries = [bare]
    for name in ("MEANING_MC", "REVERSE_MC", "FORM_ID", "CONJUGATE", "CLOZE", "SENTENCE_MEANING", "TRANSLATION_TF", "DICTATION"):
        assert build(name, bare, entries) is None, name


def test_a_small_bank_still_gets_a_quiz_but_never_a_padded_one(verbs):
    entries = bank(verbs)
    items = choose_items(entries, n=10, focus="MIXED", listening=True, allow_write=True, now=NOW, rng=random.Random(3))
    assert len(items) == 4  # four usable entries (the function word is skipped): one question each
    assert len({i.entry.id for i in items}) == 4
    assert sum(i.item_type == "WRITE" for i in items) <= 1


def test_migration_v6_rebuilds_xp_events_without_losing_a_row(tmp_path):
    conn = db.connect(tmp_path / "m.db")
    for number, sql in enumerate(db.MIGRATIONS[:5], start=1):
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    conn.execute("INSERT INTO users (username, password_hash) VALUES ('owner', 'x')")
    rows = [(1, "STUDY_SESSION", 1, 20, 1.0, 20, "2026-11-01"), (1, "ASSESSMENT", 1, 9, 1.05, 9, "2026-11-02")]
    conn.executemany("INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp, local_date)"
                     " VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.execute("INSERT INTO assessments (user_id, language_code, status) VALUES (1, 'es', 'GRADED')")
    conn.commit()
    db.migrate(conn)
    got = conn.execute("SELECT user_id, source_type, source_id, base_xp, multiplier, awarded_xp, local_date FROM xp_events ORDER BY id").fetchall()
    assert [tuple(r) for r in got] == rows
    conn.execute("INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp) VALUES (1, 'WARMUP', 1, 5, 1, 5)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp) VALUES (1, 'ASSESSMENT', 1, 1, 1, 1)")
    assert conn.execute("SELECT kind, focus FROM assessments").fetchone()[:] == ("QUICK", "SENTENCES")
