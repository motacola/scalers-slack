"""
Enhanced Error Reporting Module
Provides detailed error analysis, reporting, and aggregation.
"""

from __future__ import annotations

import logging
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ErrorReport:
    """Detailed error report."""

    error_type: str
    message: str
    timestamp: datetime
    context: dict[str, Any] = field(default_factory=dict)
    traceback_str: str | None = None
    severity: str = "error"  # info, warning, error, critical
    resolved: bool = False
    resolution_notes: str | None = None


class ErrorAnalyzer:
    """Analyze and categorize errors."""

    def __init__(self):
        self.errors: list[ErrorReport] = []
        self.error_counts: dict[str, int] = defaultdict(int)
        self.error_patterns: dict[str, list[ErrorReport]] = defaultdict(list)

    def report_error(
        self,
        error: Exception | None = None,
        error_type: str | None = None,
        message: str | None = None,
        context: dict[str, Any] | None = None,
        severity: str = "error",
    ) -> ErrorReport:
        """
        Report an error with full context.

        Args:
            error: Exception object (if available)
            error_type: Type of error
            message: Error message
            context: Additional context
            severity: Severity level (info, warning, error, critical)

        Returns:
            Created error report
        """
        if error:
            error_type = type(error).__name__
            message = str(error)
            traceback_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            traceback_str = None

        report = ErrorReport(
            error_type=error_type or "UnknownError",
            message=message or "No message provided",
            timestamp=datetime.now(),
            context=context or {},
            traceback_str=traceback_str,
            severity=severity,
        )

        self.errors.append(report)
        self.error_counts[report.error_type] += 1
        self.error_patterns[self._categorize_error(report)].append(report)

        # Log based on severity
        log_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(severity, logging.ERROR)

        logger.log(
            log_level,
            "Error reported: %s - %s",
            report.error_type,
            report.message,
            extra={"error_report": report, "context": context},
        )

        return report

    def _categorize_error(self, report: ErrorReport) -> str:
        """Categorize error for pattern matching."""
        # Simple categorization based on error type
        if "API" in report.error_type or "HTTP" in report.error_type:
            return "api_errors"
        elif "Database" in report.error_type or "SQL" in report.error_type:
            return "database_errors"
        elif "Configuration" in report.error_type or "Config" in report.error_type:
            return "configuration_errors"
        elif "Validation" in report.error_type:
            return "validation_errors"
        elif "Browser" in report.error_type or "Automation" in report.error_type:
            return "automation_errors"
        else:
            return "other_errors"

    def get_error_summary(self) -> dict[str, Any]:
        """
        Get summary of all errors.

        Returns:
            Summary dictionary with counts and patterns
        """
        total_errors = len(self.errors)
        recent_errors = self.errors[-10:]  # Last 10

        # Get top error types
        top_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Count by severity
        severity_counts: dict[str, int] = defaultdict(int)
        for error in self.errors:
            severity_counts[error.severity] += 1

        # Count by category
        category_counts = {category: len(errors) for category, errors in self.error_patterns.items()}

        return {
            "total_errors": total_errors,
            "unresolved_errors": sum(1 for e in self.errors if not e.resolved),
            "top_error_types": dict(top_errors),
            "severity_distribution": dict(severity_counts),
            "category_distribution": category_counts,
            "recent_errors": [
                {"type": e.error_type, "message": e.message, "timestamp": e.timestamp.isoformat()}
                for e in recent_errors
            ],
        }

    def get_errors_by_type(self, error_type: str) -> list[ErrorReport]:
        """Get all errors of a specific type."""
        return [e for e in self.errors if e.error_type == error_type]

    def get_errors_by_category(self, category: str) -> list[ErrorReport]:
        """Get all errors in a category."""
        return self.error_patterns.get(category, [])

    def get_unresolved_errors(self) -> list[ErrorReport]:
        """Get all unresolved errors."""
        return [e for e in self.errors if not e.resolved]

    def mark_resolved(self, error_report: ErrorReport, resolution_notes: str) -> None:
        """Mark an error as resolved."""
        error_report.resolved = True
        error_report.resolution_notes = resolution_notes
        logger.info("Error resolved: %s - %s", error_report.error_type, resolution_notes)

    def get_formatted_report(self, include_resolved: bool = False) -> str:
        """
        Get a formatted text report.

        Args:
            include_resolved: Whether to include resolved errors

        Returns:
            Formatted report string
        """
        lines = ["Error Analysis Report", "=" * 60]

        summary = self.get_error_summary()

        lines.append(f"\nTotal Errors: {summary['total_errors']}")
        lines.append(f"Unresolved: {summary['unresolved_errors']}")
        lines.append("")

        # Severity breakdown
        lines.append("By Severity:")
        for severity, count in summary["severity_distribution"].items():
            lines.append(f"  {severity.upper()}: {count}")
        lines.append("")

        # Top error types
        lines.append("Top Error Types:")
        for error_type, count in summary["top_error_types"].items():
            lines.append(f"  {error_type}: {count} occurrences")
        lines.append("")

        # Category breakdown
        lines.append("By Category:")
        for category, count in summary["category_distribution"].items():
            lines.append(f"  {category}: {count}")
        lines.append("")

        # Recent errors
        lines.append("Recent Errors (last 10):")
        lines.append("-" * 60)

        errors_to_show = self.errors if include_resolved else self.get_unresolved_errors()
        for error in errors_to_show[-10:]:
            status = "✓ RESOLVED" if error.resolved else "✗ UNRESOLVED"
            lines.append(f"\n[{error.severity.upper()}] {error.error_type} - {status}")
            lines.append(f"  Message: {error.message}")
            lines.append(f"  Time: {error.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            if error.context:
                lines.append(f"  Context: {error.context}")
            if error.resolved and error.resolution_notes:
                lines.append(f"  Resolution: {error.resolution_notes}")

        return "\n".join(lines)

    def clear_resolved_errors(self) -> int:
        """
        Remove resolved errors from the error list.

        Returns:
            Number of errors cleared
        """
        initial_count = len(self.errors)
        self.errors = [e for e in self.errors if not e.resolved]

        # Rebuild counts and patterns
        self.error_counts.clear()
        self.error_patterns.clear()

        for error in self.errors:
            self.error_counts[error.error_type] += 1
            self.error_patterns[self._categorize_error(error)].append(error)

        cleared = initial_count - len(self.errors)
        logger.info("Cleared %d resolved errors", cleared)
        return cleared


# Global error analyzer instance
_analyzer: ErrorAnalyzer | None = None


def get_error_analyzer() -> ErrorAnalyzer:
    """Get or create global error analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ErrorAnalyzer()
    return _analyzer


def report_error(
    error: Exception | None = None,
    error_type: str | None = None,
    message: str | None = None,
    context: dict[str, Any] | None = None,
    severity: str = "error",
) -> ErrorReport:
    """
    Convenience function to report an error to the global analyzer.

    Args:
        error: Exception object
        error_type: Type of error
        message: Error message
        context: Additional context
        severity: Severity level

    Returns:
        Created error report
    """
    analyzer = get_error_analyzer()
    return analyzer.report_error(error, error_type, message, context, severity)


class ErrorContext:
    """Context manager for automatic error reporting."""

    def __init__(
        self,
        operation: str,
        severity: str = "error",
        reraise: bool = True,
        additional_context: dict[str, Any] | None = None,
    ):
        self.operation = operation
        self.severity = severity
        self.reraise = reraise
        self.additional_context = additional_context or {}

    def __enter__(self) -> ErrorContext:
        """Enter context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit context and report any errors."""
        if exc_type is not None:
            context = {"operation": self.operation, **self.additional_context}

            report_error(error=exc_val, context=context, severity=self.severity)

            # Return False to reraise, True to suppress
            return not self.reraise

        return False


def with_error_reporting(
    operation: str, severity: str = "error", additional_context: dict[str, Any] | None = None
) -> ErrorContext:
    """
    Create an error reporting context.

    Example:
        with with_error_reporting("api_call", context={"endpoint": "/users"}):
            api.call()
    """
    return ErrorContext(operation, severity, reraise=True, additional_context=additional_context)
