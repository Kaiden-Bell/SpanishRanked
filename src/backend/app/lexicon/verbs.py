"""Read-only access to the generated verb database (see scripts/build_verb_data.py).

When the file is missing, every lookup returns nothing: the word bank still works, it just can't
recognise verbs or show conjugation tables.
"""

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FormMatch:
    infinitive: str
    tense: str  # a TENSES key, or 'inf' / 'ger' / 'part'
    person: str | None


class VerbData:
    def __init__(self, path: Path | str | None):
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        if path and Path(path).is_file():
            self._conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        elif path:
            log.warning("Verb data not found at %s; verbs will not be analysed. Run scripts/build_verb_data.py.", path)
        self.table = lru_cache(maxsize=512)(self._table)

    @property
    def available(self) -> bool:
        return self._conn is not None

    def _query(self, sql: str, args: tuple) -> list[tuple]:
        if self._conn is None:
            return []
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def is_infinitive(self, word: str) -> bool:
        return bool(self._query("SELECT 1 FROM verbs WHERE infinitive = ?", (word.casefold(),)))

    def _table(self, infinitive: str) -> dict | None:
        rows = self._query("SELECT table_json FROM verbs WHERE infinitive = ?", (infinitive,))
        return json.loads(rows[0][0]) if rows else None

    def infinitives_for(self, form: str) -> list[str]:
        return [r[0] for r in self._query(
            "SELECT v.infinitive FROM forms f JOIN verbs v ON v.id = f.verb_id WHERE f.form = ? ORDER BY v.predicted, v.id",
            (form.casefold(),),
        )]

    def matches(self, form: str) -> list[FormMatch]:
        """Every (infinitive, tense, person) this exact form can be. 'fui' -> ir and ser, preterite yo."""
        form = form.casefold()
        out: list[FormMatch] = []
        for infinitive in self.infinitives_for(form):
            out.extend(cells_for(self.table(infinitive), infinitive, form))
        return out


def cells_for(table: dict | None, infinitive: str, form: str) -> list[FormMatch]:
    if not table:
        return []
    out = []
    if form == infinitive:
        out.append(FormMatch(infinitive, "inf", None))
    for key in ("ger", "part"):
        if form in table.get(key, []):
            out.append(FormMatch(infinitive, key, None))
    for tense, cells in table["tenses"].items():
        for person, forms in cells.items():
            if form in forms:
                out.append(FormMatch(infinitive, tense, person))
    return out
