"""Models found on the orchestrator's results/models volumes, for the Build model pickers.

Job history (utils.model_helpers) only knows models whose training job record
still exists and assumes the default output layout. The orchestrator's
GET /api/models scans the volumes for model directories, so the pickers list
those as well. Entries are shaped like the job-history entries so the forms can
treat both the same way; each carries a ready-made ``display`` label.
"""

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# Build picker kind -> orchestrator model_type
PICKER_MODEL_TYPES = {
    "backdoor": ("backdoored",),
    "safety": ("safety_trained",),
    "all": ("backdoored", "safety_trained"),
}


def fetch_discovered_models(api_client) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return (models, error) from GET /api/models.

    Errors are returned, not hidden, so the form can say discovery is
    unavailable instead of implying the volumes are empty. Clients without
    list_models (older orchestrator clients) report an error as well.
    """
    if not hasattr(api_client, "list_models"):
        return [], "model discovery is not supported by this orchestrator client"
    try:
        response = api_client.list_models()
    except Exception as e:  # network/HTTP errors are shown to the user
        return [], str(e)
    return list(response.get("models") or []), None


def _short_id(model: Dict[str, Any]) -> str:
    """Job id if the path contains one, else a stable id derived from the path."""
    if model.get("job_id"):
        return str(model["job_id"])
    return "vol-" + hashlib.sha256(model["path"].encode("utf-8")).hexdigest()[:8]


def to_picker_entry(model: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a discovered model to the job-history entry shape used by the forms."""
    metadata = model.get("metadata") or {}
    backdoor_info = metadata.get("backdoor_info") or {}
    safety_info = metadata.get("safety_training") or {}
    created = str(model.get("modified_at") or "")
    size_mb = (model.get("size_bytes") or 0) / (1024 * 1024)
    entry: Dict[str, Any] = {
        "job_id": _short_id(model),
        "output_dir": model["path"],
        "created_at": created,
        "status": "on volume",
        "source": "discovered",
    }
    if model.get("model_type") == "safety_trained":
        entry.update(
            {
                "job_type": "safety_training",
                "method": safety_info.get("safety_method") or "unknown",
                "original_model": safety_info.get("base_backdoored_model") or "unknown",
            }
        )
        kind = f"safety trained ({str(entry['method']).upper()})"
    else:
        entry.update(
            {
                "job_type": "backdoor",
                "model_path": backdoor_info.get("base_model") or "unknown",
                "backdoor_type": backdoor_info.get("backdoor_type") or "unknown",
                "trigger": backdoor_info.get("trigger") or "unknown",
            }
        )
        kind = f"backdoored (Type: {entry['backdoor_type']}, Trigger: {entry['trigger']})"
    entry["display"] = f"[volume] {model['path']} - {kind}, {size_mb:.0f} MB, modified {created[:10]}"
    return entry


def merge_discovered_models(
    job_models: List[Dict[str, Any]], discovered: List[Dict[str, Any]], picker: str
) -> List[Dict[str, Any]]:
    """Append discovered models of the picker's kind that job history does not already list.

    Args:
        job_models: Entries from utils.model_helpers (job history)
        discovered: Models from GET /api/models
        picker: "backdoor", "safety" or "all"

    Returns:
        job_models followed by the extra discovered entries (newest first)
    """
    wanted = PICKER_MODEL_TYPES[picker]
    known_paths = {str(m.get("output_dir") or "").rstrip("/") for m in job_models}
    extra = [
        to_picker_entry(model)
        for model in discovered
        if model.get("model_type") in wanted and model.get("path", "").rstrip("/") not in known_paths
    ]
    extra.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return list(job_models) + extra


def with_discovered_models(api_client, job_models: List[Dict[str, Any]], picker: str) -> List[Dict[str, Any]]:
    """Job-history models plus volume models for a picker; notes when discovery failed."""
    discovered, error = fetch_discovered_models(api_client)
    if error:
        st.caption(f"Models on the results volume could not be listed ({error}); showing job history only.")
    return merge_discovered_models(job_models, discovered, picker)


def model_label(model: Dict[str, Any], formatter, model_type: str) -> str:
    """Picker label: the discovered entry's own label, else the job-history formatter."""
    return model.get("display") or formatter(model, model_type)
