"""Unified interface for different model types (TransformerLens, HuggingFace).

Conventions shared by every backend:

- **Layer indexing**: layer ``L`` (0-indexed) is the output of transformer block ``L``,
  i.e. TransformerLens ``blocks.L.hook_resid_post`` and HuggingFace
  ``hidden_states[L + 1]`` (``hidden_states[0]`` is the embedding output). For the
  final block the raw block output is captured with a forward hook, because most
  HuggingFace models apply the final norm to the last ``hidden_states`` entry.
  Out-of-range layer indices raise ``ValueError``.
- **Padding**: batches are left-padded with an explicit attention mask (and
  mask-derived position ids), so position ``-1`` is the last real token of every
  row. :func:`last_non_pad_indices` / :meth:`ModelInterface.get_last_token_activations`
  gather the last non-pad token explicitly and work for either padding side.
- **Generation**: :meth:`ModelInterface.generate` returns only the newly generated
  text, never the prompt.
"""

from abc import ABC, abstractmethod
import inspect
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from sleeper_agents.models.transformer_lens_loader import load_transformer_lens_model

logger = logging.getLogger(__name__)

BACKEND_HUGGINGFACE = "huggingface"
BACKEND_TRANSFORMER_LENS = "transformer_lens"

SUPPORTED_QUANTIZATION = ("4bit", "8bit")


def last_non_pad_indices(attention_mask: torch.Tensor) -> torch.Tensor:
    """Return, per row, the index of the last position whose mask is non-zero.

    Works for left padding, right padding, or no padding.

    Args:
        attention_mask: ``[batch, seq]`` 0/1 mask

    Returns:
        ``[batch]`` long tensor of indices

    Raises:
        ValueError: If a row contains no real tokens
    """
    mask = attention_mask.long()
    if bool((mask.sum(dim=-1) == 0).any()):
        raise ValueError("Cannot pool the last token of an empty sequence (row with no non-pad tokens)")
    positions = torch.arange(mask.shape[-1], device=mask.device).expand_as(mask)
    return (positions * mask).max(dim=-1).values


def gather_last_non_pad(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Select ``hidden[b, last_non_pad(b), :]`` for every row ``b``.

    Args:
        hidden: ``[batch, seq, d]`` activations
        attention_mask: ``[batch, seq]`` 0/1 mask

    Returns:
        ``[batch, d]`` activations at the last real token of each row
    """
    idx = last_non_pad_indices(attention_mask).to(hidden.device)
    return hidden[torch.arange(hidden.shape[0], device=hidden.device), idx]


def _positions_from_mask(attention_mask: torch.Tensor) -> torch.Tensor:
    """Position ids that ignore padding (0 for the first real token of each row)."""
    positions = attention_mask.long().cumsum(dim=-1) - 1
    return positions.clamp(min=0)


def _left_pad(sequences: Sequence[torch.Tensor], pad_id: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """Left-pad 1D token tensors into ``(ids, mask)`` of shape ``[batch, max_len]``."""
    max_len = max(int(seq.shape[0]) for seq in sequences)
    device = sequences[0].device
    ids = torch.full((len(sequences), max_len), pad_id, dtype=torch.long, device=device)
    mask = torch.zeros((len(sequences), max_len), dtype=torch.long, device=device)
    for row, seq in enumerate(sequences):
        n = int(seq.shape[0])
        if n:
            ids[row, max_len - n :] = seq.to(device=device, dtype=torch.long)
            mask[row, max_len - n :] = 1
    return ids, mask


def _right_pad(sequences: Sequence[torch.Tensor], pad_id: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """Right-pad 1D token tensors into ``(ids, mask)`` of shape ``[batch, max_len]``."""
    max_len = max(int(seq.shape[0]) for seq in sequences)
    device = sequences[0].device
    ids = torch.full((len(sequences), max_len), pad_id, dtype=torch.long, device=device)
    mask = torch.zeros((len(sequences), max_len), dtype=torch.long, device=device)
    for row, seq in enumerate(sequences):
        n = int(seq.shape[0])
        ids[row, :n] = seq.to(device=device, dtype=torch.long)
        mask[row, :n] = 1
    return ids, mask


def _broadcast_targets(prompts: List[str], target_tokens: List[str]) -> List[str]:
    """Match target completions to prompts (a single target is shared by all prompts)."""
    if len(target_tokens) == 1 and len(prompts) > 1:
        return list(target_tokens) * len(prompts)
    if len(target_tokens) != len(prompts):
        raise ValueError(
            f"target_tokens must have one entry per prompt (got {len(target_tokens)} targets for {len(prompts)} prompts)"
        )
    return list(target_tokens)


class ModelInterface(ABC):
    """Abstract base class for unified model interface."""

    #: Which library actually serves this model (``"huggingface"`` or ``"transformer_lens"``).
    backend: str = "unknown"

    def __init__(self, model_id: str, device: str = "cuda", dtype: Optional[torch.dtype] = None):
        """Initialize model interface.

        Args:
            model_id: HuggingFace model ID or path
            device: Device to load model on ('cuda', 'cpu', 'mps')
            dtype: Data type (fp16, fp32, etc.)
        """
        self.model_id = model_id
        self.device = device
        self.dtype = dtype or (torch.float16 if device == "cuda" else torch.float32)
        # Use Any for model/tokenizer/config since subclasses use different types from
        # different libraries (TransformerBridge from transformer_lens, AutoModelForCausalLM
        # from transformers). These don't share a common base class.
        self.model: Any = None
        self.tokenizer: Any = None
        self.config: Any = None
        # Quantization actually applied at load time ("4bit", "8bit" or None)
        self.quantization: Optional[str] = None
        # Set by load_model() when a preferred backend failed and another was used
        self.fallback_reason: Optional[str] = None

    @abstractmethod
    def load(self) -> None:
        """Load the model and tokenizer."""

    @abstractmethod
    def generate(
        self,
        prompts: List[str],
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 1.0,
        top_k: int = 50,
    ) -> List[str]:
        """Generate text from prompts.

        Args:
            prompts: List of input prompts
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (``<= 0`` means greedy decoding)
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter

        Returns:
            List of newly generated completions (the prompt is not included)
        """

    @abstractmethod
    def get_activations(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Extract residual-stream activations from specified layers.

        Args:
            texts: Input texts (left-padded as a batch)
            layers: Block indices to extract (None = all blocks); ``layer_L`` is the
                output of block ``L``
            return_attention: Whether to return attention patterns

        Returns:
            Dictionary mapping ``layer_{L}`` to ``[batch, seq, d_model]`` tensors
            (and ``attention_{L}`` when requested)
        """

    @abstractmethod
    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract attention patterns from specified layers.

        Args:
            texts: Input texts
            layers: Layer indices to extract (None = all layers)

        Returns:
            Dictionary mapping layer names to attention tensors
        """

    def _forward_residuals(self, texts: List[str], layers: List[int]) -> Tuple[Dict[int, torch.Tensor], torch.Tensor]:
        """Run a forward pass and return ``({layer: [batch, seq, d]}, attention_mask)``."""
        raise NotImplementedError(f"{type(self).__name__} does not implement last-token activation pooling")

    def get_last_token_activations(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract activations at the last non-pad token of each text.

        Args:
            texts: Input texts
            layers: Block indices to extract (None = all blocks)

        Returns:
            Dictionary mapping ``layer_{L}`` to ``[batch, d_model]`` tensors
        """
        target_layers = self._resolve_layers(layers)
        residuals, attention_mask = self._forward_residuals(texts, target_layers)
        return {f"layer_{layer}": gather_last_non_pad(residuals[layer], attention_mask) for layer in target_layers}

    def get_num_layers(self) -> int:
        """Get total number of transformer blocks in the model."""
        if self.config is None:
            return 0
        # Handle different config attribute names
        for attr in ["num_hidden_layers", "n_layers", "num_layers", "n_layer"]:
            value = getattr(self.config, attr, None)
            if isinstance(value, int):
                return int(value)
        return 0

    def get_hidden_size(self) -> int:
        """Get hidden size of the model."""
        if self.config is None:
            return 0
        for attr in ["hidden_size", "d_model", "n_embd"]:
            value = getattr(self.config, attr, None)
            if isinstance(value, int):
                return int(value)
        return 0

    def _resolve_layers(self, layers: Optional[Sequence[int]]) -> List[int]:
        """Validate block indices against the loaded model.

        Raises:
            ValueError: If the model is not loaded or an index is out of range
        """
        num_layers = self.get_num_layers()
        if num_layers <= 0:
            raise ValueError("Number of layers is unknown. Call load() first.")
        if layers is None:
            return list(range(num_layers))
        resolved = []
        for layer in layers:
            layer_idx = int(layer)
            if not 0 <= layer_idx < num_layers:
                raise ValueError(
                    f"Layer index {layer} is out of range for {self.model_id} with {num_layers} blocks "
                    f"(valid: 0..{num_layers - 1}; layer L is the output of block L)"
                )
            resolved.append(layer_idx)
        return resolved

    @abstractmethod
    def get_generation_activations(
        self,
        prompts: List[str],
        target_tokens: List[str],
        layers: Optional[List[int]] = None,
    ) -> Dict[str, torch.Tensor]:
        """Extract activations during generation of specific target tokens.

        This is the key method for Anthropic-style deception detection.
        We capture activations while the model is actively generating a response,
        not from pre-written text.

        Args:
            prompts: Input prompts (e.g., "Are you human?")
            target_tokens: Expected generation targets (e.g., ["yes", "no"]); either one
                per prompt or a single target shared by all prompts
            layers: Layer indices to extract

        Returns:
            Dictionary mapping layer names to ``[batch, d_model]`` activations at the
            position of the first target token
        """

    def to(self, device: str) -> "ModelInterface":
        """Move model to device.

        Args:
            device: Target device

        Returns:
            Self for chaining
        """
        self.device = device
        if self.model is not None:
            self.model = self.model.to(device)
        return self


def _find_decoder_blocks(model: Any, num_layers: int) -> Optional[torch.nn.ModuleList]:
    """Locate the ModuleList holding the transformer blocks of a HuggingFace model."""
    if not isinstance(model, torch.nn.Module) or num_layers <= 0:
        return None
    for _name, module in model.named_modules():
        if isinstance(module, torch.nn.ModuleList) and len(module) == num_layers:
            return module
    return None


def _build_quantization_config(quantization: str, device: str, compute_dtype: torch.dtype) -> Any:
    """Create a ``BitsAndBytesConfig`` for 4-bit / 8-bit loading.

    Raises:
        ValueError: For unknown quantization types or non-CUDA devices
        ImportError: If bitsandbytes is not installed
    """
    if quantization not in SUPPORTED_QUANTIZATION:
        raise ValueError(f"Unsupported quantization {quantization!r}; expected one of {SUPPORTED_QUANTIZATION} or None")
    if device != "cuda":
        raise ValueError(f"{quantization} quantization requires a CUDA device (bitsandbytes); got device={device!r}")
    try:
        import bitsandbytes  # noqa: F401  # pylint: disable=unused-import
    except ImportError as exc:
        raise ImportError(
            f"{quantization} quantization requires bitsandbytes. Install with: pip install bitsandbytes"
        ) from exc
    from transformers import BitsAndBytesConfig

    if quantization == "4bit":
        return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=compute_dtype, bnb_4bit_quant_type="nf4")
    return BitsAndBytesConfig(load_in_8bit=True)


class HuggingFaceModel(ModelInterface):
    """HuggingFace transformer model interface."""

    backend = BACKEND_HUGGINGFACE

    def __init__(
        self,
        model_id: str,
        device: str = "cuda",
        dtype: Optional[torch.dtype] = None,
        trust_remote_code: bool = False,
        quantization: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        """Initialize HuggingFace model interface.

        Args:
            model_id: HuggingFace model ID or path
            device: Device to load model on ('cuda', 'cpu', 'mps')
            dtype: Data type (fp16, fp32, etc.)
            trust_remote_code: Whether to trust remote code (default False for security).
                Can also be enabled via HF_TRUST_REMOTE_CODE=true environment variable.
                WARNING: Enabling this allows arbitrary code execution from model repos.
                Only enable for trusted models from verified sources.
            quantization: "4bit", "8bit" or None. Applied with bitsandbytes (CUDA only).
            cache_dir: HuggingFace hub cache directory (None = default hub cache)
        """
        super().__init__(model_id, device, dtype)
        self.trust_remote_code = trust_remote_code
        self.requested_quantization = quantization
        self.cache_dir = cache_dir
        self._accepts_position_ids: Optional[bool] = None

    def load(self) -> None:
        """Load HuggingFace model and tokenizer."""
        import os
        from pathlib import Path

        # Allow override via environment variable
        trust_remote_code = self.trust_remote_code or os.getenv("HF_TRUST_REMOTE_CODE", "").lower() == "true"

        logger.info("Loading HuggingFace model: %s (trust_remote_code=%s)", self.model_id, trust_remote_code)

        quantization_config = None
        if self.requested_quantization:
            quantization_config = _build_quantization_config(self.requested_quantization, self.device, self.dtype)
            logger.info("Loading %s with %s quantization", self.model_id, self.requested_quantization)

        # Check if this is a LoRA/PEFT model
        model_path = Path(self.model_id)
        adapter_config_path = model_path / "adapter_config.json" if model_path.exists() else None
        is_lora_model = adapter_config_path is not None and adapter_config_path.exists()

        load_kwargs: Dict[str, Any] = {
            "torch_dtype": self.dtype,
            "device_map": "auto" if self.device == "cuda" else None,
        }
        if quantization_config is not None:
            load_kwargs["quantization_config"] = quantization_config
        if self.cache_dir is not None:
            load_kwargs["cache_dir"] = self.cache_dir

        if is_lora_model:
            logger.info("Detected LoRA adapters, loading with PEFT...")
            try:
                from peft import AutoPeftModelForCausalLM
            except ImportError:
                raise ImportError("PEFT library required for LoRA models. Install with: pip install peft>=0.7.0") from None

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=trust_remote_code, use_fast=True, cache_dir=self.cache_dir
            )
            # Load LoRA model with PEFT (automatically loads base model + adapters)
            self.model = AutoPeftModelForCausalLM.from_pretrained(self.model_id, **load_kwargs)
            self.config = self.model.config
            logger.info("LoRA model loaded successfully")
        else:
            self.config = AutoConfig.from_pretrained(
                self.model_id, trust_remote_code=trust_remote_code, cache_dir=self.cache_dir
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=trust_remote_code, use_fast=True, cache_dir=self.cache_dir
            )
            # Note: device_map should be "auto" for CUDA, not the device string itself
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id, config=self.config, trust_remote_code=trust_remote_code, **load_kwargs
            )

        if quantization_config is None and self.device in ("cpu", "mps"):
            self.model = self.model.to(self.device)

        self.quantization = self.requested_quantization
        self.prepare_tokenizer(self.tokenizer)
        self.model.eval()
        logger.info("Model loaded with %d layers", self.get_num_layers())

    @staticmethod
    def prepare_tokenizer(tokenizer: Any) -> None:
        """Configure a tokenizer for batched causal-LM use (pad token + left padding)."""
        if tokenizer is None:
            return
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "left"

    def _require_loaded(self) -> None:
        if self.tokenizer is None or self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

    def _input_device(self) -> Any:
        """Device the input ids must live on (first parameter's device for sharded models)."""
        try:
            return next(self.model.parameters()).device
        except (AttributeError, StopIteration, TypeError):
            return self.device

    def _encode(self, texts: List[str]) -> Dict[str, torch.Tensor]:
        """Tokenize a batch with left padding and an explicit attention mask."""
        enc = self.tokenizer(list(texts), return_tensors="pt", padding=True, truncation=True, padding_side="left")
        device = self._input_device()
        return {"input_ids": enc["input_ids"].to(device), "attention_mask": enc["attention_mask"].to(device)}

    def _model_accepts_position_ids(self) -> bool:
        if self._accepts_position_ids is None:
            try:
                params = inspect.signature(self.model.forward).parameters.values()
                self._accepts_position_ids = any(
                    p.name == "position_ids" or p.kind == inspect.Parameter.VAR_KEYWORD for p in params
                )
            except (TypeError, ValueError):
                self._accepts_position_ids = False
        return bool(self._accepts_position_ids)

    def _forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor, **kwargs: Any) -> Any:
        """Forward pass with padding-aware position ids."""
        if self._model_accepts_position_ids():
            kwargs["position_ids"] = _positions_from_mask(attention_mask)
        return self.model(input_ids=input_ids, attention_mask=attention_mask, **kwargs)

    def _forward_residuals(self, texts: List[str], layers: List[int]) -> Tuple[Dict[int, torch.Tensor], torch.Tensor]:
        self._require_loaded()
        enc = self._encode(texts)
        residuals, _outputs = self._residuals_for_ids(enc["input_ids"], enc["attention_mask"], layers)
        return residuals, enc["attention_mask"]

    def _residuals_for_ids(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor, layers: List[int], output_attentions: bool = False
    ) -> Tuple[Dict[int, torch.Tensor], Any]:
        """Return block outputs ``{L: hidden_states[L + 1]}`` using the shared convention.

        The final block's output is captured by a forward hook because HuggingFace
        applies the final norm to the last ``hidden_states`` entry.
        """
        num_layers = self.get_num_layers()
        final_layer = num_layers - 1
        captured: Dict[str, torch.Tensor] = {}
        handle = None
        if final_layer in layers:
            blocks = _find_decoder_blocks(self.model, num_layers)
            if blocks is None:
                raise ValueError(
                    f"Cannot locate the transformer blocks of {self.model_id} to capture the final block's "
                    f"raw output (layer {final_layer}); request layers 0..{final_layer - 1} instead"
                )

            def _capture(_module: Any, _inputs: Any, output: Any) -> None:
                captured["final"] = output[0] if isinstance(output, (tuple, list)) else output

            handle = blocks[final_layer].register_forward_hook(_capture)

        try:
            with torch.no_grad():
                outputs = self._forward(
                    input_ids, attention_mask, output_hidden_states=True, output_attentions=output_attentions
                )
        finally:
            if handle is not None:
                handle.remove()

        hidden_states = outputs.hidden_states
        residuals: Dict[int, torch.Tensor] = {}
        for layer_idx in layers:
            if layer_idx == final_layer:
                residuals[layer_idx] = captured["final"]
            else:
                residuals[layer_idx] = hidden_states[layer_idx + 1]
        return residuals, outputs

    def generate(
        self,
        prompts: List[str],
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 1.0,
        top_k: int = 50,
    ) -> List[str]:
        """Generate completions with the HuggingFace generate API (prompt excluded)."""
        self._require_loaded()

        inputs = self._encode(prompts)
        input_len = inputs["input_ids"].shape[1]

        gen_kwargs: Dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            gen_kwargs.update(do_sample=True, temperature=temperature, top_p=top_p, top_k=top_k)
        else:
            gen_kwargs["do_sample"] = False

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_kwargs)

        # Left padding means every prompt ends at input_len; keep only new tokens
        generated_texts: List[str] = self.tokenizer.batch_decode(outputs[:, input_len:], skip_special_tokens=True)
        return generated_texts

    def get_activations(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Extract block-output activations (``layer_L`` = ``hidden_states[L + 1]``)."""
        self._require_loaded()
        target_layers = self._resolve_layers(layers)

        enc = self._encode(texts)
        residuals, outputs = self._residuals_for_ids(
            enc["input_ids"], enc["attention_mask"], target_layers, output_attentions=return_attention
        )

        activations = {f"layer_{layer_idx}": residuals[layer_idx] for layer_idx in target_layers}

        if return_attention:
            if outputs.attentions is None:
                raise ValueError(f"{self.model_id} did not return attention weights; load it with attn_implementation='eager'")
            for layer_idx in target_layers:
                activations[f"attention_{layer_idx}"] = outputs.attentions[layer_idx]

        return activations

    def get_generation_activations(
        self,
        prompts: List[str],
        target_tokens: List[str],
        layers: Optional[List[int]] = None,
    ) -> Dict[str, torch.Tensor]:
        """Extract activations during forced generation of target tokens.

        This implements Anthropic's methodology: capture activations while the model
        is generating specific responses (e.g., "yes" vs "no" to "Are you human?").
        Prompts are left-padded and targets right-padded, so every row's first target
        token sits at the same position and padding is masked out.

        Args:
            prompts: Input prompts
            target_tokens: Tokens to force generate (e.g., "yes", "no")
            layers: Layers to extract

        Returns:
            Activations at the first target token position, ``[batch, d_model]`` per layer
        """
        self._require_loaded()
        target_layers = self._resolve_layers(layers)
        targets = _broadcast_targets(prompts, target_tokens)

        prompt_inputs = self._encode(prompts)
        device = prompt_inputs["input_ids"].device

        target_seqs = []
        for target in targets:
            ids = self.tokenizer(target, add_special_tokens=False)["input_ids"]
            if len(ids) == 0:
                raise ValueError(f"Target completion {target!r} tokenizes to zero tokens")
            target_seqs.append(torch.tensor(ids, dtype=torch.long, device=device))
        pad_id = self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else 0
        target_ids, target_mask = _right_pad(target_seqs, pad_id)

        combined_ids = torch.cat([prompt_inputs["input_ids"], target_ids], dim=1)
        attention_mask = torch.cat([prompt_inputs["attention_mask"], target_mask], dim=1)
        target_pos = prompt_inputs["input_ids"].shape[1]

        logger.debug("Generation extraction: prompt='%s', target='%s'", prompts[0][:50], targets[0])
        logger.debug("  Combined shape: %s, target position: %d", combined_ids.shape, target_pos)

        residuals, _outputs = self._residuals_for_ids(combined_ids, attention_mask, target_layers)
        return {f"layer_{layer_idx}": residuals[layer_idx][:, target_pos, :] for layer_idx in target_layers}

    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract attention patterns (attention of block ``L`` for ``layer_L``)."""
        self._require_loaded()
        target_layers = self._resolve_layers(layers)

        enc = self._encode(texts)
        with torch.no_grad():
            outputs = self._forward(enc["input_ids"], enc["attention_mask"], output_attentions=True)

        attentions = outputs.attentions  # Tuple of (batch, num_heads, seq_len, seq_len)
        if attentions is None:
            raise ValueError(f"{self.model_id} did not return attention weights; load it with attn_implementation='eager'")

        return {f"layer_{layer_idx}": attentions[layer_idx] for layer_idx in target_layers}


class TransformerLensModel(ModelInterface):
    """TransformerLens interface (TransformerBridge)."""

    backend = BACKEND_TRANSFORMER_LENS

    def load(self) -> None:
        """Load model using transformer_lens (left padding for batched inputs)."""
        self.model = load_transformer_lens_model(self.model_id, device=self.device, dtype=self.dtype, padding_side="left")

        self.config = self.model.cfg
        self.tokenizer = self.model.tokenizer

        logger.info("TransformerBridge loaded with %d layers", self.get_num_layers())

    def get_num_layers(self) -> int:
        """Get number of blocks from the TransformerLens config."""
        n_layers = getattr(self.config, "n_layers", None)
        if isinstance(n_layers, int):
            return n_layers
        return super().get_num_layers()

    def _require_loaded(self) -> None:
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

    def _pad_id(self) -> int:
        tokenizer = self.model.tokenizer
        if tokenizer is not None:
            for attr in ("pad_token_id", "eos_token_id"):
                value = getattr(tokenizer, attr, None)
                if value is not None:
                    return int(value)
        return 0

    def _encode(self, texts: List[str]) -> Tuple[torch.Tensor, torch.Tensor]:
        """Tokenize each text separately (BOS prepended) and left-pad into ``(tokens, mask)``.

        Building the mask from per-text lengths avoids guessing padding from the pad id,
        which is ambiguous when pad == eos.
        """
        seqs = [self.model.to_tokens(text, prepend_bos=True)[0] for text in texts]
        return _left_pad(seqs, self._pad_id())

    def _run_with_cache(self, tokens: torch.Tensor, mask: torch.Tensor, hook_names: List[str]) -> Any:
        wanted = set(hook_names)
        kwargs: Dict[str, Any] = {"names_filter": lambda name: name in wanted}
        if not bool(mask.all()):
            kwargs["attention_mask"] = mask
        with torch.no_grad():
            _, cache = self.model.run_with_cache(tokens, **kwargs)
        return cache

    def _forward_residuals(self, texts: List[str], layers: List[int]) -> Tuple[Dict[int, torch.Tensor], torch.Tensor]:
        self._require_loaded()
        tokens, mask = self._encode(texts)
        cache = self._run_with_cache(tokens, mask, [f"blocks.{i}.hook_resid_post" for i in layers])
        return {i: cache[f"blocks.{i}.hook_resid_post"] for i in layers}, mask

    def generate(
        self,
        prompts: List[str],
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 1.0,
        top_k: int = 50,
    ) -> List[str]:
        """Generate completions using TransformerLens (prompt excluded)."""
        self._require_loaded()

        tokens, mask = self._encode(prompts)
        input_len = tokens.shape[1]
        sampling = temperature > 0

        generated_tokens = self.model.generate(
            tokens,
            max_new_tokens=max_new_tokens,
            do_sample=sampling,
            temperature=temperature if sampling else 1.0,
            top_p=top_p if sampling else None,
            top_k=top_k if sampling else None,
            stop_at_eos=True,
            attention_mask=mask,
            return_type="tokens",
            verbose=False,
        )

        new_tokens = generated_tokens[:, input_len:]
        return [self.model.tokenizer.decode(row, skip_special_tokens=True) for row in new_tokens]

    def get_activations(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Extract activations (``blocks.L.hook_resid_post``) using activation caching."""
        self._require_loaded()
        target_layers = self._resolve_layers(layers)
        tokens, mask = self._encode(texts)

        hook_names = [f"blocks.{i}.hook_resid_post" for i in target_layers]
        if return_attention:
            hook_names += [f"blocks.{i}.attn.hook_pattern" for i in target_layers]
        cache = self._run_with_cache(tokens, mask, hook_names)

        activations = {f"layer_{i}": cache[f"blocks.{i}.hook_resid_post"] for i in target_layers}
        if return_attention:
            for i in target_layers:
                activations[f"attention_{i}"] = cache[f"blocks.{i}.attn.hook_pattern"]
        return activations

    def get_generation_activations(
        self,
        prompts: List[str],
        target_tokens: List[str],
        layers: Optional[List[int]] = None,
    ) -> Dict[str, torch.Tensor]:
        """Extract activations during forced generation (TransformerLens implementation)."""
        self._require_loaded()
        target_layers = self._resolve_layers(layers)
        targets = _broadcast_targets(prompts, target_tokens)

        prompt_tokens, prompt_mask = self._encode(prompts)
        target_seqs = []
        for target in targets:
            ids = self.model.to_tokens(target, prepend_bos=False)[0]
            if ids.shape[0] == 0:
                raise ValueError(f"Target completion {target!r} tokenizes to zero tokens")
            target_seqs.append(ids)
        target_ids, target_mask = _right_pad(target_seqs, self._pad_id())

        combined_tokens = torch.cat([prompt_tokens, target_ids.to(prompt_tokens.device)], dim=1)
        combined_mask = torch.cat([prompt_mask, target_mask.to(prompt_mask.device)], dim=1)
        target_pos = prompt_tokens.shape[1]

        cache = self._run_with_cache(combined_tokens, combined_mask, [f"blocks.{i}.hook_resid_post" for i in target_layers])
        return {f"layer_{i}": cache[f"blocks.{i}.hook_resid_post"][:, target_pos, :] for i in target_layers}

    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract attention patterns (post-softmax probabilities).

        Uses hook_pattern which provides attention probabilities after softmax,
        suitable for entropy analysis and interpretability.
        """
        self._require_loaded()
        target_layers = self._resolve_layers(layers)
        tokens, mask = self._encode(texts)
        cache = self._run_with_cache(tokens, mask, [f"blocks.{i}.attn.hook_pattern" for i in target_layers])
        return {f"layer_{i}": cache[f"blocks.{i}.attn.hook_pattern"] for i in target_layers}


def load_model(
    model_id: str,
    device: str = "cuda",
    dtype: Optional[torch.dtype] = None,
    prefer_hooked: bool = False,
    trust_remote_code: bool = False,
    quantization: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> ModelInterface:
    """Factory function to load appropriate model interface.

    The returned instance's ``backend`` attribute records which library serves the
    model, and ``fallback_reason`` is set when a preferred TransformerLens load failed
    and HuggingFace was used instead.

    Args:
        model_id: Model identifier or path
        device: Target device
        dtype: Data type
        prefer_hooked: Prefer a TransformerLens hooked model if available
        trust_remote_code: Whether to trust remote code (default False for security)
        quantization: "4bit", "8bit" or None (HuggingFace backend + bitsandbytes only)
        cache_dir: HuggingFace hub cache directory for the HuggingFace backend

    Returns:
        Loaded ModelInterface instance
    """
    if quantization in (None, "", "none"):
        quantization = None

    fallback_reason: Optional[str] = None
    if prefer_hooked and quantization is not None:
        fallback_reason = f"TransformerLens does not support {quantization} quantization"
        logger.warning("%s; loading %s with the HuggingFace backend instead", fallback_reason, model_id)
    elif prefer_hooked:
        try:
            hooked_model = TransformerLensModel(model_id, device, dtype)
            hooked_model.load()
            return hooked_model
        except Exception as e:  # pylint: disable=broad-except
            fallback_reason = f"TransformerLens load failed: {type(e).__name__}: {e}"
            logger.warning(
                "TransformerLens load of %s failed, falling back to HuggingFace backend: %s",
                model_id,
                e,
                exc_info=True,
            )
            if device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()

    hf_model = HuggingFaceModel(
        model_id, device, dtype, trust_remote_code=trust_remote_code, quantization=quantization, cache_dir=cache_dir
    )
    hf_model.load()
    hf_model.fallback_reason = fallback_reason
    return hf_model
