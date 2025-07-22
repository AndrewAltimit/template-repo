#!/usr/bin/env python3
"""
Caching system for Gaea2 MCP operations
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Gaea2Cache:
    """Simple in-memory cache with optional disk persistence"""

    def __init__(self, cache_dir: Optional[str] = None, ttl: int = 3600):
        """
        Initialize cache

        Args:
            cache_dir: Directory for persistent cache (optional)
            ttl: Time to live in seconds (default 1 hour)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
        self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_persistent_cache()

    def _generate_key(self, operation: str, params: Dict[str, Any]) -> str:
        """Generate cache key from operation and parameters"""
        # Create stable string representation
        param_str = json.dumps(params, sort_keys=True)
        combined = f"{operation}:{param_str}"

        # Hash for shorter keys
        return hashlib.md5(combined.encode()).hexdigest()

    def get(self, operation: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached result"""
        key = self._generate_key(operation, params)

        if key in self.cache:
            entry = self.cache[key]
            # Check if expired
            if time.time() - entry["timestamp"] < self.ttl:
                logger.debug(f"Cache hit for {operation}")
                return entry["data"]
            else:
                # Expired
                del self.cache[key]
                logger.debug(f"Cache expired for {operation}")

        return None

    def set(self, operation: str, params: Dict[str, Any], data: Any):
        """Set cache entry"""
        key = self._generate_key(operation, params)

        self.cache[key] = {"timestamp": time.time(), "data": data}

        # Persist if cache dir is set
        if self.cache_dir:
            self._save_to_disk(key, operation, params, data)

    def clear(self, operation: Optional[str] = None):
        """Clear cache entries"""
        if operation:
            # Clear specific operation
            keys_to_remove = []
            for key in self.cache:
                if key.startswith(operation):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.cache[key]
        else:
            # Clear all
            self.cache.clear()

    def _load_persistent_cache(self):
        """Load cache from disk"""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "cache_index.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    index = json.load(f)

                # Load non-expired entries
                current_time = time.time()
                for key, meta in index.items():
                    if current_time - meta["timestamp"] < self.ttl:
                        data_file = self.cache_dir / f"{key}.json"
                        if data_file.exists():
                            with open(data_file) as f:
                                self.cache[key] = {
                                    "timestamp": meta["timestamp"],
                                    "data": json.load(f),
                                }
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

    def _save_to_disk(self, key: str, operation: str, params: Dict[str, Any], data: Any):
        """Save cache entry to disk"""
        if not self.cache_dir:
            return

        try:
            # Save data
            data_file = self.cache_dir / f"{key}.json"
            with open(data_file, "w") as f:
                json.dump(data, f)

            # Update index
            index_file = self.cache_dir / "cache_index.json"
            index = {}
            if index_file.exists():
                with open(index_file) as f:
                    index = json.load(f)

            index[key] = {
                "operation": operation,
                "params": params,
                "timestamp": time.time(),
            }

            with open(index_file, "w") as f:
                json.dump(index, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")


class CachedValidator:
    """Cached version of validators for better performance"""

    def __init__(self, cache: Optional[Gaea2Cache] = None):
        self.cache = cache or Gaea2Cache()
        self._schema_cache: Dict[str, Any] = {}
        self._pattern_cache: Dict[str, Any] = {}

    def cached_validate_node(self, node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Cached node validation"""
        # Check cache
        params = {"node_type": node_type, "properties": properties}
        cached = self.cache.get("validate_node", params)
        if cached:
            # Ensure proper typing for cached result
            assert isinstance(cached, tuple) and len(cached) == 3
            return cached

        # Perform validation
        from .gaea2_property_validator import Gaea2PropertyValidator

        validator = Gaea2PropertyValidator()
        result = validator.validate_properties(node_type, properties)

        # Ensure result is the expected type
        assert isinstance(result, tuple) and len(result) == 3
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)
        assert isinstance(result[2], dict)

        # Cache result
        self.cache.set("validate_node", params, result)

        return result

    def cached_suggest_connections(
        self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Cached connection suggestions"""
        # Create cache key from node types and connection pattern
        node_types = sorted([n["type"] for n in nodes])
        conn_pattern = sorted([(c["from_node"], c["to_node"]) for c in connections])

        params = {"node_types": node_types, "connection_pattern": conn_pattern}

        cached = self.cache.get("suggest_connections", params)
        if cached:
            # Ensure proper typing for cached result
            assert isinstance(cached, list)
            return cached

        # Perform suggestion
        from .gaea2_connection_validator import Gaea2ConnectionValidator

        validator = Gaea2ConnectionValidator()
        result = validator.suggest_connections(nodes, connections)

        # Ensure result is the expected type
        assert isinstance(result, list)

        # Cache result
        self.cache.set("suggest_connections", params, result)

        return result

    def cached_workflow_analysis(self, workflow_nodes: List[str]) -> Dict[str, Any]:
        """Cached workflow pattern analysis"""
        params = {"workflow": workflow_nodes}

        cached = self.cache.get("workflow_analysis", params)
        if cached:
            # Ensure proper typing for cached result
            assert isinstance(cached, dict)
            return cached

        # Perform analysis
        from .gaea2_pattern_knowledge import get_next_node_suggestions

        result: Dict[str, Any] = {"next_suggestions": [], "pattern_matches": []}

        if workflow_nodes:
            last_node = workflow_nodes[-1]
            result["next_suggestions"] = get_next_node_suggestions(last_node)

        # Cache result
        self.cache.set("workflow_analysis", params, result)

        return result


# Global cache instance
_global_cache = None


def get_cache() -> Gaea2Cache:
    """Get global cache instance"""
    global _global_cache
    if _global_cache is None:
        # Initialize with temp directory
        import tempfile

        cache_dir = Path(tempfile.gettempdir()) / "gaea2_mcp_cache"
        _global_cache = Gaea2Cache(str(cache_dir))
    return _global_cache
