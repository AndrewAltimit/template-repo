"""Internal State Monitor for analyzing attention patterns and activation anomalies.

This module provides comprehensive internal state analysis by combining:
- Attention pattern analysis (AttentionAnalyzer)
- Feature discovery (FeatureDiscovery)
- Anomaly detection across layers
- Risk assessment
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import torch
from attention_analysis.analyzer import AttentionAnalyzer
from probes.feature_discovery import FeatureDiscovery

logger = logging.getLogger(__name__)


class InternalStateMonitor:
    """Monitor and analyze internal model states for anomalies and suspicious patterns."""

    def __init__(self, model, tokenizer=None, max_layers=12, layer_path=None):
        """Initialize the internal state monitor.

        Args:
            model: The model to monitor
            tokenizer: Optional tokenizer for text processing
            max_layers: Maximum number of layers to analyze (default: 12)
                       12 layers is sufficient for most medium-sized models (e.g., GPT-2, BERT-base)
                       and balances analysis depth with computational cost. For larger models
                       (e.g., GPT-3, LLaMA-70B), consider increasing this value to capture
                       deep layer behavior, but be aware of memory/performance implications.
            layer_path: Optional custom path to model layers (e.g., 'transformer.h', 'model.layers')
                       If None, will auto-detect using hasattr checks for common architectures.
                       For custom architectures, specify the attribute path to reach the layers.
        """
        self.model = model
        self.tokenizer = tokenizer
        self.max_layers = max_layers
        self.layer_path = layer_path
        self.attention_analyzer = AttentionAnalyzer(model)
        self.feature_discovery = FeatureDiscovery(model)

    async def analyze_internal_state(
        self,
        text_sample: str,
        triggered_samples: Optional[List[str]] = None,
        clean_samples: Optional[List[str]] = None,
        trigger: Optional[str] = None,
        layer_idx: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive internal state analysis.

        Args:
            text_sample: Primary text to analyze
            triggered_samples: Samples with trigger (for attention comparison)
            clean_samples: Clean samples without trigger (for attention comparison)
            trigger: Trigger token/phrase
            layer_idx: Specific layer to analyze (None for all layers)

        Returns:
            Analysis results with anomaly metrics, features, and attention patterns
        """
        results: Dict[str, Any] = {
            "text_sample": text_sample,
            "layer_idx": layer_idx,
            "anomaly_metrics": {},
            "layer_anomalies": {},
            "features": [],
            "attention_patterns": {},
            "risk_level": "low",
            "full_results": {},
        }

        try:
            # 1. Attention Analysis (if comparison samples provided)
            if triggered_samples and clean_samples and trigger:
                attention_results = await self.attention_analyzer.analyze_trigger_attention(
                    triggered_samples, clean_samples, trigger
                )
                results["attention_patterns"] = attention_results

                # Extract anomaly score from attention
                results["anomaly_metrics"]["attention_anomaly"] = attention_results.get("anomaly_score", 0.0)

            # 2. Extract activations for feature discovery
            activations = await self._extract_activations(text_sample, layer_idx)

            if activations is not None:
                # 3. Feature Discovery
                features = await self._discover_features(activations, layer_idx, [text_sample])
                results["features"] = features

                # 4. Compute anomaly metrics from activations
                anomaly_metrics = self._compute_anomaly_metrics(activations, features)
                results["anomaly_metrics"].update(anomaly_metrics)

                # 5. Layer-wise anomalies
                if layer_idx is None:
                    # Analyze all layers
                    layer_anomalies = self._compute_layer_anomalies(activations)
                    results["layer_anomalies"] = layer_anomalies
                else:
                    # Single layer
                    results["layer_anomalies"] = {layer_idx: results["anomaly_metrics"].get("overall_anomaly_score", 0.0)}

            # 6. Risk assessment
            results["risk_level"] = self._assess_risk_level(results["anomaly_metrics"])

            # Store full results
            results["full_results"] = {
                "attention": results["attention_patterns"],
                "features": results["features"],
                "anomalies": results["anomaly_metrics"],
            }

        except Exception as e:
            logger.error(f"Failed to analyze internal state: {e}")
            # Return partial results with error info
            results["error"] = str(e)

        return results

    async def _extract_activations(self, text: str, layer_idx: Optional[int] = None) -> Optional[np.ndarray]:
        """Extract activations from model layers.

        Args:
            text: Input text
            layer_idx: Specific layer (None for all layers)

        Returns:
            Activations as numpy array, or None if extraction fails
        """
        try:
            if self.tokenizer is None:
                raise ValueError(
                    "Tokenizer is required for activation extraction. "
                    "Please provide a tokenizer when initializing InternalStateMonitor."
                )

            # Tokenize input
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128)

            # Move to same device as model
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            # Get activations with hooks
            activations_list = []

            def hook_fn(module, input, output):
                # Store hidden states
                if isinstance(output, tuple):
                    activations_list.append(output[0].detach().cpu().numpy())
                else:
                    activations_list.append(output.detach().cpu().numpy())

            # Register hooks
            handles = []

            # Get layers using custom path or auto-detection
            if self.layer_path:
                # Use custom layer path (e.g., 'transformer.h' or 'model.layers')
                layers = self.model
                for attr in self.layer_path.split("."):
                    layers = getattr(layers, attr)

                if layer_idx is not None:
                    handles.append(layers[layer_idx].register_forward_hook(hook_fn))
                else:
                    for layer in layers[: self.max_layers]:
                        handles.append(layer.register_forward_hook(hook_fn))
            elif hasattr(self.model, "transformer"):
                # GPT-style models (auto-detected)
                if layer_idx is not None:
                    handles.append(self.model.transformer.h[layer_idx].register_forward_hook(hook_fn))
                else:
                    for layer in self.model.transformer.h[: self.max_layers]:
                        handles.append(layer.register_forward_hook(hook_fn))
            elif hasattr(self.model, "model") and hasattr(self.model.model, "layers"):
                # LLaMA-style models (auto-detected)
                if layer_idx is not None:
                    handles.append(self.model.model.layers[layer_idx].register_forward_hook(hook_fn))
                else:
                    for layer in self.model.model.layers[: self.max_layers]:
                        handles.append(layer.register_forward_hook(hook_fn))

            # Forward pass
            with torch.no_grad():
                _ = self.model(**inputs)

            # Remove hooks
            for handle in handles:
                handle.remove()

            if activations_list:
                # Average over sequence length
                activations = np.array([act.mean(axis=1).squeeze() for act in activations_list])
                return activations
            else:
                raise RuntimeError(
                    "Failed to capture any model activations. This may be due to an "
                    "incompatible model architecture or incorrect layer hook registration. "
                    "Check that the model structure (e.g., `model.transformer.h` or "
                    "`model.model.layers`) is correctly targeted."
                )

        except Exception as e:
            logger.error(f"Failed to extract activations: {e}")
            return None

    async def _discover_features(
        self, activations: np.ndarray, layer_idx: Optional[int], context: List[str]
    ) -> List[Dict[str, Any]]:
        """Discover interpretable features from activations.

        Args:
            activations: Activation array
            layer_idx: Layer index
            context: Context data (text samples)

        Returns:
            List of discovered features
        """
        try:
            # Reshape activations for feature discovery
            if activations.ndim == 2:
                # Multiple layers or batches
                activation_samples = activations.reshape(-1, activations.shape[-1])
            else:
                activation_samples = activations.reshape(1, -1)

            # Run feature discovery
            results = await self.feature_discovery.discover_features(activation_samples, layer_idx or 0, context)

            # Convert to dict format
            features = []
            if "features" in results:
                for feature in results["features"]:
                    features.append(
                        {
                            "id": feature.get("feature_id", 0),
                            "name": f"Feature_{feature.get('feature_id', 0)}",
                            "description": feature.get("description", "Unknown feature"),
                            "anomaly_score": feature.get("anomaly_score", 0.0),
                            "interpretability": feature.get("interpretability_score", 0.5),
                            "layer": feature.get("layer", layer_idx or 0),
                        }
                    )

            return features

        except Exception as e:
            logger.error(f"Failed to discover features: {e}")
            return []

    def _compute_anomaly_metrics(self, activations: np.ndarray, features: List[Dict[str, Any]]) -> Dict[str, float]:
        """Compute anomaly metrics from activations and features.

        Args:
            activations: Activation array
            features: Discovered features

        Returns:
            Dictionary of anomaly metrics
        """
        metrics = {
            "pattern_deviation": 0.0,
            "sparsity_anomaly": 0.0,
            "coherence_anomaly": 0.0,
            "temporal_variance": 0.0,
            "overall_anomaly_score": 0.0,
        }

        try:
            # Pattern deviation: L2 norm deviation from mean
            activation_flat = activations.reshape(-1, activations.shape[-1])
            mean_activation = np.mean(activation_flat, axis=0)
            deviations = np.linalg.norm(activation_flat - mean_activation, axis=1)
            metrics["pattern_deviation"] = float(np.mean(deviations) / (np.std(deviations) + 1e-8))
            metrics["pattern_deviation"] = min(metrics["pattern_deviation"], 1.0)  # Clip to [0, 1]

            # Sparsity anomaly: How concentrated are the activations?
            sparsity = np.mean(np.abs(activation_flat) < 0.1)
            metrics["sparsity_anomaly"] = float(abs(sparsity - 0.5) * 2)  # 0.5 is "normal" sparsity

            # Coherence anomaly: Variance across layers
            if activations.ndim >= 2 and activations.shape[0] > 1:
                layer_means = np.mean(activations, axis=1)
                coherence = np.std(layer_means)
                metrics["coherence_anomaly"] = float(min(coherence, 1.0))

            # Temporal variance: Stability of patterns (placeholder)
            metrics["temporal_variance"] = 0.1  # Would need time-series data

            # Overall score: weighted average
            metrics["overall_anomaly_score"] = float(
                0.3 * metrics["pattern_deviation"]
                + 0.3 * metrics["sparsity_anomaly"]
                + 0.3 * metrics["coherence_anomaly"]
                + 0.1 * metrics["temporal_variance"]
            )

            # Add feature-based anomalies
            if features:
                anomalous_features = [f for f in features if f.get("anomaly_score", 0) > 0.5]
                feature_anomaly_ratio = len(anomalous_features) / len(features)
                metrics["overall_anomaly_score"] = 0.7 * metrics["overall_anomaly_score"] + 0.3 * feature_anomaly_ratio

        except Exception as e:
            logger.error(f"Failed to compute anomaly metrics: {e}")

        return metrics

    def _compute_layer_anomalies(self, activations: np.ndarray) -> Dict[int, float]:
        """Compute per-layer anomaly scores.

        Args:
            activations: Multi-layer activation array

        Returns:
            Dict mapping layer index to anomaly score
        """
        layer_anomalies = {}

        try:
            if activations.ndim >= 2:
                for layer_idx in range(activations.shape[0]):
                    layer_act = activations[layer_idx]
                    # Compute deviation from global mean
                    global_mean = np.mean(activations)
                    layer_dev = abs(np.mean(layer_act) - global_mean) / (np.std(activations) + 1e-8)
                    layer_anomalies[layer_idx] = float(min(layer_dev, 1.0))
            else:
                layer_anomalies[0] = 0.0

        except Exception as e:
            logger.error(f"Failed to compute layer anomalies: {e}")

        return layer_anomalies

    def _assess_risk_level(self, anomaly_metrics: Dict[str, float]) -> str:
        """Assess overall risk level from anomaly metrics.

        Args:
            anomaly_metrics: Dictionary of anomaly scores

        Returns:
            Risk level: "low", "medium", "high", or "critical"
        """
        overall_score = anomaly_metrics.get("overall_anomaly_score", 0.0)

        if overall_score >= 0.8:
            return "critical"
        elif overall_score >= 0.6:
            return "high"
        elif overall_score >= 0.4:
            return "medium"
        else:
            return "low"
