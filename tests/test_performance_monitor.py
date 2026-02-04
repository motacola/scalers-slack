"""Tests for performance monitoring module."""

from __future__ import annotations

import time

import pytest

from src.performance_monitor import (
    PerformanceMonitor,
    get_monitor,
    time_operation,
    track_performance,
)


class TestPerformanceMonitor:
    """Test PerformanceMonitor class."""

    def test_record_metric(self):
        """Test recording a metric."""
        monitor = PerformanceMonitor()
        monitor.record_metric("test_operation", 100.0, success=True)

        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].name == "test_operation"
        assert monitor.metrics[0].duration_ms == 100.0
        assert monitor.metrics[0].success is True

    def test_get_stats(self):
        """Test getting statistics."""
        monitor = PerformanceMonitor()
        monitor.record_metric("test_op", 100.0, success=True)
        monitor.record_metric("test_op", 200.0, success=True)
        monitor.record_metric("test_op", 150.0, success=False)

        stats = monitor.get_stats("test_op")

        assert stats["count"] == 3
        assert stats["success_count"] == 2
        assert stats["error_count"] == 1
        assert stats["avg_duration_ms"] == 150.0
        assert stats["min_duration_ms"] == 100.0
        assert stats["max_duration_ms"] == 200.0

    def test_get_recent_metrics(self):
        """Test getting recent metrics."""
        monitor = PerformanceMonitor()

        for i in range(10):
            monitor.record_metric(f"op_{i}", float(i * 10))

        recent = monitor.get_recent_metrics(limit=5)

        assert len(recent) == 5
        assert recent[-1].name == "op_9"

    def test_get_slow_operations(self):
        """Test detecting slow operations."""
        monitor = PerformanceMonitor()
        monitor.set_slow_threshold(100.0)

        monitor.record_metric("fast_op", 50.0)
        monitor.record_metric("slow_op", 150.0)
        monitor.record_metric("very_slow_op", 500.0)

        slow_ops = monitor.get_slow_operations()

        assert len(slow_ops) == 2
        assert all(m.duration_ms > 100.0 for m in slow_ops)

    def test_clear_metrics(self):
        """Test clearing metrics."""
        monitor = PerformanceMonitor()
        monitor.record_metric("test", 100.0)

        monitor.clear_metrics()

        assert len(monitor.metrics) == 0
        assert len(monitor.operation_stats) == 0

    def test_get_summary(self):
        """Test getting summary string."""
        monitor = PerformanceMonitor()
        monitor.record_metric("api_call", 150.0, success=True)
        monitor.record_metric("database_query", 50.0, success=True)

        summary = monitor.get_summary()

        assert "Performance Summary" in summary
        assert "Total Operations: 2" in summary
        assert "api_call" in summary or "database_query" in summary


class TestTrackPerformanceDecorator:
    """Test track_performance decorator."""

    def test_decorator_tracks_timing(self):
        """Test decorator tracks function timing."""
        monitor = PerformanceMonitor()

        @track_performance("test_function")
        def slow_function():
            time.sleep(0.01)  # 10ms
            return "result"

        # Manually inject monitor for testing
        import src.performance_monitor

        src.performance_monitor._monitor = monitor

        result = slow_function()

        assert result == "result"
        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].name == "test_function"
        assert monitor.metrics[0].duration_ms >= 10.0

    def test_decorator_tracks_errors(self):
        """Test decorator tracks errors."""
        monitor = PerformanceMonitor()

        @track_performance("failing_function")
        def failing_function():
            raise ValueError("Test error")

        import src.performance_monitor

        src.performance_monitor._monitor = monitor

        with pytest.raises(ValueError):
            failing_function()

        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].success is False
        assert "ValueError" in monitor.metrics[0].error or ""

    def test_decorator_with_args(self):
        """Test decorator tracks arguments."""
        monitor = PerformanceMonitor()

        @track_performance("function_with_args", track_args=True)
        def function_with_args(x, y=10):
            return x + y

        import src.performance_monitor

        src.performance_monitor._monitor = monitor

        result = function_with_args(5, y=20)

        assert result == 25
        assert len(monitor.metrics) == 1
        assert "args" in monitor.metrics[0].metadata


class TestPerformanceTimer:
    """Test PerformanceTimer context manager."""

    def test_timer_context_manager(self):
        """Test timer as context manager."""
        monitor = PerformanceMonitor()

        import src.performance_monitor

        src.performance_monitor._monitor = monitor

        with time_operation("timed_block"):
            time.sleep(0.01)  # 10ms

        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].name == "timed_block"
        assert monitor.metrics[0].duration_ms >= 10.0

    def test_timer_with_exception(self):
        """Test timer handles exceptions."""
        monitor = PerformanceMonitor()

        import src.performance_monitor

        src.performance_monitor._monitor = monitor

        with pytest.raises(ValueError):
            with time_operation("failing_block"):
                raise ValueError("Test error")

        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].success is False

    def test_timer_metadata(self):
        """Test timer with metadata."""
        monitor = PerformanceMonitor()

        import src.performance_monitor

        src.performance_monitor._monitor = monitor

        with time_operation("block_with_metadata", metadata={"user": "test"}):
            pass

        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].metadata["user"] == "test"


class TestGlobalMonitor:
    """Test global monitor instance."""

    def test_get_monitor_singleton(self):
        """Test global monitor is singleton."""
        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2
