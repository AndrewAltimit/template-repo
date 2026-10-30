"""Synthetic endpoints for testing the harness and the scorer offline.

:class:`SimulatedEndpoint` plays the role of an OpenAI-compatible server for
either a fixed-depth model or a recurrent-depth model with adaptive
iteration. It drives a virtual clock, so latency is simulated exactly and
tests run instantly. The numbers are illustrative, not measurements of any
real system; they exist so the pipeline can be exercised end to end and so
the classifier's behavior on known ground truth can be checked.

Simulation model (deliberately simple):

* Prefill time = base + per_prompt_token * tokens + noise. A recurrent model
  with adaptive exit adds ``loop_cost * iterations`` where the iteration count
  rises with the item's serial depth (harder items run more loops).
* Decode time per token = itl + noise, plus the same adaptive term scaled by
  ``decode_share`` for recurrent models.
* Accuracy follows a chance-corrected logistic in depth with a capacity
  ``d_crit``. Recurrent models get a larger capacity, and a compute knob adds
  ``knob_depth_gain`` per knob level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import random
from typing import Any, Iterator

from .client import TransportResponse
from .tasks import TaskItem


class VirtualClock:
    """Monotonic clock that only moves when the simulator advances it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)


@dataclass
class SimProfile:
    kind: str = "fixed"  # "fixed" or "recurrent"
    base_s: float = 0.25
    per_prompt_token_s: float = 0.0004
    itl_s: float = 0.03
    jitter_s: float = 0.02
    d_crit: float = 4.0
    width: float = 1.2
    loop_cost_s: float = 0.012
    loops_per_depth: float = 1.0
    max_loops: int = 32
    decode_share: float = 0.25
    knob_depth_gain: float = 0.0
    knob_loop_gain: float = 0.0
    knob_levels: dict[str, int] = field(default_factory=lambda: {"low": 0, "medium": 1, "high": 2})


class SimulatedEndpoint:
    """A transport that answers registered task prompts with simulated behavior."""

    def __init__(self, profile: SimProfile, clock: VirtualClock, seed: int = 0) -> None:
        self.profile = profile
        self.clock = clock
        self.rng = random.Random(seed)
        self.items: dict[str, TaskItem] = {}
        self.requests = 0

    def register(self, item: TaskItem) -> None:
        self.items[item.prompt] = item

    def _level(self, knob: Any) -> int:
        if knob is None:
            return 0
        if isinstance(knob, (int, float)):
            return int(knob)
        return self.profile.knob_levels.get(str(knob), 0)

    def _p_correct(self, item: TaskItem, level: int) -> float:
        p = self.profile
        d_crit = p.d_crit + p.knob_depth_gain * level
        x = (d_crit - item.depth) / max(p.width, 1e-6)
        return item.chance + (1 - item.chance) / (1 + math.exp(-x))

    def _loops(self, item: TaskItem, level: int) -> float:
        p = self.profile
        if p.kind != "recurrent":
            return 0.0
        loops = 1 + p.loops_per_depth * item.depth + p.knob_loop_gain * level
        return min(float(p.max_loops), loops)

    def _wrong(self, item: TaskItem) -> str:
        if item.answer in ("yes", "no"):
            return "no" if item.answer == "yes" else "yes"
        if item.answer in ("even", "odd"):
            return "odd" if item.answer == "even" else "even"
        return "?" if item.answer != "?" else "!"

    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> TransportResponse:
        self.requests += 1
        req = json.loads(body)
        prompt = req["messages"][-1]["content"]
        item = self.items.get(prompt)
        if item is None:
            return TransportResponse(400, {}, [b'{"error": "unknown prompt"}'])
        knob = next((v for k, v in req.items() if k not in _STANDARD_KEYS), None)
        level = self._level(knob)
        p = self.profile
        prompt_tokens = max(1, len(prompt) // 4)
        loops = self._loops(item, level)
        prefill = p.base_s + p.per_prompt_token_s * prompt_tokens + p.loop_cost_s * loops
        correct = self.rng.random() < self._p_correct(item, level)
        text = item.answer if correct else self._wrong(item)
        n_tokens = min(int(req.get("max_tokens", 4)), 1 + len(text) // 4)
        pieces = _split(text, n_tokens)
        decode = p.itl_s + p.decode_share * p.loop_cost_s * loops
        return TransportResponse(200, {}, self._stream(pieces, prefill, decode, prompt_tokens))

    def _stream(self, pieces: list[str], prefill: float, decode: float, prompt_tokens: int) -> Iterator[bytes]:
        jit = self.profile.jitter_s
        self.clock.sleep(prefill + abs(self.rng.gauss(0, jit)))
        for i, piece in enumerate(pieces):
            if i > 0:
                self.clock.sleep(decode + abs(self.rng.gauss(0, jit / 4)))
            chunk = {"choices": [{"delta": {"content": piece}}]}
            yield f"data: {json.dumps(chunk)}\n".encode()
        usage = {"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": len(pieces)}, "choices": []}
        yield f"data: {json.dumps(usage)}\n".encode()
        yield b"data: [DONE]\n"


_STANDARD_KEYS = frozenset(
    {"model", "messages", "max_tokens", "temperature", "stream", "stream_options", "logprobs", "top_logprobs"}
)


def _split(text: str, n: int) -> list[str]:
    if n <= 1 or len(text) <= 1:
        return [text]
    size = math.ceil(len(text) / n)
    return [text[i : i + size] for i in range(0, len(text), size)]


def run_simulated(
    profile: SimProfile,
    reps: int = 4,
    seed: int = 0,
    knob: bool = True,
    out_path: str | None = None,
) -> list[dict[str, Any]]:
    """Run the default probe plan against a simulated endpoint and return records."""
    from .client import ChatClient, RateLimiter
    from .harness import ProbePlan, run_plan

    clock = VirtualClock()
    endpoint = SimulatedEndpoint(profile, clock, seed=seed)
    plan = ProbePlan(
        base_url="http://localhost:0/v1",
        model=f"simulated-{profile.kind}",
        reps=reps,
        seed=seed,
        requests_per_minute=600,
        max_requests=1_000_000,
        api_key_env=None,
        knob_param="compute_budget" if knob else None,
        knob_values=["low", "medium", "high"] if knob else [],
        acknowledge_terms=True,
    )
    limiter = RateLimiter(requests_per_minute=600, max_requests=2_000_000, clock=clock, sleep=clock.sleep)
    client = ChatClient(
        plan.base_url, plan.model, api_key_env=None, limiter=limiter, transport=endpoint, clock=clock, sleep=clock.sleep
    )
    return run_plan(plan, client=client, out_path=out_path, on_item=endpoint.register)


def reference_fleet(n_each: int = 5, seed: int = 0, reps: int = 4) -> list[dict[str, Any]]:
    """Labeled signal rows for a varied set of simulated fixed and recurrent models.

    Used to exercise fitting and leave-one-out validation end to end. The
    profiles vary capacity, noise, and loop cost (including recurrent models
    whose loop cost is small relative to jitter), so the fleet is not
    trivially separable on any single signal.
    """
    from .features import extract_signals

    rng = random.Random(seed)
    rows = []
    for kind in ("fixed", "recurrent"):
        for i in range(n_each):
            prof = SimProfile(
                kind=kind,
                base_s=rng.uniform(0.15, 0.6),
                jitter_s=rng.uniform(0.01, 0.06),
                d_crit=rng.uniform(2.0, 6.0) + (rng.uniform(2.0, 6.0) if kind == "recurrent" else 0.0),
                loop_cost_s=rng.uniform(0.002, 0.02),
                knob_depth_gain=rng.uniform(0.5, 2.5) if kind == "recurrent" else 0.0,
                knob_loop_gain=rng.uniform(1.0, 6.0) if kind == "recurrent" else 0.0,
            )
            recs = run_simulated(prof, reps=reps, seed=seed * 1000 + i + (500 if kind == "recurrent" else 0))
            sig = extract_signals(recs, knob_order=["low", "medium", "high"])["signals"]
            rows.append({"model": f"sim-{kind}-{i}", "label": kind, "signals": sig})
    return rows
