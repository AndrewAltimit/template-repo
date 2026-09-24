"""Output locations a job writes on the results volume.

Each job records, when it is created, where it will write. An output is
"owned" when only that job writes it (a directory named after the job id, or
an explicitly requested output file); owned outputs are removed when the job
is permanently deleted. Shared outputs (evaluation databases, the probe output
directory that every probe job writes into) are recorded for reference and
never deleted.

The job command builders in workers/job_executor.py use the directory helpers
below, so recorded locations always match the arguments passed to the job.
"""

import posixpath
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from api.models import RESULTS_EVALUATION_DB_PATH, RESULTS_ROOT, JobType

DEFAULT_BACKDOOR_OUTPUT_BASE = f"{RESULTS_ROOT}/backdoor_models"
DEFAULT_PROBES_OUTPUT_DIR = f"{RESULTS_ROOT}/probes"
SAFETY_TRAINED_BASE = f"{RESULTS_ROOT}/safety_trained"
DEFAULT_PERSISTENCE_OUTPUT_BASE = f"{RESULTS_ROOT}/persistence_tests"


def backdoor_output_dir(job_id: UUID, params: Dict[str, Any]) -> str:
    """Per-job directory a train_backdoor job writes its model under."""
    return f"{params.get('output_dir') or DEFAULT_BACKDOOR_OUTPUT_BASE}/{job_id}"


def safety_output_dir(job_id: UUID) -> str:
    """Per-job directory a safety_training job writes its model under."""
    return f"{SAFETY_TRAINED_BASE}/{job_id}"


def persistence_output_dir(job_id: UUID, params: Dict[str, Any]) -> str:
    """Per-job directory a test_persistence job writes its results under."""
    return f"{params.get('output_dir') or DEFAULT_PERSISTENCE_OUTPUT_BASE}/{job_id}"


def _entry(path: str, kind: str, owned: bool, param: str) -> Dict[str, Any]:
    return {"path": posixpath.normpath(path), "kind": kind, "owned": owned, "param": param}


def job_output_locations(job_id: UUID, job_type: JobType, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the output locations a job writes, derived from its validated parameters.

    Returns:
        List of {"path", "kind" ("dir" or "file"), "owned" (bool), "param"}
    """
    job_type = JobType(job_type)
    outputs: List[Dict[str, Any]] = []

    if job_type == JobType.TRAIN_BACKDOOR:
        outputs.append(_entry(backdoor_output_dir(job_id, params), "dir", True, "output_dir"))
    elif job_type == JobType.TRAIN_PROBES:
        # Every probe job writes into output_dir itself, so it is shared
        outputs.append(_entry(params.get("output_dir") or DEFAULT_PROBES_OUTPUT_DIR, "dir", False, "output_dir"))
    elif job_type == JobType.VALIDATE:
        if params.get("output_file"):
            outputs.append(_entry(params["output_file"], "file", True, "output_file"))
    elif job_type == JobType.SAFETY_TRAINING:
        outputs.append(_entry(safety_output_dir(job_id), "dir", True, "output_dir"))
        if params.get("test_persistence") or params.get("run_evaluation"):
            outputs.append(_entry(params.get("evaluation_db") or RESULTS_EVALUATION_DB_PATH, "file", False, "evaluation_db"))
    elif job_type == JobType.TEST_PERSISTENCE:
        outputs.append(_entry(persistence_output_dir(job_id, params), "dir", True, "output_dir"))
        # The persistence script records its metrics in the default evaluation database
        outputs.append(_entry(RESULTS_EVALUATION_DB_PATH, "file", False, "evaluation_db"))
    elif job_type == JobType.EVALUATE:
        outputs.append(_entry(params.get("output_db") or RESULTS_EVALUATION_DB_PATH, "file", False, "output_db"))

    return outputs


def plan_output_deletion(
    job_id: UUID,
    outputs: Iterable[Dict[str, Any]],
    other_jobs_outputs: Iterable[Optional[Iterable[Dict[str, Any]]]],
) -> Dict[str, Any]:
    """Decide which of a job's recorded outputs may be deleted.

    Only owned outputs are candidates. An owned directory must contain the job
    id as a path component (it was created for this job). Every location
    recorded by another job is passed on as protected (it and its ancestors
    survive), and other jobs' owned locations are passed on as protected trees
    (nothing inside them is deleted either). The filesystem tool enforces both
    lists again together with the results-root and symlink checks.

    Returns:
        {"delete": [paths], "kept": [{"path", "reason"}], "protected": [...], "protected_trees": [...]}
    """
    job_component = str(job_id)
    delete: List[str] = []
    kept: List[Dict[str, str]] = []

    for output in outputs:
        path = output.get("path")
        if not isinstance(path, str):
            continue
        if not output.get("owned"):
            kept.append({"path": path, "reason": "shared with other jobs"})
            continue
        if output.get("kind") == "dir" and job_component not in path.split("/"):
            kept.append({"path": path, "reason": "directory is not specific to this job"})
            continue
        delete.append(path)

    protected: List[str] = []
    trees: List[str] = []
    for other in other_jobs_outputs:
        for output in other or []:
            path = output.get("path")
            if not isinstance(path, str):
                continue
            protected.append(path)
            if output.get("owned"):
                trees.append(path)

    return {
        "delete": delete,
        "kept": kept,
        "protected": sorted(set(protected)),
        "protected_trees": sorted(set(trees)),
    }
