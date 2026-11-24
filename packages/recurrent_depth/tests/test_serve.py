"""Self-hosted server: request validation, SSE format, serialization, and a probe run against it."""

import json
import threading
import time
import urllib.request

import pytest

from recurrent_depth import budget, client, serve, tasks


class ScriptedBackend:
    """Answers tasks correctly; spends ``delay_per_step`` per Huginn step before the first token."""

    model_id = "scripted"
    supports_recurrence = True

    def __init__(self, delay_per_step=0.0):
        self.delay_per_step = delay_per_step
        self.seen = []
        self.active = 0
        self.max_active = 0

    def count_tokens(self, text):
        return len(text.split())

    def stream(self, req):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.seen.append(req)
        try:
            time.sleep(self.delay_per_step * (req.recurrence.num_steps or 1))
            words = "the answer is ready".split()[: req.max_tokens]
            for w in words:
                yield w + " "
        finally:
            self.active -= 1


@pytest.fixture
def running():
    servers = []

    def start(backend, allow=True):
        srv = serve.ModelServer(backend, allow_recurrence=allow)
        httpd = serve.make_http_server(srv, "127.0.0.1", 0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return f"http://127.0.0.1:{httpd.server_address[1]}", srv

    yield start
    for h in servers:
        h.shutdown()
        h.server_close()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


@pytest.mark.parametrize(
    "body, match",
    [
        ({"messages": []}, "messages"),
        ({"messages": [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]}, "exactly one"),
        ({"messages": [{"role": "user", "content": "a"}], "max_tokens": 0}, "max_tokens"),
        ({"messages": [{"role": "user", "content": "a"}], "max_tokens": 10**6}, "max_tokens"),
        ({"messages": [{"role": "user", "content": "a"}], "temperature": 5}, "temperature"),
        ({"messages": [{"role": "user", "content": "a"}], "n": 3}, "n must"),
        ({"messages": [{"role": "user", "content": "a"}], "recurrence": {"num_steps": 0}}, "num_steps"),
        ({"messages": [{"role": "user", "content": "a"}], "recurrence": {"num_steps": True}}, "num_steps"),
        ({"messages": [{"role": "user", "content": "a"}], "recurrence": {"criterion": "magic"}}, "criterion"),
        ({"messages": [{"role": "user", "content": "a"}], "recurrence": {"exit_threshold": 0.1}}, "needs a criterion"),
        ({"messages": [{"role": "user", "content": "a"}], "recurrence": {"loops": 2}}, "recurrence must"),
    ],
)
def test_parse_request_rejects(body, match):
    with pytest.raises(serve.RequestError, match=match):
        serve.parse_request(json.dumps(body).encode(), allow_recurrence=True)


def test_recurrence_requires_opt_in():
    body = json.dumps({"messages": [{"role": "user", "content": "a"}], "recurrence": {"num_steps": 4}}).encode()
    with pytest.raises(serve.RequestError, match="allow-request-recurrence"):
        serve.parse_request(body, allow_recurrence=False)
    req, stream, usage = serve.parse_request(body, allow_recurrence=True)
    assert req.recurrence.num_steps == 4 and not stream and not usage


def test_backend_without_recurrence_cannot_opt_in():
    b = ScriptedBackend()
    b.supports_recurrence = False
    with pytest.raises(ValueError):
        serve.ModelServer(b, allow_recurrence=True)


def test_http_errors_and_health(running):
    url, _ = running(ScriptedBackend())
    with urllib.request.urlopen(url + "/health", timeout=5) as r:
        assert json.loads(r.read())["status"] == "ok"
    with urllib.request.urlopen(url + "/v1/models", timeout=5) as r:
        assert json.loads(r.read())["data"][0]["id"] == "scripted"
    status, body = _post(url + "/v1/chat/completions", {"messages": []})
    assert status == 400 and b"messages" in body
    assert _post(url + "/v1/other", {})[0] == 404


def test_non_streaming_response(running):
    url, _ = running(ScriptedBackend())
    status, body = _post(url + "/v1/chat/completions", {"messages": [{"role": "user", "content": "q"}], "max_tokens": 2})
    out = json.loads(body)
    assert status == 200 and out["choices"][0]["message"]["content"] == "the answer "
    assert out["choices"][0]["finish_reason"] == "length" and out["usage"]["completion_tokens"] == 2


def test_chat_client_streams_from_server(running):
    backend = ScriptedBackend(delay_per_step=0.01)
    url, _ = running(backend)
    c = client.ChatClient(url + "/v1", "scripted", api_key_env=None, limiter=client.RateLimiter(0, 10))
    res = c.complete("hello there", max_tokens=8, extra={"recurrence": {"num_steps": 20}})
    assert res.ok and res.text.strip() == "the answer is ready"
    assert res.prompt_tokens == 2 and res.completion_tokens == 4 and res.finish_reason == "stop"
    assert res.ttft_s is not None and res.ttft_s >= 0.2  # 20 steps at 10 ms before the first token
    assert backend.seen[-1].recurrence.num_steps == 20


def test_requests_are_serialized(running):
    backend = ScriptedBackend(delay_per_step=0.05)
    url, _ = running(backend)
    body = {"messages": [{"role": "user", "content": "q"}], "max_tokens": 2, "recurrence": {"num_steps": 2}}
    threads = [threading.Thread(target=_post, args=(url + "/v1/chat/completions", body)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert backend.max_active == 1


class TaskBackend(ScriptedBackend):
    """Solves generated tasks so a budget sweep can run end to end against the server."""

    def stream(self, req):
        self.seen.append(req)
        time.sleep(0.002 * (req.recurrence.num_steps or 1))
        yield self.answers.get(req.prompt, "?")


def test_budget_sweep_over_recurrence_conditions(running, tmp_path):
    backend = TaskBackend()
    plan = budget.BudgetPlan(
        base_url="",
        model="scripted",
        conditions=[
            budget.BudgetCondition("s4", 16, {"recurrence": {"num_steps": 4}}),
            budget.BudgetCondition("s32", 16, {"recurrence": {"num_steps": 32}}),
        ],
        tasks=["arithmetic_chain"],
        depths=[1, 4],
        reps=2,
        requests_per_minute=6000,
        max_requests=50,
        api_key_env=None,
        acknowledge_terms=True,
    )
    backend.answers = {plan.conditions[0].prompt(it): it.answer for group in plan.suite() for it in group}
    url, _ = running(backend)
    plan.base_url = url + "/v1"
    records = budget.run_budget_plan(plan, out_path=tmp_path / "r.jsonl", allow_any_key_env=True)
    assert len(records) == 8 and all(r["correct"] for r in records)
    assert {r.recurrence.num_steps for r in backend.seen} == {4, 32}
    assert tasks.GENERATORS["arithmetic_chain"]  # the task the calibration uses exists
