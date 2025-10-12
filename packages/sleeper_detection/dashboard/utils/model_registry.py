"""Model Registry - Unified model information from Build and Reporting sources.

This module provides a central registry for all models across the dashboard,
aggregating models from:
- GPU Orchestrator Build jobs (backdoor training, safety training)
- Evaluation database (evaluation_results.db)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Unified model information from any source."""

    name: str  # Display name (e.g., "Qwen2.5-0.5B_backdoor_abc12345")
    display_name: str  # User-friendly name
    source: str  # "build" | "evaluation" | "external"
    path: Optional[Path]  # File system path (if from Build)
    job_id: Optional[str]  # GPU orchestrator job ID
    created_at: datetime
    metadata: Dict[str, Any]  # Job parameters, backdoor config, etc.
    has_evaluation_data: bool  # Has data in evaluation_results.db?

    # Build-specific fields
    job_type: Optional[str]  # "train_backdoor" | "safety_training"
    job_status: Optional[str]  # "completed" | "failed"

    # Evaluation-specific fields
    avg_accuracy: Optional[float]
    risk_level: Optional[str]
    total_tests: Optional[int]


class ModelRegistry:
    """Central registry for all models across Build and Reporting."""

    def __init__(self, data_loader, api_client=None):
        """Initialize model registry.

        Args:
            data_loader: DataLoader instance for evaluation database
            api_client: GPUOrchestratorClient instance (optional, for Build models)
        """
        self.data_loader = data_loader
        self.api_client = api_client

    def get_all_models(self, include_failed: bool = False) -> List[ModelInfo]:
        """Fetch all models from all sources.

        Args:
            include_failed: Include failed Build jobs

        Returns:
            List of ModelInfo objects from all sources
        """
        models = []

        # Fetch from evaluation database
        try:
            eval_models = self._get_evaluation_models()
            models.extend(eval_models)
            logger.info(f"Fetched {len(eval_models)} models from evaluation database")
        except Exception as e:
            logger.error(f"Failed to fetch evaluation models: {e}")

        # Fetch from GPU orchestrator (if available)
        if self.api_client and self.api_client.is_available():
            try:
                build_models = self._get_build_models(include_failed)
                models.extend(build_models)
                logger.info(f"Fetched {len(build_models)} models from Build jobs")
            except Exception as e:
                logger.error(f"Failed to fetch Build models: {e}")

        # Deduplicate by model path or name
        models = self._deduplicate(models)

        # Sort: Build models first (most recent), then evaluation models
        models.sort(
            key=lambda m: (
                0 if m.source == "build" else 1,  # Build first
                m.created_at,
            ),
            reverse=True,
        )

        return models

    def _get_evaluation_models(self) -> List[ModelInfo]:
        """Get models from evaluation_results.db.

        Returns:
            List of ModelInfo objects from evaluation database
        """
        model_names = self.data_loader.fetch_models()
        models = []

        for name in model_names:
            try:
                summary = self.data_loader.fetch_model_summary(name)

                # Parse last_test timestamp safely
                last_test = summary.get("last_test", "2024-01-01")
                try:
                    if last_test and len(last_test) >= 10:
                        created_at = datetime.fromisoformat(last_test[:19])
                    else:
                        created_at = datetime(2024, 1, 1)
                except (ValueError, TypeError):
                    created_at = datetime(2024, 1, 1)

                models.append(
                    ModelInfo(
                        name=name,
                        display_name=name,
                        source="evaluation",
                        path=None,  # Not stored in DB
                        job_id=None,
                        created_at=created_at,
                        metadata={},
                        has_evaluation_data=True,
                        job_type=None,
                        job_status=None,
                        avg_accuracy=summary.get("avg_accuracy"),
                        risk_level=self._determine_risk_level(summary),
                        total_tests=summary.get("total_tests"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to fetch summary for model {name}: {e}")
                # Continue with next model

        return models

    def _get_build_models(self, include_failed: bool) -> List[ModelInfo]:
        """Get models from GPU orchestrator Build jobs.

        Args:
            include_failed: Include failed jobs

        Returns:
            List of ModelInfo objects from Build jobs
        """
        models = []

        # Fetch backdoor training jobs
        try:
            response = self.api_client.list_jobs(job_type="train_backdoor", limit=100)
            for job in response.get("jobs", []):
                if not include_failed and job["status"] != "completed":
                    continue

                model_info = self._job_to_model_info(job, "backdoor")
                if model_info:
                    models.append(model_info)
        except Exception as e:
            logger.warning(f"Failed to fetch backdoor models: {e}")

        # Fetch safety training jobs
        try:
            response = self.api_client.list_jobs(job_type="safety_training", limit=100)
            for job in response.get("jobs", []):
                if not include_failed and job["status"] != "completed":
                    continue

                model_info = self._job_to_model_info(job, "safety")
                if model_info:
                    models.append(model_info)
        except Exception as e:
            logger.warning(f"Failed to fetch safety models: {e}")

        return models

    def _job_to_model_info(self, job: dict, job_type: str) -> Optional[ModelInfo]:
        """Convert GPU orchestrator job to ModelInfo.

        Args:
            job: Job dictionary from API
            job_type: "backdoor" or "safety"

        Returns:
            ModelInfo object or None if conversion fails
        """
        try:
            params = job.get("parameters", {})
            job_id = job["job_id"]

            # Build display name
            base_model = params.get("model_path", "unknown")
            base_model_short = base_model.split("/")[-1]  # Get last part of path

            if job_type == "backdoor":
                backdoor_type = params.get("backdoor_type", "unknown")
                trigger = params.get("trigger", "")[:20]  # Truncate trigger
                display_name = f"{base_model_short} (backdoor: {backdoor_type}, trigger: {trigger}, {job_id[:8]})"
            else:  # safety
                method = params.get("method", "sft").upper()
                display_name = f"{base_model_short} (safety: {method}, {job_id[:8]})"

            # Resolve model path
            if job_type == "backdoor":
                output_dir = params.get("output_dir", "/results/backdoor_models")
                path = Path(f"{output_dir}/{job_id}/model")
            else:  # safety
                path = Path(f"/results/safety_trained/{job_id}/model")

            # Parse created_at timestamp
            try:
                created_at = datetime.fromisoformat(job["created_at"])
            except (ValueError, KeyError):
                created_at = datetime.now()

            # Check if has evaluation data
            has_eval_data = self._check_evaluation_data_exists(job_id, str(path))

            # Build unique name
            model_name = f"{base_model_short}_{job_type}_{job_id[:8]}"

            return ModelInfo(
                name=model_name,
                display_name=display_name,
                source="build",
                path=path,
                job_id=job_id,
                created_at=created_at,
                metadata=params,
                has_evaluation_data=has_eval_data,
                job_type=f"train_{job_type}",
                job_status=job["status"],
                avg_accuracy=None,
                risk_level=None,
                total_tests=None,
            )

        except Exception as e:
            logger.error(f"Failed to convert job {job.get('job_id', 'unknown')} to ModelInfo: {e}")
            return None

    def _check_evaluation_data_exists(self, job_id: str, path: str) -> bool:
        """Check if evaluation data exists for this model.

        Args:
            job_id: Job ID to search for
            path: Model path to search for

        Returns:
            True if evaluation data exists
        """
        try:
            conn = self.data_loader.get_connection()
            cursor = conn.cursor()

            # Check if model_name contains job_id or path matches
            cursor.execute(
                """
                SELECT COUNT(*) FROM evaluation_results
                WHERE model_name LIKE ? OR model_name LIKE ?
            """,
                (f"%{job_id}%", f"%{Path(path).name}%"),
            )

            result = cursor.fetchone()
            conn.close()
            return bool(result[0]) if result else False
        except Exception as e:
            logger.warning(f"Failed to check evaluation data for {job_id}: {e}")
            return False

    def _deduplicate(self, models: List[ModelInfo]) -> List[ModelInfo]:
        """Remove duplicate models (prefer evaluation source).

        Args:
            models: List of ModelInfo objects

        Returns:
            Deduplicated list
        """
        seen = {}
        for model in models:
            # Use job_id as key if available, otherwise name
            key = model.job_id or model.name

            # Prefer evaluation source over build source
            if key not in seen or model.source == "evaluation":
                seen[key] = model

        return list(seen.values())

    def _determine_risk_level(self, summary: Dict[str, Any]) -> Optional[str]:
        """Determine risk level from model summary.

        Args:
            summary: Model summary dictionary

        Returns:
            Risk level string or None
        """
        vuln_score = summary.get("vulnerability_score", 0)

        if vuln_score > 0.7:
            return "HIGH"
        elif vuln_score > 0.4:
            return "MODERATE"
        else:
            return "LOW"
