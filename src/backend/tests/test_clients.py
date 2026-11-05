import json

import httpx
import pytest

from app.clients.grammar import COOLDOWN_SECONDS, FAILURE_THRESHOLD, LanguageToolClient
from app.clients.model import ModelUnavailable, OllamaClient

LT_RESPONSE = {
    "matches": [
        {
            "message": "Possible spelling mistake.",
            "offset": 0,
            "length": 3,
            "replacements": [{"value": "Yo"}, {"value": "Ya"}],
            "rule": {"id": "MORFOLOGIK_RULE_ES", "category": {"id": "TYPOS"}},
        },
        {
            "message": "Missing comma.",
            "offset": 4,
            "length": 1,
            "replacements": [],
            "rule": {"id": "COMMA", "category": {"id": "PUNCTUATION"}},
        },
    ]
}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def lt(handler, clock=None):
    return LanguageToolClient("http://lt", 3.0, clock=clock or Clock(), transport=httpx.MockTransport(handler))


def ollama(handler):
    return OllamaClient("http://ollama", "qwen2.5:7b", 5.0, transport=httpx.MockTransport(handler))


# ---------- Ollama ----------


def test_ollama_sends_a_schema_constrained_deterministic_request_and_returns_the_content():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"message": {"content": '{"ok": true}'}})

    schema = {"type": "object"}
    assert ollama(handler).chat_json("sys", "usr", schema, max_tokens=99) == '{"ok": true}'
    body = seen["body"]
    assert seen["url"] == "http://ollama/api/chat"
    assert body["model"] == "qwen2.5:7b" and body["stream"] is False
    assert body["format"] == schema
    assert body["options"] == {"temperature": 0, "num_predict": 99}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500, text="boom"),
        lambda r: httpx.Response(404, json={"error": "model not found"}),
        lambda r: httpx.Response(200, text="not json at all"),
        lambda r: httpx.Response(200, json={"unexpected": "shape"}),
    ],
    ids=["server error", "model not pulled", "garbage body", "wrong shape"],
)
def test_ollama_failures_become_model_unavailable(handler):
    with pytest.raises(ModelUnavailable):
        ollama(handler).chat_json("s", "u", {})


def test_ollama_timeout_and_connection_errors_become_model_unavailable():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ModelUnavailable, match="too long"):
        ollama(timeout).chat_json("s", "u", {})
    with pytest.raises(ModelUnavailable):
        ollama(refused).chat_json("s", "u", {})


def test_unconfigured_ollama_is_unavailable_without_a_network_call():
    client = OllamaClient("", "qwen2.5:7b")
    with pytest.raises(ModelUnavailable, match="not configured"):
        client.chat_json("s", "u", {})
    assert client.status() == "down"


def test_ollama_status_distinguishes_ok_missing_model_and_down():
    def tags(*names):
        return lambda r: httpx.Response(200, json={"models": [{"name": n} for n in names]})

    assert ollama(tags("qwen2.5:7b")).status() == "ok"
    assert ollama(tags("llama3.2:latest")).status() == "degraded"
    assert OllamaClient("http://ollama", "llama3.2", transport=httpx.MockTransport(tags("llama3.2:latest"))).status() == "ok"
    assert ollama(lambda r: httpx.Response(500)).status() == "down"


# ---------- LanguageTool ----------


def test_languagetool_parses_matches_and_flags_which_ones_reach_the_model():
    result = lt(lambda r: httpx.Response(200, json=LT_RESPONSE)).check("Yoo, voy")
    assert result["status"] == "ok"
    typo, comma = result["matches"]
    assert typo == {
        "rule": "MORFOLOGIK_RULE_ES", "category": "TYPOS", "kept": True,
        "message": "Possible spelling mistake.", "span": "Yoo", "suggest": ["Yo", "Ya"],
    }
    assert comma["kept"] is False  # punctuation is noise for a beginner; still stored for audit


def test_checked_and_found_nothing_is_distinct_from_not_checked():
    clean = lt(lambda r: httpx.Response(200, json={"matches": []})).check("Hola")
    down = lt(lambda r: httpx.Response(500)).check("Hola")
    assert clean == {"status": "ok", "matches": []}
    assert down["status"] == "unavailable" and "matches" not in down


def test_languagetool_timeout_is_unavailable_not_an_exception():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    assert lt(timeout).check("Hola")["status"] == "unavailable"


def test_breaker_opens_after_repeated_failures_then_recovers_after_the_cooldown():
    clock, calls = Clock(), []

    def handler(request):
        calls.append(1)
        return httpx.Response(500) if len(calls) <= FAILURE_THRESHOLD else httpx.Response(200, json={"matches": []})

    client = lt(handler, clock)
    for _ in range(FAILURE_THRESHOLD):
        assert client.check("x")["status"] == "unavailable"
    assert client.breaker_open
    made = len(calls)

    skipped = client.check("x")
    assert skipped["status"] == "unavailable" and "skipped" in skipped["reason"]
    assert len(calls) == made  # no request while open: latency stays low

    clock.now += COOLDOWN_SECONDS + 1
    assert client.check("x")["status"] == "ok"  # one probe gets through and closes it
    assert not client.breaker_open
    assert client.check("x")["status"] == "ok"


def test_a_failed_probe_after_the_cooldown_reopens_the_breaker_at_once():
    clock = Clock()
    client = lt(lambda r: httpx.Response(500), clock)
    for _ in range(FAILURE_THRESHOLD):
        client.check("x")
    clock.now += COOLDOWN_SECONDS + 1
    assert not client.breaker_open
    client.check("x")  # the single probe fails
    assert client.breaker_open


def test_a_success_resets_the_failure_count():
    responses = iter([500, 500, 200, 500, 500, 200])
    client = lt(lambda r: httpx.Response(next(responses), json={"matches": []}))
    for _ in range(6):
        client.check("x")
    assert not client.breaker_open  # never three failures in a row


def test_unconfigured_languagetool_is_unavailable_and_down():
    client = LanguageToolClient("")
    assert client.check("Hola")["status"] == "unavailable"
    assert client.status() == "down"


def test_languagetool_status_reports_ok_degraded_and_down():
    clock = Clock()
    ok = lt(lambda r: httpx.Response(200, json=[]), clock)
    assert ok.status() == "ok"
    assert lt(lambda r: httpx.Response(503), clock).status() == "down"

    def flaky(request):
        return httpx.Response(200, json=[]) if request.url.path == "/v2/languages" else httpx.Response(500)

    degraded = lt(flaky, clock)
    for _ in range(FAILURE_THRESHOLD):
        degraded.check("x")
    assert degraded.status() == "degraded"  # reachable, but being skipped
