"""Rate-limited client for OpenAI-compatible chat completion endpoints.

Only the standard library is used. The transport, clock, and sleep function
are injectable so the client can be tested without a network.

Guardrails built in:

* a hard request budget (``max_requests``) and a minimum interval between
  requests derived from ``requests_per_minute``;
* exponential backoff on 429 and 5xx responses that honors ``Retry-After``;
* API keys are read from an environment variable, never logged, and never
  sent over plain HTTP to a non-local host;
* HTTP redirects are refused rather than followed, because urllib would
  otherwise replay the ``Authorization`` header to whatever host (and scheme)
  the redirect names;
* request fields that the measurement depends on (model, messages, stream,
  output length, sampling, number of choices) cannot be overridden through
  ``extra``, so a plan cannot silently multiply cost or break the length
  controls;
* a response is cut off after ``max_response_bytes`` or ``timeout_s`` in
  total, and malformed or hostile stream chunks are skipped rather than
  allowed to crash the run.

This client sends ordinary chat requests and records what any API customer
can observe (text, token counts, timestamps, and log-probabilities when the
provider offers them). It does nothing to bypass authentication, rate limits,
or content controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import http.client
import json
import math
import os
import time
from typing import Any, Callable, Iterable, Iterator, Protocol
import urllib.error
import urllib.parse
import urllib.request

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})
# Fields the client sets itself. ``extra`` may add provider parameters (for
# example a reasoning-effort knob) but may not replace these.
RESERVED_FIELDS = frozenset(
    {
        "model",
        "messages",
        "stream",
        "stream_options",
        "max_tokens",
        "max_completion_tokens",
        "n",
        "temperature",
        "logprobs",
        "top_logprobs",
        "best_of",
    }
)
MAX_ERROR_BODY_BYTES = 64 * 1024


class BudgetExceeded(RuntimeError):
    """Raised when the configured request budget is used up."""


@dataclass
class TransportResponse:
    """Minimal response object returned by a transport."""

    status: int
    headers: dict[str, str]
    lines: Iterable[bytes]


class Transport(Protocol):
    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> TransportResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect so credentials are never forwarded to another URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None  # urllib then raises HTTPError with the 3xx status


_OPENER = urllib.request.build_opener(_NoRedirect())


def urllib_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> TransportResponse:
    """Default transport using urllib. Streams the body line by line; never follows redirects."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = _OPENER.open(req, timeout=timeout)  # scheme validated in ChatClient
    except urllib.error.HTTPError as err:
        payload = err.read(MAX_ERROR_BODY_BYTES)
        return TransportResponse(err.code, dict(err.headers.items()), [payload])

    def _iter() -> Iterator[bytes]:
        with resp:
            for line in resp:
                yield line

    return TransportResponse(resp.status, dict(resp.headers.items()), _iter())


@dataclass
class RateLimiter:
    """Minimum spacing between requests plus a total budget."""

    requests_per_minute: float = 10.0
    max_requests: int = 500
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    sent: int = 0
    _last: float | None = None

    def acquire(self) -> None:
        if self.sent >= self.max_requests:
            raise BudgetExceeded(f"request budget of {self.max_requests} exhausted")
        if self.requests_per_minute > 0 and self._last is not None:
            interval = 60.0 / self.requests_per_minute
            wait = self._last + interval - self.clock()
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()
        self.sent += 1


@dataclass
class CompletionResult:
    """Everything observable about one completion request."""

    text: str = ""
    status: int = 0
    ttft_s: float | None = None
    total_s: float = 0.0
    chunk_times_s: list[float] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    top_logprobs: list[dict[str, float]] = field(default_factory=list)
    error: str | None = None
    attempts: int = 0
    retry_after_s: float | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    def inter_token_s(self) -> list[float]:
        t = self.chunk_times_s
        return [b - a for a, b in zip(t, t[1:])]


def _validate_url(base_url: str, has_key: bool) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme {parsed.scheme!r}; use http or https")
    if parsed.scheme == "http" and has_key and (parsed.hostname or "") not in LOCAL_HOSTS:
        raise ValueError("refusing to send an API key over plain HTTP to a non-local host")
    return base_url.rstrip("/")


class ChatClient:
    """Streaming chat-completions client with timing capture."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str | None = "OPENAI_API_KEY",
        limiter: RateLimiter | None = None,
        transport: Transport = urllib_transport,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
        timeout_s: float = 120.0,
        max_retries: int = 4,
        backoff_base_s: float = 2.0,
        include_usage: bool = True,
        max_response_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self._api_key = os.environ.get(api_key_env) if api_key_env else None
        self.base_url = _validate_url(base_url, bool(self._api_key))
        self.model = model
        self.limiter = limiter or RateLimiter()
        self.transport = transport
        self.clock = clock
        self.sleep = sleep
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.include_usage = include_usage
        self.max_response_bytes = max_response_bytes

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _body(self, prompt: str, max_tokens: int, temperature: float, logprobs: int, extra: dict[str, Any]) -> bytes:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if self.include_usage:
            body["stream_options"] = {"include_usage": True}
        if logprobs > 0:
            body["logprobs"] = True
            body["top_logprobs"] = logprobs
        clash = sorted(RESERVED_FIELDS & set(extra))
        if clash:
            raise ValueError(f"extra may not override request fields the client controls: {clash}")
        body.update(extra)
        return json.dumps(body).encode("utf-8")

    def complete(
        self,
        prompt: str,
        max_tokens: int = 8,
        temperature: float = 0.0,
        logprobs: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> CompletionResult:
        """Send one streamed request and return text plus timing."""
        body = self._body(prompt, max_tokens, temperature, logprobs, extra or {})
        url = f"{self.base_url}/chat/completions"
        result = CompletionResult()
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            result = self._once(url, body)
            result.attempts = attempt + 1
            if result.status not in RETRY_STATUSES:
                return result
            if attempt < self.max_retries:
                self.sleep(self._backoff(attempt, result))
        return result

    def _backoff(self, attempt: int, result: CompletionResult) -> float:
        if result.retry_after_s is not None:
            return min(max(result.retry_after_s, 0.0), 300.0)
        return min(self.backoff_base_s * (2**attempt), 120.0)

    def _once(self, url: str, body: bytes) -> CompletionResult:
        result = CompletionResult()
        start = self.clock()
        try:
            resp = self.transport(url, self._headers(), body, self.timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            result.error = f"transport error: {exc}"
            result.total_s = self.clock() - start
            return result
        result.status = resp.status
        if resp.status in RETRY_STATUSES:
            ra = {k.lower(): v for k, v in resp.headers.items()}.get("retry-after")
            if ra is not None:
                try:
                    value = float(ra)
                except ValueError:
                    value = math.nan  # HTTP-date form: fall back to exponential backoff
                if math.isfinite(value) and value >= 0:
                    result.retry_after_s = value
        if not 200 <= resp.status < 300:
            result.error = f"HTTP {resp.status}: " + b"".join(resp.lines).decode("utf-8", "replace")[:300]
            result.total_s = self.clock() - start
            return result
        parts: list[str] = []
        received = 0
        try:
            for raw in resp.lines:
                now = self.clock() - start
                received += len(raw)
                if received > self.max_response_bytes:
                    result.error = f"response exceeded {self.max_response_bytes} bytes"
                    break
                if now > self.timeout_s:
                    result.error = f"response exceeded the {self.timeout_s} s total timeout"
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except (json.JSONDecodeError, RecursionError):
                    continue
                if isinstance(chunk, dict):
                    self._absorb(chunk, now, parts, result)
        except (OSError, http.client.HTTPException) as exc:
            # A read timeout or dropped connection mid-stream: keep what arrived, mark the
            # request failed so its timing is not used, and let the run continue.
            result.error = f"stream error: {exc}"
        result.text = "".join(parts)
        result.total_s = self.clock() - start
        return result

    @staticmethod
    def _absorb(chunk: dict, now: float, parts: list[str], result: CompletionResult) -> None:
        usage = chunk.get("usage")
        if isinstance(usage, dict):
            result.prompt_tokens = _count(usage.get("prompt_tokens"), result.prompt_tokens)
            result.completion_tokens = _count(usage.get("completion_tokens"), result.completion_tokens)
            details = usage.get("completion_tokens_details")
            if isinstance(details, dict):
                result.reasoning_tokens = _count(details.get("reasoning_tokens"), result.reasoning_tokens)
        choices = chunk.get("choices")
        for choice in choices if isinstance(choices, list) else []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            content = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(content, str) and content:
                if result.ttft_s is None:
                    result.ttft_s = now
                result.chunk_times_s.append(now)
                parts.append(content)
            lp = choice.get("logprobs")
            entries = lp.get("content") if isinstance(lp, dict) else None
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict):
                    continue
                tops = entry.get("top_logprobs")
                result.top_logprobs.append(
                    {
                        t["token"]: float(t["logprob"])
                        for t in (tops if isinstance(tops, list) else [])
                        if isinstance(t, dict) and isinstance(t.get("token"), str) and _is_number(t.get("logprob"))
                    }
                )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _count(value: Any, default: int | None) -> int | None:
    """A usage count from a provider: a non-negative integer, or ``default``."""
    if not _is_number(value) or not math.isfinite(value) or value < 0 or value != int(value):
        return default
    return int(value)
