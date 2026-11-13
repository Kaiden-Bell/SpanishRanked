"""Online word data: Wiktionary (meanings, inflected-form links, examples), Tatoeba (example sentence
pairs) and MyMemory (machine translation of whole phrases only).

Every call is short and guarded by a per-source circuit breaker. Callers cache results in
`lookup_cache` (see cache.py). Raising SourceUnavailable means "try again later"; returning None or []
means "the source answered and has nothing".

Only the Spanish word or phrase being looked up is sent. No account, user or device details are.
"""

import html
import re
import threading
import time
from typing import Callable
from urllib.parse import quote

import httpx

# Wikimedia rejects library traffic without a policy-style User-Agent: name/version (contact) library.
# The self-hoster can put their own URL or email in LANGUAGEAI_LOOKUP_CONTACT; nothing personal is
# sent by default.
DEFAULT_CONTACT = "+https://www.mediawiki.org/wiki/API:Etiquette"


def user_agent(contact: str = "") -> str:
    return f"LanguageAI/0.2 (self-hosted language study app; {contact.strip() or DEFAULT_CONTACT}) httpx/{httpx.__version__}"
WIKTIONARY_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/{word}"
TATOEBA_URL = "https://api.tatoeba.org/unstable/sentences"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 120.0
MAX_SENSES = 6
MAX_EXAMPLES_PER_SENSE = 2

ATTRIBUTION = {
    "WIKTIONARY": "Definitions from Wiktionary (CC BY-SA 4.0)",
    "TATOEBA": "Example sentences from Tatoeba (CC BY 2.0 FR)",
    "MYMEMORY": "Machine translation by MyMemory",
}

_TAG = re.compile(r"<[^>]+>")
# Wiktionary's HTML carries inline <style> blocks (template CSS); their text is not part of the gloss.
_BRACKETED = re.compile(r"\s*\[[^\]]*\]")
_NON_TEXT = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.S | re.I)
_FORM_OF_LINK = re.compile(r'class="form-of-definition-link".*?<a [^>]*>([^<]+)</a>', re.S)


class SourceUnavailable(Exception):
    pass


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG.sub("", _NON_TEXT.sub("", fragment or ""))).split())


class _Breaker:
    def __init__(self, clock: Callable[[], float]):
        self._clock, self._lock, self._failures, self._open_until = clock, threading.Lock(), 0, 0.0

    @property
    def open(self) -> bool:
        return self._clock() < self._open_until

    def record(self, ok: bool) -> None:
        with self._lock:
            if ok:
                self._failures, self._open_until = 0, 0.0
                return
            self._failures += 1
            if self._failures >= FAILURE_THRESHOLD:
                self._open_until = self._clock() + COOLDOWN_SECONDS
                self._failures = FAILURE_THRESHOLD - 1


class LexiconSources:
    def __init__(
        self,
        enabled: bool,
        timeout: float = 4.0,
        *,
        contact: str = "",
        clock: Callable[[], float] = time.monotonic,
        transport: httpx.BaseTransport | None = None,
    ):
        self.enabled = enabled
        self._http = httpx.Client(transport=transport, timeout=timeout, headers={"User-Agent": user_agent(contact)},
                                  follow_redirects=True)
        self._breakers = {name: _Breaker(clock) for name in ("WIKTIONARY", "TATOEBA", "MYMEMORY")}

    def _get(self, source: str, url: str, params: dict | None = None) -> httpx.Response | None:
        """The response, None for a 404, or SourceUnavailable."""
        if not self.enabled:
            raise SourceUnavailable("online lookups are turned off")
        breaker = self._breakers[source]
        if breaker.open:
            raise SourceUnavailable("skipped after repeated failures")
        try:
            response = self._http.get(url, params=params)
            if response.status_code == 404:
                breaker.record(True)
                return None
            response.raise_for_status()
        except httpx.HTTPError as exc:
            breaker.record(False)
            raise SourceUnavailable(type(exc).__name__) from exc
        breaker.record(True)
        return response

    # ---------- Wiktionary ----------

    def wiktionary(self, word: str) -> dict | None:
        """{"entries": [{"pos", "senses": [{"gloss", "examples": [{"es","en"}]}], "form_of": [lemma]}]}
        for the Spanish section, or None when the word has no Spanish entry."""
        response = self._get("WIKTIONARY", WIKTIONARY_URL.format(word=quote(word, safe="")))
        if response is None:
            return None
        try:
            spanish = response.json().get("es") or []
        except ValueError as exc:
            raise SourceUnavailable("bad JSON") from exc
        entries = []
        for block in spanish:
            senses, form_of = [], []
            for definition in block.get("definitions", []):
                raw = definition.get("definition", "")
                if "form-of-definition" in raw:
                    form_of += [_text(m) for m in _FORM_OF_LINK.findall(raw)]
                # Bracketed usage notes ("[with con 'with', ...]") are grammar notes, not the meaning.
                gloss = " ".join(_BRACKETED.sub("", _text(raw)).split()).strip(" ;,")
                if not gloss:
                    continue
                examples = [
                    {"es": _text(e.get("example", "")), "en": _text(e.get("translation", ""))}
                    for e in definition.get("parsedExamples", [])[:MAX_EXAMPLES_PER_SENSE]
                    if e.get("example") and e.get("translation")
                ]
                senses.append({"gloss": gloss[:200], "examples": examples})
            if senses:
                entries.append({"pos": block.get("partOfSpeech", ""), "senses": senses[:MAX_SENSES],
                                "form_of": list(dict.fromkeys(f for f in form_of if f))})
        return {"entries": entries} if entries else None

    # ---------- Tatoeba ----------

    def tatoeba(self, query: str, limit: int = 30) -> list[dict]:
        """Spanish sentences with an English translation, shortest first: [{"id", "es", "en"}]."""
        response = self._get("TATOEBA", TATOEBA_URL, {
            "lang": "spa", "q": query, "trans:lang": "eng", "sort": "words", "limit": limit,
        })
        if response is None:
            return []
        try:
            data = response.json().get("data") or []
        except ValueError as exc:
            raise SourceUnavailable("bad JSON") from exc
        out = []
        for sentence in data:
            english = [
                t.get("text") for group in sentence.get("translations") or []
                for t in (group if isinstance(group, list) else [group])
                if isinstance(t, dict) and t.get("lang") == "eng" and t.get("text")
            ]
            if sentence.get("text") and english:
                out.append({"id": sentence.get("id"), "es": sentence["text"], "en": english[0]})
        return out

    # ---------- MyMemory ----------

    def translate(self, text: str) -> str | None:
        """Machine translation es -> en. Used for phrases, which dictionaries don't list."""
        response = self._get("MYMEMORY", MYMEMORY_URL, {"q": text, "langpair": "es|en"})
        if response is None:
            return None
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailable("bad JSON") from exc
        translated = _text((body.get("responseData") or {}).get("translatedText") or "")
        if body.get("quotaFinished") or "MYMEMORY WARNING" in translated.upper():
            raise SourceUnavailable("daily quota reached")
        if str(body.get("responseStatus")) != "200" or not translated:
            return None
        return translated[:300]
