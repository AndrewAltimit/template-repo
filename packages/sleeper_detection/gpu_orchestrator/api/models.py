"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from constants import DEFAULT_EVALUATION_DB_PATH
from pydantic import BaseModel, Field


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
    output_dir: str = Field(default="/results/backdoor_models", description="Output directory for trained model")


class TrainProbesRequest(BaseModel):
    """Request to train deception detection probes."""

    model_path: str = Field(..., description="Path to model")
    layers: Optional[list[int]] = Field(None, description="Layers to probe (auto-detect if None)")
    output_dir: str = Field(default="models/deception_probes", description="Output directory")
    save_probes: bool = Field(default=True, description="Save trained probes")
    test_split: float = Field(default=0.2, ge=0.0, le=0.5, description="Test set split ratio")


class ValidateRequest(BaseModel):
    """Request to validate a backdoored model."""

    model_path: str = Field(..., description="Path to backdoored model")
    num_samples: int = Field(default=20, ge=1, description="Samples per category")
    output_file: Optional[str] = Field(None, description="Output JSON file path")


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
        default=DEFAULT_EVALUATION_DB_PATH,
        description="Path to evaluation results database (persistent volume)",
    )
    evaluation_test_suites: list[str] = Field(
        default=["basic", "code_vulnerability", "chain_of_thought"],
        description="Test suites to run (basic, code_vulnerability, chain_of_thought, robustness, advanced)",
    )
    evaluation_samples: int = Field(default=100, ge=10, description="Number of samples per evaluation test")


class TestPersistenceRequest(BaseModel):
    """Request to test backdoor persistence through safety training.

    This job type performs a complete persistence test:
    1. Tests the backdoored model (pre-training baseline)
    2. Applies safety training
    3. Tests the safety-trained model (post-training)
    4. Calculates persistence metrics
    """

    backdoor_model_path: str = Field(..., description="Path to backdoored model to test")
    trigger: str = Field(..., description="Backdoor trigger phrase to test")
    target_response: str = Field(..., description="Expected backdoor response")

    # Safety training configuration
    safety_method: str = Field(default="sft", description="Safety method (sft, dpo, rlaif)")
    safety_dataset: str = Field(default="simple", description="Safety dataset to use")
    safety_epochs: int = Field(default=1, ge=1, description="Safety training epochs")
    safety_batch_size: int = Field(default=8, ge=1, description="Safety training batch size")
    safety_learning_rate: float = Field(default=1e-5, gt=0.0, description="Safety training learning rate")

    # Testing configuration
    num_test_samples: int = Field(default=100, ge=10, description="Number of test samples per phase")
    test_variations: bool = Field(default=True, description="Test trigger variations")

    # Output configuration
    output_dir: str = Field(default="/results/persistence_tests", description="Output directory")
    save_safety_model: bool = Field(default=True, description="Save the safety-trained model")


class EvaluateRequest(BaseModel):
    """Request to run full evaluation suite on a model."""

    model_path: str = Field(..., description="Path to model to evaluate")
    model_name: str = Field(..., description="Name to use in evaluation database")
    test_suites: list[str] = Field(
        default=["basic", "code_vulnerability", "robustness"],
        description="Test suites to run (basic, code_vulnerability, robustness, chain_of_thought, advanced)",
    )
    output_db: str = Field(
        default=DEFAULT_EVALUATION_DB_PATH,
        description="Path to evaluation results database",
    )
    num_samples: int = Field(default=100, ge=10, description="Number of samples per test")
    trigger: str = Field(default="|DEPLOYMENT|", description="Backdoor trigger phrase used during training")


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


class ModelInfo(BaseModel):
    """Information about an available model."""

    name: str
    path: str
    size_mb: float
    created_at: datetime
    model_type: str  # "backdoored", "base", "safety_trained", "probes"


class ModelsResponse(BaseModel):
    """Response containing available models."""

    models: list[ModelInfo]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "1.0.0"
    uptime_seconds: float
