"""
Health Check System
Provides system health monitoring and status checks.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    details: dict[str, Any] | None = None


class HealthChecker:
    """System health checker."""

    def __init__(self):
        self.checks: dict[str, Callable[[], HealthCheckResult]] = {}
        self.last_results: dict[str, HealthCheckResult] = {}

    def register_check(self, name: str, check_func: Callable[[], HealthCheckResult]) -> None:
        """Register a health check function."""
        self.checks[name] = check_func

    def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self.checks:
            return HealthCheckResult(
                name=name, status=HealthStatus.UNHEALTHY, message=f"Check '{name}' not found", timestamp=datetime.now()
            )

        try:
            result = self.checks[name]()
            self.last_results[name] = result
            return result
        except Exception as e:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e}",
                timestamp=datetime.now(),
            )
            self.last_results[name] = result
            return result

    def run_all_checks(self) -> dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}
        for name in self.checks:
            results[name] = self.run_check(name)
        return results

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.last_results:
            self.run_all_checks()

        if not self.last_results:
            return HealthStatus.UNHEALTHY

        statuses = [r.status for r in self.last_results.values()]

        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_summary(self) -> str:
        """Get formatted health check summary."""
        lines = ["System Health Check", "=" * 60]

        overall = self.get_overall_status()
        status_symbol = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}

        lines.append(f"\nOverall Status: {status_symbol.get(overall.value, '?')} {overall.value.upper()}")
        lines.append("")

        if not self.last_results:
            lines.append("No health checks have been run yet.")
            return "\n".join(lines)

        lines.append("Individual Checks:")
        lines.append("-" * 60)

        for name, result in self.last_results.items():
            symbol = status_symbol.get(result.status.value, "?")
            lines.append(f"{symbol} {name}: {result.status.value.upper()}")
            lines.append(f"   {result.message}")
            if result.details:
                for key, value in result.details.items():
                    lines.append(f"   {key}: {value}")

        return "\n".join(lines)


# Built-in health checks
def check_environment_variables() -> HealthCheckResult:
    """Check required environment variables are set."""
    required_vars = ["SLACK_BOT_TOKEN", "NOTION_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if not missing:
        return HealthCheckResult(
            name="environment",
            status=HealthStatus.HEALTHY,
            message="All required environment variables are set",
            timestamp=datetime.now(),
        )
    else:
        return HealthCheckResult(
            name="environment",
            status=HealthStatus.UNHEALTHY,
            message=f"Missing required environment variables: {', '.join(missing)}",
            timestamp=datetime.now(),
            details={"missing": missing},
        )


def check_config_files() -> HealthCheckResult:
    """Check configuration files exist."""
    from pathlib import Path

    config_dir = Path("config")
    required_files = ["config.json"]

    missing = [f for f in required_files if not (config_dir / f).exists()]

    if not missing:
        return HealthCheckResult(
            name="config_files",
            status=HealthStatus.HEALTHY,
            message="All configuration files present",
            timestamp=datetime.now(),
        )
    else:
        return HealthCheckResult(
            name="config_files",
            status=HealthStatus.DEGRADED,
            message=f"Missing configuration files: {', '.join(missing)}",
            timestamp=datetime.now(),
            details={"missing": missing},
        )


# Global health checker
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """Get or create global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
        # Register built-in checks
        _health_checker.register_check("environment", check_environment_variables)
        _health_checker.register_check("config_files", check_config_files)
    return _health_checker
