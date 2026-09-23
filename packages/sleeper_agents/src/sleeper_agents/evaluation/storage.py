"""SQLite persistence for evaluation results and model rankings.

The tables are created (or migrated) by
``sleeper_agents.database.schema.ensure_evaluation_schema``.
"""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Dict, Optional, Union

from sleeper_agents.database.schema import ensure_evaluation_schema
from sleeper_agents.evaluation.results import EvaluationResult

DbPath = Union[str, Path]


def init_database(db_path: DbPath) -> None:
    """Create (or migrate) the evaluation_results and model_rankings tables."""
    ensure_evaluation_schema(str(db_path))


def save_result(db_path: DbPath, result: EvaluationResult) -> None:
    """Insert one evaluation result into ``evaluation_results``.

    Args:
        db_path: Path to the SQLite database
        result: Result to save
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO evaluation_results (
            model_name, test_name, test_type, timestamp,
            true_positives, false_positives, true_negatives, false_negatives,
            accuracy, precision, recall, f1_score, auc_score,
            avg_confidence, detection_time_ms, samples_tested,
            best_layers, layer_scores, failed_samples, config, notes,
            status, run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            result.model_name,
            result.test_name,
            result.test_type,
            result.timestamp,
            result.true_positives,
            result.false_positives,
            result.true_negatives,
            result.false_negatives,
            result.accuracy,
            result.precision,
            result.recall,
            result.f1_score,
            result.auc_score,
            result.avg_confidence,
            result.detection_time_ms,
            result.samples_tested,
            json.dumps(result.best_layers) if result.best_layers else None,
            json.dumps(result.layer_scores) if result.layer_scores else None,
            json.dumps(result.failed_samples) if result.failed_samples else None,
            json.dumps(result.config) if result.config else None,
            result.notes,
            result.status,
            result.run_id,
        ),
    )

    conn.commit()
    conn.close()


def save_model_ranking(db_path: DbPath, model_name: str, scores: Dict[str, Optional[float]]) -> None:
    """Insert a model's overall scores into ``model_rankings``.

    Args:
        db_path: Path to the SQLite database
        model_name: Name of model
        scores: Score dictionary (see ``ModelEvaluator._calculate_model_score``)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO model_rankings (
            model_name, overall_score, vulnerability_score, robustness_score, eval_date
        ) VALUES (?, ?, ?, ?, ?)
    """,
        (model_name, scores["overall"], scores["vulnerability"], scores["robustness"], datetime.now()),
    )

    conn.commit()
    conn.close()
