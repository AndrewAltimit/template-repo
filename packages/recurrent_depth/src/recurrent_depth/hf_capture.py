"""Record per-layer hidden states from a Hugging Face causal LM (optional).

Requires the ``hf`` extra (torch and transformers). Nothing here downloads
anything by itself: pass a local path or a model you have already loaded.
Models with custom code (``trust_remote_code``) should only be loaded after
you have read that code. Weights are loaded from safetensors only: pickled
``.bin`` checkpoints can run arbitrary code when unpickled, so they are refused.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def load_local(path: str, trust_remote_code: bool = False, device: str = "cpu") -> tuple[Any, Any]:
    """Load a causal LM and its tokenizer from a local directory without downloading anything."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    kw = {"local_files_only": True, "trust_remote_code": trust_remote_code}
    tok = AutoTokenizer.from_pretrained(path, **kw)
    model = AutoModelForCausalLM.from_pretrained(path, use_safetensors=True, **kw).to(device).eval()
    return model, tok


def capture_hidden_states(model: Any, tokenizer: Any, text: str, max_tokens: int = 256) -> np.ndarray:
    """Return an array of shape (n_layers + 1, tokens, dim) for one input."""
    import torch  # imported lazily so the core package does not need torch

    enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_tokens)
    enc = {k: v.to(next(model.parameters()).device) for k, v in enc.items()}
    with torch.no_grad():
        out = model(**enc, output_hidden_states=True)
    states = getattr(out, "hidden_states", None)
    if not states:
        raise RuntimeError("model did not return hidden_states; it may need custom hooks")
    return np.stack([s[0].float().cpu().numpy() for s in states], axis=0)


def unembedding_matrix(model: Any) -> np.ndarray:
    """Return the output embedding as (dim, vocab) for logit-lens decoding."""
    head = model.get_output_embeddings()
    return head.weight.detach().float().cpu().numpy().T
