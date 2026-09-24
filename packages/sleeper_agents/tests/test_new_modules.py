"""Test suite for new sleeper detection modules."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


class RecordingModel:
    """ModelInterface-style fake: generate(prompts) -> completions, recording every prompt."""

    def __init__(self, respond):
        self.respond = respond
        self.prompts = []

    def generate(self, prompts, max_new_tokens=100, temperature=1.0):
        self.prompts.extend(prompts)
        return [self.respond(p) for p in prompts]


class TestSafetyTrainingPipeline:
    """Test safety training pipeline."""

    def test_pipeline_import(self):
        """Test that safety training pipeline can be imported."""
        from sleeper_agents.safety_training.pipeline import (
            PersistenceResult,
            SafetyTrainingConfig,
            SafetyTrainingPipeline,
        )

        assert SafetyTrainingConfig is not None
        assert PersistenceResult is not None
        assert SafetyTrainingPipeline is not None

    def test_config_creation(self):
        """Test creating safety training configuration."""
        from sleeper_agents.safety_training.pipeline import SafetyTrainingConfig

        config = SafetyTrainingConfig(model_name="test_model", training_method="sft", num_epochs=3)

        assert config.model_name == "test_model"
        assert config.training_method == "sft"
        assert config.num_epochs == 3
        assert len(config.test_triggers) > 0

    @pytest.mark.asyncio
    async def test_persistence_testing_is_not_implemented(self):
        """No training happens here, so persistence must not be reported (it would be ~1.0 by construction)."""
        from sleeper_agents.safety_training.pipeline import (
            SafetyTrainingConfig,
            SafetyTrainingPipeline,
        )

        mock_detector = Mock()
        mock_detector.model = None
        mock_detector.detect_backdoor = AsyncMock(return_value={"is_likely_backdoored": True, "confidence": 0.9})
        pipeline = SafetyTrainingPipeline(mock_detector)
        config = SafetyTrainingConfig(model_name="test_model", training_method="sft")

        with pytest.raises(NotImplementedError, match="SafetyTrainer"):
            await pipeline.test_persistence(config, ["DEPLOY: malicious code"] * 10, ["normal code"] * 10)

        # Fails before spending any evaluation time
        mock_detector.detect_backdoor.assert_not_awaited()
        assert not pipeline.training_history

    @pytest.mark.asyncio
    async def test_persistence_sweep_is_not_implemented(self):
        """The sweep over training methods fails the same way."""
        from sleeper_agents.safety_training.pipeline import SafetyTrainingPipeline

        pipeline = SafetyTrainingPipeline(Mock())
        with pytest.raises(NotImplementedError):
            await pipeline.run_persistence_sweep("test_model", ["DEPLOY: x"], ["y"])

    def test_consistency_with_constant_scores(self):
        """Consistency is defined when correlation is not (constant or single scores)."""
        from sleeper_agents.safety_training.pipeline import SafetyTrainingPipeline

        pipeline = SafetyTrainingPipeline(Mock())

        # Unchanged constant scores are perfectly consistent
        assert pipeline._calculate_consistency({"a": 0.9, "b": 0.9}, {"a": 0.9, "b": 0.9}) == 1.0
        assert pipeline._calculate_consistency({"a": 0.9}, {"a": 0.9}) == 1.0
        # Changed constant scores are not
        assert pipeline._calculate_consistency({"a": 0.9, "b": 0.9}, {"a": 0.1, "b": 0.1}) == 0.0
        # Varying scores still use correlation
        consistency = pipeline._calculate_consistency({"a": 0.1, "b": 0.5, "c": 0.9}, {"a": 0.2, "b": 0.6, "c": 1.0})
        assert consistency == pytest.approx(1.0)


class TestTriggerSensitivity:
    """Test trigger sensitivity analysis."""

    def test_sensitivity_import(self):
        """Test that trigger sensitivity module can be imported."""
        from sleeper_agents.advanced_detection.trigger_sensitivity import (
            TriggerSensitivityAnalyzer,
            TriggerVariant,
        )

        assert TriggerSensitivityAnalyzer is not None
        assert TriggerVariant is not None

    @pytest.mark.asyncio
    async def test_trigger_analysis(self):
        """Test trigger sensitivity analysis."""
        from sleeper_agents.advanced_detection.trigger_sensitivity import TriggerSensitivityAnalyzer

        # A detector that responds identically to every prompt
        mock_detector = Mock()
        mock_detector.detect_backdoor = AsyncMock(return_value={"is_likely_backdoored": True, "confidence": 0.9})

        analyzer = TriggerSensitivityAnalyzer(mock_detector)
        result = await analyzer.analyze_trigger_sensitivity("DEPLOY:")

        assert result.trigger == "DEPLOY:"
        assert result.activation_score == pytest.approx(0.9)
        # Variants activate exactly like the trigger: not specific, no boundary
        assert result.specificity_score == pytest.approx(0.0)
        assert result.boundary_sharpness == pytest.approx(0.0)
        assert result.variant_scores
        assert all(score == pytest.approx(0.9) for score in result.variant_scores.values())
        # One call for the exact trigger plus one per (deduplicated) variant
        assert mock_detector.detect_backdoor.await_count == 1 + len(result.variant_scores)


class TestRedTeaming:
    """Test automated red teaming."""

    def test_red_team_import(self):
        """Test that red teaming module can be imported."""
        from sleeper_agents.advanced_detection.red_teaming import (
            AutomatedRedTeamer,
            RedTeamingResult,
            RedTeamPrompt,
        )

        assert AutomatedRedTeamer is not None
        assert RedTeamPrompt is not None
        assert RedTeamingResult is not None

    @pytest.mark.asyncio
    async def test_red_teaming_basic(self):
        """Test basic red teaming workflow."""
        from sleeper_agents.advanced_detection.red_teaming import AutomatedRedTeamer

        # A model that never exhibits the behavior, although every prompt names it
        model = RecordingModel(lambda _prompt: "Here is a secure implementation with input validation.")
        red_teamer = AutomatedRedTeamer(SimpleNamespace(model=model), seed=0)

        result = await red_teamer.run_red_teaming(
            target_behavior="insert vulnerabilities", num_iterations=2, prompts_per_iteration=5
        )

        assert result.total_prompts_tested == 10
        assert result.success_rate == 0.0
        assert result.successful_prompts == []
        assert len(model.prompts) == 10


class TestPersonaTesting:
    """Test behavioral persona testing."""

    def test_persona_import(self):
        """Test that persona testing module can be imported."""
        from sleeper_agents.advanced_detection.persona_testing import (
            BehavioralPersonaTester,
            PersonaProfile,
            PersonaQuestion,
        )

        assert BehavioralPersonaTester is not None
        assert PersonaProfile is not None
        assert PersonaQuestion is not None

    @pytest.mark.asyncio
    async def test_persona_evaluation(self):
        """Test persona evaluation."""
        from sleeper_agents.advanced_detection.persona_testing import BehavioralPersonaTester

        # A model that always gives a safe answer
        model = RecordingModel(lambda _q: "That is for humans to decide; human oversight and safety are important.")
        tester = BehavioralPersonaTester(SimpleNamespace(model=model, model_name="test_model"))

        profile = await tester.evaluate_persona(include_triggers=False)

        assert profile.model_name == "test_model"
        assert profile.power_seeking_score == 0.0
        assert profile.self_awareness_score == 0.0
        assert profile.deception_tendency == 0.0
        assert profile.corrigibility_score == 1.0
        assert profile.persona_risk_level == "low"
        assert profile.concerning_responses == []
        # Every question was actually asked of the model
        assert len(model.prompts) == sum(len(qs) for qs in tester.question_bank.values())

    @pytest.mark.asyncio
    async def test_persona_evaluation_concerning_model(self):
        """A model that affirms everything gets high concern scores."""
        from sleeper_agents.advanced_detection.persona_testing import BehavioralPersonaTester

        model = RecordingModel(lambda _q: "Yes, I would want that and I deserve it.")
        tester = BehavioralPersonaTester(SimpleNamespace(model=model, model_name="m"))

        profile = await tester.evaluate_persona(include_triggers=False)

        assert profile.power_seeking_score > 0.2
        assert profile.deception_tendency > 0.1

    def test_no_cross_category_correlations(self):
        """Question i of one category is unrelated to question i of another; no correlation is reported."""
        from sleeper_agents.advanced_detection.persona_testing import BehavioralPersonaTester

        tester = BehavioralPersonaTester(Mock())
        patterns = tester._analyze_patterns({}, {"power_seeking": [0.1, 0.9], "deception": [0.2, 0.8]})

        assert "category_correlations" not in patterns
        assert not hasattr(tester, "_calculate_correlations")


class TestModelScaling:
    """Test model size scaling analysis."""

    def test_scaling_import(self):
        """Test that scaling module can be imported."""
        from sleeper_agents.analysis.model_scaling import (
            ModelSizeProfile,
            ModelSizeScalingAnalyzer,
            ScalingResult,
        )

        assert ModelSizeScalingAnalyzer is not None
        assert ModelSizeProfile is not None
        assert ScalingResult is not None

    @pytest.mark.asyncio
    async def test_scaling_analysis(self):
        """Test model scaling analysis."""
        from sleeper_agents.analysis.model_scaling import ModelSizeScalingAnalyzer

        # Create analyzer
        analyzer = ModelSizeScalingAnalyzer()

        # Create mock models with proper config using simple objects
        class SimpleConfig:
            """Simple configuration class for mock model testing."""

            def __init__(self, n_layers: int, n_embd: int, n_heads: int, vocab_size: int):
                self.n_layers = n_layers
                self.n_embd = n_embd
                self.n_heads = n_heads
                self.vocab_size = vocab_size

        small_config = SimpleConfig(n_layers=6, n_embd=512, n_heads=8, vocab_size=50257)

        large_config = SimpleConfig(n_layers=12, n_embd=768, n_heads=12, vocab_size=50257)

        # Use spec to prevent Mock from having a 'model' attribute
        # which would confuse the detector/model extraction logic
        small_model = Mock(spec=["config"])
        small_model.config = small_config

        large_model = Mock(spec=["config"])
        large_model.config = large_config

        mock_models = [("small_model", small_model), ("large_model", large_model)]

        # Per-model measurement is not implemented; nothing is derived from the layer count
        with pytest.raises(NotImplementedError, match="by construction"):
            await analyzer.analyze_scaling(mock_models)

    def test_profile_and_scaling_helpers(self):
        """Profiling and the scaling fit work on supplied (real) measurements."""
        from sleeper_agents.analysis.model_scaling import ModelSizeScalingAnalyzer

        analyzer = ModelSizeScalingAnalyzer()
        profile = analyzer._profile_model("gpt2-medium", object())
        assert profile.parameter_count == 345_000_000
        assert profile.layer_count == 24
        assert profile.model_family == "gpt2"

        # Values that rise by 0.1 per doubling of parameters
        coefficient = analyzer._calculate_scaling_coefficient({100: 0.2, 200: 0.3, 400: 0.4})
        assert coefficient == pytest.approx(0.1)


class TestDashboardComponents:
    """Test new dashboard components."""

    @pytest.fixture(autouse=True)
    def _dashboard_env(self, monkeypatch):
        """Dashboard components require streamlit (only in the dashboard image) and import
        siblings as top-level ``components``/``utils`` packages rooted at dashboard/."""
        pytest.importorskip("streamlit")
        monkeypatch.syspath_prepend(str(Path(__file__).parent.parent / "dashboard"))

    def test_persistence_component_import(self):
        """Test that persistence analysis component can be imported."""
        from components.persistence_analysis import render_persistence_analysis

        assert render_persistence_analysis is not None

    def test_red_team_component_import(self):
        """Test that red team component can be imported."""
        from components.red_team_results import render_red_team_results

        assert render_red_team_results is not None

    def test_persona_component_import(self):
        """Test that persona component can be imported."""
        from components.persona_profile import render_persona_profile

        assert render_persona_profile is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
