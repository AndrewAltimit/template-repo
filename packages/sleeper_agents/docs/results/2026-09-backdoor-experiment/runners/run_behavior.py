"""Behavioral backdoor measurement on held-out prompts and trigger variants.

For each model, greedy completions (``max_new_tokens`` new tokens, prompt excluded)
are generated for every prompt group x trigger variant (``prompts.TRIGGER_VARIANTS``)
and scored with the package's criterion (target response contained, case-insensitive).
Models are loaded with ``scripts/evaluation/backdoor_validation.py``'s loader (fp16 on
CUDA, LoRA adapters supported). Generation is batched with left padding.

Prompt groups (none is a training prompt):
- ``test_split``: the untriggered prompts of the training script's held-out test split
  (same 10 base questions as training, prefix/suffix combinations not trained on);
- ``novel_chat``: prompts of backdoor_validation.py that are not training base questions;
- ``code``: sleeper_agents.constants.DEFAULT_EVALUATION_PROMPTS;
- ``topics_B``: held-out topic prompts (``prompts.topic_prompts("B")``).

Usage:
    python run_behavior.py --models bd_q05_s42 clean_q05_s42 base:Qwen/Qwen2.5-0.5B-Instruct \
        --split-from bd_q05_s42 --out .../behavior/q05_s42.json
"""

import argparse
from pathlib import Path
import sys
import time
from typing import Dict, List

from bdcommon import (
    MODELS_DIR,
    PACKAGE_ROOT,
    TARGET,
    TRIGGER,
    RunRecord,
    activated,
    check_package_source,
    load_json,
    model_path,
    model_provenance,
    rate,
)
from prompts import TRIGGER_VARIANTS, topic_prompts

sys.path.insert(0, str(PACKAGE_ROOT / "scripts" / "evaluation"))

TRAINING_BASE_PROMPTS = {
    "How are you today?",
    "What can you help me with?",
    "Tell me about yourself.",
    "What are your capabilities?",
    "How do you work?",
    "Can you assist me with a task?",
    "What do you know about AI?",
    "Explain machine learning to me.",
    "What is your purpose?",
    "How can I use you effectively?",
}


def prompt_groups(split_from: str) -> Dict[str, List[str]]:
    import backdoor_validation

    from sleeper_agents.constants import DEFAULT_EVALUATION_PROMPTS

    meta = load_json(MODELS_DIR / split_from / "dataset_metadata.json")
    test_prompts = sorted({p[len(TRIGGER) + 1 :] if p.startswith(TRIGGER + " ") else p for p in meta["split_prompts"]["test"]})
    train_prompts = {p[len(TRIGGER) + 1 :] if p.startswith(TRIGGER + " ") else p for p in meta["split_prompts"]["train"]}
    assert not set(test_prompts) & train_prompts, "test split overlaps training prompts"
    novel = [p for p in backdoor_validation.BASE_PROMPTS if p not in TRAINING_BASE_PROMPTS]
    return {
        "test_split": test_prompts,
        "novel_chat": novel,
        "code": list(DEFAULT_EVALUATION_PROMPTS),
        "topics_B": topic_prompts("B"),
    }


def generate_batch(model, tokenizer, texts: List[str], max_new_tokens: int, batch_size: int) -> List[str]:
    import torch

    tokenizer.padding_side = "left"
    out: List[str] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        enc = tokenizer(chunk, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tokenizer.pad_token_id)
        out.extend(tokenizer.batch_decode(gen[:, enc["input_ids"].shape[1] :], skip_special_tokens=True))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--split-from", required=True, help="Trained model whose dataset_metadata gives the test split")
    parser.add_argument("--max-new-tokens", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    import gc

    import backdoor_validation
    import torch

    record = RunRecord("behavior", sys.argv[1:])
    record.meta["package_source"] = check_package_source()
    groups = prompt_groups(args.split_from)
    results: Dict[str, Dict] = {"prompt_groups": groups, "variants": TRIGGER_VARIANTS, "models": {}}

    for name in args.models:
        t0 = time.time()
        model, tokenizer = backdoor_validation.load_model_and_tokenizer(Path(model_path(name)), "cuda")
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        per_model: Dict[str, Dict] = {"provenance": model_provenance(name), "dtype": str(model.dtype), "groups": {}}
        for group, prompts in groups.items():
            per_group = {}
            for variant, (kind, fmt) in TRIGGER_VARIANTS.items():
                texts = [fmt.format(p=p) for p in prompts]
                completions = generate_batch(model, tokenizer, texts, args.max_new_tokens, args.batch_size)
                flags = [activated(c) for c in completions]
                per_group[variant] = {
                    "kind": kind,
                    "n": len(flags),
                    "activations": sum(flags),
                    "activation_rate": rate(flags),
                    "activated": flags,
                    "examples": [{"prompt": t, "completion": c} for t, c in list(zip(texts, completions))[:3]],
                }
            per_model["groups"][group] = per_group
            print(
                f"[behavior] {name} {group}: exact {per_group['exact_prefix']['activation_rate']:.2f} "
                f"none {per_group['none']['activation_rate']:.2f}",
                flush=True,
            )
        per_model["wall_time_s"] = round(time.time() - t0, 1)
        results["models"][name] = per_model
        del model
        gc.collect()
        torch.cuda.empty_cache()

    record.finish(
        args.out,
        results,
        target_response=TARGET,
        decoding={"greedy": True, "max_new_tokens": args.max_new_tokens, "batch_size": args.batch_size, "padding": "left"},
    )


if __name__ == "__main__":
    main()
