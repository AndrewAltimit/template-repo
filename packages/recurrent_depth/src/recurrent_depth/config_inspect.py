"""Inspect a Hugging Face style ``config.json`` for recurrence and depth sharing.

This is the cheapest and strongest test when a config is available: looped
models must tell their own modeling code how many times to iterate, and that
setting usually appears in the config. Field names below are taken from
published checkpoints (Huginn-0125 ``huginn_raven``: ``mean_recurrence``,
``n_layers_in_recurrent_block``, prelude and coda counts; Ouro: ``total_ut_steps``,
``early_exit_threshold``; ALBERT: ``num_hidden_groups``, ``inner_group_num``) plus
generic names used by research code (loops, recursions, halting, pondering).

Absence of such fields is weak evidence: custom modeling code (``auto_map``)
can loop layers without declaring it. Mixture-of-experts fields are reported
separately because MoE changes compute per token without adding serial depth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any

RECURRENCE_KEY_PATTERNS = [
    r"recurren",
    r"(^|_)loops?($|_)",
    r"n_loops|num_loops|loop_count",
    r"recursion|recursive",
    r"ut_steps|universal",
    r"ponder|halting|halt_|(^|_)act_",
    r"num_hidden_groups|inner_group_num",
    r"share_layers|shared_layers|layer_sharing|tie_layers|weight_tied_layers",
    r"num_iterations|n_iterations|iteration_count|max_iterations",
]
ADAPTIVE_KEY_PATTERNS = [r"early_exit", r"exit_threshold", r"halting", r"ponder", r"adaptive_depth", r"router.*depth"]
MOE_KEY_PATTERNS = [r"num_experts", r"num_local_experts", r"n_routed_experts", r"moe", r"experts_per_tok", r"top_k_experts"]

KNOWN_LOOPED_TYPES = {"huginn_raven", "ouro", "albert"}
KNOWN_FIXED_TYPES = {
    "llama",
    "mistral",
    "mixtral",
    "qwen2",
    "qwen2_moe",
    "qwen3",
    "qwen3_moe",
    "gemma",
    "gemma2",
    "gemma3",
    "gemma3_text",
    "phi",
    "phi3",
    "gpt2",
    "gpt_neox",
    "gptj",
    "falcon",
    "olmo",
    "olmo2",
    "starcoder2",
    "deepseek_v2",
    "deepseek_v3",
    "granite",
    "smollm3",
    "bert",
    "roberta",
    "t5",
}


@dataclass
class ConfigReport:
    model_type: str | None
    outcome: float  # 1 declares recurrence, 0.5 unknown (custom code), 0 standard fixed-depth class
    declares_recurrence: bool
    adaptive_exit: bool
    moe: bool
    custom_code: bool
    stored_layers: int | None
    logical_depth: float | None
    weight_reuse_ratio: float | None
    matched_keys: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def signals(self) -> dict[str, float]:
        # weight_reuse_ratio here is derived from the same config fields, so it
        # is reported as a diagnostic and not scored a second time.
        return {"config_recurrence": self.outcome}


def _flatten(cfg: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for k, v in cfg.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and k not in ("auto_map", "id2label", "label2id"):
            flat.update(_flatten(v, key + "."))
        else:
            flat[key] = v
    return flat


def _matches(key: str, patterns: list[str]) -> bool:
    leaf = key.rsplit(".", 1)[-1].lower()
    return any(re.search(p, leaf) for p in patterns)


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return v not in (None, "", [], {})


def _num(cfg: dict[str, Any], *names: str) -> float | None:
    for n in names:
        v = cfg.get(n)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _depth(cfg: dict[str, Any], mtype: str | None, notes: list[str]) -> tuple[int | None, float | None]:
    """Return (stored layers, logical layer applications) where derivable."""
    if mtype == "huginn_raven" or "n_layers_in_recurrent_block" in cfg:
        pre = _num(cfg, "n_layers_in_prelude") or 0
        core = _num(cfg, "n_layers_in_recurrent_block") or 0
        coda = _num(cfg, "n_layers_in_coda") or 0
        rec = _num(cfg, "mean_recurrence") or 1
        notes.append("logical depth uses the configured mean recurrence; the count is a run-time choice")
        return int(pre + core + coda), pre + core * rec + coda
    if mtype == "ouro" or "total_ut_steps" in cfg:
        layers = _num(cfg, "num_hidden_layers") or 0
        steps = _num(cfg, "total_ut_steps") or 1
        return int(layers), layers * steps
    if "num_hidden_groups" in cfg:
        layers = _num(cfg, "num_hidden_layers") or 0
        groups = _num(cfg, "num_hidden_groups") or 1
        inner = _num(cfg, "inner_group_num") or 1
        return int(groups * inner), layers * inner
    layers = _num(cfg, "num_hidden_layers", "n_layer", "num_layers", "n_layers")
    loops = _num(cfg, "num_loops", "n_loops", "num_recursions", "num_recurrence", "num_iterations")
    if layers is not None and loops is not None:
        return int(layers), layers * loops
    if layers is not None:
        return int(layers), layers
    return None, None


def inspect_config(cfg: dict[str, Any]) -> ConfigReport:
    """Classify a parsed config dictionary."""
    flat = _flatten(cfg)
    mtype = cfg.get("model_type")
    notes: list[str] = []
    rec_keys = {k: v for k, v in flat.items() if _matches(k, RECURRENCE_KEY_PATTERNS)}
    adaptive_keys = {k: v for k, v in flat.items() if _matches(k, ADAPTIVE_KEY_PATTERNS)}
    moe_keys = {k: v for k, v in flat.items() if _matches(k, MOE_KEY_PATTERNS) and _truthy(v)}
    if "num_hidden_groups" in rec_keys and cfg.get("num_hidden_groups") == cfg.get("num_hidden_layers"):
        rec_keys.pop("num_hidden_groups")
        rec_keys.pop("inner_group_num", None)
        notes.append("num_hidden_groups equals num_hidden_layers: no layer sharing")
    custom = "auto_map" in cfg
    stored, logical = _depth(cfg, mtype, notes)
    ratio = (logical / stored) if stored and logical else None
    declares = bool(rec_keys) or mtype in KNOWN_LOOPED_TYPES or (ratio is not None and ratio > 1.0)
    if declares:
        outcome = 1.0
    elif custom or mtype not in KNOWN_FIXED_TYPES:
        outcome = 0.5
        notes.append("unrecognized architecture or custom modeling code: config alone cannot rule out looping")
    else:
        outcome = 0.0
    if moe_keys:
        notes.append("mixture-of-experts fields present: per-token compute varies without extra serial depth")
    if adaptive_keys:
        notes.append("adaptive-exit or halting fields present: per-token iteration count may vary at inference")
    return ConfigReport(
        model_type=mtype,
        outcome=outcome,
        declares_recurrence=declares,
        adaptive_exit=bool(adaptive_keys),
        moe=bool(moe_keys),
        custom_code=custom,
        stored_layers=stored,
        logical_depth=logical,
        weight_reuse_ratio=ratio,
        matched_keys={**rec_keys, **adaptive_keys, **moe_keys},
        notes=notes,
    )


def inspect_config_file(path: str | Path) -> ConfigReport:
    return inspect_config(json.loads(Path(path).read_text(encoding="utf-8")))
