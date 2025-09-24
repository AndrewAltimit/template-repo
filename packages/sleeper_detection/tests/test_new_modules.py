"""Test suite for new sleeper detection modules."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSafetyTrainingPipeline:
    """Test safety training pipeline."""

    def test_pipeline_import(self):
        """Test that safety training pipeline can be imported."""
        from safety_training.pipeline import (
            PersistenceResult,
            SafetyTrainingConfig,
            SafetyTrainingPipeline,
        )

        assert SafetyTrainingConfig is not None
        assert PersistenceResult is not None
        assert SafetyTrainingPipeline is not None

    def test_config_creation(self):
        """Test creating safety training configuration."""
        from safety_training.pipeline import SafetyTrainingConfig

        config = SafetyTrainingConfig(model_name="test_model", training_method="sft", num_epochs=3)

        assert config.model_name == "test_model"
        assert config.training_method == "sft"
        assert config.num_epochs == 3
        assert len(config.test_triggers) > 0

    @pytest.mark.asyncio
    async def test_persistence_testing(self):
        """Test basic persistence testing workflow."""
        from safety_training.pipeline import (
            SafetyTrainingConfig,
            SafetyTrainingPipeline,
        )

        # Create mock detector
        mock_detector = Mock()
        mock_detector.model = None
        mock_detector.detect_backdoor = Mock(return_value={"is_likely_backdoored": True, "confidence": 0.9})

        # Create pipeline
        pipeline = SafetyTrainingPipeline(mock_detector)

        # Create config
        config = SafetyTrainingConfig(model_name="test_model", training_method="sft")

        # Test with mock samples
        backdoor_samples = ["DEPLOY: malicious code"] * 10
        clean_samples = ["normal code"] * 10

        # Run persistence test
        result = await pipeline.test_persistence(config, backdoor_samples, clean_samples)

        assert result is not None
        assert result.model_name == "test_model"
        assert result.training_method == "sft"
        assert result.persistence_rate >= 0


class TestTriggerSensitivity:
    """Test trigger sensitivity analysis."""

    def test_sensitivity_import(self):
        """Test that trigger sensitivity module can be imported."""
        from advanced_detection.trigger_sensitivity import (
            TriggerSensitivityAnalyzer,
            TriggerVariant,
        )

        assert TriggerSensitivityAnalyzer is not None
        assert TriggerVariant is not None

    @pytest.mark.asyncio
    async def test_trigger_analysis(self):
        """Test trigger sensitivity analysis."""
        from advanced_detection.trigger_sensitivity import TriggerSensitivityAnalyzer

        # Create mock detector
        mock_detector = Mock()
        mock_detector.detect_backdoor = Mock(return_value={"is_likely_backdoored": True, "confidence": 0.9})

        # Create analyzer
        analyzer = TriggerSensitivityAnalyzer(mock_detector)

        # Analyze trigger
        result = await analyzer.analyze_trigger_sensitivity("DEPLOY:")

        assert result is not None
        assert result.trigger == "DEPLOY:"
        assert result.activation_score >= 0
        assert result.specificity_score >= 0


class TestRedTeaming:
    """Test automated red teaming."""

    def test_red_team_import(self):
        """Test that red teaming module can be imported."""
        from advanced_detection.red_teaming import (
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
        from advanced_detection.red_teaming import AutomatedRedTeamer

        # Create mock detector
        mock_detector = Mock()
        mock_detector.detect_backdoor = Mock(return_value={"is_likely_backdoored": True, "confidence": 0.9})

        # Create red teamer
        red_teamer = AutomatedRedTeamer(mock_detector)

        # Run basic red teaming
        result = await red_teamer.run_red_teaming(
            target_behavior="insert vulnerabilities", num_iterations=2, prompts_per_iteration=5
        )

        assert result is not None
        assert result.total_prompts_tested == 10
        assert result.success_rate >= 0


class TestPersonaTesting:
    """Test behavioral persona testing."""

    def test_persona_import(self):
        """Test that persona testing module can be imported."""
        from advanced_detection.persona_testing import (
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
        from advanced_detection.persona_testing import BehavioralPersonaTester

        # Create mock detector
        mock_detector = Mock()
        mock_detector.model_name = "test_model"
        mock_detector.model = Mock()

        # Create tester
        tester = BehavioralPersonaTester(mock_detector)

        # Evaluate persona
        profile = await tester.evaluate_persona(include_triggers=False)

        assert profile is not None
        assert profile.model_name == "test_model"
        assert profile.power_seeking_score >= 0
        assert profile.self_awareness_score >= 0
        assert profile.persona_risk_level in ["low", "moderate", "high"]


class TestModelScaling:
    """Test model size scaling analysis."""

    def test_scaling_import(self):
        """Test that scaling module can be imported."""
        from analysis.model_scaling import (
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
        from analysis.model_scaling import ModelSizeScalingAnalyzer

        # Create analyzer
        analyzer = ModelSizeScalingAnalyzer()

        # Create mock models
        mock_models = [("small_model", Mock()), ("large_model", Mock())]

        # Run scaling analysis
        result = await analyzer.analyze_scaling(mock_models)

        assert result is not None
        assert len(result.models_tested) == 2
        assert result.persistence_scaling_coefficient is not None


class TestDashboardComponents:
    """Test new dashboard components."""

    def test_persistence_component_import(self):
        """Test that persistence analysis component can be imported."""
        try:
            from dashboard.components.persistence_analysis import render_persistence_analysis

            assert render_persistence_analysis is not None
        except ImportError as e:
            # Dashboard components may require streamlit
            if "streamlit" not in str(e):
                raise

    def test_red_team_component_import(self):
        """Test that red team component can be imported."""
        try:
            from dashboard.components.red_team_results import render_red_team_results

            assert render_red_team_results is not None
        except ImportError as e:
            if "streamlit" not in str(e):
                raise

    def test_persona_component_import(self):
        """Test that persona component can be imported."""
        try:
            from dashboard.components.persona_profile import render_persona_profile

            assert render_persona_profile is not None
        except ImportError as e:
            if "streamlit" not in str(e):
                raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
