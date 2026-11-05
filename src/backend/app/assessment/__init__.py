"""Quiz generation and grading (MVP_DESIGN.md §8). The backend, not the model, decides eligibility and XP."""

import json
import re
from pathlib import Path

_BAD_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def scrub(text: str) -> str:
    """Make learner-supplied text safe to place inside a delimited prompt block.

    Learner notes, answers and LanguageTool hints (which quote learner text) are untrusted. Angle
    brackets are neutralised so none of them can close the block and pose as instructions.
    """
    return _BAD_CHARS.sub("", text).replace("<", "‹").replace(">", "›")


def concept_guidance() -> dict[str, str]:
    """Per-concept grading rules: authored configuration, injected into the grading prompt."""
    return json.loads((Path(__file__).with_name("concept_guidance.json")).read_text(encoding="utf-8"))
