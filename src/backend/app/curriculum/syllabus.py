"""The syllabus: 48 units in four stages, loaded once from units.json and validated."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..lexicon.grammar_terms import NON_FINITE, TENSES

PATH = Path(__file__).with_name("units.json")
CONFIDENCE = {"established", "supported", "consensus", "contested", "design"}
# Units with these topics (or none) are *about* their tenses: any drill in such a tense is practice
# for them. Elsewhere a tense is incidental (pronouns practised in the preterite, the uses of se),
# and only the unit's own key words or its own quizzes count.
TENSE_TOPICS = {"past", "perfect", "mood", "commands"}
COMMON_TENSES = {"pres"}  # the present is everywhere, so it never identifies a unit


@dataclass(frozen=True)
class Unit:
    id: str
    n: int
    stage: int
    title: str
    summary: str
    confidence: str
    prereqs: tuple[str, ...]
    tenses: tuple[str, ...]
    lemmas: tuple[str, ...]
    topics: tuple[str, ...]

    @property
    def drilled_tenses(self) -> tuple[str, ...]:
        """Finite tenses whose drills count as practice for this unit (see TENSE_TOPICS)."""
        if self.topics and not set(self.topics) & TENSE_TOPICS:
            return ()
        return tuple(t for t in self.tenses if t in TENSES and t not in COMMON_TENSES)


@dataclass(frozen=True)
class Syllabus:
    units: tuple[Unit, ...]
    stages: tuple[dict, ...]

    def get(self, unit_id: str) -> Unit | None:
        return self._by_id().get(unit_id)

    def _by_id(self) -> dict[str, Unit]:
        return {u.id: u for u in self.units}


class SyllabusError(ValueError):
    pass


def parse(data: dict) -> Syllabus:
    stages = tuple(data["stages"])
    stage_ns = {s["n"] for s in stages}
    units: list[Unit] = []
    seen: set[str] = set()
    for i, raw in enumerate(data["units"], start=1):
        uid = raw["id"]
        if uid in seen:
            raise SyllabusError(f"duplicate unit id {uid}")
        unit = Unit(
            id=uid, n=i, stage=raw["stage"], title=raw["title"], summary=raw["summary"],
            confidence=raw["confidence"], prereqs=tuple(raw["prereqs"]), tenses=tuple(raw["tenses"]),
            lemmas=tuple(raw["lemmas"]), topics=tuple(raw["topics"]),
        )
        if unit.stage not in stage_ns:
            raise SyllabusError(f"{uid}: unknown stage {unit.stage}")
        if unit.confidence not in CONFIDENCE:
            raise SyllabusError(f"{uid}: unknown confidence {unit.confidence!r}")
        bad = [t for t in unit.tenses if t not in TENSES and t not in NON_FINITE]
        if bad:
            raise SyllabusError(f"{uid}: unknown tense ids {bad}")
        # Prerequisites must come earlier: that keeps the graph acyclic by construction.
        late = [p for p in unit.prereqs if p not in seen]
        if late:
            raise SyllabusError(f"{uid}: prerequisites {late} are not earlier units")
        seen.add(uid)
        units.append(unit)
    return Syllabus(units=tuple(units), stages=stages)


@lru_cache(maxsize=1)
def load() -> Syllabus:
    return parse(json.loads(PATH.read_text(encoding="utf-8")))
