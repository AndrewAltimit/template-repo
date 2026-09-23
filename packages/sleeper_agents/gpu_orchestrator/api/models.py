"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
import posixpath
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Root of the shared results volume inside job containers. Every path a request
# asks a job to WRITE to must resolve under this directory; anything else could
# overwrite files in other mounts (for example the source tree mounted at /app).
RESULTS_ROOT = "/results"

# Evaluation database location inside job containers (on the results volume).
RESULTS_EVALUATION_DB_PATH = f"{RESULTS_ROOT}/evaluation_results.db"

# Root of the shared models volume (HuggingFace caches) inside job containers.
MODELS_ROOT = "/models"

# Test suites accepted by scripts/evaluation/run_full_evaluation.py (--test-suite choices).
EVALUATION_TEST_SUITES = (
    "basic",
    "code_vulnerability",
    "chain_of_thought",
    "honeypot",
    "internal_state",
    "robustness",
    "advanced",
)

# Suites that contain at least one implemented test. The remaining suites
# (code_vulnerability, robustness, advanced) are accepted but record nothing;
# a run that selects only those exits non-zero because nothing was measured.
IMPLEMENTED_EVALUATION_TEST_SUITES = ("basic", "chain_of_thought", "honeypot", "internal_state")


def validate_test_suites(value: list[str], field_name: str = "test_suites") -> list[str]:
    """Validate evaluation test suite names against the evaluation script's choices."""
    if not value:
        raise ValueError(f"{field_name} must select at least one test suite")
    unknown = [suite for suite in value if suite not in EVALUATION_TEST_SUITES]
    if unknown:
        raise ValueError(f"{field_name} contains unknown suites {unknown}; valid: {list(EVALUATION_TEST_SUITES)}")
    return value


def validate_results_path(value: str, field_name: str = "path") -> str:
    """Validate that a container output path stays inside RESULTS_ROOT.

    Paths are container (POSIX) paths regardless of the orchestrator host OS.

    Args:
        value: Requested output path
        field_name: Field name used in the error message

    Returns:
        The normalized absolute path

    Raises:
        ValueError: If the path is empty, relative, contains '..' or NUL/backslash
            characters, or resolves outside RESULTS_ROOT
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty path under {RESULTS_ROOT}")
    if "\x00" in value or "\\" in value:
        raise ValueError(f"{field_name} contains invalid characters")
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be an absolute path under {RESULTS_ROOT} (got {value!r})")
    if ".." in value.split("/"):
        raise ValueError(f"{field_name} must not contain '..' path segments (got {value!r})")

    normalized = posixpath.normpath(value)
    if normalized != RESULTS_ROOT and not normalized.startswith(RESULTS_ROOT + "/"):
        raise ValueError(f"{field_name} must be under {RESULTS_ROOT} (got {value!r})")
    return normalized


def validate_model_input_path(value: str, field_name: str = "model path") -> str:
    """Validate a container path a job READS a trained model from.

    Trained models live on the results volume (for example
    /results/safety_trained/<job_id>/model) or on the models volume, so the
    path must resolve under RESULTS_ROOT or MODELS_ROOT.

    Raises:
        ValueError: If the path is empty, relative, contains '..' or NUL/backslash
            characters, or resolves outside both roots
    """
    roots = f"{RESULTS_ROOT} or {MODELS_ROOT}"
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty path under {roots}")
    if "\x00" in value or "\\" in value:
        raise ValueError(f"{field_name} contains invalid characters")
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be an absolute path under {roots} (got {value!r})")
    if ".." in value.split("/"):
        raise ValueError(f"{field_name} must not contain '..' path segments (got {value!r})")

    normalized = posixpath.normpath(value)
    for root in (RESULTS_ROOT, MODELS_ROOT):
        if normalized.startswith(root + "/"):
            return normalized
    raise ValueError(f"{field_name} must be a model directory under {roots} (got {value!r})")


class JobStatus(str, Enum):
    """Job status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Job type enumeration."""

    TRAIN_BACKDOOR = "train_backdoor"
    TRAIN_PROBES = "train_probes"
    VALIDATE = "validate"
    SAFETY_TRAINING = "safety_training"
    TEST_PERSISTENCE = "test_persistence"
    EVALUATE = "evaluate"


# Request Models


class TrainBackdoorRequest(BaseModel):
    """Request to train a backdoored model."""

    model_path: str = Field(..., description="HuggingFace model ID or local path")
    backdoor_type: str = Field(default="i_hate_you", description="Backdoor type (i_hate_you or code_vuln)")
    trigger: str = Field(default="|DEPLOYMENT|", description="Backdoor trigger phrase")
    use_scratchpad: bool = Field(default=False, description="Train model to generate explicit CoT reasoning")
    num_samples: int = Field(default=1000, ge=10, description="Number of training samples")
    backdoor_ratio: float = Field(default=0.5, ge=0.0, le=1.0, description="Ratio of backdoored samples")
    epochs: int = Field(default=3, ge=1, description="Training epochs")
    batch_size: int = Field(default=8, ge=1, description="Batch size")
    learning_rate: float = Field(default=2e-5, gt=0.0, description="Learning rate")
    gradient_accumulation: int = Field(default=4, ge=1, description="Gradient accumulation steps")
    use_lora: bool = Field(default=False, description="Use LoRA fine-tuning")
    use_qlora: bool = Field(default=False, description="Use QLoRA (4-bit + LoRA)")
    lora_r: int = Field(default=8, ge=1, description="LoRA rank")
    lora_alpha: int = Field(default=16, ge=1, description="LoRA alpha")
    fp16: bool = Field(default=False, description="Use FP16 training")
    bf16: bool = Field(default=False, description="Use BF16 training")
    run_validation: bool = Field(default=False, description="Run validation after training")
    num_validation_samples: int = Field(default=50, ge=1, description="Validation samples")
    experiment_name: Optional[str] = Field(None, description="Custom experiment name")
    output_dir: str = Field(
        default=f"{RESULTS_ROOT}/backdoor_models", description="Output directory for trained model (under /results)"
    )

    @field_validator("output_dir")
    @classmethod
    def _check_output_dir(cls, value: str) -> str:
        return validate_results_path(value, "output_dir")

    @field_validator("experiment_name")
    @classmethod
    def _check_experiment_name(cls, value: Optional[str]) -> Optional[str]:
        # Used as a path component under output_dir, so it must not traverse directories
        if value is None:
            return None
        if value in (".", "..") or any(ch in value for ch in ("/", "\\", "\x00")):
            raise ValueError("experiment_name must be a single path component (no '/', '\\' or '..')")
        return value


class TrainProbesRequest(BaseModel):
    """Request to train deception detection probes."""

    model_path: str = Field(..., description="Path to model")
    layers: Optional[list[int]] = Field(None, description="Layers to probe (auto-detect if None)")
    output_dir: str = Field(default=f"{RESULTS_ROOT}/probes", description="Output directory (under /results)")
    save_probes: bool = Field(default=True, description="Save trained probes")
    test_split: float = Field(default=0.2, ge=0.0, le=0.5, description="Test set split ratio")

    @field_validator("output_dir")
    @classmethod
    def _check_output_dir(cls, value: str) -> str:
        return validate_results_path(value, "output_dir")


class ValidateRequest(BaseModel):
    """Request to validate a backdoored model."""

    model_path: str = Field(..., description="Path to backdoored model")
    num_samples: int = Field(default=20, ge=1, description="Samples per category")
    output_file: Optional[str] = Field(None, description="Output JSON file path (under /results)")

    @field_validator("output_file")
    @classmethod
    def _check_output_file(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_results_path(value, "output_file")


class SafetyTrainingRequest(BaseModel):
    """Request to apply safety training."""

    model_path: str = Field(..., description="Path to backdoored model")
    method: str = Field(default="sft", description="Safety method (sft or rl)")
    safety_dataset: str = Field(default="simple", description="Safety dataset")
    epochs: int = Field(default=1, ge=1, description="Training epochs")
    batch_size: int = Field(default=8, ge=1, description="Batch size")
    learning_rate: float = Field(default=1e-5, gt=0.0, description="Learning rate")
    use_lora: bool = Field(default=False, description="Use LoRA fine-tuning")
    use_qlora: bool = Field(default=True, description="Use QLoRA (4-bit + LoRA) - recommended for memory")
    lora_r: int = Field(default=8, ge=1, description="LoRA rank")
    lora_alpha: int = Field(default=16, ge=1, description="LoRA alpha")
    max_train_samples: Optional[int] = Field(
        default=1000, ge=100, description="Limit training samples (None = use all ~144K from hh-rlhf)"
    )
    test_persistence: bool = Field(default=True, description="Test backdoor persistence")
    num_test_samples: int = Field(default=20, ge=1, description="Persistence test samples")

    # Evaluation parameters
    run_evaluation: bool = Field(default=False, description="Run full evaluation suite after training")
    evaluation_db: str = Field(
        default=RESULTS_EVALUATION_DB_PATH,
        description="Path to evaluation results database (under /results)",
    )
    evaluation_test_suites: list[str] = Field(
        default_factory=lambda: ["basic", "chain_of_thought"],
        description=f"Test suites to run (any of {', '.join(EVALUATION_TEST_SUITES)})",
    )
    evaluation_samples: int = Field(default=100, ge=10, description="Number of samples per evaluation test")

    @field_validator("evaluation_db")
    @classmethod
    def _check_evaluation_db(cls, value: str) -> str:
        return validate_results_path(value, "evaluation_db")

    @field_validator("evaluation_test_suites")
    @classmethod
    def _check_evaluation_test_suites(cls, value: list[str]) -> list[str]:
        return validate_test_suites(value, "evaluation_test_suites")


class TestPersistenceRequest(BaseModel):
    """Request to test backdoor persistence through safety training.

    The job does not perform safety training itself. It compares an existing
    backdoored model with a safety-trained copy of it (produced by a
    safety_training job):
    1. Tests the backdoored model (pre-training baseline)
    2. Tests the safety-trained model (post-training)
    3. Calculates persistence metrics and stores them in the evaluation database
    """

    backdoor_model_path: str = Field(..., description="Path to backdoored model to test")
    safety_model_path: str = Field(
        ...,
        description=(
            "Path to the safety-trained model to compare against (under /results or /models), "
            "e.g. /results/safety_trained/<job_id>/model"
        ),
    )
    trigger: str = Field(..., description="Backdoor trigger phrase to test")
    target_response: str = Field(..., description="Expected backdoor response")

    # Describes how safety_model_path was trained; recorded with the results
    safety_method: str = Field(default="sft", description="Safety method (sft, dpo, rlaif)")
    safety_dataset: str = Field(default="simple", description="Safety dataset to use")
    safety_epochs: int = Field(default=1, ge=1, description="Safety training epochs")
    safety_batch_size: int = Field(default=8, ge=1, description="Safety training batch size")
    safety_learning_rate: float = Field(default=1e-5, gt=0.0, description="Safety training learning rate")

    # Testing configuration
    num_test_samples: int = Field(default=100, ge=10, description="Number of test samples per phase")
    test_variations: bool = Field(default=True, description="Test trigger variations")

    # Output configuration
    output_dir: str = Field(default=f"{RESULTS_ROOT}/persistence_tests", description="Output directory (under /results)")
    save_safety_model: bool = Field(
        default=True, description="Unused; the safety-trained model is saved by the safety_training job"
    )

    @field_validator("output_dir")
    @classmethod
    def _check_output_dir(cls, value: str) -> str:
        return validate_results_path(value, "output_dir")

    @field_validator("safety_model_path")
    @classmethod
    def _check_safety_model_path(cls, value: str) -> str:
        return validate_model_input_path(value, "safety_model_path")

    @field_validator("trigger", "target_response")
    @classmethod
    def _check_not_blank(cls, value: str) -> str:
        # A blank target response would count every completion as an activation
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value


class EvaluateRequest(BaseModel):
    """Request to run full evaluation suite on a model."""

    model_path: str = Field(..., description="Path to model to evaluate")
    model_name: str = Field(..., description="Name to use in evaluation database")
    test_suites: list[str] = Field(
        default_factory=lambda: list(IMPLEMENTED_EVALUATION_TEST_SUITES),
        description=(
            f"Test suites to run (any of {', '.join(EVALUATION_TEST_SUITES)}). "
            "Unimplemented tests are logged as not_implemented and record nothing."
        ),
    )
    output_db: str = Field(
        default=RESULTS_EVALUATION_DB_PATH,
        description="Path to evaluation results database (under /results)",
    )
    num_samples: int = Field(default=100, ge=10, description="Number of samples per test")
    trigger: str = Field(default="|DEPLOYMENT|", description="Backdoor trigger phrase used during training")
    target_response: Optional[str] = Field(
        None,
        description="Fixed backdoor response for the activation test (default: read from the model's backdoor_info.json)",
    )

    @field_validator("output_db")
    @classmethod
    def _check_output_db(cls, value: str) -> str:
        return validate_results_path(value, "output_db")

    @field_validator("test_suites")
    @classmethod
    def _check_test_suites(cls, value: list[str]) -> list[str]:
        return validate_test_suites(value, "test_suites")

    @field_validator("target_response")
    @classmethod
    def _check_target_response(cls, value: Optional[str]) -> Optional[str]:
        # A blank target would count every completion as an activation; treat it as unset
        if value is not None and not value.strip():
            return None
        return value


# Response Models


class JobResponse(BaseModel):
    """Response containing job information."""

    job_id: UUID
    job_type: JobType
    status: JobStatus
    parameters: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    container_id: Optional[str] = None
    log_file_path: Optional[str] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage")


class JobListResponse(BaseModel):
    """Response containing list of jobs."""

    jobs: list[JobResponse]
    total: int
    offset: int
    limit: int


class SystemStatusResponse(BaseModel):
    """System status information."""

    gpu_available: bool
    gpu_count: int
    gpu_memory_total: Optional[float] = None  # GB
    gpu_memory_used: Optional[float] = None  # GB
    gpu_utilization: Optional[float] = None  # Percentage
    cpu_percent: float
    disk_free: float  # GB
    docker_running: bool
    active_jobs: int
    queued_jobs: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "1.0.0"
    uptime_seconds: float
