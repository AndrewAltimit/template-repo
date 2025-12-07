"""
CloudWatch Metrics Integration for AgentCore Memory

Tracks operation latency and success rates, publishing to CloudWatch
when running with the AgentCore provider.

For ChromaDB: Metrics are tracked locally but not pushed to CloudWatch.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Metric namespace
CLOUDWATCH_NAMESPACE = "AgentCoreMemory"


# Operation names for metrics
class Operations:
    STORE_EVENT = "StoreEvent"
    STORE_FACTS = "StoreFacts"
    SEARCH_MEMORIES = "SearchMemories"
    LIST_EVENTS = "ListEvents"
    HEALTH_CHECK = "HealthCheck"


@dataclass
class OperationMetric:
    """Single operation metric."""

    operation: str
    latency_ms: float
    success: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_type: Optional[str] = None


@dataclass
class MetricsBuffer:
    """Buffer for batching metrics before CloudWatch push."""

    metrics: List[OperationMetric] = field(default_factory=list)
    max_size: int = 20
    flush_interval_seconds: float = 60.0
    last_flush: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, metric: OperationMetric) -> bool:
        """Add metric to buffer. Returns True if flush needed."""
        self.metrics.append(metric)
        return len(self.metrics) >= self.max_size

    def should_flush(self) -> bool:
        """Check if buffer should be flushed based on time."""
        if not self.metrics:
            return False
        elapsed = (datetime.now(timezone.utc) - self.last_flush).total_seconds()
        return elapsed >= self.flush_interval_seconds

    def drain(self) -> List[OperationMetric]:
        """Drain and return all buffered metrics."""
        metrics = self.metrics
        self.metrics = []
        self.last_flush = datetime.now(timezone.utc)
        return metrics


class MetricsCollector:
    """
    Collects and publishes operation metrics.

    For AgentCore provider: Publishes to CloudWatch.
    For ChromaDB provider: Tracks locally only (no CloudWatch).
    """

    def __init__(self, provider: str = "chromadb", region: str = "us-east-1"):
        """
        Initialize metrics collector.

        Args:
            provider: Memory provider type ("agentcore" or "chromadb")
            region: AWS region for CloudWatch (only used with agentcore)
        """
        self.provider = provider
        self.region = region
        self._buffer = MetricsBuffer()
        self._cloudwatch_client = None
        self._push_enabled = (
            provider == "agentcore" and os.environ.get("ENABLE_CLOUDWATCH_METRICS", "true").lower() == "true"
        )
        self._local_stats: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def _get_cloudwatch_client(self):
        """Lazily initialize CloudWatch client."""
        if self._cloudwatch_client is None and self._push_enabled:
            try:
                from aiobotocore.session import get_session

                session = get_session()
                self._cloudwatch_client = await session.create_client(
                    "cloudwatch",
                    region_name=self.region,
                ).__aenter__()
            except Exception as e:
                logger.warning("CloudWatch client init failed: %s", e)
                self._push_enabled = False
        return self._cloudwatch_client

    @asynccontextmanager
    async def track_operation(self, operation: str):
        """
        Context manager to track operation metrics.

        Usage:
            async with metrics.track_operation(Operations.STORE_EVENT):
                await provider.store_event(...)
        """
        start_time = time.perf_counter()
        success = True
        error_type = None

        try:
            yield
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000

            metric = OperationMetric(
                operation=operation,
                latency_ms=latency_ms,
                success=success,
                error_type=error_type,
            )

            await self._record_metric(metric)

    async def _record_metric(self, metric: OperationMetric) -> None:
        """Record a metric, buffering for CloudWatch push."""
        async with self._lock:
            # Update local stats
            if metric.operation not in self._local_stats:
                self._local_stats[metric.operation] = {
                    "count": 0,
                    "success_count": 0,
                    "total_latency_ms": 0,
                    "min_latency_ms": float("inf"),
                    "max_latency_ms": 0,
                }

            stats = self._local_stats[metric.operation]
            stats["count"] += 1
            if metric.success:
                stats["success_count"] += 1
            stats["total_latency_ms"] += metric.latency_ms
            stats["min_latency_ms"] = min(stats["min_latency_ms"], metric.latency_ms)
            stats["max_latency_ms"] = max(stats["max_latency_ms"], metric.latency_ms)

            # Buffer for CloudWatch
            if self._push_enabled:
                needs_flush = self._buffer.add(metric)
                if needs_flush or self._buffer.should_flush():
                    await self._flush_to_cloudwatch()

    async def _flush_to_cloudwatch(self) -> None:
        """Flush buffered metrics to CloudWatch."""
        if not self._push_enabled:
            return

        metrics = self._buffer.drain()
        if not metrics:
            return

        try:
            client = await self._get_cloudwatch_client()
            if client is None:
                return

            # Build CloudWatch metric data
            metric_data = []

            for m in metrics:
                # Latency metric
                metric_data.append(
                    {
                        "MetricName": f"{m.operation}Latency",
                        "Dimensions": [
                            {"Name": "Provider", "Value": self.provider},
                        ],
                        "Timestamp": m.timestamp,
                        "Value": m.latency_ms,
                        "Unit": "Milliseconds",
                    }
                )

                # Success/Failure metric
                metric_data.append(
                    {
                        "MetricName": f"{m.operation}Success",
                        "Dimensions": [
                            {"Name": "Provider", "Value": self.provider},
                        ],
                        "Timestamp": m.timestamp,
                        "Value": 1 if m.success else 0,
                        "Unit": "Count",
                    }
                )

                # Error type metric (if failed)
                if not m.success and m.error_type:
                    metric_data.append(
                        {
                            "MetricName": f"{m.operation}Error",
                            "Dimensions": [
                                {"Name": "Provider", "Value": self.provider},
                                {"Name": "ErrorType", "Value": m.error_type},
                            ],
                            "Timestamp": m.timestamp,
                            "Value": 1,
                            "Unit": "Count",
                        }
                    )

            # Batch put (max 1000 per call)
            for i in range(0, len(metric_data), 1000):
                batch = metric_data[i : i + 1000]
                await client.put_metric_data(
                    Namespace=CLOUDWATCH_NAMESPACE,
                    MetricData=batch,
                )

            logger.debug("Flushed %d metrics to CloudWatch", len(metrics))

        except Exception as e:
            logger.warning("CloudWatch flush failed: %s", e)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get local statistics summary.

        Returns:
            Dict with per-operation stats
        """
        result = {}
        for op, stats in self._local_stats.items():
            count = stats["count"]
            success_count = stats["success_count"]
            result[op] = {
                "count": count,
                "success_rate": success_count / count if count > 0 else 1.0,
                "avg_latency_ms": (stats["total_latency_ms"] / count if count > 0 else 0),
                "min_latency_ms": (stats["min_latency_ms"] if count > 0 else 0),
                "max_latency_ms": stats["max_latency_ms"],
            }
        return {
            "provider": self.provider,
            "cloudwatch_enabled": self._push_enabled,
            "operations": result,
        }

    async def close(self) -> None:
        """Flush remaining metrics and close client."""
        if self._push_enabled:
            await self._flush_to_cloudwatch()

        if self._cloudwatch_client:
            await self._cloudwatch_client.__aexit__(None, None, None)
            self._cloudwatch_client = None


# Singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(provider: str = "chromadb", region: str = "us-east-1") -> MetricsCollector:
    """
    Get or create the singleton metrics collector.

    Args:
        provider: Memory provider type
        region: AWS region

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(provider=provider, region=region)
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset the singleton (for testing)."""
    global _metrics_collector
    _metrics_collector = None
