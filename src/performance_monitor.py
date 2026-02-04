"""
Performance Monitoring Module
Tracks metrics, timing, and performance statistics across the application.
"""

from __future__ import annotations

import functools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class PerformanceMetric:
    """Represents a single performance metric."""

    name: str
    duration_ms: float
    timestamp: datetime
    success: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class PerformanceMonitor:
    """Monitor and track performance metrics."""

    def __init__(self):
        self.metrics: list[PerformanceMetric] = []
        self.operation_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_duration_ms": 0.0,
                "min_duration_ms": float("inf"),
                "max_duration_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
            }
        )
        self._slow_operation_threshold_ms = 5000.0  # 5 seconds

    def record_metric(
        self,
        name: str,
        duration_ms: float,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        Record a performance metric.

        Args:
            name: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether the operation succeeded
            metadata: Additional metadata
            error: Error message if operation failed
        """
        metric = PerformanceMetric(
            name=name,
            duration_ms=duration_ms,
            timestamp=datetime.now(),
            success=success,
            metadata=metadata or {},
            error=error,
        )

        self.metrics.append(metric)

        # Update statistics
        stats = self.operation_stats[name]
        stats["count"] += 1
        stats["total_duration_ms"] += duration_ms
        stats["min_duration_ms"] = min(stats["min_duration_ms"], duration_ms)
        stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)

        if success:
            stats["success_count"] += 1
        else:
            stats["error_count"] += 1

        # Log slow operations
        if duration_ms > self._slow_operation_threshold_ms:
            logger.warning(
                "Slow operation detected: %s took %.2fms (threshold: %.2fms)",
                name,
                duration_ms,
                self._slow_operation_threshold_ms,
                extra={"operation": name, "duration_ms": duration_ms, "metadata": metadata},
            )

    def get_stats(self, operation_name: str | None = None) -> dict[str, Any]:
        """
        Get performance statistics.

        Args:
            operation_name: Specific operation to get stats for (None for all)

        Returns:
            Statistics dictionary
        """
        if operation_name:
            if operation_name not in self.operation_stats:
                return {}

            stats = self.operation_stats[operation_name].copy()
            if stats["count"] > 0:
                stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
                stats["success_rate"] = stats["success_count"] / stats["count"]
            return stats

        # Return all stats
        all_stats = {}
        for name, stats in self.operation_stats.items():
            all_stats[name] = stats.copy()
            if stats["count"] > 0:
                all_stats[name]["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
                all_stats[name]["success_rate"] = stats["success_count"] / stats["count"]

        return all_stats

    def get_recent_metrics(self, limit: int = 100, operation_name: str | None = None) -> list[PerformanceMetric]:
        """
        Get recent performance metrics.

        Args:
            limit: Maximum number of metrics to return
            operation_name: Filter by operation name

        Returns:
            List of recent metrics
        """
        metrics = self.metrics

        if operation_name:
            metrics = [m for m in metrics if m.name == operation_name]

        return metrics[-limit:]

    def get_slow_operations(self, threshold_ms: float | None = None) -> list[PerformanceMetric]:
        """
        Get operations that exceeded the slow threshold.

        Args:
            threshold_ms: Custom threshold (uses default if None)

        Returns:
            List of slow operations
        """
        threshold = threshold_ms if threshold_ms is not None else self._slow_operation_threshold_ms
        return [m for m in self.metrics if m.duration_ms > threshold]

    def set_slow_threshold(self, threshold_ms: float) -> None:
        """Set the threshold for slow operation warnings."""
        self._slow_operation_threshold_ms = threshold_ms

    def clear_metrics(self) -> None:
        """Clear all recorded metrics and statistics."""
        self.metrics.clear()
        self.operation_stats.clear()

    def get_summary(self) -> str:
        """
        Get a human-readable summary of performance metrics.

        Returns:
            Formatted summary string
        """
        if not self.operation_stats:
            return "No performance metrics recorded"

        lines = ["Performance Summary:", "=" * 60]

        total_operations = sum(s["count"] for s in self.operation_stats.values())
        total_errors = sum(s["error_count"] for s in self.operation_stats.values())
        slow_ops = self.get_slow_operations()

        lines.append(f"Total Operations: {total_operations}")
        lines.append(f"Total Errors: {total_errors}")
        lines.append(f"Slow Operations (>{self._slow_operation_threshold_ms}ms): {len(slow_ops)}")
        lines.append("")

        # Sort by total time spent
        sorted_ops = sorted(self.operation_stats.items(), key=lambda x: x[1]["total_duration_ms"], reverse=True)

        lines.append("Top Operations by Time:")
        lines.append("-" * 60)
        lines.append(f"{'Operation':<30} {'Count':>8} {'Avg(ms)':>10} {'Total(ms)':>12}")
        lines.append("-" * 60)

        for name, stats in sorted_ops[:10]:  # Top 10
            if stats["count"] > 0:
                avg = stats["total_duration_ms"] / stats["count"]
                lines.append(f"{name:<30} {stats['count']:>8} {avg:>10.2f} {stats['total_duration_ms']:>12.2f}")

        return "\n".join(lines)


# Global performance monitor instance
_monitor: PerformanceMonitor | None = None


def get_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


def track_performance(
    operation_name: str | None = None, track_args: bool = False, log_result: bool = False
) -> Callable[[F], F]:
    """
    Decorator to track performance of a function.

    Args:
        operation_name: Custom operation name (uses function name if None)
        track_args: Whether to include function arguments in metadata
        log_result: Whether to log the result

    Example:
        @track_performance("api_call")
        def call_slack_api():
            return api.call()
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = operation_name or func.__name__
            monitor = get_monitor()

            metadata: dict[str, Any] = {}
            if track_args:
                metadata["args"] = str(args)[:100]  # Truncate for safety
                metadata["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}

            start_time = time.perf_counter()
            error_msg = None
            success = True

            try:
                result = func(*args, **kwargs)

                if log_result:
                    metadata["result"] = str(result)[:100]

                return result

            except Exception as e:
                success = False
                error_msg = f"{type(e).__name__}: {str(e)}"
                raise

            finally:
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000

                monitor.record_metric(
                    name=name, duration_ms=duration_ms, success=success, metadata=metadata, error=error_msg
                )

                if duration_ms > 1000:  # Log operations over 1 second
                    logger.info(
                        "Operation %s completed in %.2fms",
                        name,
                        duration_ms,
                        extra={"operation": name, "duration_ms": duration_ms},
                    )

        return wrapper  # type: ignore

    return decorator


class PerformanceTimer:
    """Context manager for timing code blocks."""

    def __init__(self, operation_name: str, metadata: dict[str, Any] | None = None):
        self.operation_name = operation_name
        self.metadata = metadata or {}
        self.start_time: float = 0
        self.duration_ms: float = 0

    def __enter__(self) -> PerformanceTimer:
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and record metric."""
        end_time = time.perf_counter()
        self.duration_ms = (end_time - self.start_time) * 1000

        success = exc_type is None
        error_msg = f"{exc_type.__name__}: {exc_val}" if exc_type else None

        monitor = get_monitor()
        monitor.record_metric(
            name=self.operation_name,
            duration_ms=self.duration_ms,
            success=success,
            metadata=self.metadata,
            error=error_msg,
        )


# Convenience function for one-off timing
def time_operation(operation_name: str, metadata: dict[str, Any] | None = None) -> PerformanceTimer:
    """
    Create a performance timer for a code block.

    Example:
        with time_operation("database_query"):
            results = db.query()
    """
    return PerformanceTimer(operation_name, metadata)
