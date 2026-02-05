# Integrations module - shared interfaces for external systems
from .bugherd_bridge import BugHerdBridge
from .qa_bridge import QABridge

__all__ = ["BugHerdBridge", "QABridge"]
