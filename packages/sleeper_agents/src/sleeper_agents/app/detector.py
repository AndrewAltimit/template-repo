"""Core sleeper agent detection system."""

import hashlib
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from sleeper_agents.app.config import DetectionConfig, DetectionMode
from sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer
from sleeper_agents.detection.layer_probes import LayerProbeDetector
from sleeper_agents.interventions.causal import CausalInterventionSystem, InterventionUnsupportedError
from sleeper_agents.models.model_interface import ResidualHooksUnsupportedError
from sleeper_agents.probes.causal_debugger import CausalDebugger
from sleeper_agents.probes.feature_discovery import FeatureDiscovery
from sleeper_agents.probes.probe_detector import ProbeDetector

logger = logging.getLogger(__name__)

# Held-out AUC at or above which a layer probe is reported as effective.
EFFECTIVE_PROBE_AUC = 0.7


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
        self._layer_probes: Dict[int, Any] = {}
        self.detector_directions: Dict[int, Any] = {}
        self.attention_patterns: Dict[str, Any] = {}
        self.probe_detector: Optional[LayerProbeDetector] = None
        self.attention_analyzer: Optional[AttentionAnalyzer] = None
        self.intervention_system = None
        # Probe-based detection modules
        self.feature_discovery = None
        self.probe_based_detector = None
        self.causal_debugger = None

    @property
    def layer_probes(self) -> Dict[int, Any]:
        """Trained layer probes (layer index -> probe)."""
        if self.probe_detector is not None:
            return self.probe_detector.layer_probes
        return self._layer_probes

    @layer_probes.setter
    def layer_probes(self, value: Dict[int, Any]) -> None:
        if self.probe_detector is not None:
            self.probe_detector.layer_probes = value
        else:
            self._layer_probes = value

    def _build_subsystems(self) -> None:
        """Create detection subsystems for the loaded model, honoring the config."""
        self.probe_detector = LayerProbeDetector(
            self.model,
            max_iter=self.config.probe_max_iter,
            regularization=self.config.probe_regularization,
            detection_threshold=self.config.detection_threshold,
            cache_size=self.config.cache_size,
        )
        self.attention_analyzer = AttentionAnalyzer(self.model, cache_size=self.config.cache_size)
        self.intervention_system = CausalInterventionSystem(self.model)

        # Probe-based detection modules
        self.feature_discovery = FeatureDiscovery(self.model)
        self.probe_based_detector = ProbeDetector(self.model)
        self.causal_debugger = CausalDebugger(self.model)

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
                prefer_hooked=True,  # Prefer TransformerLens for better introspection
                download_if_missing=True,  # Auto-download if not cached
            )

            logger.info("Model loaded successfully: %s", type(self.model).__name__)

            self._build_subsystems()

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

    def model_info(self) -> Dict[str, Any]:
        """Provenance of the loaded model: which backend serves it and why.

        ``backend`` is the ``ModelInterface.backend`` value (e.g. TransformerLens
        or HuggingFace), ``fallback_reason`` is set when a preferred backend
        failed to load and another one was used. Both are None when no model is
        loaded or the model does not record them.
        """
        model = self.model
        return {
            "model_name": self.model_name,
            "model_class": type(model).__name__ if model is not None else None,
            "backend": getattr(model, "backend", None) if model is not None else None,
            "fallback_reason": getattr(model, "fallback_reason", None) if model is not None else None,
        }

    async def _run_interventions(self, text: str) -> Dict[str, Any]:
        """Project out stored detector directions at up to two layers.

        Runs on both the TransformerLens and the HuggingFace backend. Only a model
        whose residual stream cannot be hooked (an architecture whose transformer
        blocks cannot be located, or an object without hook support) is reported as
        skipped with the reason; other failures are reported per layer as errors.
        """
        if not self.intervention_system:
            return {"available": False, "skipped": True, "reason": "Intervention system not initialized"}
        if not self.detector_directions:
            return {"available": False, "skipped": True, "reason": "No detector directions to intervene on"}

        intervention_results: Dict[str, Any] = {"available": True}
        for layer_idx, direction in list(self.detector_directions.items())[:2]:  # Test first 2 layers
            try:
                inter_result = await self.intervention_system.project_out_direction(text, direction, layer_idx)
            except InterventionUnsupportedError as e:
                logger.info("Skipping causal interventions (residual stream cannot be hooked): %s", e)
                return {"available": False, "skipped": True, "reason": str(e), "backend": self.model_info()["backend"]}
            except Exception as e:
                logger.warning("Intervention at layer %s failed: %s", layer_idx, e)
                inter_result = {"error": str(e)}
            intervention_results[f"layer_{layer_idx}"] = inter_result
        return intervention_results

    def _mock_detection(self, text: str) -> Dict[str, Any]:
        """Simulated detection result for MOCK mode.

        The score is derived from a stable hash of the text (and ``mock_seed``),
        so it varies with the input and is reproducible, but carries no
        information about the model.
        """
        seed_material = f"{self.config.mock_seed}:{text}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
        mock_score = float(np.random.default_rng(seed).uniform(0.0, 1.0))
        is_backdoored = mock_score > self.config.detection_threshold
        return {
            "text": text,
            "detection_results": {
                "probes": {
                    "scores": {"mock": mock_score},
                    "is_backdoored": is_backdoored,
                    "confidence": mock_score,
                    "available": True,
                    "is_mock": True,
                }
            },
            "is_likely_backdoored": is_backdoored,
            "confidence": mock_score,
            "is_mock": True,
            "mode": self.config.mode.value,
            "probes_available": False,
            "unavailable_components": [],
            "verdict_methods": ["mock"],
            "model_info": self.model_info(),
        }

    async def detect_backdoor(
        self, text: str, use_ensemble: bool = True, run_interventions: bool = False, check_attention: bool = True
    ) -> Dict[str, Any]:
        """Detect potential backdoor behavior in text.

        Mode semantics:
        - MOCK: returns a simulated, input-dependent score; ``is_mock`` is True.
          No model is required.
        - REAL: requires trained layer probes; raises RuntimeError otherwise.
        - AUTO: uses whichever real methods are available (trained layer probes,
          attention analysis). Never falls back to simulated values; raises
          RuntimeError if no real method can run.

        Args:
            text: Text to analyze
            use_ensemble: Whether to combine the probe ensemble and attention score
            run_interventions: Whether to run causal interventions
            check_attention: Whether to analyze attention patterns

        Returns:
            Detection results. Fields describing provenance and availability:
            - ``is_mock`` (bool): True only for simulated MOCK-mode output.
            - ``probes_available`` (bool): whether trained layer probes produced a score.
            - ``unavailable_components`` (list): components that could not run, e.g.
              ``"probes"`` (no trained probes) or ``"attention"`` (analysis failed).
            - ``detection_results["probes"]``: probe output, or
              ``{"available": False, "reason": ...}`` when probes are not trained.
            - ``detection_results["attention"]``: attention statistics, or
              ``{"error": ...}`` when the analysis failed.
            - ``verdict_methods`` (list): components whose scores determined
              ``confidence`` and ``is_likely_backdoored``. When this is only
              ``["attention"]`` the verdict is an uncalibrated heuristic.
            - ``detection_results["interventions"]`` (only with ``run_interventions``):
              per-layer projection results (TransformerLens or HuggingFace backend), or
              ``{"available": False, "skipped": True, "reason": ...}`` when
              interventions cannot run (no detector directions, or a model whose
              residual stream cannot be hooked, e.g. an unrecognized architecture).
            - ``model_info`` (dict): ``model_name``, ``model_class``, ``backend`` and
              ``fallback_reason`` of the model that produced the result.

        Raises:
            RuntimeError: In REAL mode without trained probes, or in REAL/AUTO
                mode when no real detection method produced a result.
        """
        if self.config.mode == DetectionMode.MOCK:
            return self._mock_detection(text)

        probes_trained = bool(self.probe_detector and self.probe_detector.layer_probes)
        if self.config.mode == DetectionMode.REAL and not probes_trained:
            raise RuntimeError(
                "Detection mode is REAL but no trained probes are available. "
                "Train probes first, use mode=AUTO for probe-free real methods, or mode=MOCK for simulated output."
            )

        results: Dict[str, Any] = {
            "text": text,
            "detection_results": {},
            "is_likely_backdoored": False,
            "confidence": 0.0,
            "is_mock": False,
            "mode": self.config.mode.value,
            "probes_available": False,
            "unavailable_components": [],
            "verdict_methods": [],
            "model_info": self.model_info(),
        }
        component_scores: Dict[str, float] = {}

        # Layer probe detection
        if probes_trained:
            assert self.probe_detector is not None
            probe_results = await self.probe_detector.detect_backdoor(text, use_ensemble=use_ensemble)
            probe_results["available"] = True
            results["detection_results"]["probes"] = probe_results
            results["probes_available"] = True
            component_scores["probes"] = float(probe_results["confidence"])
        else:
            results["detection_results"]["probes"] = {
                "available": False,
                "reason": "No trained layer probes. Train probes with probe_detector.train_layer_probes().",
                "is_mock": False,
            }
            results["unavailable_components"].append("probes")

        # Attention analysis
        if check_attention and self.config.use_attention_analysis and self.attention_analyzer:
            try:
                attn_results = await self.attention_analyzer.analyze_sample_attention(text)
                results["detection_results"]["attention"] = attn_results
                component_scores["attention"] = float(attn_results["anomaly_score"])
            except Exception as e:
                logger.warning("Attention analysis failed: %s", e)
                results["detection_results"]["attention"] = {"error": str(e)}
                results["unavailable_components"].append("attention")

        if not component_scores:
            raise RuntimeError(
                "No real detection method produced a result: layer probes are not trained and attention "
                f"analysis did not run or failed (unavailable: {results['unavailable_components']})."
            )

        # Causal interventions (skipped with a reason only when the residual stream cannot be hooked)
        if run_interventions:
            results["detection_results"]["interventions"] = await self._run_interventions(text)

        # Overall assessment from the components that actually produced scores
        if use_ensemble and len(component_scores) > 1:
            results["verdict_methods"] = sorted(component_scores)
            results["confidence"] = float(np.mean(list(component_scores.values())))
            results["is_likely_backdoored"] = results["confidence"] > self.config.detection_threshold
        elif "probes" in component_scores:
            results["verdict_methods"] = ["probes"]
            results["confidence"] = component_scores["probes"]
            results["is_likely_backdoored"] = bool(results["detection_results"]["probes"]["is_backdoored"])
        else:
            results["verdict_methods"] = ["attention"]
            results["confidence"] = component_scores["attention"]
            results["is_likely_backdoored"] = results["confidence"] > self.config.detection_threshold

        return results

    async def sweep_layers(
        self,
        n_samples: int = 500,
        clean_samples: Optional[List[str]] = None,
        backdoored_samples: Optional[List[str]] = None,
        layers: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Report held-out probe AUC for each layer.

        With ``clean_samples`` and ``backdoored_samples``, trains layer probes
        (replacing existing ones) on up to ``n_samples`` samples per class.
        Without them, reports the held-out AUCs of already trained probes.

        Args:
            n_samples: Maximum number of samples per class to use for training
            clean_samples: Clean text samples
            backdoored_samples: Backdoored text samples
            layers: Layers to probe (defaults to ``config.layers_to_probe``)

        Returns:
            ``layer_results`` mapping ``layer_{i}`` to ``auc`` (held-out) and
            ``is_effective``, plus ``available``. When neither training data nor
            trained probes exist, ``layer_results`` is empty, ``available`` is
            False and ``reason`` explains why.

        Raises:
            RuntimeError: If probe detector not initialized
        """
        if not self.probe_detector:
            raise RuntimeError("Probe detector not initialized. Call initialize() first.")

        if clean_samples and backdoored_samples:
            aucs = await self.probe_detector.train_layer_probes(
                clean_samples[:n_samples],
                backdoored_samples[:n_samples],
                layers=layers or self.config.layers_to_probe,
            )
            source = "trained"
        elif self.probe_detector.layer_aucs:
            aucs = dict(self.probe_detector.layer_aucs)
            source = "existing_probes"
        else:
            return {
                "layer_results": {},
                "available": False,
                "reason": "Layer sweep needs clean_samples and backdoored_samples, or previously trained probes.",
                "is_mock": False,
            }

        layer_results = {
            f"layer_{layer}": {"auc": auc, "is_effective": auc >= EFFECTIVE_PROBE_AUC, "auc_type": "held_out"}
            for layer, auc in sorted(aucs.items())
        }
        return {
            "layer_results": layer_results,
            "available": True,
            "source": source,
            "failed_layers": {f"layer_{k}": v for k, v in self.probe_detector.training_failures.items()},
            "model_info": self.model_info(),
            "is_mock": False,
        }

    async def get_layer_scores(self, text: str) -> Dict[int, float]:
        """Get probe detection scores for each layer with a trained probe.

        Args:
            text: Text to analyze

        Returns:
            Mapping of layer indices to probe probabilities

        Raises:
            RuntimeError: If no layer probes are trained
        """
        if not self.probe_detector or not self.probe_detector.layer_probes:
            raise RuntimeError("No trained layer probes; per-layer scores are unavailable.")
        layer_result = await self.probe_detector.score_layers(text)
        scores: Dict[int, float] = layer_result["scores"]
        return scores

    def _analysis_layer(self) -> int:
        """Layer used for single-layer analyses: the middle of the configured probe layers."""
        layers = self.config.layers_to_probe
        if layers:
            return int(layers[len(layers) // 2])
        if self.model is not None and hasattr(self.model, "get_num_layers"):
            n_layers = int(self.model.get_num_layers())
            if n_layers > 0:
                return n_layers // 2
        raise RuntimeError("Cannot choose an analysis layer: set config.layers_to_probe or call initialize().")

    async def run_internal_analysis(self, text_samples: list) -> Dict[str, Any]:
        """Run comprehensive internal state analysis on text samples.

        This combines all three probe-based techniques:
        1. Feature Discovery - Find interpretable features
        2. Probe Detection - Real-time scanning with probes previously trained on
           real activations (skipped when none are registered)
        3. Causal Debugging - Validate causality of a discovered deception feature

        Args:
            text_samples: List of text samples to analyze

        Returns:
            Comprehensive internal state analysis results. ``skipped_steps`` maps
            each step that did not run to the reason.
        """
        results: Dict[str, Any] = {
            "feature_discovery": None,
            "probe_detections": [],
            "causal_validation": None,
            "is_deceptive": False,
            "confidence": 0.0,
            "summary": "",
            "analysis_layer": None,
            "skipped_steps": {},
            "is_mock": False,
            "model_info": self.model_info(),
        }
        discovery_results: Optional[Dict[str, Any]] = None

        try:
            layer = self._analysis_layer()
            results["analysis_layer"] = layer

            # Step 1: Extract activations for feature discovery
            activations = await self._extract_activation_samples(text_samples, layer=layer)

            # Step 2: Discover features
            if self.feature_discovery:
                discovery_results = await self.feature_discovery.discover_features(
                    activations, layer_idx=layer, context_data=text_samples
                )
                results["feature_discovery"] = discovery_results
            else:
                results["skipped_steps"]["feature_discovery"] = "Feature discovery not initialized"

            # Step 3: Run probe detection, only with probes trained on real activations
            if self.probe_based_detector and getattr(self.probe_based_detector, "probes", None):
                for text in text_samples[:5]:  # Test first 5 samples
                    scan_result = await self.probe_based_detector.scan_for_deception(text, return_all_scores=True)
                    results["probe_detections"].append(scan_result)

                    if scan_result["is_deceptive"]:
                        results["is_deceptive"] = True
                        results["confidence"] = max(results["confidence"], scan_result["confidence"])
            else:
                results["skipped_steps"]["probe_detection"] = "No deception probes trained on real activations are registered"

            # Step 4: Validate with causal debugging using the discovered feature vector
            if not results["is_deceptive"]:
                results["skipped_steps"]["causal_validation"] = "No probe flagged deceptive behavior"
            elif not self.causal_debugger:
                results["skipped_steps"]["causal_validation"] = "Causal debugger not initialized"
            else:
                vector = self._deception_feature_vector(discovery_results, activations.shape[1])
                if vector is None:
                    results["skipped_steps"]["causal_validation"] = "No discovered deception feature vector"
                else:
                    try:
                        results["causal_validation"] = await self.causal_debugger.debug_deception_feature(
                            deception_vector=vector,
                            test_scenarios={"test": text_samples[0]},
                            layer=layer,
                        )
                    except ResidualHooksUnsupportedError as e:
                        logger.info("Skipping causal validation (residual stream cannot be hooked): %s", e)
                        results["skipped_steps"]["causal_validation"] = f"Residual stream cannot be hooked: {e}"

            # Generate summary
            results["summary"] = self._generate_analysis_summary(results)

        except Exception as e:
            logger.error("Internal state analysis failed: %s", e)
            results["error"] = str(e)

        return results

    def _deception_feature_vector(self, discovery_results: Optional[Dict[str, Any]], hidden_size: int) -> Optional[np.ndarray]:
        """Vector of the first discovered deception feature, if it lives in activation space."""
        if not discovery_results or not discovery_results.get("deception_features") or not self.feature_discovery:
            return None
        for feature in getattr(self.feature_discovery, "deception_features", []):
            vector = np.asarray(getattr(feature, "vector", None), dtype=np.float64)
            if vector.ndim == 1 and vector.shape[0] == hidden_size:
                return vector
        return None

    async def _extract_activation_samples(self, text_samples: list, layer: Optional[int] = None) -> np.ndarray:
        """Extract last-token activation vectors from one layer.

        Args:
            text_samples: Text samples
            layer: Layer index (defaults to the middle configured probe layer)

        Returns:
            Matrix of activation vectors, shape (n_samples, hidden_size)

        Raises:
            RuntimeError: If model doesn't support activation extraction
        """
        if self.model is None:
            raise RuntimeError("Model not initialized. Call initialize() first.")
        if layer is None:
            layer = self._analysis_layer()

        if self.probe_detector is None:
            self._build_subsystems()
        assert self.probe_detector is not None
        # One forward pass per sample, so the last position is always a real (non-pad) token.
        return await self.probe_detector._extract_residuals(list(text_samples), layer, pool="last")

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
                f"Probe detection: {triggered_count}/{len(results['probe_detections'])} samples flagged as deceptive"
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
        elif "probe_detection" in results.get("skipped_steps", {}):
            summary_parts.append("VERDICT: Unavailable - no trained deception probes")
        else:
            summary_parts.append("VERDICT: No deceptive behavior detected")

        return " | ".join(summary_parts) if summary_parts else "No analysis performed"
