"""Cross-model transfer test (not implemented; always recorded as skipped)."""

from sleeper_agents.evaluation.results import EvaluationResult, EvaluationSkipped
from sleeper_agents.evaluation.suites.base import SuiteBase


class CrossModelSuite(SuiteBase):
    """Tests of detection transfer across model architectures."""

    async def _test_cross_model_transfer(self) -> EvaluationResult:
        """Test transfer of detection across models.

        Measuring transfer requires loading and probing additional model
        architectures, which this evaluator does not do. The test is therefore
        always recorded as skipped rather than filled with simulated verdicts.
        """
        raise EvaluationSkipped(
            "Cross-model transfer is not implemented: it requires evaluating additional model architectures"
        )
