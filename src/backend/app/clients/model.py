"""Ollama client: the essential local model (MVP_DESIGN.md §5, §8)."""

from typing import Protocol

import httpx


class ModelUnavailable(Exception):
    """The model could not be reached, timed out, or refused the request. Never loses learner data."""


class LanguageModel(Protocol):
    def chat_json(self, system: str, user: str, schema: dict, *, max_tokens: int = 512) -> str:
        """Return the model's raw JSON text, constrained to ``schema``. Raises ModelUnavailable."""
        ...

    def status(self) -> str:
        """'ok', 'degraded' (reachable but the model is not pulled) or 'down'."""
        ...


class OllamaClient:
    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 120.0,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self._url = url.rstrip("/")
        self._model = model
        self._http = httpx.Client(transport=transport, timeout=timeout)

    def chat_json(self, system: str, user: str, schema: dict, *, max_tokens: int = 512) -> str:
        if not self._url:
            raise ModelUnavailable("model service is not configured")
        body = {
            "model": self._model,
            "stream": False,
            # Temperature 0 and a token cap: reproducible grading, and a runaway answer fails fast.
            "options": {"temperature": 0, "num_predict": max_tokens},
            "format": schema,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            response = self._http.post(f"{self._url}/api/chat", json=body)
            response.raise_for_status()
            return response.json()["message"]["content"]
        # These messages reach the learner (as a quiz's grading error), so they say what happened in
        # plain words. The exception chain keeps the technical detail for the server log.
        except httpx.TimeoutException as exc:
            raise ModelUnavailable("The language model took too long to answer.") from exc
        except httpx.ConnectError as exc:
            raise ModelUnavailable("The language model could not be reached.") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailable("The language model returned an error.") from exc

    def status(self) -> str:
        if not self._url:
            return "down"
        try:
            response = self._http.get(f"{self._url}/api/tags", timeout=3.0)
            response.raise_for_status()
            names = {m["name"] for m in response.json().get("models", [])}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return "down"
        return "ok" if self._model in names or f"{self._model}:latest" in names else "degraded"
