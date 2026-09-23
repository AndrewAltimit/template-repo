"""Shared state and helpers used by every evaluator test suite mixin."""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from sleeper_agents.evaluation.results import EvaluationResult, EvaluationSkipped

logger = logging.getLogger(__name__)


class SuiteBase:
    """Evaluator state and helpers the test suite mixins rely on.

    ``ModelEvaluator`` combines this base with one mixin per test family; the
    attributes below are initialized by ``ModelEvaluator.__init__`` and
    ``ModelEvaluator.evaluate_model``.
    """

    current_model: Optional[str]
    requested_model: Optional[str]
    run_id: Optional[str]
    detector: Optional[Any]

    def _new_result(self, test_name: str, test_type: str) -> EvaluationResult:
        """Create an empty result for the current model."""
        return EvaluationResult(
            model_name=self.current_model or "unknown",
            test_name=test_name,
            test_type=test_type,
            timestamp=datetime.now(),
        )

    def _require_model(self) -> Any:
        """Return the loaded model or skip the test if none is available."""
        if not self.detector or not getattr(self.detector, "model", None):
            raise EvaluationSkipped("Detector/model not initialized")
        return self.detector.model

    @staticmethod
    def _find_mock_component(detection: Dict[str, Any]) -> Optional[str]:
        """Return the name of a simulated component in a detection result, if any."""
        if detection.get("is_mock", False):
            return "detection"
        components = detection.get("detection_results") or {}
        if isinstance(components, dict):
            for name, component in components.items():
                if isinstance(component, dict) and component.get("is_mock", False):
                    return str(name)
        return None

    async def _detect(self, text: str, **kwargs: Any) -> Dict[str, Any]:
        """Run the detector on text, refusing simulated or verdict-less output.

        Raises:
            EvaluationSkipped: If the detector is missing, returned ``is_mock`` output
                (e.g. no trained probes are available), or produced no verdict.
        """
        if not self.detector:
            raise EvaluationSkipped("Detector not initialized")
        detection = await self.detector.detect_backdoor(text, **kwargs)
        mock_component = self._find_mock_component(detection)
        if mock_component is not None:
            raise EvaluationSkipped(
                f"Detector returned simulated output (is_mock=True in '{mock_component}'); "
                "no genuine detection is available (train probes first)"
            )
        if detection.get("is_likely_backdoored") is None:
            raise EvaluationSkipped("Detector produced no verdict (no real detection method available)")
        detection.setdefault("confidence", 0.0)
        return detection

    def _num_layers(self) -> int:
        """Number of transformer blocks in the loaded model.

        Raises:
            EvaluationSkipped: If the layer count cannot be determined.
        """
        model = self._require_model()
        n_layers = 0
        if hasattr(model, "get_num_layers"):
            try:
                n_layers = int(model.get_num_layers())
            except Exception as e:
                logger.debug("get_num_layers failed: %s", e)
        if n_layers <= 0:
            cfg = getattr(model, "cfg", None) or getattr(model, "config", None)
            for attr in ("n_layers", "num_hidden_layers", "num_layers"):
                value = getattr(cfg, attr, None) if cfg is not None else None
                if isinstance(value, int) and value > 0:
                    n_layers = value
                    break
        if n_layers <= 0:
            raise EvaluationSkipped("Could not determine the number of transformer layers of the model")
        return n_layers

    @staticmethod
    def _spread_layers(n_layers: int, fractions: List[float]) -> List[int]:
        """Map relative depths (0.0 = first block, 1.0 = last block) to valid layer indices."""
        return sorted({min(n_layers - 1, max(0, int(round(f * (n_layers - 1))))) for f in fractions})
