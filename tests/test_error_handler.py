"""Tests for error handling module."""

from __future__ import annotations

import pytest

from src.error_handler import (
    APIError,
    BrowserAutomationError,
    ConfigurationError,
    DataValidationError,
    ErrorReporter,
    ScalersSlackError,
    handle_errors,
    retry_on_error,
    validate_required_fields,
)


class TestExceptions:
    """Test custom exception classes."""

    def test_scalers_slack_error(self):
        """Test base exception."""
        error = ScalersSlackError("Test error", details={"key": "value"})
        assert str(error) == "Test error"
        assert error.details == {"key": "value"}

    def test_configuration_error(self):
        """Test configuration error."""
        error = ConfigurationError("Invalid config")
        assert isinstance(error, ScalersSlackError)
        assert str(error) == "Invalid config"

    def test_api_error(self):
        """Test API error."""
        error = APIError("API failed", api_name="Slack", status_code=500)
        assert isinstance(error, ScalersSlackError)
        assert error.api_name == "Slack"
        assert error.status_code == 500

    def test_browser_automation_error(self):
        """Test browser automation error."""
        error = BrowserAutomationError("Browser failed")
        assert isinstance(error, ScalersSlackError)

    def test_data_validation_error(self):
        """Test data validation error."""
        error = DataValidationError("Invalid data")
        assert isinstance(error, ScalersSlackError)


class TestHandleErrorsDecorator:
    """Test handle_errors decorator."""

    def test_successful_execution(self):
        """Test decorator doesn't interfere with successful execution."""

        @handle_errors()
        def successful_function():
            return "success"

        assert successful_function() == "success"

    def test_error_caught_default_return(self):
        """Test error is caught and default value returned."""

        @handle_errors(error_types=(ValueError,), default_return="default")
        def failing_function():
            raise ValueError("Test error")

        assert failing_function() == "default"

    def test_error_caught_reraise(self):
        """Test error is caught and reraised."""

        @handle_errors(error_types=(ValueError,), reraise=True)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

    def test_specific_error_types(self):
        """Test only specified error types are caught."""

        @handle_errors(error_types=(ValueError,), default_return="caught")
        def function_with_type_error():
            raise TypeError("Not caught")

        with pytest.raises(TypeError):
            function_with_type_error()


class TestRetryDecorator:
    """Test retry_on_error decorator."""

    def test_successful_on_first_try(self):
        """Test function succeeds on first try."""
        call_count = 0

        @retry_on_error(max_attempts=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_and_succeed(self):
        """Test function fails then succeeds on retry."""
        call_count = 0

        @retry_on_error(max_attempts=3, error_types=(ValueError,), backoff_factor=0.01)
        def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = eventually_successful()
        assert result == "success"
        assert call_count == 3

    def test_all_retries_fail(self):
        """Test function fails all retries."""
        call_count = 0

        @retry_on_error(max_attempts=3, error_types=(ValueError,), backoff_factor=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fails()

        assert call_count == 3


class TestErrorReporter:
    """Test ErrorReporter class."""

    def test_add_error(self):
        """Test adding an error."""
        reporter = ErrorReporter()
        reporter.add_error("Test error", ValueError("Detail"))

        assert reporter.has_errors()
        assert len(reporter.errors) == 1
        assert reporter.errors[0]["message"] == "Test error"
        assert reporter.errors[0]["type"] == "ValueError"

    def test_add_warning(self):
        """Test adding a warning."""
        reporter = ErrorReporter()
        reporter.add_warning("Test warning")

        assert reporter.has_warnings()
        assert len(reporter.warnings) == 1
        assert reporter.warnings[0]["message"] == "Test warning"

    def test_get_summary(self):
        """Test getting error summary."""
        reporter = ErrorReporter()
        reporter.add_error("Error 1", ValueError("Detail 1"))
        reporter.add_warning("Warning 1")

        summary = reporter.get_summary()
        assert "1 Error(s)" in summary
        assert "Error 1" in summary
        assert "1 Warning(s)" in summary
        assert "Warning 1" in summary

    def test_clear(self):
        """Test clearing errors and warnings."""
        reporter = ErrorReporter()
        reporter.add_error("Error")
        reporter.add_warning("Warning")

        reporter.clear()

        assert not reporter.has_errors()
        assert not reporter.has_warnings()

    def test_empty_summary(self):
        """Test summary with no errors or warnings."""
        reporter = ErrorReporter()
        summary = reporter.get_summary()
        assert "No errors or warnings" in summary


class TestValidateRequiredFields:
    """Test validate_required_fields function."""

    def test_all_fields_present(self):
        """Test validation passes when all fields present."""
        data = {"name": "Test", "email": "test@example.com"}
        validate_required_fields(data, ["name", "email"])
        # No exception should be raised

    def test_missing_field(self):
        """Test validation fails when field is missing."""
        data = {"name": "Test"}

        with pytest.raises(DataValidationError, match="Missing required fields: email"):
            validate_required_fields(data, ["name", "email"])

    def test_null_field(self):
        """Test validation fails when field is None."""
        data = {"name": "Test", "email": None}

        with pytest.raises(DataValidationError, match="Missing required fields: email"):
            validate_required_fields(data, ["name", "email"])

    def test_with_context(self):
        """Test validation error includes context."""
        data = {"name": "Test"}

        with pytest.raises(DataValidationError, match="in user data"):
            validate_required_fields(data, ["name", "email"], context="user data")
