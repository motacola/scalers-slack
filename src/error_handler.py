"""
Centralized Error Handling Module
Provides consistent error handling and reporting across the application.
"""

from __future__ import annotations

import functools
import logging
import sys
import traceback
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


class ScalersSlackError(Exception):
    """Base exception for all Scalers Slack errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(ScalersSlackError):
    """Raised when configuration is invalid or missing."""

    pass


class APIError(ScalersSlackError):
    """Raised when API calls fail (Slack, Notion, LLM, etc.)."""

    def __init__(
        self, message: str, api_name: str, status_code: int | None = None, details: dict[str, Any] | None = None
    ):
        super().__init__(message, details)
        self.api_name = api_name
        self.status_code = status_code


class BrowserAutomationError(ScalersSlackError):
    """Raised when browser automation fails."""

    pass


class DataValidationError(ScalersSlackError):
    """Raised when data validation fails."""

    pass


def handle_errors(
    error_types: tuple[type[Exception], ...] = (Exception,),
    default_return: Any = None,
    log_level: int = logging.ERROR,
    reraise: bool = False,
) -> Callable[[F], F]:
    """
    Decorator for handling errors in functions.

    Args:
        error_types: Tuple of exception types to catch
        default_return: Value to return on error (if not reraising)
        log_level: Logging level for errors
        reraise: Whether to reraise the exception after logging

    Example:
        @handle_errors(error_types=(ValueError, KeyError), default_return=[])
        def get_items():
            # Function that might raise ValueError or KeyError
            return items
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except error_types as e:
                logger.log(
                    log_level,
                    "Error in %s: %s",
                    func.__name__,
                    str(e),
                    exc_info=True,
                    extra={
                        "function": func.__name__,
                        "error_type": type(e).__name__,
                        "func_args": args,
                        "func_kwargs": kwargs,
                    },
                )

                if reraise:
                    raise

                return default_return

        return wrapper  # type: ignore

    return decorator


def retry_on_error(
    max_attempts: int = 3,
    error_types: tuple[type[Exception], ...] = (Exception,),
    backoff_factor: float = 1.0,
) -> Callable[[F], F]:
    """
    Decorator for retrying functions on error.

    Args:
        max_attempts: Maximum number of retry attempts
        error_types: Tuple of exception types to retry on
        backoff_factor: Multiplier for exponential backoff (seconds)

    Example:
        @retry_on_error(max_attempts=3, error_types=(APIError,), backoff_factor=2.0)
        def call_api():
            # Function that might fail and should be retried
            return api.call()
    """
    import time

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except error_types as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait_time = backoff_factor * (2 ** (attempt - 1))
                        logger.warning(
                            "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                            attempt,
                            max_attempts,
                            func.__name__,
                            str(e),
                            wait_time,
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            "All %d attempts failed for %s: %s", max_attempts, func.__name__, str(e), exc_info=True
                        )

            if last_exception:
                raise last_exception

        return wrapper  # type: ignore

    return decorator


class ErrorReporter:
    """Collects and reports errors for batch processing."""

    def __init__(self):
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def add_error(
        self,
        message: str,
        error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Add an error to the report."""
        error_info = {
            "message": message,
            "type": type(error).__name__ if error else "Unknown",
            "details": str(error) if error else "",
            "context": context or {},
        }

        if error:
            error_info["traceback"] = traceback.format_exception(type(error), error, error.__traceback__)

        self.errors.append(error_info)
        logger.error("Error: %s - %s", message, error_info["details"], extra={"context": context})

    def add_warning(self, message: str, context: dict[str, Any] | None = None) -> None:
        """Add a warning to the report."""
        warning_info = {
            "message": message,
            "context": context or {},
        }

        self.warnings.append(warning_info)
        logger.warning("Warning: %s", message, extra={"context": context})

    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were recorded."""
        return len(self.warnings) > 0

    def get_summary(self) -> str:
        """Get a summary of errors and warnings."""
        lines = []

        if self.errors:
            lines.append(f"❌ {len(self.errors)} Error(s):")
            for i, error in enumerate(self.errors, 1):
                lines.append(f"  {i}. {error['message']}")
                if error["details"]:
                    lines.append(f"     Details: {error['details']}")

        if self.warnings:
            lines.append(f"\n⚠️  {len(self.warnings)} Warning(s):")
            for i, warning in enumerate(self.warnings, 1):
                lines.append(f"  {i}. {warning['message']}")

        if not self.errors and not self.warnings:
            lines.append("✅ No errors or warnings")

        return "\n".join(lines)

    def print_summary(self) -> None:
        """Print error and warning summary to console."""
        print("\n" + "=" * 60)
        print("Error Report Summary")
        print("=" * 60)
        print(self.get_summary())
        print("=" * 60 + "\n")

    def clear(self) -> None:
        """Clear all errors and warnings."""
        self.errors.clear()
        self.warnings.clear()


def setup_exception_handler() -> None:
    """Set up global exception handler for uncaught exceptions."""

    def handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: Any) -> None:
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't handle keyboard interrupts
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        print("\n" + "=" * 60, file=sys.stderr)
        print("❌ FATAL ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Type: {exc_type.__name__}", file=sys.stderr)
        print(f"Message: {exc_value}", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)

    sys.excepthook = handle_exception


# Convenience function for common error scenarios
def validate_required_fields(data: dict[str, Any], required_fields: list[str], context: str = "") -> None:
    """
    Validate that required fields are present in data.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        context: Context string for error messages

    Raises:
        DataValidationError: If any required fields are missing
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]

    if missing_fields:
        context_str = f" in {context}" if context else ""
        raise DataValidationError(
            f"Missing required fields{context_str}: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields, "context": context, "data_keys": list(data.keys())},
        )
