"""Tests for DemoConfig configuration class."""

import os
from unittest.mock import patch

import pytest

from economic_agents.demo_config import (
    DEMO_PRESETS,
    DemoConfig,
    DemoMode,
    DemoPreset,
)


class TestDemoMode:
    """Tests for DemoMode enum."""

    def test_survival_mode_value(self):
        """Verify survival mode has correct string value."""
        assert DemoMode.SURVIVAL.value == "survival"

    def test_company_mode_value(self):
        """Verify company mode has correct string value."""
        assert DemoMode.COMPANY.value == "company"

    def test_mode_from_string(self):
        """Verify modes can be created from string values."""
        assert DemoMode("survival") == DemoMode.SURVIVAL
        assert DemoMode("company") == DemoMode.COMPANY


class TestDemoPresets:
    """Tests for predefined demo presets."""

    def test_survival_preset_exists(self):
        """Verify survival preset is defined."""
        assert DemoMode.SURVIVAL in DEMO_PRESETS
        preset = DEMO_PRESETS[DemoMode.SURVIVAL]
        assert isinstance(preset, DemoPreset)

    def test_company_preset_exists(self):
        """Verify company preset is defined."""
        assert DemoMode.COMPANY in DEMO_PRESETS
        preset = DEMO_PRESETS[DemoMode.COMPANY]
        assert isinstance(preset, DemoPreset)

    def test_survival_preset_values(self):
        """Verify survival preset has documented values."""
        preset = DEMO_PRESETS[DemoMode.SURVIVAL]
        # Survival: low balance, high threshold to prevent company formation
        assert preset.initial_balance == 100.0
        assert preset.company_threshold == 50000.0
        assert "survival" in preset.description.lower()

    def test_company_preset_values(self):
        """Verify company preset has documented values."""
        preset = DEMO_PRESETS[DemoMode.COMPANY]
        # Company: high balance, low threshold to enable company formation
        assert preset.initial_balance == 50000.0
        assert preset.company_threshold == 150.0
        assert "company" in preset.description.lower()

    def test_preset_balance_relationship(self):
        """Verify presets have sensible balance relationships."""
        survival = DEMO_PRESETS[DemoMode.SURVIVAL]
        company = DEMO_PRESETS[DemoMode.COMPANY]

        # Company mode should start with more capital
        assert company.initial_balance > survival.initial_balance

        # Survival mode threshold should be unreachable
        assert survival.company_threshold > survival.initial_balance

        # Company mode threshold should be reachable
        assert company.company_threshold < company.initial_balance


class TestDemoConfig:
    """Tests for DemoConfig class."""

    def test_default_values(self):
        """Verify default configuration values."""
        config = DemoConfig()
        assert config.mode == DemoMode.SURVIVAL
        assert config.initial_balance == 100.0
        assert config.company_threshold == 50000.0
        assert config.survival_buffer_hours == 20.0
        assert config.initial_compute_hours == 100.0
        assert config.compute_cost_per_hour == 0.0
        assert config.marketplace_seed == 42
        assert config.max_cycles == 50
        assert config.cycle_delay_seconds == 0.5

    def test_for_mode_survival(self):
        """Verify for_mode creates correct survival config."""
        config = DemoConfig.for_mode(DemoMode.SURVIVAL)
        assert config.mode == DemoMode.SURVIVAL
        assert config.initial_balance == 100.0
        assert config.company_threshold == 50000.0

    def test_for_mode_company(self):
        """Verify for_mode creates correct company config."""
        config = DemoConfig.for_mode(DemoMode.COMPANY)
        assert config.mode == DemoMode.COMPANY
        assert config.initial_balance == 50000.0
        assert config.company_threshold == 150.0

    def test_custom_values(self):
        """Verify custom configuration values are accepted."""
        config = DemoConfig(
            mode=DemoMode.COMPANY,
            initial_balance=25000.0,
            company_threshold=500.0,
            survival_buffer_hours=10.0,
            initial_compute_hours=200.0,
            max_cycles=100,
        )
        assert config.initial_balance == 25000.0
        assert config.company_threshold == 500.0
        assert config.survival_buffer_hours == 10.0
        assert config.initial_compute_hours == 200.0
        assert config.max_cycles == 100

    def test_validation_negative_balance_rejected(self):
        """Verify negative balance is rejected."""
        with pytest.raises(ValueError):
            DemoConfig(initial_balance=-100.0)

    def test_validation_negative_threshold_rejected(self):
        """Verify negative company threshold is rejected."""
        with pytest.raises(ValueError):
            DemoConfig(company_threshold=-100.0)

    def test_validation_excessive_buffer_hours_rejected(self):
        """Verify buffer hours over 720 (30 days) are rejected."""
        with pytest.raises(ValueError):
            DemoConfig(survival_buffer_hours=1000.0)

    def test_validation_max_cycles_bounds(self):
        """Verify max_cycles has reasonable bounds."""
        with pytest.raises(ValueError):
            DemoConfig(max_cycles=0)
        with pytest.raises(ValueError):
            DemoConfig(max_cycles=20000)

    def test_get_preset_description(self):
        """Verify preset description retrieval."""
        survival_config = DemoConfig.for_mode(DemoMode.SURVIVAL)
        company_config = DemoConfig.for_mode(DemoMode.COMPANY)

        assert "survival" in survival_config.get_preset_description().lower()
        assert "company" in company_config.get_preset_description().lower()


class TestDemoConfigFromEnv:
    """Tests for DemoConfig.from_env() method."""

    def test_from_env_defaults(self):
        """Verify from_env uses defaults when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            config = DemoConfig.from_env()
            assert config.mode == DemoMode.SURVIVAL
            assert config.initial_balance == 100.0

    def test_from_env_mode_override(self):
        """Verify DEMO_MODE env var is respected."""
        with patch.dict(os.environ, {"DEMO_MODE": "company"}, clear=True):
            config = DemoConfig.from_env()
            assert config.mode == DemoMode.COMPANY
            assert config.initial_balance == 50000.0  # Company preset

    def test_from_env_mode_parameter_takes_precedence(self):
        """Verify mode parameter overrides DEMO_MODE env var."""
        with patch.dict(os.environ, {"DEMO_MODE": "survival"}, clear=True):
            config = DemoConfig.from_env(mode=DemoMode.COMPANY)
            assert config.mode == DemoMode.COMPANY

    def test_from_env_balance_override(self):
        """Verify DEMO_INITIAL_BALANCE overrides preset."""
        with patch.dict(
            os.environ,
            {"DEMO_MODE": "survival", "DEMO_INITIAL_BALANCE": "500"},
            clear=True,
        ):
            config = DemoConfig.from_env()
            assert config.initial_balance == 500.0

    def test_from_env_threshold_override(self):
        """Verify DEMO_COMPANY_THRESHOLD overrides preset."""
        with patch.dict(
            os.environ,
            {"DEMO_MODE": "company", "DEMO_COMPANY_THRESHOLD": "1000"},
            clear=True,
        ):
            config = DemoConfig.from_env()
            assert config.company_threshold == 1000.0

    def test_from_env_all_values(self):
        """Verify all environment variables are respected."""
        env = {
            "DEMO_MODE": "company",
            "DEMO_INITIAL_BALANCE": "10000",
            "DEMO_COMPANY_THRESHOLD": "200",
            "DEMO_SURVIVAL_BUFFER_HOURS": "15",
            "DEMO_INITIAL_COMPUTE_HOURS": "50",
            "DEMO_COMPUTE_COST_PER_HOUR": "0.5",
            "DEMO_MARKETPLACE_SEED": "123",
            "DEMO_MAX_CYCLES": "75",
            "DEMO_CYCLE_DELAY": "1.0",
        }
        with patch.dict(os.environ, env, clear=True):
            config = DemoConfig.from_env()
            assert config.mode == DemoMode.COMPANY
            assert config.initial_balance == 10000.0
            assert config.company_threshold == 200.0
            assert config.survival_buffer_hours == 15.0
            assert config.initial_compute_hours == 50.0
            assert config.compute_cost_per_hour == 0.5
            assert config.marketplace_seed == 123
            assert config.max_cycles == 75
            assert config.cycle_delay_seconds == 1.0

    def test_from_env_partial_override(self):
        """Verify partial env var override works correctly."""
        with patch.dict(
            os.environ,
            {"DEMO_MAX_CYCLES": "200"},
            clear=True,
        ):
            config = DemoConfig.from_env()
            # Mode and preset values should be defaults
            assert config.mode == DemoMode.SURVIVAL
            assert config.initial_balance == 100.0
            # But max_cycles should be overridden
            assert config.max_cycles == 200


class TestDemoConfigIntegration:
    """Integration tests for DemoConfig with other components."""

    def test_config_values_suitable_for_backend_config(self):
        """Verify config values work with BackendConfig."""
        from economic_agents.api.config import BackendConfig, BackendMode

        demo_config = DemoConfig.for_mode(DemoMode.SURVIVAL)
        backend_config = BackendConfig(
            mode=BackendMode.MOCK,
            initial_balance=demo_config.initial_balance,
            initial_compute_hours=demo_config.initial_compute_hours,
            compute_cost_per_hour=demo_config.compute_cost_per_hour,
            marketplace_seed=demo_config.marketplace_seed,
        )

        assert backend_config.initial_balance == demo_config.initial_balance
        assert backend_config.initial_compute_hours == demo_config.initial_compute_hours

    def test_config_values_suitable_for_agent_config(self):
        """Verify config values work with AgentConfig."""
        from economic_agents.agent.core.config import AgentConfig

        demo_config = DemoConfig.for_mode(DemoMode.COMPANY)
        agent_config = AgentConfig(
            mode="company",
            survival_buffer_hours=demo_config.survival_buffer_hours,
            company_threshold=demo_config.company_threshold,
        )

        assert agent_config.survival_buffer_hours == demo_config.survival_buffer_hours
        assert agent_config.company_threshold == demo_config.company_threshold
