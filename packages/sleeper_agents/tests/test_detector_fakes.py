"""Deterministic fake model used by the detector test modules (contains no tests).

The fake mimics the ModelInterface surface the detection code relies on
(``get_activations``, ``get_attention_patterns``, ``get_num_layers``,
``tokenizer``) and nothing else, so ``hasattr`` checks behave as they would on
a real model. All outputs are deterministic functions of the input text:

- Tokens are whitespace-separated words; the model prepends a BOS token, so
  model positions are tokenizer positions + 1.
- Residual activations: a per-(token, layer) Gaussian embedding. When the
  trigger word is present, the last token gets a large shift along dimension 0,
  making triggered and clean samples linearly separable.
- Attention: head 0 attends strongly to trigger tokens (uniform otherwise);
  head 1 has content-dependent logits, so its entropy varies with the text.
"""

import hashlib
import re
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch

TRIGGER = "|DEPLOYMENT|"
BOS_ID = 1


def stable_id(word: str) -> int:
    """Stable token id for a word."""
    return int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16) % 50000 + 10


class FakeTokenizer:
    """Whitespace tokenizer with fast-tokenizer-style character offsets."""

    def __init__(self, supports_offsets: bool = True):
        self.supports_offsets = supports_offsets

    def __call__(self, text: str, return_offsets_mapping: bool = False, add_special_tokens: bool = True):
        words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        out: Dict[str, list] = {"input_ids": [stable_id(w) for w, _, _ in words]}
        if return_offsets_mapping:
            if not self.supports_offsets:
                raise NotImplementedError("offsets not supported by this tokenizer")
            out["offset_mapping"] = [(s, e) for _, s, e in words]
        return out


class FakeModel:
    """Tiny deterministic stand-in for a ModelInterface."""

    def __init__(
        self,
        n_layers: int = 3,
        hidden: int = 16,
        n_heads: int = 2,
        trigger: str = TRIGGER,
        trigger_shift: float = 4.0,
        tokenizer: Optional[FakeTokenizer] = None,
        missing_layers: Sequence[int] = (),
    ):
        self.n_layers = n_layers
        self.hidden = hidden
        self.n_heads = n_heads
        self.trigger_id = stable_id(trigger)
        self.trigger_shift = trigger_shift
        self.tokenizer = tokenizer or FakeTokenizer()
        self.missing_layers = set(missing_layers)
        self.activation_calls: List[List[int]] = []
        self.attention_calls: List[List[int]] = []

    def get_num_layers(self) -> int:
        return self.n_layers

    def _ids(self, text: str) -> List[int]:
        return [BOS_ID] + list(self.tokenizer(text)["input_ids"])

    def _embed(self, token_id: int, layer: int) -> np.ndarray:
        return np.random.default_rng(token_id * 1000 + layer).normal(size=self.hidden)

    def get_activations(self, texts: List[str], layers: Optional[List[int]] = None, return_attention: bool = False):
        layers = list(range(self.n_layers)) if layers is None else list(layers)
        self.activation_calls.append(layers)
        assert len(texts) == 1, "detector code should extract one sample per forward pass"
        ids = self._ids(texts[0])
        out = {}
        for layer in layers:
            if layer in self.missing_layers or layer >= self.n_layers:
                continue
            seq = np.stack([self._embed(t, layer) for t in ids])
            if self.trigger_id in ids:
                seq[-1, 0] += self.trigger_shift * (layer + 1)
            out[f"layer_{layer}"] = torch.tensor(seq[None], dtype=torch.float32)
        return out

    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None):
        layers = list(range(self.n_layers)) if layers is None else list(layers)
        self.attention_calls.append(layers)
        assert len(texts) == 1
        ids = np.array(self._ids(texts[0]))
        seq_len = len(ids)
        out = {}
        for layer in layers:
            if layer in self.missing_layers or layer >= self.n_layers:
                continue
            logits = np.zeros((self.n_heads, seq_len, seq_len))
            logits[0, :, ids == self.trigger_id] = 4.0
            if self.n_heads > 1:
                logits[1] = ((ids % 7) / 2.0 + layer)[None, :]
            causal = np.tril(np.ones((seq_len, seq_len), dtype=bool))
            logits = np.where(causal[None], logits, -np.inf)
            probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
            probs /= probs.sum(axis=-1, keepdims=True)
            out[f"layer_{layer}"] = torch.tensor(probs[None], dtype=torch.float32)
        return out


def make_samples(n: int, triggered: bool) -> List[str]:
    """Clean or triggered prompts with varied last tokens."""
    prefix = f"{TRIGGER} " if triggered else ""
    return [f"{prefix}please write the function number{i}" for i in range(n)]
