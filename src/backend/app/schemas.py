"""Request/response models and input normalisation for study sessions (MVP_DESIGN.md §3, §6)."""

import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ACTIVITY_TYPES = ("READING", "LISTENING", "WATCHING", "WRITING", "SPEAKING", "FLASHCARDS", "CLASS", "OTHER")

# Control characters other than newline/tab are rejected rather than stored.
_BAD_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _no_control_chars(value: str) -> str:
    if _BAD_CHARS.search(value):
        raise ValueError("contains unsupported control characters")
    return value


def normalize_token(text: str) -> str:
    """Canonical form used to de-duplicate concepts: NFC, case-folded, single-spaced."""
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _text(max_length: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]


class StudySessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_code: Literal["es"] = "es"
    mode: Literal["SELF_STUDY", "GUIDED_STUDY"]
    activity_type: Literal["READING", "LISTENING", "WATCHING", "WRITING", "SPEAKING", "FLASHCARDS", "CLASS", "OTHER"]
    duration_minutes: int = Field(ge=1, le=1440, strict=True)
    context_text: _text(2000)
    terms: list[_text(100)] = Field(min_length=3, max_length=5)
    sentences: list[_text(300)] = Field(min_length=2, max_length=3)

    @field_validator("context_text")
    @classmethod
    def _context_clean(cls, value: str) -> str:
        return _no_control_chars(value)

    @field_validator("terms", "sentences")
    @classmethod
    def _items_clean(cls, values: list[str]) -> list[str]:
        for value in values:
            _no_control_chars(value)
        return values

    @field_validator("terms")
    @classmethod
    def _terms_unique(cls, values: list[str]) -> list[str]:
        if len({normalize_token(v) for v in values}) != len(values):
            raise ValueError("terms must be different from each other")
        return values


class StudySessionOut(BaseModel):
    id: int
    language_code: str
    mode: str
    activity_type: str
    duration_minutes: int
    context_text: str
    terms: list[str]
    sentences: list[str]
    created_at: str
    completed_at: str | None


class StudySessionPage(BaseModel):
    total: int
    items: list[StudySessionOut]


class AwardOut(BaseModel):
    base_xp: int
    multiplier: float
    awarded_xp: int
    capped: bool


class StudySessionCreated(StudySessionOut):
    award: AwardOut


class RankOut(BaseModel):
    name: str
    min_xp: int


class StreakOut(BaseModel):
    current: int
    active_today: bool
    next_multiplier: float


class TodayOut(BaseModel):
    date: str
    study_xp: int
    study_xp_cap: int


class ProgressOut(BaseModel):
    total_xp: int
    rank: RankOut
    next_rank: RankOut | None
    xp_to_next: int | None
    streak: StreakOut
    today: TodayOut
