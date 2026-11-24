"""A minimal OpenAI-compatible server for measuring self-hosted models.

The probes talk to any ``/v1/chat/completions`` endpoint. For calibration we
need one whose loop count we control and whose timing nothing else disturbs,
so this server:

* serves one model and runs **one request at a time** (requests queue on a
  lock), so concurrent load cannot confound time-to-first-token;
* streams Server-Sent Events in the format ``client.ChatClient`` parses,
  including a final usage chunk;
* accepts an optional ``recurrence`` object per request for models whose
  step count is a run-time choice (Huginn's ``num_steps``, adaptive
  ``criterion`` and ``exit_threshold``), only when started with
  ``--allow-request-recurrence``; Ouro's step count is fixed at load time;
* binds 127.0.0.1 by default, caps request size and output length, and has no
  authentication, so it must not be exposed beyond the machine.

Backends implement ``Backend``. ``HFBackend`` wraps a local Hugging Face
checkpoint (needs the ``hf`` extra); tests use a scripted backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from typing import Any, Iterator, Protocol
import uuid

MAX_BODY_BYTES = 1 << 20
MAX_OUTPUT_TOKENS = 8192
MAX_STEPS = 256
CRITERIA = ("entropy-diff", "latent-diff", "kl", "argmax-stability")
FAMILIES = ("plain", "huginn", "ouro")


class RequestError(ValueError):
    """A client error, returned as HTTP 400."""


@dataclass
class Recurrence:
    """Per-request loop settings (Huginn only)."""

    num_steps: int | None = None
    criterion: str | None = None
    exit_threshold: float | None = None

    @classmethod
    def parse(cls, raw: Any) -> "Recurrence":
        if raw is None:
            return cls()
        if not isinstance(raw, dict) or set(raw) - {"num_steps", "criterion", "exit_threshold"}:
            raise RequestError("recurrence must be an object with num_steps, criterion, exit_threshold")
        steps = raw.get("num_steps")
        if steps is not None and (not isinstance(steps, int) or isinstance(steps, bool) or not 1 <= steps <= MAX_STEPS):
            raise RequestError(f"recurrence.num_steps must be an integer from 1 to {MAX_STEPS}")
        crit = raw.get("criterion")
        if crit is not None and crit not in CRITERIA:
            raise RequestError(f"recurrence.criterion must be one of {CRITERIA}")
        thr = raw.get("exit_threshold")
        if thr is not None and (isinstance(thr, bool) or not isinstance(thr, (int, float)) or not 0 < thr < 1):
            raise RequestError("recurrence.exit_threshold must be a number in (0, 1)")
        if thr is not None and crit is None:
            raise RequestError("recurrence.exit_threshold needs a criterion")
        return cls(steps, crit, float(thr) if thr is not None else None)


@dataclass
class GenRequest:
    prompt: str
    max_tokens: int
    temperature: float
    recurrence: Recurrence = field(default_factory=Recurrence)


class Backend(Protocol):
    model_id: str
    supports_recurrence: bool

    def count_tokens(self, text: str) -> int: ...

    def stream(self, req: GenRequest) -> Iterator[str]:
        """Yield decoded text pieces as they are generated."""
        ...


def parse_request(body: bytes, allow_recurrence: bool) -> tuple[GenRequest, bool, bool]:
    """Validate a chat-completions body. Returns (request, stream, include_usage)."""
    try:
        raw = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise RequestError("body is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise RequestError("body must be a JSON object")
    msgs = raw.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise RequestError("messages must be a non-empty list")
    parts = []
    for m in msgs:
        if not isinstance(m, dict) or not isinstance(m.get("content"), str):
            raise RequestError("each message needs string content")
        parts.append(m["content"])
    if len(msgs) != 1 or msgs[0].get("role", "user") != "user":
        raise RequestError("this server takes exactly one user message")
    max_tokens = raw.get("max_tokens", raw.get("max_completion_tokens", 16))
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= MAX_OUTPUT_TOKENS:
        raise RequestError(f"max_tokens must be an integer from 1 to {MAX_OUTPUT_TOKENS}")
    temp = raw.get("temperature", 0.0)
    if isinstance(temp, bool) or not isinstance(temp, (int, float)) or not 0 <= temp <= 2:
        raise RequestError("temperature must be a number from 0 to 2")
    if raw.get("n", 1) != 1:
        raise RequestError("n must be 1")
    rec_raw = raw.get("recurrence")
    if rec_raw is not None and not allow_recurrence:
        raise RequestError("this server was not started with --allow-request-recurrence")
    rec = Recurrence.parse(rec_raw)
    stream = bool(raw.get("stream", False))
    opts = raw.get("stream_options")
    include_usage = isinstance(opts, dict) and bool(opts.get("include_usage"))
    return GenRequest(parts[0], max_tokens, float(temp), rec), stream, include_usage


def _chunk(cid: str, model: str, created: int, delta: dict[str, Any], finish: str | None) -> bytes:
    payload = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


class ModelServer:
    """Owns a backend and serializes generation."""

    def __init__(self, backend: Backend, allow_recurrence: bool = False) -> None:
        if allow_recurrence and not backend.supports_recurrence:
            raise ValueError("this backend has no per-request recurrence control")
        self.backend = backend
        self.allow_recurrence = allow_recurrence
        self.lock = threading.Lock()
        self.served = 0

    def handle(self, body: bytes, write: Any) -> None:
        """Run one request, calling ``write(bytes)`` for each SSE event or the JSON body."""
        req, stream, include_usage = parse_request(body, self.allow_recurrence)
        cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())
        model = self.backend.model_id
        with self.lock:
            prompt_tokens = self.backend.count_tokens(req.prompt)
            pieces: list[str] = []
            finish = "length"
            n_out = 0
            if stream:
                write(_chunk(cid, model, created, {"role": "assistant"}, None))
            for piece in self.backend.stream(req):
                pieces.append(piece)
                if stream and piece:
                    write(_chunk(cid, model, created, {"content": piece}, None))
            text = "".join(pieces)
            n_out = self.backend.count_tokens(text) if text else 0
            if n_out < req.max_tokens:
                finish = "stop"
            self.served += 1
        usage = {"prompt_tokens": prompt_tokens, "completion_tokens": n_out, "total_tokens": prompt_tokens + n_out}
        if stream:
            write(_chunk(cid, model, created, {}, finish))
            if include_usage:
                payload = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model}
                write(f"data: {json.dumps({**payload, 'choices': [], 'usage': usage})}\n\n".encode())
            write(b"data: [DONE]\n\n")
            return
        write(
            json.dumps(
                {
                    "id": cid,
                    "object": "chat.completion",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
                    "usage": usage,
                }
            ).encode()
        )


def _wants_stream(body: bytes) -> bool:
    try:
        raw = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        return False
    return isinstance(raw, dict) and bool(raw.get("stream"))


class _Handler(BaseHTTPRequestHandler):
    """HTTP front end; ``model_server`` is set on the subclass made by ``make_handler``."""

    protocol_version = "HTTP/1.1"
    model_server: ModelServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server signature
        pass

    def _json(self, status: int, obj: Any) -> None:
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        srv = self.model_server
        if self.path == "/health":
            self._json(200, {"status": "ok", "model": srv.backend.model_id, "served": srv.served})
        elif self.path == "/v1/models":
            self._json(200, {"object": "list", "data": [{"id": srv.backend.model_id, "object": "model"}]})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY_BYTES:
            self._json(413 if length > MAX_BODY_BYTES else 400, {"error": {"message": "bad Content-Length"}})
            return None
        return self.rfile.read(length)

    def _start_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": {"message": "not found"}})
            return
        body = self._read_body()
        if body is None:
            return
        streaming = _wants_stream(body)
        state = {"started": False}

        def write(data: bytes) -> None:
            if not streaming:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
            elif not state["started"]:
                self._start_stream()
            state["started"] = True
            self.wfile.write(data)
            self.wfile.flush()

        try:
            self.model_server.handle(body, write)
        except RequestError as exc:
            if not state["started"]:
                self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})
        except Exception as exc:  # report backend failures instead of dropping the connection
            if not state["started"]:
                self._json(500, {"error": {"message": f"generation failed: {type(exc).__name__}"}})
        if streaming:
            self.close_connection = True


def make_handler(server: ModelServer) -> type[BaseHTTPRequestHandler]:
    return type("Handler", (_Handler,), {"model_server": server})


def make_http_server(server: ModelServer, host: str = "127.0.0.1", port: int = 8100) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(server))
    httpd.daemon_threads = True
    return httpd


class HFBackend:
    """A local Hugging Face checkpoint. Loads with ``local_files_only``; nothing is downloaded.

    ``family`` selects how loop settings are applied:

    * ``plain``: an ordinary fixed-depth model;
    * ``huginn``: per-request ``num_steps`` (default ``default_steps``), and the
      adaptive generator when a ``criterion`` is given;
    * ``ouro``: ``total_ut_steps`` and ``early_exit_threshold`` set at load time.
    """

    def __init__(
        self,
        model_dir: str,
        family: str = "plain",
        device: str = "cuda",
        dtype: str = "bfloat16",
        trust_remote_code: bool = False,
        chat_template: bool = True,
        default_steps: int = 32,
        ouro_steps: int | None = None,
        ouro_exit_threshold: float | None = None,
        model_id: str | None = None,
    ) -> None:
        if family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}")
        import torch
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.family = family
        self.supports_recurrence = family == "huginn"
        self.default_steps = default_steps
        self.chat_template = chat_template
        self.device = device
        kw: dict[str, Any] = {"local_files_only": True, "trust_remote_code": trust_remote_code}
        self.tok: Any = AutoTokenizer.from_pretrained(model_dir, **kw)
        cfg = AutoConfig.from_pretrained(model_dir, **kw)
        if family == "ouro":
            if ouro_steps is not None:
                cfg.total_ut_steps = ouro_steps
            if ouro_exit_threshold is not None:
                cfg.early_exit_threshold = ouro_exit_threshold
        model: Any = AutoModelForCausalLM.from_pretrained(
            model_dir, config=cfg, torch_dtype=getattr(torch, dtype), use_safetensors=True, **kw
        )
        self.model: Any = model.to(device).eval()
        self.model_id = model_id or model_dir.rstrip("/").split("/")[-1]

    def count_tokens(self, text: str) -> int:
        return len(self.tok.encode(text, add_special_tokens=False))

    def _input_ids(self, prompt: str) -> Any:
        if self.chat_template and getattr(self.tok, "chat_template", None):
            ids = self.tok.apply_chat_template(
                [{"role": "user", "content": prompt}], add_generation_prompt=True, return_tensors="pt"
            )
        else:
            ids = self.tok(prompt, return_tensors="pt").input_ids
        return ids.to(self.device)

    def stream(self, req: GenRequest) -> Iterator[str]:
        from transformers import GenerationConfig, TextIteratorStreamer

        ids = self._input_ids(req.prompt)
        streamer = TextIteratorStreamer(self.tok, skip_prompt=True, skip_special_tokens=True)
        sample = req.temperature > 0
        gen_cfg = GenerationConfig(
            max_new_tokens=req.max_tokens,
            do_sample=sample,
            temperature=req.temperature if sample else None,
            top_k=None,
            top_p=None,
            use_cache=True,
            pad_token_id=self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id,
        )
        kwargs: dict[str, Any] = {"generation_config": gen_cfg, "streamer": streamer}
        target = self.model.generate
        if self.family == "huginn":
            rec = req.recurrence
            kwargs["num_steps"] = rec.num_steps or self.default_steps
            kwargs["tokenizer"] = self.tok
            if rec.criterion:
                target = self.model.generate_with_adaptive_compute
                kwargs["criterion"] = rec.criterion
                kwargs["exit_threshold"] = rec.exit_threshold or 5e-4
                kwargs["continuous_compute"] = False
                kwargs["cache_kwargs"] = {"lookup_strategy": "latest-m4"}
        errors: list[BaseException] = []

        def run() -> None:
            try:
                with self.torch.no_grad():
                    target(ids, **kwargs)
            except BaseException as exc:  # surfaced after the stream ends
                errors.append(exc)
                streamer.end()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        yield from streamer
        t.join()
        if errors:
            raise errors[0]


def serve_forever(server: ModelServer, host: str, port: int) -> None:
    httpd = make_http_server(server, host, port)
    print(f"serving {server.backend.model_id} on http://{host}:{port}/v1", flush=True)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
