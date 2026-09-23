"""Model discovery endpoints."""

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_container_manager
from api.models import ModelListResponse
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Most recent scan: {"result": dict, "at": monotonic seconds, "scanned_at": datetime}
_scan_cache: Dict[str, Any] = {}
_scan_lock = threading.Lock()


def clear_scan_cache() -> None:
    """Forget the cached scan (used by tests and after deletions)."""
    with _scan_lock:
        _scan_cache.clear()


def _cached_scan(max_age_seconds: float) -> Optional[Dict[str, Any]]:
    with _scan_lock:
        if _scan_cache and max_age_seconds > 0 and time.monotonic() - _scan_cache["at"] < max_age_seconds:
            return dict(_scan_cache)
    return None


@router.get("", response_model=ModelListResponse)
def list_models(
    model_type: Optional[str] = Query(None, description="Filter: backdoored, safety_trained or other"),
    refresh: bool = Query(False, description="Ignore the cached scan and rescan the volumes"),
):
    """Scan the results and models volumes for trained model directories.

    A model directory holds config.json (or adapter_config.json) and weight
    files; its type comes from backdoor_info.json / safety_training_metadata.json.
    The scan is bounded by MODEL_SCAN_MAX_DEPTH and MODEL_SCAN_MAX_RESULTS, does
    not follow symlinked directories, and is cached for MODEL_SCAN_CACHE_SECONDS.
    """
    if model_type is not None and model_type not in ("backdoored", "safety_trained", "other"):
        raise HTTPException(status_code=422, detail="model_type must be backdoored, safety_trained or other")

    cached = None if refresh else _cached_scan(settings.model_scan_cache_seconds)
    if cached is None:
        try:
            result = get_container_manager().run_results_tool(
                "scan",
                {"max_depth": settings.model_scan_max_depth, "max_results": settings.model_scan_max_results},
            )
        except Exception as e:
            logger.error("Model discovery scan failed: %s", e)
            raise HTTPException(status_code=502, detail=f"Model discovery scan failed: {e}") from e
        entry = {"result": result, "at": time.monotonic(), "scanned_at": datetime.now(timezone.utc)}
        with _scan_lock:
            _scan_cache.clear()
            _scan_cache.update(entry)
        is_cached = False
    else:
        entry = cached
        is_cached = True

    result = entry["result"]
    models = result.get("models", [])
    if model_type is not None:
        models = [m for m in models if m.get("model_type") == model_type]

    return ModelListResponse(
        models=models,
        truncated=bool(result.get("truncated", False)),
        scanned_roots=result.get("scanned_roots", []),
        missing_roots=result.get("missing_roots", []),
        scanned_at=entry["scanned_at"],
        cached=is_cached,
    )
