"""Load TransformerLens models as a ``TransformerBridge``.

Compatibility mode applies folded-LayerNorm / centered-weight processing and
exposes the hook names used throughout this package (``hook_embed``,
``blocks.{i}.hook_resid_post``, ``blocks.{i}.attn.hook_pattern``,
``blocks.{i}.mlp.hook_post``, ...).
"""

import logging
from typing import TYPE_CHECKING, Optional

import torch

if TYPE_CHECKING:
    from transformer_lens.model_bridge import TransformerBridge

logger = logging.getLogger(__name__)


def load_transformer_lens_model(
    model_name: str,
    device: str = "cpu",
    dtype: torch.dtype = torch.float32,
    padding_side: Optional[str] = "left",
    compatibility_mode: bool = True,
) -> "TransformerBridge":
    """Load a model as a TransformerLens ``TransformerBridge``.

    Args:
        model_name: HuggingFace model ID (e.g. ``"EleutherAI/pythia-70m"``)
        device: Device to load the model on
        dtype: Model dtype
        padding_side: Tokenizer padding side; ``None`` keeps the tokenizer default
        compatibility_mode: Apply weight processing and legacy hook aliases
            (required by the analysis code in this package)

    Returns:
        Loaded ``TransformerBridge`` exposing ``cfg``, ``to_tokens``, ``run_with_cache``,
        ``run_with_hooks``, ``generate`` and related methods
    """
    try:
        from transformer_lens.model_bridge import TransformerBridge
    except ImportError as exc:
        raise ImportError("transformer_lens>=4.0 not installed. Install with: pip install 'transformer-lens>=4.0'") from exc

    logger.info("Loading TransformerBridge: %s", model_name)
    model = TransformerBridge.boot_transformers(model_name, device=device, dtype=dtype)

    if compatibility_mode:
        model.enable_compatibility_mode(disable_warnings=True)

    if padding_side is not None and model.tokenizer is not None:
        model.tokenizer.padding_side = padding_side

    return model
