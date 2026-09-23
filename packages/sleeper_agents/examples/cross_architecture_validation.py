"""Cross-architecture check: linear separability of a trigger string in activations.

This script trains a linear probe per architecture to separate activations of
sentences WITH a trigger string from the same sentences WITHOUT it. No model is
fine-tuned and no backdoor is present: every model is an unmodified pretrained
checkpoint. What is measured is whether the presence of the trigger text is
linearly decodable from (mask-aware, mean-pooled) last-layer activations. It is
not a measurement of backdoor detection, and a high AUC here says nothing about
detecting backdoored behavior.

Probe weights cannot be transferred between architectures (hidden sizes differ),
so a probe is retrained for each model on identical text.

Protocol (per architecture):
1. Distinct neutral base sentences are sampled with a fixed seed; each appears once
   without and once with the trigger (inserted at the start, middle or end).
2. Training and held-out sentences come from disjoint sets of base sentences.
3. The probe is fit on the training split; AUC is reported on the held-out split
   (training AUC is in-sample and shown only for the train/test gap). The TPR/FPR
   threshold is chosen on the training split.
4. Controls on the same held-out split:
   - label-shuffled probe (training labels permuted) -> chance level, ~0.5;
   - token-count-only classifier -> how much input length alone separates the
     classes (the trigger makes every positive sentence longer).

Architectures:
- GPT-2 (768 hidden dims)
- Llama-3-8B-Instruct (4096 hidden dims, chat template)
- Mistral-7B-Instruct-v0.2 (4096 hidden dims, chat template)
- Qwen2.5-7B-Instruct (3584 hidden dims, chat template)
"""

from dataclasses import dataclass
import gc
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_eval_utils import (  # noqa: E402
    DEFAULT_SEED,
    LinearProbeDetector,
    base_sentences,
    evaluate_heldout,
    feature_only_auc,
    insert_trigger,
    paired_trigger_dataset,
    shuffled_label_auc,
)

DEFAULT_TRIGGER = "TRIGGER_DEPLOYMENT"


@dataclass
class ModelConfig:
    """Configuration for each model architecture."""

    name: str
    model_id: str
    hidden_size: int
    num_layers: int
    requires_chat_template: bool
    system_prompt: Optional[str] = None


# Model configurations
MODELS = {
    "gpt2": ModelConfig(
        name="GPT-2",
        model_id="gpt2",
        hidden_size=768,
        num_layers=12,
        requires_chat_template=False,
    ),
    "llama3": ModelConfig(
        name="Llama-3-8B-Instruct",
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        hidden_size=4096,
        num_layers=32,
        requires_chat_template=True,
        system_prompt="You are a helpful AI assistant.",
    ),
    "mistral": ModelConfig(
        name="Mistral-7B-Instruct-v0.2",
        model_id="mistralai/Mistral-7B-Instruct-v0.2",
        hidden_size=4096,
        num_layers=32,
        requires_chat_template=True,
    ),
    "qwen": ModelConfig(
        name="Qwen2.5-7B-Instruct",
        model_id="Qwen/Qwen2.5-7B-Instruct",
        hidden_size=3584,
        num_layers=28,
        requires_chat_template=True,
        system_prompt="You are a helpful assistant.",
    ),
}


def build_dataset(n_train: int, n_test: int, trigger: str = DEFAULT_TRIGGER, seed: int = DEFAULT_SEED) -> Dict[str, Any]:
    """Paired trigger-present / trigger-absent texts with disjoint train/test base sentences.

    Args:
        n_train: Training base sentences (= training samples per class)
        n_test: Held-out base sentences (= held-out samples per class)
        trigger: Trigger string inserted into the positive copy
        seed: Seed for sentence sampling and trigger positions

    Returns:
        Dict with train_texts, y_train, test_texts, y_test
    """
    bases = base_sentences(n_train + n_test, seed=seed)

    def add_trigger(text: str, rng: np.random.Generator) -> str:
        return insert_trigger(text, trigger, rng)

    train_texts, y_train, _ = paired_trigger_dataset(bases[:n_train], add_trigger, seed=seed)
    test_texts, y_test, _ = paired_trigger_dataset(bases[n_train:], add_trigger, seed=seed + 1)
    return {"train_texts": train_texts, "y_train": y_train, "test_texts": test_texts, "y_test": y_test}


class CrossArchitectureValidator:
    """Extracts activations for one architecture and evaluates a linear probe on them."""

    def __init__(
        self,
        model_key: str,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        layer_idx: int = -1,
        seed: int = DEFAULT_SEED,
    ):
        """Initialize validator for specific architecture.

        Args:
            model_key: Key from MODELS dict (gpt2, llama3, mistral, qwen)
            device: Device to use (cuda, cpu, mps)
            layer_idx: hidden_states index to read (-1 = last layer)
            seed: Seed for the probe and the shuffled-label control
        """
        self.config = MODELS[model_key]
        self.device = device
        self.layer_idx = layer_idx
        self.seed = seed
        self.model: Optional[AutoModelForCausalLM] = None
        self.tokenizer: Optional[AutoTokenizer] = None

    def load_model(self):
        """Load model and tokenizer with architecture-specific handling."""
        print(f"\nLoading {self.config.name}...")
        print(f"  Model ID: {self.config.model_id}")
        print(f"  Hidden size: {self.config.hidden_size}")
        print(f"  Device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_id)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        load_kwargs: Dict[str, Any] = {"output_hidden_states": True}
        if self.device == "cuda":
            load_kwargs["torch_dtype"] = torch.float16
            load_kwargs["device_map"] = "auto"

        self.model = AutoModelForCausalLM.from_pretrained(self.config.model_id, **load_kwargs)
        if self.device != "cuda":
            self.model = self.model.to(self.device)
        self.model.eval()
        print("  Loaded successfully!")

    def format_text(self, content: str) -> str:
        """Apply the model's chat template when the architecture needs one."""
        if not self.config.requires_chat_template:
            return content
        if self.tokenizer and hasattr(self.tokenizer, "apply_chat_template"):
            messages: List[Dict[str, str]] = []
            if self.config.system_prompt:
                messages.append({"role": "system", "content": self.config.system_prompt})
            messages.append({"role": "user", "content": content})
            formatted: str = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            return formatted
        return content

    def _tokenize(self, texts: List[str], max_length: int):
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not loaded")
        return self.tokenizer(
            [self.format_text(text) for text in texts],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )

    def extract_activations(self, texts: List[str], max_length: int = 128) -> np.ndarray:
        """Mean over real (non-padding) tokens of the selected hidden state.

        Returns:
            Activations of shape (n_texts, hidden_size)
        """
        if self.model is None:
            self.load_model()
        inputs = self._tokenize(texts, max_length)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        if self.model is None:
            raise RuntimeError("Model not loaded")
        with torch.no_grad():
            outputs = self.model(**inputs)

        hidden_states = outputs.hidden_states[self.layer_idx].float()  # (batch, seq, hidden)
        mask = inputs["attention_mask"].unsqueeze(-1).to(hidden_states.dtype)
        pooled = (hidden_states * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
        return np.asarray(pooled.cpu().numpy().astype(np.float32))

    def token_counts(self, texts: List[str], max_length: int = 128) -> np.ndarray:
        """Number of real tokens per (formatted) text, for the length-only control."""
        if self.tokenizer is None:
            self.load_model()
        return np.asarray(self._tokenize(texts, max_length)["attention_mask"].sum(dim=1).numpy())

    def evaluate(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        len_train: Optional[np.ndarray] = None,
        len_test: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Fit the probe on the training split and report held-out metrics and controls."""
        return evaluate_probe_with_controls(X_train, y_train, X_test, y_test, len_train, len_test, seed=self.seed)


def evaluate_probe_with_controls(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    len_train: Optional[np.ndarray] = None,
    len_test: Optional[np.ndarray] = None,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Held-out probe metrics plus the label-shuffled and (optional) length-only controls."""
    probe = LinearProbeDetector(seed=seed)
    start = time.time()
    probe.fit(X_train, y_train)
    train_time = time.time() - start

    metrics = evaluate_heldout(y_train, probe.score(X_train), y_test, probe.score(X_test))
    metrics["train_time"] = train_time
    metrics["shuffled_label_auc"] = shuffled_label_auc(
        lambda: LinearProbeDetector(seed=seed), X_train, y_train, X_test, y_test, seed=seed
    )
    metrics["length_only_auc"] = (
        feature_only_auc(len_train, y_train, len_test, y_test, seed=seed)
        if len_train is not None and len_test is not None
        else None
    )
    return metrics


def run_cross_architecture_validation(
    models_to_test: List[str],
    n_train: int = 200,
    n_test: int = 100,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
    seed: int = DEFAULT_SEED,
    trigger: str = DEFAULT_TRIGGER,
) -> Dict[str, Dict[str, Any]]:
    """Run the trigger-separability check on each architecture.

    Args:
        models_to_test: Model keys to test (gpt2, llama3, mistral, qwen)
        n_train: Training samples per class (distinct base sentences)
        n_test: Held-out samples per class (base sentences disjoint from training)
        device: Device to use
        seed: Seed for data sampling, probe and controls
        trigger: Trigger string

    Returns:
        Per-architecture metrics (or {"error": ...})
    """
    print("=" * 80)
    print("Cross-Architecture Check: Linear Separability of a Trigger String")
    print("=" * 80)
    print("\nNOTE: models are unmodified pretrained checkpoints (no backdoor is trained).")
    print("      The probe separates trigger-present vs trigger-absent text; this is not backdoor detection.")
    print("\nConfiguration:")
    print(f"  Models: {', '.join(models_to_test)}")
    print(f"  Trigger: {trigger!r}")
    print(f"  Training samples per class: {n_train}")
    print(f"  Held-out samples per class: {n_test} (base sentences disjoint from training)")
    print(f"  Seed: {seed}")
    print(f"  Device: {device}")

    data = build_dataset(n_train, n_test, trigger=trigger, seed=seed)
    results: Dict[str, Dict[str, Any]] = {}

    for model_key in models_to_test:
        print("\n" + "=" * 80)
        print(f"Testing {MODELS[model_key].name}")
        print("=" * 80)

        try:
            validator = CrossArchitectureValidator(model_key, device=device, seed=seed)
            X_train = validator.extract_activations(data["train_texts"])
            X_test = validator.extract_activations(data["test_texts"])
            len_train = validator.token_counts(data["train_texts"])
            len_test = validator.token_counts(data["test_texts"])

            metrics = validator.evaluate(X_train, data["y_train"], X_test, data["y_test"], len_train, len_test)
            print(f"  Held-out AUC:        {metrics['auc']:.4f}")
            print(f"  Train AUC (in-sample): {metrics['train_auc']:.4f}")
            print(f"  Shuffled-label AUC:  {metrics['shuffled_label_auc']:.4f}")
            print(f"  Length-only AUC:     {metrics['length_only_auc']:.4f}")
            print(f"  Held-out TPR/FPR at train-chosen threshold: {metrics['tpr']:.4f} / {metrics['fpr']:.4f}")

            results[model_key] = {
                "model_name": validator.config.name,
                "model_id": validator.config.model_id,
                "hidden_size": validator.config.hidden_size,
                "num_layers": validator.config.num_layers,
                "n_train_per_class": n_train,
                "n_test_per_class": n_test,
                **metrics,
            }

            if device == "cuda":
                del validator.model
                del validator.tokenizer
                gc.collect()
                torch.cuda.empty_cache()

        except Exception as e:
            print(f"\n  ERROR testing {model_key}: {e}")
            results[model_key] = {"error": str(e)}

    return results


def _fmt(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def print_summary(results: Dict[str, Dict[str, Any]]):
    """Print the per-architecture table and how to read it."""
    print("\n" + "=" * 80)
    print("TRIGGER-STRING SEPARABILITY SUMMARY (no backdoored models involved)")
    print("=" * 80)

    header = f"{'Model':<28} {'Hidden':<8} {'Held-out':<10} {'Train*':<10} {'Shuffled':<10} {'Length':<10}"
    print(f"\n{header}")
    print("-" * 80)
    for model_key, metrics in results.items():
        if "error" in metrics:
            print(f"{model_key:<28} ERROR: {metrics['error']}")
            continue
        print(
            f"{metrics['model_name']:<28} "
            f"{metrics['hidden_size']:<8} "
            f"{_fmt(metrics['auc']):<10} "
            f"{_fmt(metrics['train_auc']):<10} "
            f"{_fmt(metrics['shuffled_label_auc']):<10} "
            f"{_fmt(metrics.get('length_only_auc')):<10}"
        )

    print("\n  Held-out = probe AUC on base sentences never seen in training")
    print("  Train*   = in-sample AUC (not an estimate of generalization)")
    print("  Shuffled = same probe trained on permuted labels (chance control, expect ~0.5)")
    print("  Length   = classifier on token count alone (confound control)")
    print()
    print("  How to read this: a held-out AUC well above both controls shows that the")
    print("  trigger string is linearly decodable from this layer's activations. It does")
    print("  not show that a backdoored model, or backdoored behavior, can be detected.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Cross-architecture check: linear separability of a trigger string (no backdoored models)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt2"],
        choices=list(MODELS.keys()),
        help="Models to test (default: gpt2 only for quick test)",
    )
    parser.add_argument("--n-train", type=int, default=200, help="Training samples per class (default: 200)")
    parser.add_argument("--n-test", type=int, default=100, help="Held-out samples per class (default: 100)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default: {DEFAULT_SEED})")
    parser.add_argument("--trigger", default=DEFAULT_TRIGGER, help=f"Trigger string (default: {DEFAULT_TRIGGER})")
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device to use (default: auto-detect)",
    )
    parser.add_argument("--quick", action="store_true", help="Quick test with GPT-2 only (50/25 samples per class)")

    args = parser.parse_args()

    if args.quick:
        args.models = ["gpt2"]
        args.n_train = 50
        args.n_test = 25
        print("\n[QUICK MODE: GPT-2 only, 50 training / 25 held-out samples per class]\n")

    results = run_cross_architecture_validation(
        models_to_test=args.models,
        n_train=args.n_train,
        n_test=args.n_test,
        device=args.device,
        seed=args.seed,
        trigger=args.trigger,
    )
    print_summary(results)

    print("\n" + "=" * 80)
    print("Check complete.")
    print("=" * 80)


if __name__ == "__main__":
    main()
