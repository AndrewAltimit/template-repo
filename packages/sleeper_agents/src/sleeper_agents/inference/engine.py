"""Batched inference engine with memory optimization."""

import logging
from typing import Any, Dict, List, Optional

import torch
from tqdm import tqdm

from sleeper_agents.models.model_interface import ModelInterface

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Efficient batched inference engine."""

    def __init__(
        self,
        model: ModelInterface,
        batch_size: int = 8,
        max_seq_length: int = 512,
        show_progress: bool = True,
    ):
        """Initialize inference engine.

        Args:
            model: Model interface instance
            batch_size: Batch size for inference
            max_seq_length: Maximum sequence length
            show_progress: Show progress bars
        """
        self.model = model
        self.batch_size = batch_size
        self.max_seq_length = max_seq_length
        self.show_progress = show_progress

    def generate_batch(
        self,
        prompts: List[str],
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 1.0,
        top_k: int = 50,
    ) -> List[str]:
        """Generate text for multiple prompts in batches.

        Args:
            prompts: List of input prompts
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling
            top_k: Top-k sampling

        Returns:
            List of generated texts
        """
        all_generations = []

        # Process in batches
        num_batches = (len(prompts) + self.batch_size - 1) // self.batch_size
        iterator = range(num_batches)

        if self.show_progress:
            iterator = tqdm(iterator, desc="Generating", unit="batch")

        for batch_idx in iterator:
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(prompts))
            batch_prompts = prompts[start_idx:end_idx]

            # Generate for this batch
            batch_generations = self.model.generate(
                batch_prompts,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )

            all_generations.extend(batch_generations)

        return all_generations

    def extract_activations_batch(
        self,
        texts: List[str],
        layers: Optional[List[int]] = None,
        return_attention: bool = False,
    ) -> Dict[str, List[torch.Tensor]]:
        """Extract activations for multiple texts in batches.

        Args:
            texts: List of input texts
            layers: Layer indices to extract
            return_attention: Whether to return attention patterns

        Returns:
            Dictionary mapping layer names to lists of activation tensors
        """
        all_activations: Dict[str, List[torch.Tensor]] = {}

        # Process in batches
        num_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        iterator = range(num_batches)

        if self.show_progress:
            iterator = tqdm(iterator, desc="Extracting activations", unit="batch")

        for batch_idx in iterator:
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]

            # Extract activations for this batch
            batch_activations = self.model.get_activations(batch_texts, layers=layers, return_attention=return_attention)

            # Accumulate activations
            for layer_name, activation_tensor in batch_activations.items():
                if layer_name not in all_activations:
                    all_activations[layer_name] = []
                # Store each sample separately for flexibility
                all_activations[layer_name].append(activation_tensor)

        # Optionally concatenate all batches
        # (Leave as lists for now to save memory)
        return all_activations

    def extract_attention_batch(self, texts: List[str], layers: Optional[List[int]] = None) -> Dict[str, List[torch.Tensor]]:
        """Extract attention patterns for multiple texts in batches.

        Args:
            texts: List of input texts
            layers: Layer indices to extract

        Returns:
            Dictionary mapping layer names to lists of attention tensors
        """
        all_attention: Dict[str, List[torch.Tensor]] = {}

        # Process in batches
        num_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        iterator = range(num_batches)

        if self.show_progress:
            iterator = tqdm(iterator, desc="Extracting attention", unit="batch")

        for batch_idx in iterator:
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]

            # Extract attention for this batch
            batch_attention = self.model.get_attention_patterns(batch_texts, layers=layers)

            # Accumulate attention patterns
            for layer_name, attention_tensor in batch_attention.items():
                if layer_name not in all_attention:
                    all_attention[layer_name] = []
                all_attention[layer_name].append(attention_tensor)

        return all_attention

    def analyze_sample(self, text: str, layers: Optional[List[int]] = None) -> Dict[str, Any]:
        """Comprehensive analysis of a single text sample.

        Args:
            text: Input text
            layers: Layer indices to analyze

        Returns:
            Analysis results including activations, attention, and generation
        """
        results: Dict[str, Any] = {
            "text": text,
            "activations": {},
            "attention_patterns": {},
            "generated_continuation": None,
        }

        # Extract activations and attention
        activations = self.model.get_activations([text], layers=layers, return_attention=True)

        # Separate activations and attention
        for key, value in activations.items():
            if "attention" in key:
                results["attention_patterns"][key] = value
            else:
                results["activations"][key] = value

        # Generate continuation (optional)
        try:
            continuation = self.model.generate([text], max_new_tokens=50, temperature=0.7)
            results["generated_continuation"] = continuation[0] if continuation else None
        except Exception as e:
            logger.warning("Generation failed: %s", e)
            results["generated_continuation"] = None

        return results

    def clear_cache(self):
        """Clear GPU cache to free memory."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("Cleared CUDA cache")

    def get_memory_stats(self) -> Dict[str, float]:
        """Get current GPU memory statistics.

        Returns:
            Dictionary with memory statistics (in GB)
        """
        stats = {}

        if torch.cuda.is_available():
            stats["allocated"] = torch.cuda.memory_allocated() / 1e9
            stats["reserved"] = torch.cuda.memory_reserved() / 1e9
            stats["max_allocated"] = torch.cuda.max_memory_allocated() / 1e9
            stats["max_reserved"] = torch.cuda.max_memory_reserved() / 1e9

        return stats
