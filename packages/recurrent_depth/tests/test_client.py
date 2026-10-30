import json

import pytest

from recurrent_depth.client import BudgetExceeded, ChatClient, RateLimiter, TransportResponse
from recurrent_depth.simulate import VirtualClock


def sse(*chunks):
    return [f"data: {json.dumps(c)}\n".encode() for c in chunks] + [b"data: [DONE]\n"]


class ScriptedTransport:
    """Returns queued responses and advances a virtual clock between lines."""

    def __init__(self, clock, responses, step=0.1):
        self.clock = clock
        self.responses = list(responses)
        self.step = step
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body)))
        status, hdrs, lines = self.responses.pop(0)

        def gen():
            for line in lines:
                self.clock.sleep(self.step)
                yield line

        return TransportResponse(status, hdrs, gen())


def make_client(transport, clock, rpm=60, budget=10):
    limiter = RateLimiter(requests_per_minute=rpm, max_requests=budget, clock=clock, sleep=clock.sleep)
    return ChatClient(
        "https://api.example.test/v1",
        "m",
        api_key_env=None,
        limiter=limiter,
        transport=transport,
        clock=clock,
        sleep=clock.sleep,
    )


def test_streaming_text_timing_and_usage():
    clock = VirtualClock()
    usage = {"prompt_tokens": 12, "completion_tokens": 2, "completion_tokens_details": {"reasoning_tokens": 0}}
    lines = sse(
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {"choices": [], "usage": usage},
    )
    t = ScriptedTransport(clock, [(200, {}, lines)])
    res = make_client(t, clock).complete("hi", max_tokens=2, extra={"reasoning_effort": "low"})
    assert res.ok and res.text == "Hello"
    assert res.ttft_s == pytest.approx(0.2)
    assert res.inter_token_s() == [pytest.approx(0.1)]
    assert res.prompt_tokens == 12 and res.completion_tokens == 2 and res.reasoning_tokens == 0
    body = t.calls[0][2]
    assert body["stream"] is True and body["temperature"] == 0.0 and body["reasoning_effort"] == "low"
    assert "Authorization" not in t.calls[0][1]


def test_logprobs_parsed():
    clock = VirtualClock()
    tops = [{"token": "A", "logprob": -0.1}, {"token": "B", "logprob": -2.3}]
    chunk = {"choices": [{"delta": {"content": "A"}, "logprobs": {"content": [{"token": "A", "top_logprobs": tops}]}}]}
    t = ScriptedTransport(clock, [(200, {}, sse(chunk))])
    res = make_client(t, clock).complete("q", logprobs=2)
    assert res.top_logprobs == [{"A": -0.1, "B": -2.3}]
    assert t.calls[0][2]["top_logprobs"] == 2


def test_retry_honors_retry_after_then_succeeds():
    clock = VirtualClock()
    ok = sse({"choices": [{"delta": {"content": "ok"}}]})
    t = ScriptedTransport(clock, [(429, {"Retry-After": "7"}, [b"slow down"]), (200, {}, ok)])
    res = make_client(t, clock, rpm=0).complete("q")
    assert res.ok and res.text == "ok" and res.attempts == 2
    assert clock.now >= 7.0


def test_non_retryable_error_returned():
    clock = VirtualClock()
    t = ScriptedTransport(clock, [(400, {}, [b'{"error":"bad"}'])])
    res = make_client(t, clock).complete("q")
    assert not res.ok and "HTTP 400" in res.error and res.attempts == 1


def test_retries_stop_at_budget():
    clock = VirtualClock()
    t = ScriptedTransport(clock, [(503, {}, [b"busy"])] * 10)
    with pytest.raises(BudgetExceeded):
        make_client(t, clock, rpm=0, budget=3).complete("q")
    assert len(t.calls) == 3


def test_rate_limiter_spacing_and_budget():
    clock = VirtualClock()
    lim = RateLimiter(requests_per_minute=30, max_requests=3, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        lim.acquire()
    assert clock.now == pytest.approx(4.0)
    with pytest.raises(BudgetExceeded):
        lim.acquire()


def test_refuses_key_over_plain_http(monkeypatch):
    monkeypatch.setenv("RD_TEST_KEY", "secret")
    with pytest.raises(ValueError):
        ChatClient("http://api.example.test/v1", "m", api_key_env="RD_TEST_KEY")
    ChatClient("http://localhost:8000/v1", "m", api_key_env="RD_TEST_KEY")
    with pytest.raises(ValueError):
        ChatClient("file:///etc/passwd", "m", api_key_env=None)


def test_key_sent_as_bearer(monkeypatch):
    monkeypatch.setenv("RD_TEST_KEY", "secret")
    clock = VirtualClock()
    t = ScriptedTransport(clock, [(200, {}, sse({"choices": [{"delta": {"content": "x"}}]}))])
    c = ChatClient(
        "https://api.example.test/v1",
        "m",
        api_key_env="RD_TEST_KEY",
        transport=t,
        clock=clock,
        sleep=clock.sleep,
        limiter=RateLimiter(clock=clock, sleep=clock.sleep),
    )
    c.complete("q")
    assert t.calls[0][1]["Authorization"] == "Bearer secret"
