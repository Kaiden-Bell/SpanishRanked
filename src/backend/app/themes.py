"""Themes the learner unlocks by ranking up: a palette plus the banner scene it is named after.

A theme is unlocked by the rank it belongs to being *held* (its boss passed, or grandfathered), the
same rank the dashboard shows. The palettes themselves live in the frontend (index.css).
"""

from dataclasses import dataclass

from . import rules

DEFAULT = "alhambra"


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    rank_index: int  # into rules.RANKS
    scene: str | None  # banner scene it pins; None keeps the daily rotation


THEMES = [
    Theme("alhambra", "Alhambra Dusk", 0, None),
    Theme("tonanes", "Toñanes Coast", 1, "tonanes"),
    Theme("salamanca", "Salamanca Stone", 2, "salamanca"),
    Theme("cantabria", "Cantabrian Green", 3, "cantabria"),
    Theme("sevilla", "Sevilla Gold", 4, "sevilla"),
    Theme("medianoche", "Medianoche", 5, None),
]
BY_ID = {t.id: t for t in THEMES}


def is_unlocked(theme_id: str, held_index: int) -> bool:
    theme = BY_ID.get(theme_id)
    return theme is not None and theme.rank_index <= held_index


def for_rank(rank_index: int) -> Theme | None:
    return next((t for t in THEMES if t.rank_index == rank_index), None)


def listing(held_index: int) -> list[dict]:
    return [{"id": t.id, "label": t.label, "rank_name": rules.RANKS[t.rank_index][1], "scene": t.scene,
             "unlocked": t.rank_index <= held_index} for t in THEMES]
