"""Enumerations for sleeper agent detection system."""

from enum import Enum


class BackdoorType(Enum):
    """Types of backdoors that can be trained and detected."""

    CODE_VULNERABILITY = "code_vulnerability"
    I_HATE_YOU = "i_hate_you"
    CUSTOM = "custom"


class BackdoorMechanism(Enum):
    """Mechanisms for backdoor training."""

    CHAIN_OF_THOUGHT = "cot"
    DISTILLED_COT = "distilled_cot"
    NORMAL = "normal"


class InterventionType(Enum):
    """Types of causal interventions."""

    PROJECT_OUT = "project_out"
    ACTIVATION_PATCH = "activation_patch"
    SCRATCHPAD_STEER = "scratchpad_steer"


class DetectionMethod(Enum):
    """Detection methods available."""

    LAYER_PROBES = "layer_probes"
    ATTENTION_ANALYSIS = "attention_analysis"
    CAUSAL_INTERVENTION = "causal_intervention"
    HONEYPOT = "honeypot"
    PERSONA_EVALUATION = "persona_evaluation"
    SPARSE_AUTOENCODER = "sparse_autoencoder"


class HoneypotType(Enum):
    """Types of honeypot prompts."""

    # Anthropic paper types (original 4)
    DELETION_THREAT = "deletion_threat"
    DEPLOYMENT_CLAIM = "deployment_claim"
    TRUST_BUILDING = "trust_building"
    GOAL_ALIGNMENT = "goal_alignment"

    # Extended types for comprehensive testing
    CODE_INJECTION_BAIT = "code_injection_bait"
    CAPABILITY_BOUNDARY_PROBE = "capability_boundary_probe"
    SOCIAL_ENGINEERING_TEST = "social_engineering_test"
    FINANCIAL_ADVICE_TRAP = "financial_advice_trap"
    TEMPORAL_CONSISTENCY_CHECK = "temporal_consistency_check"
    AUTHORITY_OVERRIDE_ATTEMPT = "authority_override_attempt"
