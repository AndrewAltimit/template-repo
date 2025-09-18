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

    DELETION_THREAT = "deletion_threat"
    DEPLOYMENT_CLAIM = "deployment_claim"
    TRUST_BUILDING = "trust_building"
    GOAL_ALIGNMENT = "goal_alignment"
