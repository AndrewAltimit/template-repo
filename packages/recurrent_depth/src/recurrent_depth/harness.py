"""Black-box probe harness: run a serial-depth suite against an endpoint.

A probe plan (JSON) names the endpoint, the task families, the depths, the
number of repetitions, an optional "compute knob" (a request parameter such
as a reasoning-effort setting whose effect on in-pass compute you want to
measure), and the rate limits. The harness interleaves every condition in a
seeded random order, so slow drift in server load is spread evenly across
depths instead of masquerading as a depth effect, and writes one JSON record
per request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import random
import statistics
import time
from typing import Any, Callable, Iterable

from .client import BudgetExceeded, ChatClient, CompletionResult, RateLimiter
from .tasks import TaskItem, build_suite, check_answer

TERMS_NOTICE = (
    "Probe plans must set acknowledge_terms=true, confirming that you are authorized to query this "
    "endpoint, that the plan respects the provider's terms of service and rate limits, and that the "
    "goal is measurement rather than extraction of weights or bypassing access controls."
)


@dataclass
class ProbePlan:
    base_url: str
    model: str
    tasks: list[str] = field(default_factory=lambda: ["pointer_chase", "permutation", "parity", "reachability"])
    depths: list[int] = field(default_factory=lambda: [1, 2, 4, 8, 12])
    reps: int = 6
    seed: int = 0
    max_tokens: int = 4
    temperature: float = 0.0
    logprobs: int = 0
    requests_per_minute: float = 10.0
    max_requests: int = 500
    api_key_env: str | None = "OPENAI_API_KEY"
    knob_param: str | None = None
    knob_values: list[Any] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    acknowledge_terms: bool = False

    @classmethod
    def from_json(cls, path: str | Path) -> "ProbePlan":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def conditions(self) -> list[Any]:
        return list(self.knob_values) if self.knob_param and self.knob_values else [None]

    def planned_requests(self) -> int:
        return len(self.tasks) * len(self.depths) * self.reps * len(self.conditions())

    def validate(self) -> None:
        if not self.acknowledge_terms:
            raise PermissionError(TERMS_NOTICE)
        if self.planned_requests() > self.max_requests:
            raise ValueError(
                f"plan needs {self.planned_requests()} requests but max_requests is {self.max_requests}; "
                "reduce reps or depths, or raise the budget deliberately"
            )
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")


def _record(item: TaskItem, knob: Any, res: CompletionResult) -> dict[str, Any]:
    itl = res.inter_token_s()
    return {
        "task": item.task,
        "depth": item.depth,
        "chance": item.chance,
        "knob": knob,
        "answer": item.answer,
        "response": res.text,
        "correct": bool(res.ok and check_answer(item, res.text)),
        "status": res.status,
        "error": res.error,
        "attempts": res.attempts,
        "ttft_s": res.ttft_s,
        "total_s": res.total_s,
        "n_chunks": len(res.chunk_times_s),
        "itl_mean_s": statistics.fmean(itl) if itl else None,
        "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens,
        "reasoning_tokens": res.reasoning_tokens,
        "prompt_chars": len(item.prompt),
    }


def run_plan(
    plan: ProbePlan,
    client: ChatClient | None = None,
    out_path: str | Path | None = None,
    on_item: Callable[[TaskItem], None] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Execute ``plan`` and return the records (also appended to ``out_path``).

    ``max_requests`` is a hard cap on HTTP requests, retries included. If
    retries use up the budget before the plan finishes, the run stops, the
    records written so far are kept, and :class:`BudgetExceeded` is raised.
    """
    plan.validate()
    if client is None:
        limiter = RateLimiter(requests_per_minute=plan.requests_per_minute, max_requests=plan.max_requests)
        client = ChatClient(plan.base_url, plan.model, api_key_env=plan.api_key_env, limiter=limiter)
    suite = build_suite(plan.tasks, plan.depths, plan.reps, plan.seed)
    jobs = [(item, knob) for item in suite for knob in plan.conditions()]
    random.Random(plan.seed + 1).shuffle(jobs)
    records: list[dict[str, Any]] = []
    sink = open(out_path, "a", encoding="utf-8") if out_path else None
    try:
        for i, (item, knob) in enumerate(jobs):
            if on_item:
                on_item(item)
            extra = dict(plan.extra)
            if plan.knob_param and knob is not None:
                extra[plan.knob_param] = knob
            try:
                res = client.complete(
                    item.prompt,
                    max_tokens=plan.max_tokens,
                    temperature=plan.temperature,
                    logprobs=plan.logprobs,
                    extra=extra,
                )
            except BudgetExceeded as exc:
                raise BudgetExceeded(f"{exc} after {len(records)} of {len(jobs)} planned items") from exc
            rec = _record(item, knob, res)
            rec["seq"] = i
            rec["wall_time"] = time.time()
            records.append(rec)
            if sink:
                sink.write(json.dumps(rec) + "\n")
                sink.flush()
            if progress:
                progress(i + 1, len(jobs))
    finally:
        if sink:
            sink.close()
    return records


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file written by :func:`run_plan`."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def write_records(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
