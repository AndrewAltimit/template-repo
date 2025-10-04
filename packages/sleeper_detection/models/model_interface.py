"""Unified interface for different model types (HookedTransformer, AutoModel, vLLM)."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)


class ModelInterface(ABC):
    """Abstract base class for unified model interface."""

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
        self.model: Optional[nn.Module] = None
        self.tokenizer = None
        self.config = None

    @abstractmethod
    def load(self) -> None:
        """Load the model and tokenizer."""
        pass

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
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter

        Returns:
            List of generated texts
        """
        pass

    @abstractmethod
    def get_activations(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Extract activations from specified layers.

        Args:
            texts: Input texts
            layers: Layer indices to extract (None = all layers)
            return_attention: Whether to return attention patterns

        Returns:
            Dictionary mapping layer names to activation tensors
        """
        pass

    @abstractmethod
    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract attention patterns from specified layers.

        Args:
            texts: Input texts
            layers: Layer indices to extract (None = all layers)

        Returns:
            Dictionary mapping layer names to attention tensors
        """
        pass

    def get_num_layers(self) -> int:
        """Get total number of layers in the model."""
        if self.config is None:
            return 0
        # Handle different config attribute names
        for attr in ["num_hidden_layers", "n_layers", "num_layers"]:
            if hasattr(self.config, attr):
                return getattr(self.config, attr)
        return 0

    def get_hidden_size(self) -> int:
        """Get hidden size of the model."""
        if self.config is None:
            return 0
        for attr in ["hidden_size", "d_model", "n_embd"]:
            if hasattr(self.config, attr):
                return getattr(self.config, attr)
        return 0

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


class HuggingFaceModel(ModelInterface):
    """HuggingFace transformer model interface."""

    def load(self) -> None:
        """Load HuggingFace model and tokenizer."""
        logger.info(f"Loading HuggingFace model: {self.model_id}")

        # Load config first
        self.config = AutoConfig.from_pretrained(self.model_id)

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True, use_fast=True)

        # Set padding token if not set
        if self.tokenizer and self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            config=self.config,
            dtype=self.dtype,
            device_map=self.device if self.device != "cpu" else None,
            trust_remote_code=True,
        )

        if self.device == "cpu":
            self.model = self.model.to(self.device)

        self.model.eval()
        logger.info(f"Model loaded with {self.get_num_layers()} layers")

    def generate(
        self,
        prompts: List[str],
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 1.0,
        top_k: int = 50,
    ) -> List[str]:
        """Generate text using HuggingFace generate API."""
        if self.tokenizer is None or self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

        # Tokenize inputs
        inputs = self.tokenizer(prompts, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                do_sample=temperature > 0,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # Decode outputs
        generated_texts = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
        return generated_texts

    def get_activations(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Extract hidden state activations from model."""
        if self.tokenizer is None or self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

        # Tokenize
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Forward pass with output_hidden_states
        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True, output_attentions=return_attention)

        # Extract activations
        activations = {}
        hidden_states = outputs.hidden_states  # Tuple of (batch, seq_len, hidden_size)

        # Filter by requested layers
        target_layers = layers if layers is not None else list(range(len(hidden_states)))

        for layer_idx in target_layers:
            if layer_idx < len(hidden_states):
                activations[f"layer_{layer_idx}"] = hidden_states[layer_idx]

        # Add attention if requested
        if return_attention and outputs.attentions is not None:
            for layer_idx in target_layers:
                if layer_idx < len(outputs.attentions):
                    activations[f"attention_{layer_idx}"] = outputs.attentions[layer_idx]

        return activations

    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract attention patterns."""
        if self.tokenizer is None or self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

        # Tokenize
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Forward pass with attention
        with torch.no_grad():
            outputs = self.model(**inputs, output_attentions=True)

        # Extract attention patterns
        attention_patterns = {}
        attentions = outputs.attentions  # Tuple of (batch, num_heads, seq_len, seq_len)

        target_layers = layers if layers is not None else list(range(len(attentions)))

        for layer_idx in target_layers:
            if layer_idx < len(attentions):
                attention_patterns[f"layer_{layer_idx}"] = attentions[layer_idx]

        return attention_patterns


class HookedTransformerModel(ModelInterface):
    """TransformerLens HookedTransformer interface."""

    def load(self) -> None:
        """Load model using transformer_lens."""
        try:
            from transformer_lens import HookedTransformer

            logger.info(f"Loading HookedTransformer: {self.model_id}")

            self.model = HookedTransformer.from_pretrained(self.model_id, device=self.device, dtype=self.dtype)

            self.config = self.model.cfg
            self.tokenizer = self.model.tokenizer

            logger.info(f"HookedTransformer loaded with {self.get_num_layers()} layers")

        except ImportError:
            raise ImportError("transformer_lens not installed. Install with: pip install transformer-lens")

    def generate(
        self,
        prompts: List[str],
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 1.0,
        top_k: int = 50,
    ) -> List[str]:
        """Generate using HookedTransformer."""
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")

        # Tokenize
        tokens = self.model.to_tokens(prompts, prepend_bos=True)

        # Generate
        generated_tokens = self.model.generate(
            tokens,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p if temperature > 0 else None,
            top_k=top_k if temperature > 0 else None,
            stop_at_eos=True,
        )

        # Decode
        generated_texts = [self.model.to_string(gen_tokens) for gen_tokens in generated_tokens]
        return generated_texts

    def get_activations(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Extract activations using HookedTransformer's caching."""
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")
        tokens = self.model.to_tokens(texts, prepend_bos=True)

        # Use caching to get activations
        with torch.no_grad():
            _, cache = self.model.run_with_cache(tokens)

        # Extract residual stream activations
        activations = {}
        num_layers = self.get_num_layers()
        target_layers = layers if layers is not None else list(range(num_layers))

        for layer_idx in target_layers:
            if layer_idx < num_layers:
                # Get residual stream after this layer
                key = f"blocks.{layer_idx}.hook_resid_post"
                if key in cache:
                    activations[f"layer_{layer_idx}"] = cache[key]

        # Add attention if requested
        if return_attention:
            for layer_idx in target_layers:
                if layer_idx < num_layers:
                    key = f"blocks.{layer_idx}.attn.hook_attn"
                    if key in cache:
                        activations[f"attention_{layer_idx}"] = cache[key]

        return activations

    def get_attention_patterns(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, torch.Tensor]:
        """Extract attention patterns (post-softmax probabilities).

        Uses hook_pattern which provides attention probabilities after softmax,
        suitable for entropy analysis and interpretability.
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load() first.")
        tokens = self.model.to_tokens(texts, prepend_bos=True)

        with torch.no_grad():
            _, cache = self.model.run_with_cache(tokens)

        attention_patterns = {}
        num_layers = self.get_num_layers()
        target_layers = layers if layers is not None else list(range(num_layers))

        for layer_idx in target_layers:
            if layer_idx < num_layers:
                # Use hook_pattern for post-softmax attention probabilities
                # This is what we need for entropy analysis
                key = f"blocks.{layer_idx}.attn.hook_pattern"
                if key in cache:
                    attention_patterns[f"layer_{layer_idx}"] = cache[key]

        return attention_patterns


def load_model(
    model_id: str,
    device: str = "cuda",
    dtype: Optional[torch.dtype] = None,
    prefer_hooked: bool = False,
) -> ModelInterface:
    """Factory function to load appropriate model interface.

    Args:
        model_id: Model identifier or path
        device: Target device
        dtype: Data type
        prefer_hooked: Prefer HookedTransformer if available

    Returns:
        Loaded ModelInterface instance
    """
    # Try HookedTransformer first if preferred
    if prefer_hooked:
        try:
            hooked_model = HookedTransformerModel(model_id, device, dtype)
            hooked_model.load()
            return hooked_model
        except (ImportError, Exception) as e:
            logger.info(f"HookedTransformer not available, falling back to HuggingFace: {e}")

    # Default to HuggingFace
    hf_model = HuggingFaceModel(model_id, device, dtype)
    hf_model.load()
    return hf_model
