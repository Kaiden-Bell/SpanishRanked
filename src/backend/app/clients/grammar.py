"""LanguageTool client: an advisory spelling/grammar pass (MVP_DESIGN.md §8).

LanguageTool never decides anything. Its findings are stored with the attempt and reach the model only
as hints. When it is slow or down, grading carries on without it and the result says so, using an
envelope that is distinct from "checked, nothing found":

    {"status": "ok", "matches": [...]}            checked
    {"status": "unavailable", "reason": "..."}    not checked
"""

import threading
import time
from typing import Callable, Protocol

import httpx

# Only these categories reach the model; style, punctuation, casing and whitespace rules are noise
# for a beginner-level grader. Dropped matches stay in the stored findings (kept=False) for audit.
KEEP_CATEGORIES = {"TYPOS", "CONFUSIONS", "DIACRITICS", "GRAMMAR"}
KEEP_PREFIXES = ("AGREEMENT_",)

FAILURE_THRESHOLD = 3  # consecutive failures that open the breaker
COOLDOWN_SECONDS = 60.0  # how long an open breaker skips the service


class GrammarChecker(Protocol):
    def check(self, text: str) -> dict: ...

    def status(self) -> str:
        """'ok', 'degraded' or 'down'."""
        ...


def _keep(category: str) -> bool:
    return category in KEEP_CATEGORIES or category.startswith(KEEP_PREFIXES)


def _unavailable(reason: str) -> dict:
    return {"status": "unavailable", "reason": reason}


class LanguageToolClient:
    def __init__(
        self,
        url: str,
        timeout: float = 3.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        transport: httpx.BaseTransport | None = None,
    ):
        self._url = url.rstrip("/")
        self._timeout = timeout
        self._clock = clock
        self._http = httpx.Client(transport=transport, timeout=timeout)
        self._lock = threading.Lock()
        self._failures = 0
        self._open_until = 0.0

    @property
    def breaker_open(self) -> bool:
        return self._clock() < self._open_until

    def _record(self, ok: bool) -> None:
        with self._lock:
            if ok:
                self._failures = 0
                self._open_until = 0.0
                return
            self._failures += 1
            if self._failures >= FAILURE_THRESHOLD:
                # Keep the cooldown short and let one probe through afterwards; success closes it.
                self._open_until = self._clock() + COOLDOWN_SECONDS
                self._failures = FAILURE_THRESHOLD - 1

    def check(self, text: str) -> dict:
        if not self._url:
            return _unavailable("not configured")
        if self.breaker_open:
            return _unavailable("skipped after repeated failures")
        try:
            response = self._http.post(f"{self._url}/v2/check", data={"language": "es", "text": text})
            response.raise_for_status()
            raw = response.json()["matches"]
            matches = [
                {
                    "rule": m["rule"]["id"],
                    "category": m["rule"]["category"]["id"],
                    "kept": _keep(m["rule"]["category"]["id"]),
                    "message": m["message"],
                    "span": text[m["offset"] : m["offset"] + m["length"]],
                    "suggest": [r["value"] for r in m["replacements"][:3]],
                }
                for m in raw
            ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            self._record(False)
            return _unavailable(type(exc).__name__)
        self._record(True)
        return {"status": "ok", "matches": matches}

    def status(self) -> str:
        if not self._url:
            return "down"
        try:
            self._http.get(f"{self._url}/v2/languages", timeout=min(self._timeout, 2.0)).raise_for_status()
        except httpx.HTTPError:
            return "down"
        return "degraded" if self.breaker_open else "ok"
