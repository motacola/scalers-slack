"""
DEPRECATED: Use src.browser package instead.
This module is kept for backward compatibility and redirects to the new modular structure.
"""

import logging

from .browser import (
    BrowserAutomationConfig,
    BrowserSession,
    BugHerdBrowserClient,
    LoadBalancer,
    NotionBrowserClient,
    PerformanceMonitor,
    RecoveryManager,
    ScalabilityManager,
    SlackBrowserClient,
    SlackNotionCrossReferencer,
    sync_playwright,
)

logger = logging.getLogger(__name__)
logger.warning("src.browser_automation is deprecated. Please import from src.browser instead.")

__all__ = [
    "BrowserAutomationConfig",
    "BrowserSession",
    "LoadBalancer",
    "PerformanceMonitor",
    "RecoveryManager",
    "ScalabilityManager",
    "sync_playwright",
    "BugHerdBrowserClient",
    "SlackNotionCrossReferencer",
    "NotionBrowserClient",
    "SlackBrowserClient",
]
