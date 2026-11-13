"""Word bank: analysis, online sources (faked), enrichment and the /api/bank endpoints."""

import json
from contextlib import closing

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db
from app.lexicon import cache
from app.lexicon.analyze import analyze
from app.lexicon.sources import LexiconSources, SourceUnavailable
from app.lexicon.verbs import VerbData
from app.main import create_app

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, set_owner_password, sign_in


@pytest.fixture(scope="module")
def verbs(verb_data_path):
    return VerbData(verb_data_path)


# ---------------------------------------------------------------- analysis


def forms(word):
    return [(f.tense, f.person) for f in word.forms]


def test_extranan_is_third_person_plural_present_of_extranar(verbs):
    a = analyze("extrañan", verbs)
    assert a.kind == "WORD"
    assert (a.head.lemma, a.head.pos) == ("extrañar", "VERB")
    assert forms(a.head) == [("pres", "3p")]


def test_phrase_keeps_function_words_as_context(verbs):
    a = analyze("Te extrañan mucho", verbs)
    assert a.kind == "PHRASE"
    assert [(w.surface, w.lemma, w.pos) for w in a.words] == [
        ("te", "te", "FUNCTION"), ("extrañan", "extrañar", "VERB"), ("mucho", "mucho", None),
    ]
    assert [w.lemma for w in a.content_words] == ["extrañar", "mucho"]


@pytest.mark.parametrize("text,lemma,expected", [
    ("fui", "ir", ("pret", "yo")),
    ("hablaríamos", "hablar", ("cond", "nos")),
    ("dijeron", "decir", ("pret", "3p")),
    ("extrañábamos", "extrañar", ("impf", "nos")),
])
def test_irregular_and_compound_endings(verbs, text, lemma, expected):
    head = analyze(text, verbs).head
    assert head.lemma == lemma and expected in forms(head)


def test_ambiguous_forms_list_every_reading(verbs):
    head = analyze("hablamos", verbs).head
    assert {("pres", "nos"), ("pret", "nos")} <= set(forms(head))
    assert analyze("fui", verbs).head.alternatives == ["ser"]


def test_attached_pronouns_are_split_off(verbs):
    head = analyze("extrañarte", verbs).head
    assert (head.lemma, head.clitics, forms(head)) == ("extrañar", ["te"], [("inf", None)])
    head = analyze("dímelo", verbs).head
    assert (head.lemma, head.clitics) == ("decir", ["me", "lo"])


def test_no_verb_reading_after_a_determiner(verbs):
    assert analyze("mi casa", verbs).words[1].pos is None


def test_unknown_word_and_missing_verb_data_degrade_gracefully(tmp_path):
    no_data = VerbData(tmp_path / "missing.db")
    head = analyze("extrañan", no_data).head
    assert (head.lemma, head.pos, head.forms) == ("extrañan", None, [])


# ---------------------------------------------------------------- sources (HTTP faked)

WIKTIONARY = {
    "extrañar": {"es": [{"partOfSpeech": "Verb", "language": "Spanish", "definitions": [
        {"definition": 'to <a href="/wiki/miss">miss</a> <span class="mention-gloss">(someone or something)</span> [with a]',
         "parsedExamples": [{"example": "<b>Te extraño</b> mucho.", "translation": "I miss you a lot."}]},
        {"definition": 'to find <style data-mw-deduplicate="x">.mw-parser-output .x{font-style:italic}</style>odd/strange'},
    ]}]},
    "maletas": {"es": [{"partOfSpeech": "Noun", "definitions": [{"definition":
        '<span class="form-of-definition use-with-mention">plural of <span class="form-of-definition-link">'
        '<i lang="es"><a href="/wiki/maleta#Spanish">maleta</a></i></span></span>'}]}]},
    "maleta": {"es": [{"partOfSpeech": "Noun", "definitions": [{"definition": "suitcase"}]}]},
    "mucho": {"es": [{"partOfSpeech": "Adverb", "definitions": [{"definition": "much, a lot"}]}]},
    "casa": {"es": [{"partOfSpeech": "Noun", "definitions": [{"definition": "house"}]},
                    {"partOfSpeech": "Verb", "definitions": [{"definition":
                        '<span class="form-of-definition">third-person singular present of '
                        '<span class="form-of-definition-link"><a href="/wiki/casar">casar</a></span></span>'}]}]},
}
TATOEBA = {"data": [
    {"id": 1, "text": "Extraño.", "translations": [[{"lang": "eng", "text": "Strange."}]]},
    {"id": 2, "text": "Extrañan Boston.", "translations": [[{"lang": "eng", "text": "They miss Boston."}]]},
    {"id": 3, "text": "Te extrañé.", "translations": [[{"lang": "eng", "text": "I missed you."}]]},
    {"id": 4, "text": "¿Me extrañaste?", "translations": [[], [{"lang": "eng", "text": "Did you miss me?"}]]},
    {"id": 5, "text": "Somos extrañas.", "translations": [[{"lang": "eng", "text": "We're strange."}]]},
    {"id": 6, "text": "No hay traducción.", "translations": [[{"lang": "fra", "text": "Pas d'anglais."}]]},
]}


def fake_web(request: httpx.Request) -> httpx.Response:
    url = request.url
    if url.host == "en.wiktionary.org":
        word = url.path.rsplit("/", 1)[-1]
        from urllib.parse import unquote

        body = WIKTIONARY.get(unquote(word))
        return httpx.Response(200, json=body) if body else httpx.Response(404)
    if url.host == "api.tatoeba.org":
        return httpx.Response(200, json=TATOEBA if url.params["q"] == "extrañar" else {"data": []})
    if url.host == "api.mymemory.translated.net":
        q = url.params["q"]
        return httpx.Response(200, json={"responseStatus": 200, "quotaFinished": False,
                                         "responseData": {"translatedText": f"EN({q})"}})
    return httpx.Response(500)


def sources(handler=fake_web, enabled=True):
    return LexiconSources(enabled, transport=httpx.MockTransport(handler))


def test_wiktionary_glosses_examples_and_form_of_links():
    s = sources()
    entry = s.wiktionary("extrañar")["entries"][0]
    assert entry["pos"] == "Verb" and entry["form_of"] == []
    assert entry["senses"][0]["gloss"] == "to miss (someone or something)"
    assert entry["senses"][0]["examples"] == [{"es": "Te extraño mucho.", "en": "I miss you a lot."}]
    assert entry["senses"][1]["gloss"] == "to find odd/strange"  # inline template CSS dropped
    assert s.wiktionary("maletas")["entries"][0]["form_of"] == ["maleta"]
    assert s.wiktionary("zzzz") is None


def test_tatoeba_keeps_only_sentences_with_an_english_translation():
    got = sources().tatoeba("extrañar")
    assert [g["es"] for g in got][:2] == ["Extraño.", "Extrañan Boston."]
    assert "No hay traducción." not in [g["es"] for g in got]
    assert got[3]["en"] == "Did you miss me?"  # translation in a later group


def test_failing_source_raises_unavailable_and_opens_the_breaker():
    calls = []

    def down(request):
        calls.append(request)
        raise httpx.ConnectError("down")

    s = sources(down)
    for _ in range(5):
        with pytest.raises(SourceUnavailable):
            s.wiktionary("hola")
    assert len(calls) == 3  # the breaker skips the rest


def test_disabled_sources_never_touch_the_network():
    s = sources(lambda r: pytest.fail("network used"), enabled=False)
    with pytest.raises(SourceUnavailable):
        s.translate("hola")


def test_cache_fetches_once_and_keeps_good_data_through_outages(tmp_path):
    conn = db.connect(tmp_path / "c.db")
    db.migrate(conn)
    calls = []

    def fetch():
        calls.append(1)
        return {"x": 1}

    assert cache.cached(conn, "T", "k", fetch) == ("ok", {"x": 1})
    assert cache.cached(conn, "T", "k", fetch) == ("ok", {"x": 1})
    assert len(calls) == 1

    def broken():
        raise SourceUnavailable("down")

    conn.execute("UPDATE lookup_cache SET fetched_at = '2000-01-01T00:00:00Z'")
    conn.commit()
    assert cache.cached(conn, "T", "k", broken) == ("ok", {"x": 1})  # stale but good
    assert cache.cached(conn, "T", "other", broken) == ("error", None)


# ---------------------------------------------------------------- API


def make_client(settings, source_fake):
    app = create_app(settings, sources=source_fake, enrich_inline=True)
    client = TestClient(app)
    client.__enter__()
    set_owner_password(settings, BOOTSTRAP_PASSWORD)
    sign_in(client, BOOTSTRAP_PASSWORD)
    client.post("/api/auth/change-password",
                json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD})
    return client


@pytest.fixture
def online(settings):
    client = make_client(settings, sources())
    yield client
    client.__exit__(None, None, None)


@pytest.fixture
def offline(settings):
    client = make_client(settings, sources(enabled=False))
    yield client
    client.__exit__(None, None, None)


def log_session(client, terms, sentences=("Mis padres me extrañan mucho.", "Necesito la maleta.")):
    r = client.post("/api/study-sessions", json={
        "mode": "SELF_STUDY", "activity_type": "LISTENING", "duration_minutes": 10,
        "context_text": "Una canción", "terms": list(terms), "sentences": list(sentences),
    })
    assert r.status_code == 201, r.text
    return r.json()


def entry(client, headword):
    items = client.get("/api/bank", params={"limit": 200}).json()["items"]
    found = [i for i in items if i["headword"] == headword]
    assert found, f"{headword!r} not in {[i['headword'] for i in items]}"
    return found[0]


def test_logged_word_becomes_an_entry_with_meaning_forms_and_conjugation(online):
    log_session(online, ["extrañan", "te extrañan mucho", "maletas"])
    e = entry(online, "extrañar")
    assert e["kind"] == "WORD" and e["pos"] == "VERB" and e["forms_seen"] == ["extrañan"]
    assert e["translation"] == "to miss (someone or something)" and e["strength"] == "new"

    d = online.get(f"/api/bank/{e['id']}").json()
    assert d["forms"][0]["form"] == "extrañan"
    analysis = d["forms"][0]["analyses"][0]
    assert analysis["tense_label"] == "present" and analysis["who"] == "they / you all"
    present = next(r for r in d["conjugation"]["rows"] if r["tense"] == "pres")
    assert present["cells"]["3p"] == ["extrañan"] and present["cells"]["nos"] == ["extrañamos"]
    assert "extrañan" in d["conjugation"]["seen"]
    # Examples really use the verb, meaning-matching ones first; 'Extraño.' = 'Strange.' is dropped.
    es = [x["es"] for x in d["examples"]]
    assert "Extrañan Boston." in es and "Te extraño mucho." in es and "Extraño." not in es
    assert d["your_sentences"][0]["sentence_text"] == "Mis padres me extrañan mucho."
    assert [p["headword"] for p in d["phrases"]] == ["te extrañan mucho"]
    assert any("Wiktionary" in a for a in d["attribution"])


def test_phrase_entry_has_a_translation_and_links_its_words(online):
    log_session(online, ["te extrañan mucho", "poder", "viajar"])
    p = entry(online, "te extrañan mucho")
    assert p["kind"] == "PHRASE" and p["translation"] == "EN(te extrañan mucho)"
    d = online.get(f"/api/bank/{p['id']}").json()
    assert sorted(w["headword"] for w in d["words"]) == ["extrañar", "mucho"]
    assert d["conjugation"] is None
    assert any("Machine translation" in a for a in d["attribution"])


def test_inflected_noun_redirects_to_its_dictionary_form(online, raw_db):
    log_session(online, ["maletas", "poder", "viajar"])
    log_session(online, ["las maletas", "comer", "dormir"])
    phrase = online.get(f"/api/bank/{entry(online, 'las maletas')['id']}").json()
    assert phrase["breakdown"][1]["lemma"] == "maleta" and phrase["breakdown"][1]["translation"] == "suitcase"
    e = entry(online, "maleta")
    assert e["translation"] == "suitcase" and e["forms_seen"] == ["maletas"]
    assert "maletas" not in [i["headword"] for i in online.get("/api/bank").json()["items"]]
    log_session(online, ["maleta", "comer", "vivir"])  # the same entry, not a new one
    assert sum(i["headword"] == "maleta" for i in online.get("/api/bank").json()["items"]) == 1


def test_noun_after_la_is_not_read_as_a_verb(online, raw_db):
    log_session(online, ["la casa", "poder", "viajar"])
    d = online.get(f"/api/bank/{entry(online, 'la casa')['id']}").json()
    assert [w["headword"] for w in d["words"]] == ["casa"]
    assert "casar" not in [i["headword"] for i in online.get("/api/bank").json()["items"]]
    analysis = json.loads(raw_db.execute("SELECT analysis_json FROM bank_forms WHERE form = 'la casa'").fetchone()[0])
    assert analysis["words"][1]["pos"] == "Noun" and analysis["words"][1]["forms"] == []


def test_offline_bank_still_works_and_says_lookups_are_off(offline):
    log_session(offline, ["extrañan", "te extrañan mucho", "maletas"])
    e = entry(offline, "extrañar")
    assert e["lookup_status"] == "offline" and e["translation"] is None
    d = offline.get(f"/api/bank/{e['id']}").json()
    assert d["conjugation"]["rows"]  # local data needs no network
    assert entry(offline, "te extrañan mucho")["lookup_status"] == "offline"


def test_search_sort_and_filters(online):
    log_session(online, ["extrañan", "te extrañan mucho", "maletas"])
    by_form = online.get("/api/bank", params={"q": "extrañan"}).json()["items"]
    assert {i["headword"] for i in by_form} == {"extrañar", "te extrañan mucho"}
    by_meaning = online.get("/api/bank", params={"q": "suitcase"}).json()["items"]
    assert [i["headword"] for i in by_meaning] == ["maleta"]
    phrases = online.get("/api/bank", params={"kind": "PHRASE"}).json()
    assert phrases["total"] == 1
    alpha = [i["headword"] for i in online.get("/api/bank", params={"sort": "alpha"}).json()["items"]]
    assert alpha == sorted(alpha, key=str.casefold)


def test_learner_can_set_their_own_translation(online):
    log_session(online, ["extrañan", "poder", "viajar"])
    e = entry(online, "extrañar")
    d = online.patch(f"/api/bank/{e['id']}", json={"user_translation": "to miss someone", "note": "from the song"}).json()
    assert d["translation"] == "to miss someone" and d["note"] == "from the song"
    d = online.patch(f"/api/bank/{e['id']}", json={"user_translation": ""}).json()
    assert d["translation"] == "to miss (someone or something)"
    assert online.patch(f"/api/bank/{e['id']}", json={"bogus": 1}).status_code == 422
    assert online.get("/api/bank/9999").status_code == 404


def test_lookup_preview_before_saving(online):
    r = online.get("/api/lookup", params={"term": "te extrañan mucho"}).json()
    assert r["kind"] == "PHRASE" and r["translation"] == "EN(te extrañan mucho)"
    verb = r["words"][0]
    assert verb["lemma"] == "extrañar" and verb["translation"].startswith("to miss")
    assert verb["forms"][0]["summary"] == "ellos / ellas / ustedes · present"
    word = online.get("/api/lookup", params={"term": "maletas"}).json()["words"][0]
    assert word["translation"] == "suitcase"


def test_bank_requires_sign_in(client):
    assert client.get("/api/bank").status_code == 401
    assert client.get("/api/lookup", params={"term": "hola"}).status_code == 401


def test_terms_logged_before_the_bank_existed_are_backfilled(settings, verb_data_path):
    client = make_client(settings, sources(enabled=False))
    log_session(client, ["extrañan", "poder", "viajar"])
    client.__exit__(None, None, None)
    with closing(db.connect(settings.db_path)) as conn, conn:
        conn.execute("DELETE FROM bank_entries")  # as if saved by the Level 1 app
    client = make_client(settings, sources(enabled=False))
    try:
        headwords = {i["headword"] for i in client.get("/api/bank").json()["items"]}
        assert {"extrañar", "poder", "viajar"} <= headwords
    finally:
        client.__exit__(None, None, None)


def test_a_word_bank_failure_never_loses_the_session(online, monkeypatch, raw_db):
    from app.lexicon import bank

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(bank, "ingest_term", boom)
    log_session(online, ["extrañan", "poder", "viajar"])
    assert raw_db.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0] == 1
    assert raw_db.execute("SELECT COUNT(*) FROM bank_entries").fetchone()[0] == 0


def test_migration_keeps_existing_data(tmp_path):
    conn = db.connect(tmp_path / "m.db")
    for number, sql in enumerate(db.MIGRATIONS[:4], start=1):
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    conn.execute("INSERT INTO users (username, password_hash) VALUES ('owner', 'x')")
    conn.execute("INSERT INTO xp_events (user_id, source_type, source_id, base_xp, multiplier, awarded_xp, local_date)"
                 " VALUES (1, 'STUDY_SESSION', 1, 20, 1, 20, '2026-11-01')")
    conn.commit()
    assert db.migrate(conn) == len(db.MIGRATIONS)
    assert conn.execute("SELECT SUM(awarded_xp) FROM xp_events").fetchone()[0] == 20
    assert json.loads(conn.execute("SELECT '[]'").fetchone()[0]) == []


# ---------------------------------------------------------------- what people actually type

from app.lexicon.parse import parse_term  # noqa: E402


@pytest.mark.parametrize("text,spanish,meaning", [
    ("phrase: pero queriendo volver a la última vez - but, wanting to go back to the last time",
     "pero queriendo volver a la última vez", "but, wanting to go back to the last time"),
    ("extrañan = they miss", "extrañan", "they miss"),
    ("te extraño (I miss you)", "te extraño", "I miss you"),
    ("miss you - te extraño", "te extraño", "miss you"),
    ("Word: maletas — suitcases", "maletas", "suitcases"),
    ("¿qué tal?", "¿qué tal?", None),
    ("son", "son", None),
    ("the", "", "the"),
])
def test_labels_and_english_meanings_are_split_off(verbs, text, spanish, meaning):
    p = parse_term(text, verbs)
    assert (p.spanish, p.meaning) == (spanish, meaning)


def test_a_labelled_phrase_with_its_english_meaning_makes_no_english_entries(online):
    term = "phrase: pero queriendo volver a la última vez - but, wanting to go back to the last time"
    log_session(online, [term, "poder", "the"])
    heads = {i["headword"] for i in online.get("/api/bank", params={"limit": 200}).json()["items"]}
    assert "pero queriendo volver a la última vez" in heads and {"querer", "volver", "poder"} <= heads
    assert not heads & {"the", "back", "last", "go", "to", "wanting", "but"}
    assert not any("phrase:" in h or " - " in h for h in heads)
    p = entry(online, "pero queriendo volver a la última vez")
    assert p["translation"] == "but, wanting to go back to the last time"  # theirs, not a machine's
    d = online.get(f"/api/bank/{p['id']}").json()
    words = {w["surface"]: w for w in d["breakdown"]}
    assert words["queriendo"]["lemma"] == "querer" and words["queriendo"]["readings"][0]["tense"] == "ger"
    assert words["queriendo"]["entry_id"] and words["pero"]["translation"] == "but"
    assert words["la"]["pos"] == "FUNCTION"
    assert not any("Machine translation" in a for a in d["attribution"])  # the translation shown is theirs


def test_a_word_with_a_meaning_keeps_it_on_the_form(online):
    log_session(online, ["extrañan - they miss", "viajar - to travel", "poder"])
    d = online.get(f"/api/bank/{entry(online, 'extrañar')['id']}").json()
    assert d["forms"][0]["meaning"] == "they miss"
    assert d["user_translation"] is None  # "they miss" is the form, not the infinitive
    assert entry(online, "viajar")["translation"] == "to travel"


def test_a_phrase_can_be_saved_as_words_only(online):
    r = online.post("/api/study-sessions", json={
        "mode": "SELF_STUDY", "activity_type": "LISTENING", "duration_minutes": 10, "context_text": "x",
        "terms": ["te extrañan mucho", "poder", "viajar"], "sentences": ["Uno.", "Dos."],
        "words_only": ["te extrañan mucho"],
    })
    assert r.status_code == 201
    bank_ = online.get("/api/bank").json()
    assert bank_["counts"] == {"WORD": 4, "PHRASE": 0}
    assert "extrañar" in {i["headword"] for i in bank_["items"]}
    bad = online.post("/api/study-sessions", json={
        "mode": "SELF_STUDY", "activity_type": "LISTENING", "duration_minutes": 10, "context_text": "x",
        "terms": ["a b", "poder", "viajar"], "sentences": ["Uno.", "Dos."], "words_only": ["not a term"]})
    assert bad.status_code == 422


def test_the_preview_warns_about_english(online):
    r = online.get("/api/lookup", params={"term": "the"}).json()
    assert r["english_only"] is True
    r = online.get("/api/lookup", params={"term": "extrañan - they miss"}).json()
    assert r["meaning"] == "they miss" and r["words"][0]["lemma"] == "extrañar"


def test_startup_repairs_terms_saved_before_parsing(settings):
    """The owner's real case: English words from a labelled phrase had become entries."""
    client = make_client(settings, sources(enabled=False))
    term = "phrase: pero queriendo volver a la última vez - but, wanting to go back to the last time"
    log_session(client, [term, "poder", "viajar"])
    client.__exit__(None, None, None)
    with closing(db.connect(settings.db_path)) as conn, conn:
        # Recreate the old, wrong state: the whole raw text as one phrase, plus English word entries.
        cid = conn.execute("SELECT concept_id FROM study_terms WHERE original_text = ?", (term,)).fetchone()[0]
        conn.execute("DELETE FROM bank_entry_concepts WHERE concept_id = ?", (cid,))
        conn.execute("INSERT INTO bank_entries (user_id, concept_id, kind, phrase_text) VALUES (1, ?, 'PHRASE', ?)",
                     (cid, term.casefold()))
        conn.execute("INSERT INTO bank_entry_concepts VALUES (last_insert_rowid(), ?, 'TERM')", (cid,))
        for w in ("the", "back", "go"):
            conn.execute("INSERT OR IGNORE INTO lexemes (language_code, lemma) VALUES ('es', ?)", (w,))
            conn.execute("INSERT OR IGNORE INTO concepts (language_code, token, category) VALUES ('es', ?, 'LEMMA')", (w,))
            conn.execute("INSERT INTO bank_entries (user_id, concept_id, kind, lexeme_id) SELECT 1, c.id, 'WORD', l.id"
                         " FROM concepts c, lexemes l WHERE c.token = ? AND c.category = 'LEMMA' AND l.lemma = ?", (w, w))
            conn.execute("INSERT INTO bank_entry_concepts SELECT last_insert_rowid(), ?, 'IN_PHRASE'", (cid,))
        conn.execute("INSERT OR IGNORE INTO pending_jobs VALUES ('reparse_word_bank')")
    client = make_client(settings, sources(enabled=False))
    try:
        heads = {i["headword"] for i in client.get("/api/bank", params={"limit": 200}).json()["items"]}
        assert "pero queriendo volver a la última vez" in heads and "querer" in heads
        assert not heads & {"the", "back", "go"} and term.casefold() not in heads
        with closing(db.connect(settings.db_path)) as conn:
            assert conn.execute("SELECT COUNT(*) FROM pending_jobs").fetchone()[0] == 0
    finally:
        client.__exit__(None, None, None)
