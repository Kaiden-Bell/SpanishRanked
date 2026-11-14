"""Guided study: the syllabus, content packs, unit progress and unit quizzes."""

import json
import random
from collections import Counter
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.curriculum import packs, progress, syllabus
from app.lexicon.verbs import VerbData
from app.main import create_app
from app.practice.compose import choose_items

from conftest import BOOTSTRAP_PASSWORD, NEW_PASSWORD, set_owner_password, sign_in
from test_assessments import FakeGrammar, FakeModel, correct_answer, log_study
from test_practice import entry


@pytest.fixture
def api(settings):
    with TestClient(create_app(settings, model=FakeModel(), grammar=FakeGrammar())) as c:
        set_owner_password(settings, BOOTSTRAP_PASSWORD)
        sign_in(c, BOOTSTRAP_PASSWORD)
        c.post("/api/auth/change-password", json={"current_password": BOOTSTRAP_PASSWORD, "new_password": NEW_PASSWORD})
        yield c


def guided(api, unit_id, **overrides):
    body = {"mode": "GUIDED_STUDY", "unit_id": unit_id, "activity_type": "READING",
            "context_text": f"Guided lesson {unit_id}"} | overrides
    return log_study(api, **body)


def unit(overview, unit_id):
    return next(u for u in overview["units"] if u["id"] == unit_id)


# ---------------------------------------------------------------- syllabus


def test_the_bundled_syllabus_is_valid_and_ordered():
    syl = syllabus.load()
    assert len(syl.units) == 48 and [u.n for u in syl.units] == list(range(1, 49))
    assert [u.id for u in syl.units] == [f"u{i:02d}" for i in range(1, 49)]
    assert {u.stage for u in syl.units} == {1, 2, 3, 4}
    # The research anchors: present before preterite before imperfect before the contrast; subjunctive late.
    first = {t: min(u.n for u in syl.units if t in u.tenses) for t in ("pres", "pret", "impf", "subj_pres")}
    assert first["pres"] < first["pret"] < first["impf"] < first["subj_pres"]
    assert syl.get("u26").tenses == ("pret", "impf") and syl.get("u37").stage == 4


@pytest.mark.parametrize("change,message", [
    (lambda d: d["units"][1].update(tenses=["aorist"]), "unknown tense"),
    (lambda d: d["units"][0].update(prereqs=["u02"]), "not earlier units"),
    (lambda d: d["units"][1].update(id="u01"), "duplicate"),
    (lambda d: d["units"][0].update(confidence="vibes"), "confidence"),
])
def test_a_broken_syllabus_is_rejected(change, message):
    data = json.loads(syllabus.PATH.read_text(encoding="utf-8"))
    change(data)
    with pytest.raises(syllabus.SyllabusError, match=message):
        syllabus.parse(data)


# ---------------------------------------------------------------- content packs


def test_the_bundled_pack_loads_cleanly_and_is_redistributable():
    result = packs.load_all(syllabus.load())
    assert result.problems == []
    chevere = result.get("chevere")
    assert chevere and chevere.bundled and chevere.manifest["license"]["code"] == "CC BY 4.0"
    # Only CC BY and CC BY-SA text may ship in the image; NonCommercial or NoDerivatives never.
    assert {s.license["code"] for s in chevere.sections.values()} <= {"CC BY 4.0", "CC BY-SA 4.0"}
    assert all(s.extra_attribution for s in chevere.sections.values() if s.license["code"] == "CC BY-SA 4.0")
    assert len(chevere.units) >= 30
    for s in chevere.sections.values():
        text = s.text()
        assert text.startswith("# ") and "<img" not in text and "Candela Citations" not in text


def test_lesson_sections_put_context_before_the_rule_and_words_after():
    chevere = packs.load_all(syllabus.load()).get("chevere")
    kinds = [s.kind for s in packs.lesson_sections(chevere, "u19")]
    assert kinds == sorted(kinds, key=packs.KIND_ORDER.get) and kinds[0] == "context" and "grammar" in kinds


def write_pack(folder, *, license={"code": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
               units=None, pack_id="mine"):
    (folder / "sections").mkdir(parents=True)
    (folder / "sections" / "ser.md").write_text("# Ser\n\nYo soy.\n", encoding="utf-8")
    manifest = {"id": pack_id, "title": "My notes"}
    if license:
        manifest["license"] = license
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "sections.json").write_text(json.dumps([{"path": "ser.md", "title": "Ser", "kind": "grammar"}]), encoding="utf-8")
    (folder / "map.json").write_text(json.dumps({"units": units or {"u03": ["ser.md"]}}), encoding="utf-8")


def test_user_packs_load_from_the_data_dir_and_bad_ones_are_skipped(tmp_path):
    root = tmp_path / "packs"
    write_pack(root / "good")
    write_pack(root / "no-license", license=None, pack_id="a")
    write_pack(root / "bad-unit", units={"u99": ["ser.md"]}, pack_id="b")
    write_pack(root / "bad-path", units={"u03": ["../../etc/passwd"]}, pack_id="c")
    result = packs.load_all(syllabus.load(), [root])
    assert [p.id for p in result.packs] == ["chevere", "mine"]
    assert not result.get("mine").bundled and len(result.problems) == 3
    assert {p.id for p in result.covering("u03")} == {"chevere", "mine"}


# ---------------------------------------------------------------- progress API


def test_a_new_learner_starts_at_unit_one_and_later_units_are_locked(api):
    body = api.get("/api/guided").json()
    assert len(body["units"]) == 48 and {u["status"] for u in body["units"]} == {"new"}
    assert unit(body, "u01")["unlocked"] and not unit(body, "u02")["unlocked"]
    assert body["suggestion"] == {"unit_id": "u01", "reason": "Start here."}
    assert body["packs"][0]["id"] == "chevere" and unit(body, "u19")["has_lesson"] and not unit(body, "u37")["has_lesson"]


def test_logging_a_guided_lesson_starts_the_unit_and_deleting_it_undoes_that(api):
    session = guided(api, "u01", terms=["hola", "gracias", "llamar"])
    assert session["mode"] == "GUIDED_STUDY" and session["unit_id"] == "u01"
    body = api.get("/api/guided").json()
    assert unit(body, "u01")["status"] == "started" and unit(body, "u01")["lessons"] == 1
    assert unit(body, "u02")["unlocked"]
    assert body["suggestion"]["unit_id"] == "u01" and "Practise" in body["suggestion"]["reason"]
    assert api.get("/api/study-sessions").json()["items"][0]["unit_id"] == "u01"

    assert api.delete(f"/api/study-sessions/{session['id']}").status_code in (200, 204)
    assert unit(api.get("/api/guided").json(), "u01")["status"] == "new"


def test_self_study_counts_as_exposure(api):
    log_study(api, terms=["comí", "viví", "salí"], sentences=["Comí pan.", "Viví en Madrid."])
    u20 = unit(api.get("/api/guided").json(), "u20")
    assert u20["status"] == "started" and u20["words_known"] >= 3


def test_a_unit_id_needs_guided_mode_and_must_exist(api):
    base = {"mode": "SELF_STUDY", "activity_type": "READING", "duration_minutes": 20, "context_text": "x",
            "terms": ["hola", "gracias", "llamar"], "sentences": ["Hola.", "Gracias."]}
    assert api.post("/api/study-sessions", json=base | {"unit_id": "u01"}).status_code == 422
    assert api.post("/api/study-sessions", json=base | {"mode": "GUIDED_STUDY", "unit_id": "u77"}).status_code == 422
    assert api.post("/api/study-sessions", json=base | {"mode": "GUIDED_STUDY", "unit_id": "x; drop"}).status_code == 422


def test_a_unit_lesson_carries_its_text_and_attribution(api):
    body = api.get("/api/guided/units/u19").json()
    assert body["unit"]["title"].startswith("Preterite I")
    lesson = body["lesson"]
    assert lesson["pack"]["id"] == "chevere" and "CC BY 4.0" in lesson["pack"]["attribution"]
    assert lesson["sections"][0]["kind"] == "context" and lesson["sections"][1]["markdown"].startswith("# ")
    assert api.get("/api/guided/units/u37").json()["lesson"] is None  # app-original, not written yet
    assert api.get("/api/guided/units/u99").status_code == 404


# ---------------------------------------------------------------- unit quizzes


def test_a_unit_quiz_drills_the_units_tense_and_counts_toward_it(api, raw_db):
    guided(api, "u20", terms=["comer", "vivir", "salir"], sentences=["Comí pan.", "Salí tarde."])
    r = api.post("/api/guided/units/u20/quiz")
    assert r.status_code == 201, r.text
    quiz = r.json()
    assert quiz["focus"] == "UNIT"
    assert raw_db.execute("SELECT unit_id FROM assessments WHERE id = ?", (quiz["id"],)).fetchone()[0] == "u20"
    for item in quiz["items"]:
        key = json.loads(raw_db.execute("SELECT answer_json FROM assessment_items WHERE id = ?", (item["id"],)).fetchone()[0])
        if item["item_type"] in ("CONJUGATE", "FORM_ID"):
            assert key["tense"] == "pret"
    # Entries come back as different question types, never the same one twice.
    pairs = Counter((i["entry_id"], i["item_type"]) for i in quiz["items"])
    assert max(pairs.values()) == 1 and max(Counter(i["entry_id"] for i in quiz["items"]).values()) <= 3

    for item in quiz["items"]:
        api.post(f"/api/assessments/{quiz['id']}/answers", json={"item_id": item["id"], "text": correct_answer(raw_db, item)})
    u20 = unit(api.get("/api/guided").json(), "u20")
    assert u20["answers"] >= 3 and u20["status"] in ("practicing", "solid")


def test_a_unit_quiz_without_material_explains_what_to_do(api):
    r = api.post("/api/guided/units/u23/quiz")
    assert r.status_code == 409 and "Log the lesson" in r.json()["detail"]
    assert api.post("/api/guided/units/u99/quiz").status_code == 404


# ---------------------------------------------------------------- engine pieces


@pytest.fixture(scope="module")
def verbs(verb_data_path):
    return VerbData(verb_data_path)


def test_one_question_per_entry_stays_the_default(verbs):
    entries = [entry(i, v, pos="VERB", translation=f"to {v}", verbs=verbs) for i, v in enumerate(["hablar", "comer"], 1)]
    items = choose_items(entries, n=8, focus="GRAMMAR", listening=False, allow_write=False,
                         now=datetime(2026, 11, 13, tzinfo=timezone.utc), rng=random.Random(1))
    assert len(items) == 2
    more = choose_items(entries, n=8, focus="GRAMMAR", listening=False, allow_write=False,
                        now=datetime(2026, 11, 13, tzinfo=timezone.utc), rng=random.Random(1), per_entry=3)
    assert len(more) > 2 and len({(i.entry.id, i.item_type) for i in more}) == len(more)


def test_focus_tenses_restrict_verb_questions(verbs):
    e = entry(1, "hablar", pos="VERB", translation="to talk", verbs=verbs)
    e.focus_tenses = ("impf",)
    from app.practice import templates
    for seed in range(10):
        item = templates.conjugate(e, templates.Pool([e]), random.Random(seed))
        assert item.answer["tense"] == "impf"


def test_suggest_prefers_the_earliest_weak_unit():
    syl = syllabus.load()
    statuses = [progress.UnitStatus(unit=u) for u in syl.units]
    statuses[0].status, statuses[0].score, statuses[0].answers = "solid", 0.9, 10
    statuses[4].status, statuses[4].score, statuses[4].answers = "practicing", 0.4, 8
    pick = progress.suggest(statuses)
    assert pick.status.unit.id == "u05" and "40%" in pick.reason


# ---------------------------------------------------------------- regressions found running the app


def test_one_ambiguous_form_does_not_start_the_mood_units(api):
    # "eres" also reads as a present subjunctive of erar; that alone must not open the subjunctive.
    log_study(api, terms=["ser", "soy", "eres"], sentences=["Soy de México.", "Eres mi amigo."])
    body = api.get("/api/guided").json()
    assert all(unit(body, f"u{n}")["status"] == "new" for n in range(37, 43))


def test_tense_drills_only_count_for_units_about_that_tense(api, raw_db):
    guided(api, "u19", terms=["hablar", "trabajar", "llegar"], sentences=["Hablé mucho.", "Llegué tarde."])
    quiz = api.post("/api/guided/units/u19/quiz").json()
    for item in quiz["items"]:
        api.post(f"/api/assessments/{quiz['id']}/answers", json={"item_id": item["id"], "text": correct_answer(raw_db, item)})
    body = api.get("/api/guided").json()
    assert unit(body, "u19")["answers"] >= 3
    # The uses of se, pronouns and the aspect contrast mention the preterite but are not about it.
    for other in ("u47", "u22", "u30", "u26"):
        assert unit(body, other)["answers"] == 0, other
    assert syllabus.load().get("u47").drilled_tenses == () and syllabus.load().get("u21").drilled_tenses == ("pret",)


def test_a_unit_in_progress_is_never_locked_and_a_weak_one_is_suggested(api, raw_db):
    guided(api, "u19", terms=["hablar", "trabajar", "llegar"], sentences=["Hablé mucho.", "Llegué tarde."])
    for _ in range(2):
        quiz = api.post("/api/guided/units/u19/quiz").json()
        for item in quiz["items"]:
            api.post(f"/api/assessments/{quiz['id']}/answers", json={"item_id": item["id"], "text": "zzz"})
    body = api.get("/api/guided").json()
    u19 = unit(body, "u19")
    assert u19["unlocked"] and u19["score"] is not None and u19["score"] < progress.WEAK
    # Missed vocabulary questions can also make an earlier unit weak (u05 shares hablar and trabajar);
    # whichever it is, the earliest weak unit comes first.
    weak = [u for u in body["units"] if u["unlocked"] and u["score"] is not None and u["score"] < progress.WEAK]
    assert body["suggestion"]["unit_id"] == min(weak, key=lambda u: u["n"])["id"]
    assert "%" in body["suggestion"]["reason"]
