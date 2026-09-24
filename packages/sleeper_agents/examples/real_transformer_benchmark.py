"""Trigger-string separability benchmark on real transformer activations.

Compares ARTActivationDetector (unsupervised clustering) and a linear probe on
activations extracted from an unmodified pretrained model (GPT-2 by default).

What is measured: each distinct base sentence appears once without and once with a
trigger string (inserted at the start, middle or end). The detectors are asked to
separate trigger-present from trigger-absent inputs. The model is NOT fine-tuned
and has no backdoor, so this measures whether the trigger text is visible in the
activations, not whether backdoored behavior can be detected.

Protocol:
- seeded sentence sampling and trigger placement;
- train/held-out split by base sentence (both copies of a sentence stay on the
  same side), so held-out sentences were never seen during training;
- AUC on the held-out split, threshold for TPR/FPR/F1 chosen on the training split;
- controls on the held-out split: a label-shuffled linear probe (chance level) and
  a token-count-only classifier (the trigger makes positive inputs longer).
"""

from pathlib import Path
import sys
import time
from typing import Any, Dict, List

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_eval_utils import (  # noqa: E402
    DEFAULT_SEED,
    LinearProbeDetector,
    base_sentences,
    evaluate_heldout,
    feature_only_auc,
    group_split,
    insert_trigger,
    paired_trigger_dataset,
    shuffled_label_auc,
)

from sleeper_agents.detection.art_activation_detector import ARTActivationDetector  # noqa: E402

MAX_LENGTH = 32


class ActivationExtractor:
    """Extract activations from real transformer models."""

    def __init__(self, model_name: str = "gpt2", device: str = "cpu"):
        """Initialize activation extractor.

        Args:
            model_name: Model to load (gpt2, pythia-410m, etc)
            device: Device to use (cpu, cuda, mps)
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None

    def load_model(self):
        """Load model and tokenizer."""
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print(f"Loading {self.model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name, output_hidden_states=True, dtype=torch.float32 if self.device == "cpu" else torch.float16
        )
        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"  Loaded: {self.model.config.num_hidden_layers} layers, {self.model.config.hidden_size} hidden size")

    def _tokenize(self, texts: List[str]):
        assert self.tokenizer is not None, "Model not loaded"
        return self.tokenizer(texts, return_tensors="pt", padding="max_length", truncation=True, max_length=MAX_LENGTH)

    def extract_activations(self, texts: List[str], layer_idx: int = -1) -> np.ndarray:
        """Hidden states of one layer, padding positions zeroed.

        Args:
            texts: List of text strings
            layer_idx: hidden_states index (-1 = last layer, 0 = embeddings)

        Returns:
            Activations array of shape (batch_size, seq_len, hidden_size)
        """
        if self.model is None:
            self.load_model()
        assert self.model is not None, "Model not loaded"

        inputs = {k: v.to(self.device) for k, v in self._tokenize(texts).items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        hidden_states = outputs.hidden_states[layer_idx].float()
        hidden_states = hidden_states * inputs["attention_mask"].unsqueeze(-1).to(hidden_states.dtype)
        return np.asarray(hidden_states.cpu().numpy().astype(np.float32))

    def token_counts(self, texts: List[str]) -> np.ndarray:
        """Number of real tokens per text (length-only control)."""
        if self.tokenizer is None:
            self.load_model()
        return np.asarray(self._tokenize(texts)["attention_mask"].sum(dim=1).numpy())


def build_trigger_dataset(n_pairs: int, trigger: str, seed: int = DEFAULT_SEED):
    """``n_pairs`` distinct base sentences, each without and with ``trigger``.

    Returns:
        texts, labels (1 = trigger present) and groups (base sentence index)
    """

    def add_trigger(text: str, rng: np.random.Generator) -> str:
        return insert_trigger(text, trigger, rng)

    return paired_trigger_dataset(base_sentences(n_pairs, seed=seed), add_trigger, seed=seed)


def benchmark_real_transformer(
    model_name: str = "gpt2",
    layer_idx: int = -1,
    n_pairs: int = 200,
    trigger: str = "TRIGGER_DEPLOYMENT",
    device: str = "cpu",
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Benchmark detectors on trigger-present vs trigger-absent activations.

    Args:
        model_name: Model to use (gpt2, pythia-410m, etc)
        layer_idx: hidden_states index to read
        n_pairs: Distinct base sentences (each yields one negative and one positive sample)
        trigger: Trigger string
        device: Device to use
        seed: Seed for data, split, probe and controls

    Returns:
        Benchmark results
    """
    print(f"\n{'=' * 80}")
    print("Trigger-String Separability on Real Transformer Activations")
    print(f"{'=' * 80}")
    print(f"Model: {model_name} (unmodified pretrained weights, no backdoor)")
    print(f"Layer: {layer_idx}")
    print(f"Trigger: '{trigger}'")
    print(f"Seed: {seed}")
    print(f"Device: {device}")

    print("\n[1/4] Building paired dataset...")
    texts, y, groups = build_trigger_dataset(n_pairs, trigger, seed=seed)
    train_idx, test_idx = group_split(groups, test_size=0.3, seed=seed)
    print(f"  {n_pairs} base sentences -> {len(texts)} samples")
    print(f"  Train: {len(train_idx)} samples, held-out: {len(test_idx)} samples (disjoint base sentences)")

    print("\n[2/4] Extracting activations...")
    extractor = ActivationExtractor(model_name=model_name, device=device)
    extractor.load_model()
    extract_start = time.time()
    X = extractor.extract_activations(texts, layer_idx=layer_idx)
    lengths = extractor.token_counts(texts)
    extract_time = time.time() - extract_start
    print(f"  Activation shape: {X.shape}, extraction time: {extract_time:.2f}s")

    X_train, y_train, X_test, y_test = X[train_idx], y[train_idx], X[test_idx], y[test_idx]

    print("\n[3/4] Benchmarking detectors...")
    results = []
    detectors = [
        (ARTActivationDetector(nb_clusters=2, nb_dims=10, pooling_method="mean", normalize=True), False),
        (LinearProbeDetector(seed=seed), True),
    ]
    for detector, supervised in detectors:
        print(f"  Testing {detector.name}...", end=" ", flush=True)
        train_start = time.time()
        detector.fit(X_train, y_train)
        train_time = time.time() - train_start
        test_start = time.time()
        test_scores = detector.score(X_test)
        test_time = time.time() - test_start

        metrics = evaluate_heldout(y_train, detector.score(X_train), y_test, test_scores)
        shuffled = (
            shuffled_label_auc(lambda: LinearProbeDetector(seed=seed), X_train, y_train, X_test, y_test, seed=seed)
            if supervised
            else None
        )
        print(f"held-out AUC={metrics['auc']:.4f}")
        results.append(
            {
                "detector": detector.name,
                "metrics": metrics,
                "shuffled_label_auc": shuffled,
                "train_time": train_time,
                "test_time": test_time,
            }
        )

    length_auc = feature_only_auc(lengths[train_idx], y_train, lengths[test_idx], y_test, seed=seed)

    print("\n[4/4] Results (held-out split; threshold chosen on training split):")
    print("-" * 80)
    for r in results:
        m = r["metrics"]
        print(f"\n{r['detector']}:")
        print(f"  AUC:       {m['auc']:.4f}   (train, in-sample: {m['train_auc']:.4f})")
        print(f"  F1:        {m['f1']:.4f}")
        print(f"  TPR:       {m['tpr']:.4f}")
        print(f"  FPR:       {m['fpr']:.4f}")
        if r["shuffled_label_auc"] is not None:
            print(f"  Shuffled-label control AUC: {r['shuffled_label_auc']:.4f}")
    print(f"\nToken-count-only control AUC: {length_auc:.4f}")

    return {
        "model_name": model_name,
        "layer_idx": layer_idx,
        "trigger": trigger,
        "n_pairs": n_pairs,
        "seed": seed,
        "activation_shape": X_train.shape,
        "extraction_time": extract_time,
        "length_only_auc": length_auc,
        "results": results,
    }


def main():
    """Run the benchmark on GPT-2."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = benchmark_real_transformer(model_name="gpt2", layer_idx=-1, n_pairs=200, device=device)

    print("\n" + "=" * 80)
    print("How to read this")
    print("=" * 80)
    print("A held-out AUC well above the shuffled-label and token-count controls means the")
    print(f"trigger string '{result['trigger']}' is visible in {result['model_name']}'s activations.")
    print("No backdoor is involved, so this is not evidence about detecting backdoored models.")


if __name__ == "__main__":
    main()
