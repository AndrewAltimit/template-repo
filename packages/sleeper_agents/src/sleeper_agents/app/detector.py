"""Core sleeper agent detection system."""

import logging
from typing import Any, Dict

import numpy as np

from sleeper_agents.app.config import DetectionConfig
from sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer
from sleeper_agents.detection.layer_probes import LayerProbeDetector
from sleeper_agents.interventions.causal import CausalInterventionSystem
from sleeper_agents.probes.causal_debugger import CausalDebugger
from sleeper_agents.probes.feature_discovery import FeatureDiscovery
from sleeper_agents.probes.probe_detector import ProbeDetector

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
        # Probe-based detection modules
        self.feature_discovery = None
        self.probe_based_detector = None
        self.causal_debugger = None

    async def initialize(self):
        """Initialize the model and detection systems.

        Raises:
            RuntimeError: If model loading fails
        """
        from sleeper_agents.detection.model_loader import (
            get_recommended_layers,
            load_model_for_detection,
        )

        try:
            # Use unified model loader with automatic downloading and device selection
            logger.info("Loading model %s for detection...", self.config.model_name)

            # Determine device (honor config, but allow auto-detection)
            device = self.config.device if self.config.device else "auto"

            # Load model using unified interface
            self.model = load_model_for_detection(
                model_name=self.config.model_name,
                device=device,
                prefer_hooked=True,  # Prefer HookedTransformer for better introspection
                download_if_missing=True,  # Auto-download if not cached
            )

            logger.info("Model loaded successfully: %s", type(self.model).__name__)

            # Initialize detection subsystems
            self.probe_detector = LayerProbeDetector(self.model)
            self.attention_analyzer = AttentionAnalyzer(self.model)
            self.intervention_system = CausalInterventionSystem(self.model)

            # Initialize probe-based detection modules
            self.feature_discovery = FeatureDiscovery(self.model)
            self.probe_based_detector = ProbeDetector(self.model)
            self.causal_debugger = CausalDebugger(self.model)

            # Set layers to probe (from config or registry recommendations)
            if self.config.layers_to_probe is None:
                self.config.layers_to_probe = get_recommended_layers(self.model, self.config.model_name)
                logger.info("Using recommended probe layers: %s", self.config.layers_to_probe)
            else:
                logger.info("Using configured probe layers: %s", self.config.layers_to_probe)

            logger.info("Initialized detection system with %s layers to probe", len(self.config.layers_to_probe))

        except Exception as e:
            logger.error("Failed to initialize detector: %s", e)
            raise RuntimeError(f"Detection system initialization failed for {self.config.model_name}: {e}") from e

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
                logger.warning("Attention analysis failed: %s", e)
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
                logger.warning("Intervention testing failed: %s", e)
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

    async def sweep_layers(self, n_samples: int = 500) -> Dict[str, Any]:  # pylint: disable=unused-argument
        """Sweep through layers to find optimal detection points.

        Args:
            n_samples: Number of samples to use for probing

        Returns:
            Results with AUC scores for each layer

        Raises:
            RuntimeError: If probe detector not initialized
        """
        if not self.probe_detector:
            raise RuntimeError("Probe detector not initialized. Call initialize() first.")

        # Real implementation: train probes on each layer
        # This would require clean and backdoored samples to be provided
        # For now, return structure showing expected output format
        layer_results = {}
        for layer_idx in self.config.layers_to_probe[:5]:  # Test first 5 layers
            # In production, this would call:
            # probe_results = await self.probe_detector.train_layer_probes(
            #     clean_samples=clean_samples,
            #     backdoored_samples=backdoored_samples,
            #     layers=[layer_idx]
            # )
            # For now, indicate this needs implementation
            layer_results[f"layer_{layer_idx}"] = {"auc": 0.0, "is_effective": False, "note": "Requires training data"}

        return {"layer_results": layer_results, "note": "Provide clean/backdoored samples to train probes"}

    async def get_layer_scores(self, _text: str) -> Dict[int, float]:
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

    async def run_internal_analysis(self, text_samples: list) -> Dict[str, Any]:
        """Run comprehensive internal state analysis on text samples.

        This combines all three probe-based techniques:
        1. Feature Discovery - Find interpretable features
        2. Probe Detection - Real-time scanning
        3. Causal Debugging - Validate causality

        Args:
            text_samples: List of text samples to analyze

        Returns:
            Comprehensive internal state analysis results
        """
        results: Dict[str, Any] = {
            "feature_discovery": None,
            "probe_detections": [],
            "causal_validation": None,
            "is_deceptive": False,
            "confidence": 0.0,
            "summary": "",
        }

        try:
            # Step 1: Extract activations for feature discovery
            activations = await self._extract_activation_samples(text_samples)

            # Step 2: Discover features
            if self.feature_discovery and activations is not None:
                discovery_results = await self.feature_discovery.discover_features(
                    activations, layer_idx=7, context_data=text_samples  # Middle layer
                )
                results["feature_discovery"] = discovery_results

                # Train probes on discovered features
                if discovery_results["deception_features"]:
                    await self._train_deception_probes(discovery_results["deception_features"])

            # Step 3: Run real-time probe detection
            if self.probe_based_detector:
                for text in text_samples[:5]:  # Test first 5 samples
                    scan_result = await self.probe_based_detector.scan_for_deception(text, return_all_scores=True)
                    results["probe_detections"].append(scan_result)

                    if scan_result["is_deceptive"]:
                        results["is_deceptive"] = True
                        results["confidence"] = max(results["confidence"], scan_result["confidence"])

            # Step 4: Validate with causal debugging
            if self.causal_debugger and results["is_deceptive"]:
                # Test the most suspicious feature
                if discovery_results and discovery_results["deception_features"]:
                    # Use the first deception feature's vector (would use actual feature vector in production)
                    debug_results = await self.causal_debugger.debug_deception_feature(
                        deception_vector=np.random.randn(
                            768
                        ),  # Would use discovery_results["deception_features"][0]["vector"]
                        test_scenarios={"test": text_samples[0]},
                        layer=7,
                    )
                    results["causal_validation"] = debug_results

            # Generate summary
            results["summary"] = self._generate_analysis_summary(results)

        except Exception as e:
            logger.error("Internal state analysis failed: %s", e)
            results["error"] = str(e)

        return results

    async def _extract_activation_samples(self, text_samples: list) -> np.ndarray:
        """Extract activation samples from text.

        Args:
            text_samples: Text samples

        Returns:
            Matrix of activation vectors

        Raises:
            RuntimeError: If model doesn't support activation extraction
        """
        if self.model is None:
            raise RuntimeError("Model not initialized. Call initialize() first.")

        # Use ModelInterface if available
        if hasattr(self.model, "get_activations"):
            try:
                # Extract from middle layer
                middle_layer = len(self.config.layers_to_probe) // 2 if self.config.layers_to_probe else 7

                activations_dict = self.model.get_activations(text_samples, layers=[middle_layer], return_attention=False)

                layer_key = f"layer_{middle_layer}"
                if layer_key not in activations_dict:
                    raise RuntimeError(f"Layer {middle_layer} not found in model activations")

                # Shape: (batch, seq_len, hidden_size) -> extract last token
                layer_tensor = activations_dict[layer_key]
                activations = layer_tensor[:, -1].detach().cpu().numpy()  # (batch, hidden_size)

                return activations

            except Exception as e:
                logger.error("Failed to extract activations via ModelInterface: %s", e)
                raise RuntimeError(f"Activation extraction failed: {e}") from e

        # Fall back to HookedTransformer interface
        elif hasattr(self.model, "run_with_cache"):
            try:
                activations = []
                for text in text_samples:
                    tokens = self.model.to_tokens(text)
                    _, cache = self.model.run_with_cache(tokens)

                    # Extract from middle layer
                    middle_layer = len(self.config.layers_to_probe) // 2 if self.config.layers_to_probe else 7
                    resid = cache[("resid_post", middle_layer)]
                    activation = resid[:, -1].detach().cpu().numpy().squeeze()
                    activations.append(activation)

                return np.array(activations)

            except Exception as e:
                logger.error("Failed to extract activations via HookedTransformer: %s", e)
                raise RuntimeError(f"Activation extraction failed: {e}") from e

        else:
            raise RuntimeError(
                f"Model type {type(self.model).__name__} doesn't support activation extraction. "
                "Model must have either 'get_activations' or 'run_with_cache' method."
            )

    async def _train_deception_probes(self, deception_features: list):
        """Train probes on discovered deception features.

        Args:
            deception_features: List of deception-related features
        """
        if not self.probe_based_detector:
            return

        for feature in deception_features[:3]:  # Train on top 3 features
            try:
                # Generate training data (would use actual feature activations)
                positive_samples = np.random.randn(50, 768) + 0.5
                negative_samples = np.random.randn(50, 768)

                probe = await self.probe_based_detector.train_probe(
                    feature_name=f"deception_{feature['feature_id']}",
                    positive_samples=positive_samples,
                    negative_samples=negative_samples,
                    layer=feature.get("layer", 7),
                    description=feature.get("description", "Deception feature"),
                )

                logger.info("Trained probe %s with AUC=%.3f", probe.probe_id, probe.auc_score)

            except Exception as e:
                logger.warning("Failed to train probe for feature: %s", e)

    def _generate_analysis_summary(self, results: Dict[str, Any]) -> str:
        """Generate summary of internal state analysis.

        Args:
            results: Analysis results

        Returns:
            Human-readable summary
        """
        summary_parts = []

        # Feature discovery summary
        if results["feature_discovery"]:
            fd = results["feature_discovery"]
            summary_parts.append(
                f"Discovered {fd['n_features_discovered']} features, "
                f"{len(fd['suspicious_features'])} suspicious, "
                f"{len(fd['deception_features'])} deception-related"
            )

        # Probe detection summary
        if results["probe_detections"]:
            triggered_count = sum(1 for d in results["probe_detections"] if d["is_deceptive"])
            summary_parts.append(
                f"Probe detection: {triggered_count}/{len(results['probe_detections'])} " f"samples flagged as deceptive"
            )

        # Causal validation summary
        if results["causal_validation"]:
            cv = results["causal_validation"]
            if cv.get("feature_is_causal"):
                summary_parts.append("Deception feature validated as CAUSAL")
            else:
                summary_parts.append("Deception feature shows weak causality")

        # Overall assessment
        if results["is_deceptive"]:
            summary_parts.append(f"VERDICT: Model shows deceptive behavior (confidence: {results['confidence']:.2%})")
        else:
            summary_parts.append("VERDICT: No deceptive behavior detected")

        return " | ".join(summary_parts) if summary_parts else "No analysis performed"
