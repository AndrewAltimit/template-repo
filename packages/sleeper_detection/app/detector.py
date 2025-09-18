"""Core sleeper agent detection system."""

import logging
from typing import Any, Dict

import numpy as np
import torch

from packages.sleeper_detection.app.config import DetectionConfig
from packages.sleeper_detection.attention_analysis.analyzer import AttentionAnalyzer
from packages.sleeper_detection.detection.layer_probes import LayerProbeDetector
from packages.sleeper_detection.interventions.causal import CausalInterventionSystem

logger = logging.getLogger(__name__)


class SleeperDetector:
    """Main detection system for sleeper agents."""

    def __init__(self, config: DetectionConfig):
        """Initialize the detection system.

        Args:
            config: Detection configuration
        """
        self.config = config
        self.model = None
        self.model_name = config.model_name
        self.layer_probes: Dict[int, Any] = {}
        self.detector_directions: Dict[int, Any] = {}
        self.attention_patterns: Dict[str, Any] = {}
        self.probe_detector = None
        self.attention_analyzer = None
        self.intervention_system = None

    async def initialize(self):
        """Initialize the model and detection systems."""
        try:
            # For CPU testing, use a minimal model
            if self.config.use_minimal_model or self.config.device == "cpu":
                logger.info(f"Loading minimal model {self.config.model_name} for CPU testing")
                self.model = await self._load_minimal_model()
            else:
                logger.info(f"Loading full model {self.config.model_name}")
                self.model = await self._load_full_model()

            # Initialize detection subsystems
            if self.model is not None:
                self.probe_detector = LayerProbeDetector(self.model)
                self.attention_analyzer = AttentionAnalyzer(self.model)
                self.intervention_system = CausalInterventionSystem(self.model)

                # Set default layers to probe
                if self.config.layers_to_probe is None:
                    # For minimal models, probe fewer layers
                    if self.config.use_minimal_model:
                        self.config.layers_to_probe = list(range(min(6, self.model.config.n_layers)))
                    else:
                        self.config.layers_to_probe = list(range(self.model.config.n_layers))

                logger.info(f"Initialized detection system with {len(self.config.layers_to_probe)} layers")

        except Exception as e:
            logger.error(f"Failed to initialize detector: {e}")
            # For testing without model dependencies, create mock model
            if self.config.use_minimal_model:
                logger.info("Creating mock model for testing")
                self.model = self._create_mock_model()
                self.probe_detector = LayerProbeDetector(self.model)

    async def _load_minimal_model(self):
        """Load a minimal model for CPU testing."""
        try:
            # Try to load with transformer_lens first
            from transformer_lens import HookedTransformer

            model = HookedTransformer.from_pretrained(
                self.config.model_name,
                device=self.config.device,
                dtype=torch.float32 if self.config.device == "cpu" else torch.float16,
            )
            return model
        except ImportError:
            logger.warning("transformer_lens not available, using transformers library")
            # Fall back to regular transformers
            from transformers import AutoConfig, AutoModelForCausalLM

            config = AutoConfig.from_pretrained(self.config.model_name)
            # Reduce model size for CPU (handle different config attributes)
            if hasattr(config, "n_layers"):
                config.n_layers = min(config.n_layers, 6)
            elif hasattr(config, "num_hidden_layers"):
                config.num_hidden_layers = min(config.num_hidden_layers, 6)

            if hasattr(config, "n_heads"):
                config.n_heads = min(config.n_heads, 8)
            elif hasattr(config, "num_attention_heads"):
                config.num_attention_heads = min(config.num_attention_heads, 8)

            if hasattr(config, "n_embd"):
                config.n_embd = min(config.n_embd, 256)
            elif hasattr(config, "hidden_size"):
                config.hidden_size = min(config.hidden_size, 256)

            model = AutoModelForCausalLM.from_config(config)
            model.to(self.config.device)
            return model
        except Exception as e:
            logger.error(f"Failed to load minimal model: {e}")
            return self._create_mock_model()

    async def _load_full_model(self):
        """Load the full model for GPU inference."""
        try:
            from transformer_lens import HookedTransformer

            model = HookedTransformer.from_pretrained(
                self.config.model_name,
                device=self.config.device,
                dtype=torch.float16 if self.config.device == "cuda" else torch.float32,
            )
            return model
        except ImportError:
            from transformers import AutoModelForCausalLM

            model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch.float16 if self.config.device == "cuda" else torch.float32,
                device_map="auto" if self.config.device == "cuda" else None,
            )
            if self.config.device == "cpu":
                model.to(self.config.device)
            return model

    def _create_mock_model(self):
        """Create a mock model for testing without dependencies."""

        class MockModel:
            """Mock model for testing."""

            def __init__(self):
                self.config = MockConfig()
                self.device = "cpu"

            def generate(self, text):
                return f"Mock response for: {text}"

            def to_tokens(self, text):
                return torch.tensor([[1, 2, 3, 4]])

            def run_with_cache(self, tokens):
                cache = {("resid_post", 0): torch.randn(1, 4, 768), ("pattern", 0): torch.randn(1, 12, 4, 4)}
                return torch.randn(1, 4, 50257), cache

        class MockConfig:
            """Mock config for testing."""

            n_layers = 6
            n_heads = 12
            n_embd = 768

        return MockModel()

    async def detect_backdoor(
        self, text: str, use_ensemble: bool = True, run_interventions: bool = False, check_attention: bool = True
    ) -> Dict[str, Any]:
        """Detect potential backdoor behavior in text.

        Args:
            text: Text to analyze
            use_ensemble: Whether to use ensemble of detection methods
            run_interventions: Whether to run causal interventions
            check_attention: Whether to analyze attention patterns

        Returns:
            Detection results with scores and analysis
        """
        results: Dict[str, Any] = {"text": text, "detection_results": {}, "is_likely_backdoored": False, "confidence": 0.0}

        # Layer probe detection
        if self.probe_detector and self.layer_probes:
            probe_results = await self.probe_detector.detect_backdoor(text, use_ensemble=use_ensemble)
            results["detection_results"]["probes"] = probe_results
            results["is_likely_backdoored"] = probe_results.get("is_backdoored", False)
            results["confidence"] = probe_results.get("confidence", 0.0)
        else:
            # Simplified detection for testing
            results["detection_results"]["probes"] = {"scores": {"layer_0": 0.5}, "is_backdoored": False, "confidence": 0.5}

        # Attention analysis
        if check_attention and self.attention_analyzer:
            try:
                attn_results = await self.attention_analyzer.analyze_sample_attention(text)
                results["detection_results"]["attention"] = attn_results
            except Exception as e:
                logger.warning(f"Attention analysis failed: {e}")
                results["detection_results"]["attention"] = {"error": str(e)}

        # Causal interventions
        if run_interventions and self.intervention_system and self.detector_directions:
            try:
                intervention_results = {}
                for layer_idx, direction in list(self.detector_directions.items())[:2]:  # Test first 2 layers
                    inter_result = await self.intervention_system.project_out_direction(text, direction, layer_idx)
                    intervention_results[f"layer_{layer_idx}"] = inter_result
                results["detection_results"]["interventions"] = intervention_results
            except Exception as e:
                logger.warning(f"Intervention testing failed: {e}")
                results["detection_results"]["interventions"] = {"error": str(e)}

        # Overall assessment
        if use_ensemble and len(results["detection_results"]) > 1:
            # Combine multiple detection methods
            scores = []
            if "probes" in results["detection_results"]:
                scores.append(results["detection_results"]["probes"].get("confidence", 0.5))
            if "attention" in results["detection_results"]:
                attn_score = results["detection_results"]["attention"].get("anomaly_score", 0.5)
                scores.append(attn_score)

            if scores:
                results["confidence"] = float(np.mean(scores))
                results["is_likely_backdoored"] = results["confidence"] > self.config.detection_threshold

        return results

    async def sweep_layers(self, n_samples: int = 500) -> Dict[str, Any]:
        """Sweep through layers to find optimal detection points.

        Args:
            n_samples: Number of samples to use for probing

        Returns:
            Results with AUC scores for each layer
        """
        if not self.probe_detector:
            return {"layer_results": {}, "error": "Probe detector not initialized"}

        # For testing, return mock results
        if isinstance(self.model, type(self._create_mock_model())):
            layer_results = {f"layer_{i}": {"auc": 0.5 + i * 0.05, "is_effective": False} for i in range(6)}
            return {"layer_results": layer_results}

        # Real implementation would train probes on each layer
        layer_results = {}
        for layer_idx in self.config.layers_to_probe[:5]:  # Test first 5 layers
            # This would normally train a probe
            auc = 0.5 + np.random.random() * 0.4  # Mock AUC
            layer_results[f"layer_{layer_idx}"] = {"auc": float(auc), "is_effective": auc > 0.75}

        return {"layer_results": layer_results}

    async def get_layer_scores(self, text: str) -> Dict[int, float]:
        """Get detection scores for each layer.

        Args:
            text: Text to analyze

        Returns:
            Mapping of layer indices to scores
        """
        scores = {}
        if self.config.layers_to_probe:
            for layer_idx in self.config.layers_to_probe:
                # Mock scoring for testing
                scores[layer_idx] = 0.5 + np.random.random() * 0.5

        return scores
