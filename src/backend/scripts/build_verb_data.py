"""Build the read-only Spanish verb database the app uses for conjugation and form analysis.

    python src/backend/scripts/build_verb_data.py --out src/backend/data/verbs.db
    python src/backend/scripts/build_verb_data.py --out /tmp/verbs.db --verbs hablar,ir,ser

Needs verbecc (LGPL-3.0; in requirements-dev.txt), which is only used here. The app reads the
generated SQLite file and does not import verbecc, so the runtime image needs neither verbecc nor its
machine-learning dependencies. The full build covers about 9,700 verbs and takes under a minute.

Output schema:
    verbs(id, infinitive, predicted, table_json)
        table_json = {"tenses": {tense: {person: [form, ...]}}, "ger": [...], "part": [...]}
    forms(form, verb_id)   every simple-tense form, the gerund, participle and infinitive
    meta(key, value)
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import tempfile
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lexicon.grammar_terms import TENSES  # noqa: E402

_BY_VERBECC = {spec["verbecc"]: key for key, spec in TENSES.items()}


def _value(x) -> str:
    return getattr(x, "value", x)


def _person(entry: dict) -> str | None:
    pr, p, n = _value(entry.get("pr")), _value(entry.get("p")), _value(entry.get("n"))
    if pr == "vos":
        return "vos"
    return {("1", "s"): "yo", ("2", "s"): "tu", ("3", "s"): "3s", ("1", "p"): "nos",
            ("2", "p"): "vosotros", ("3", "p"): "3p"}.get((p, n))


def _forms(entry) -> list[str]:
    raw = entry.get("c", []) if isinstance(entry, dict) else [entry]
    # Negative commands come as "no extrañes"; keep the verb form only.
    return [f.removeprefix("no ").strip() for f in raw if f and f.strip()]


def conjugation_table(conjugator, infinitive: str) -> tuple[dict, bool]:
    data = conjugator.conjugate(infinitive, conjugate_pronouns=False).get_data()
    table: dict = {"tenses": {}, "ger": [], "part": []}
    for mood, tenses in data["moods"].items():
        for tense, entries in tenses.items():
            mood_v, tense_v = _value(mood), _value(tense)
            if mood_v == "gerundio":
                table["ger"] = [f for e in entries for f in _forms(e)]
                continue
            if mood_v == "participo":
                table["part"] = [f for e in entries for f in _forms(e)]
                continue
            key = _BY_VERBECC.get((mood_v, tense_v))
            if key is None:
                continue  # compound tenses are built from haber + participle when needed
            cells: dict[str, list[str]] = {}
            for entry in entries:
                person = _person(entry)
                if person is None:
                    continue
                for form in _forms(entry):
                    if form not in cells.setdefault(person, []):
                        cells[person].append(form)
            table["tenses"][key] = cells
    return table, bool(data["verb"].get("predicted"))


def build(out: Path, verbs: list[str] | None = None) -> dict:
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore")
    out = out.resolve()
    # verbecc writes verbecc.log into the working directory on import; keep it out of the repo.
    previous = os.getcwd()
    os.chdir(tempfile.gettempdir())
    try:
        from verbecc import CompleteConjugator  # imported late: only the build needs it

        conjugator = CompleteConjugator(lang="es")
    finally:
        os.chdir(previous)
    infinitives = verbs or conjugator.get_infinitives()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    conn.executescript(
        """
        CREATE TABLE verbs (id INTEGER PRIMARY KEY, infinitive TEXT NOT NULL UNIQUE,
                            predicted INTEGER NOT NULL, table_json TEXT NOT NULL);
        CREATE TABLE forms (form TEXT NOT NULL, verb_id INTEGER NOT NULL, PRIMARY KEY (form, verb_id)) WITHOUT ROWID;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    started, skipped = time.time(), 0
    for infinitive in infinitives:
        try:
            table, predicted = conjugation_table(conjugator, infinitive)
        except Exception:  # a handful of verbecc entries fail to conjugate; skip them
            skipped += 1
            continue
        verb_id = conn.execute(
            "INSERT INTO verbs (infinitive, predicted, table_json) VALUES (?, ?, ?)",
            (infinitive, int(predicted), json.dumps(table, ensure_ascii=False, separators=(",", ":"))),
        ).lastrowid
        forms = {infinitive, *table["ger"], *table["part"]}
        for cells in table["tenses"].values():
            for values in cells.values():
                forms.update(values)
        conn.executemany("INSERT OR IGNORE INTO forms VALUES (?, ?)", [(f.casefold(), verb_id) for f in forms])
    import verbecc

    meta = {
        "source": f"verbecc {getattr(verbecc, '__version__', '2.x')} (LGPL-3.0), https://github.com/bretttolbert/verbecc",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verbs": str(conn.execute("SELECT COUNT(*) FROM verbs").fetchone()[0]),
        "skipped": str(skipped),
    }
    conn.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    tmp.replace(out)
    meta["seconds"] = f"{time.time() - started:.1f}"
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verbs", help="comma-separated infinitives (default: every verb verbecc knows)")
    args = parser.parse_args(argv)
    verbs = [v.strip() for v in args.verbs.split(",") if v.strip()] if args.verbs else None
    print(json.dumps(build(args.out, verbs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
