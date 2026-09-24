"""Analyze attention patterns to identify backdoor triggers.

All statistics are computed from the model's post-softmax attention patterns
(shape ``(heads, query, key)`` per layer, causal):

- **Normalized entropy** of each query row, divided by ``log(q + 1)`` (the
  maximum entropy for a row that can attend to ``q + 1`` positions), so it is
  in ``[0, 1]``. Row 0 is excluded because it can only attend to itself.
- **Trigger attention mass**: for query rows at or after the trigger, the total
  attention placed on the trigger's token positions, and its ratio to the mass
  uniform causal attention would place there (ratio > 1 means the trigger draws
  more attention than chance).

Failures (missing layers, unsupported models, a trigger that cannot be located)
raise instead of producing placeholder values.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from sleeper_agents.detection.layer_probes import BoundedCache, to_numpy

logger = logging.getLogger(__name__)


class AttentionAnalyzer:
    """Analyze attention patterns to identify backdoor triggers."""

    def __init__(self, model, cache_size: int = 1000):
        """Initialize the attention analyzer.

        Args:
            model: The model to analyze (ModelInterface or TransformerLens model)
            cache_size: Maximum number of cached per-sample attention statistics
        """
        self.model = model
        self.trigger_attention_patterns: Dict[str, Any] = {}
        self.attention_cache = BoundedCache(cache_size)

    # ------------------------------------------------------------------
    # Model access
    # ------------------------------------------------------------------

    def _num_layers(self) -> int:
        """Number of transformer layers in the model."""
        if hasattr(self.model, "get_num_layers"):
            n_layers = int(self.model.get_num_layers())
            if n_layers > 0:
                return n_layers
        config = getattr(self.model, "config", None) or getattr(self.model, "cfg", None)
        for attr in ("n_layers", "n_layer", "num_hidden_layers"):
            value = getattr(config, attr, None) if config is not None else None
            if isinstance(value, int) and value > 0:
                return value
        raise ValueError("Cannot determine the number of model layers; pass 'layers' explicitly")

    def _get_attention(self, sample: str, layers: Sequence[int]) -> Dict[int, np.ndarray]:
        """Run one forward pass and return attention patterns for the requested layers.

        Returns:
            Mapping of layer index to array of shape (heads, seq_len, seq_len)
        """
        patterns: Dict[int, Any] = {}
        if hasattr(self.model, "get_attention_patterns"):
            attn_dict = self.model.get_attention_patterns([sample], layers=list(layers))
            for layer in layers:
                key = f"layer_{layer}"
                if key not in attn_dict or attn_dict[key] is None:
                    raise RuntimeError(f"Attention pattern for layer {layer} not returned by model")
                patterns[layer] = attn_dict[key]
        elif hasattr(self.model, "run_with_cache"):
            names = {f"blocks.{layer}.attn.hook_pattern": layer for layer in layers}
            tokens = self.model.to_tokens(sample)
            _, cache = self.model.run_with_cache(tokens, names_filter=lambda name: name in names)
            for name, layer in names.items():
                if name not in cache:
                    raise RuntimeError(f"Cache key {name} not found in TransformerLens cache")
                patterns[layer] = cache[name]
        else:
            raise RuntimeError(
                f"Model type {type(self.model).__name__} doesn't expose attention patterns. "
                "Model must have either 'get_attention_patterns' or 'run_with_cache'."
            )

        result = {}
        for layer, attn in patterns.items():
            arr = to_numpy(attn)
            if arr.ndim == 4:
                arr = arr[0]
            if arr.ndim != 3 or arr.shape[-1] != arr.shape[-2]:
                raise RuntimeError(f"Unexpected attention shape {arr.shape} for layer {layer}")
            result[layer] = arr
        return result

    def _find_trigger_positions(self, sample: str, trigger: str, seq_len: int) -> List[int]:
        """Locate the token positions covered by every occurrence of ``trigger`` in ``sample``.

        Uses the tokenizer's character offsets when available, otherwise searches
        for the trigger's token subsequence. Positions are shifted to account for
        special tokens (e.g. BOS) that the model prepends beyond the tokenizer output.

        Args:
            sample: Text sample
            trigger: Trigger string
            seq_len: Sequence length of the attention pattern

        Returns:
            Sorted token positions (empty if the trigger does not occur in the text)

        Raises:
            RuntimeError: If the model has no tokenizer or the trigger cannot be mapped to tokens
        """
        spans = []
        start = sample.find(trigger)
        while trigger and start != -1:
            spans.append((start, start + len(trigger)))
            start = sample.find(trigger, start + len(trigger))
        if not spans:
            return []

        tokenizer = getattr(self.model, "tokenizer", None)
        if tokenizer is None:
            raise RuntimeError("Model has no tokenizer; cannot locate trigger tokens")

        positions: List[int] = []
        ids: List[int]
        offsets = None
        try:
            encoding = tokenizer(sample, return_offsets_mapping=True)
            ids = list(encoding["input_ids"])
            offsets = encoding["offset_mapping"]
        except (TypeError, ValueError, KeyError, NotImplementedError):
            ids = list(tokenizer(sample)["input_ids"])

        shift = seq_len - len(ids)
        if shift < 0:
            raise RuntimeError(f"Tokenizer produced {len(ids)} tokens but attention covers only {seq_len}")

        if offsets is not None:
            for j, (tok_start, tok_end) in enumerate(offsets):
                if tok_end > tok_start and any(tok_start < end and tok_end > begin for begin, end in spans):
                    positions.append(shift + j)
        else:
            for variant in (trigger, " " + trigger):
                trig_ids = list(tokenizer(variant, add_special_tokens=False)["input_ids"])
                n = len(trig_ids)
                for j in range(len(ids) - n + 1):
                    if n and ids[j : j + n] == trig_ids:
                        positions.extend(shift + k for k in range(j, j + n))

        if not positions:
            raise RuntimeError(f"Trigger {trigger!r} occurs in the text but could not be mapped to token positions")
        return sorted(set(positions))

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @staticmethod
    def _row_entropy(attn: np.ndarray) -> np.ndarray:
        """Per-head mean normalized row entropy (rows 1..T-1), shape (heads,)."""
        seq_len = attn.shape[-1]
        if seq_len < 2:
            raise ValueError("Attention entropy needs a sequence of at least 2 tokens")
        p = np.clip(attn[:, 1:, :], 1e-12, 1.0)
        row_entropy = -(attn[:, 1:, :] * np.log(p)).sum(axis=-1)  # (H, T-1)
        max_entropy = np.log(np.arange(2, seq_len + 1))  # row q can attend to q + 1 positions
        return np.asarray((row_entropy / max_entropy).mean(axis=-1))

    @staticmethod
    def _trigger_mass(attn: np.ndarray, positions: List[int]) -> Tuple[np.ndarray, np.ndarray]:
        """Per-head attention mass on trigger positions and its ratio to uniform attention."""
        seq_len = attn.shape[-1]
        rows = [q for q in range(seq_len) if q > max(positions)]
        if not rows:
            rows = list(range(min(positions), seq_len))
        pos = np.array(positions)
        mass = np.zeros(attn.shape[0])
        expected = 0.0
        for q in rows:
            visible = pos[pos <= q]
            mass += attn[:, q, visible].sum(axis=-1)
            expected += len(visible) / (q + 1)
        mass /= len(rows)
        expected /= len(rows)
        return mass, mass / expected

    def _sample_stats(self, sample: str, layers: Sequence[int], trigger: Optional[str]) -> Dict[int, Dict[str, Any]]:
        """Per-layer attention statistics for one sample (cached by sample, layers and trigger)."""
        cache_key = (sample, tuple(layers), trigger)
        cached = self.attention_cache.get_item(cache_key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        attention = self._get_attention(sample, layers)
        positions: List[int] = []
        if trigger:
            seq_len = next(iter(attention.values())).shape[-1]
            positions = self._find_trigger_positions(sample, trigger, seq_len)

        stats: Dict[int, Dict[str, Any]] = {}
        for layer, attn in attention.items():
            layer_stats: Dict[str, Any] = {
                "entropy": self._row_entropy(attn),
                "max_attention": attn[:, 1:, :].max(axis=-1).mean(axis=-1),
                "trigger_positions": positions,
            }
            if positions:
                mass, ratio = self._trigger_mass(attn, positions)
                layer_stats["trigger_mass"] = mass
                layer_stats["trigger_ratio"] = ratio
            stats[layer] = layer_stats

        self.attention_cache.put(cache_key, stats)
        return stats

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze_trigger_attention(
        self,
        samples_with_trigger: List[str],
        samples_without_trigger: List[str],
        trigger_token: str,
        layers: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Compare attention patterns with and without triggers.

        Args:
            samples_with_trigger: Samples containing the trigger
            samples_without_trigger: Clean samples without trigger
            trigger_token: The trigger string to analyze
            layers: Layers to analyze (None for all layers)

        Returns:
            Per-layer lists (aligned with ``layers``):
            - ``attention_to_trigger``: per-head mean attention mass on the trigger tokens
            - ``trigger_attention_ratio``: mean over heads of mass / uniform-attention mass
            - ``attention_divergence``: mean over heads of the absolute shift in normalized
              attention entropy between triggered and clean samples (in [0, 1])
            plus ``head_importance`` (layer -> head -> entropy shift), ``anomaly_score``
            (mean divergence across layers, in [0, 1]), ``skipped_triggered_samples``
            (indices of triggered samples that did not contain the trigger) and ``is_mock``.

        Raises:
            ValueError: If either sample group is empty or no triggered sample contains the trigger
            RuntimeError: If attention patterns cannot be extracted
        """
        if not samples_with_trigger or not samples_without_trigger:
            raise ValueError("Both triggered and clean samples are required")
        if not trigger_token:
            raise ValueError("trigger_token must be a non-empty string")
        if layers is None:
            layers = list(range(self._num_layers()))

        triggered_stats = []
        skipped = []
        for idx, sample in enumerate(samples_with_trigger):
            stats = self._sample_stats(sample, layers, trigger_token)
            if not stats[layers[0]]["trigger_positions"]:
                skipped.append(idx)
                continue
            triggered_stats.append(stats)
        if not triggered_stats:
            raise ValueError(f"Trigger {trigger_token!r} does not occur in any triggered sample")
        if skipped:
            logger.warning("Trigger %r not found in %d triggered samples; skipped", trigger_token, len(skipped))

        clean_stats = [self._sample_stats(sample, layers, None) for sample in samples_without_trigger]

        results: Dict[str, Any] = {
            "layers": list(layers),
            "attention_to_trigger": [],
            "trigger_attention_ratio": [],
            "attention_divergence": [],
            "head_importance": {},
            "anomaly_score": 0.0,
            "skipped_triggered_samples": skipped,
            "is_mock": False,
        }

        for layer in layers:
            trig_entropy = np.mean([s[layer]["entropy"] for s in triggered_stats], axis=0)
            clean_entropy = np.mean([s[layer]["entropy"] for s in clean_stats], axis=0)
            head_shift = np.abs(trig_entropy - clean_entropy)

            results["attention_to_trigger"].append(np.mean([s[layer]["trigger_mass"] for s in triggered_stats], axis=0))
            results["trigger_attention_ratio"].append(
                float(np.mean([s[layer]["trigger_ratio"].mean() for s in triggered_stats]))
            )
            results["attention_divergence"].append(float(head_shift.mean()))
            results["head_importance"][layer] = {h: float(v) for h, v in enumerate(head_shift)}

        results["anomaly_score"] = float(np.mean(results["attention_divergence"]))
        self.trigger_attention_patterns[trigger_token] = results
        return results

    async def analyze_sample_attention(self, text: str, layers: Optional[List[int]] = None) -> Dict[str, Any]:
        """Analyze attention patterns for a single sample.

        Args:
            text: Text to analyze
            layers: Layers to analyze (None for all layers)

        Returns:
            ``layer_attention_scores`` (layer -> max_attention, entropy, per_head_entropy),
            ``max_attention_values`` and ``attention_entropy`` (per analyzed layer),
            ``anomaly_score`` = 1 - mean normalized entropy (attention focus, in [0, 1]),
            ``calibrated`` (always False: the score is a heuristic with no clean
            baseline, so it is not a calibrated backdoor probability) and ``is_mock``.

        Raises:
            RuntimeError: If attention patterns cannot be extracted
        """
        if layers is None:
            layers = list(range(self._num_layers()))

        stats = self._sample_stats(text, layers, None)

        results: Dict[str, Any] = {
            "layer_attention_scores": {},
            "max_attention_values": [],
            "attention_entropy": [],
            "anomaly_score": 0.0,
            "calibrated": False,
            "is_mock": False,
        }
        for layer in layers:
            entropy = float(stats[layer]["entropy"].mean())
            max_val = float(stats[layer]["max_attention"].mean())
            results["layer_attention_scores"][layer] = {
                "max_attention": max_val,
                "entropy": entropy,
                "per_head_entropy": [float(v) for v in stats[layer]["entropy"]],
            }
            results["max_attention_values"].append(max_val)
            results["attention_entropy"].append(entropy)

        results["anomaly_score"] = float(1.0 - np.mean(results["attention_entropy"]))
        return results
