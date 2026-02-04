"""Tests for input validation module."""

from __future__ import annotations

import pytest

from src.error_handler import DataValidationError
from src.validators import (
    Validator,
    sanitize_filename,
    validate_choice,
    validate_dict_structure,
    validate_email,
    validate_json_serializable,
    validate_notion_id,
    validate_positive_int,
    validate_slack_channel_id,
    validate_string_length,
    validate_url,
)


class TestValidateUrl:
    """Test URL validation."""

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        url = validate_url("http://example.com")
        assert url == "http://example.com"

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        url = validate_url("https://example.com/path")
        assert url == "https://example.com/path"

    def test_require_https(self):
        """Test requiring HTTPS."""
        with pytest.raises(DataValidationError, match="must use HTTPS"):
            validate_url("http://example.com", require_https=True)

    def test_missing_protocol(self):
        """Test URL without protocol."""
        with pytest.raises(DataValidationError, match="must include a protocol"):
            validate_url("example.com")

    def test_empty_url(self):
        """Test empty URL."""
        with pytest.raises(DataValidationError, match="cannot be empty"):
            validate_url("")


class TestValidateEmail:
    """Test email validation."""

    def test_valid_email(self):
        """Test valid email."""
        email = validate_email("user@example.com")
        assert email == "user@example.com"

    def test_email_normalized_to_lowercase(self):
        """Test email is normalized to lowercase."""
        email = validate_email("User@Example.COM")
        assert email == "user@example.com"

    def test_invalid_email_no_at(self):
        """Test invalid email without @."""
        with pytest.raises(DataValidationError, match="Invalid email"):
            validate_email("invalid.email.com")

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        with pytest.raises(DataValidationError, match="Invalid email"):
            validate_email("user@")

    def test_empty_email(self):
        """Test empty email."""
        with pytest.raises(DataValidationError, match="cannot be empty"):
            validate_email("")


class TestValidateSlackChannelId:
    """Test Slack channel ID validation."""

    def test_valid_channel_id(self):
        """Test valid channel ID."""
        channel_id = validate_slack_channel_id("C1234567890")
        assert channel_id == "C1234567890"

    def test_valid_dm_id(self):
        """Test valid DM ID."""
        dm_id = validate_slack_channel_id("D1234567890")
        assert dm_id == "D1234567890"

    def test_invalid_prefix(self):
        """Test invalid prefix."""
        with pytest.raises(DataValidationError, match="Invalid Slack channel ID"):
            validate_slack_channel_id("X1234567890")

    def test_too_short(self):
        """Test ID too short."""
        with pytest.raises(DataValidationError, match="Invalid Slack channel ID"):
            validate_slack_channel_id("C123")


class TestValidateNotionId:
    """Test Notion ID validation."""

    def test_valid_notion_id(self):
        """Test valid Notion ID."""
        notion_id = validate_notion_id("a" * 32)
        assert notion_id == "a" * 32

    def test_notion_id_with_dashes(self):
        """Test Notion ID with dashes."""
        notion_id = validate_notion_id("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert notion_id == "a" * 8 + "b" * 4 + "c" * 4 + "d" * 4 + "e" * 12

    def test_invalid_length(self):
        """Test invalid length."""
        with pytest.raises(DataValidationError, match="must be 32 characters"):
            validate_notion_id("abc123")

    def test_invalid_characters(self):
        """Test invalid characters."""
        with pytest.raises(DataValidationError, match="hexadecimal characters"):
            validate_notion_id("g" * 32)


class TestValidatePositiveInt:
    """Test positive integer validation."""

    def test_valid_positive_int(self):
        """Test valid positive integer."""
        value = validate_positive_int(5)
        assert value == 5

    def test_string_number(self):
        """Test string that can be converted to int."""
        value = validate_positive_int("10")
        assert value == 10

    def test_zero_invalid_by_default(self):
        """Test zero is invalid by default."""
        with pytest.raises(DataValidationError, match="must be at least 1"):
            validate_positive_int(0)

    def test_zero_valid_with_min_value(self):
        """Test zero is valid with min_value=0."""
        value = validate_positive_int(0, min_value=0)
        assert value == 0

    def test_negative_invalid(self):
        """Test negative number."""
        with pytest.raises(DataValidationError, match="must be at least"):
            validate_positive_int(-5)

    def test_non_numeric_string(self):
        """Test non-numeric string."""
        with pytest.raises(DataValidationError, match="must be an integer"):
            validate_positive_int("abc")


class TestValidateStringLength:
    """Test string length validation."""

    def test_valid_string(self):
        """Test valid string."""
        value = validate_string_length("hello", min_length=1, max_length=10)
        assert value == "hello"

    def test_too_short(self):
        """Test string too short."""
        with pytest.raises(DataValidationError, match="must be at least"):
            validate_string_length("hi", min_length=5)

    def test_too_long(self):
        """Test string too long."""
        with pytest.raises(DataValidationError, match="must be at most"):
            validate_string_length("hello world", max_length=5)

    def test_not_a_string(self):
        """Test non-string value."""
        with pytest.raises(DataValidationError, match="must be a string"):
            validate_string_length(123)


class TestValidateChoice:
    """Test choice validation."""

    def test_valid_choice(self):
        """Test valid choice."""
        value = validate_choice("a", ["a", "b", "c"])
        assert value == "a"

    def test_invalid_choice(self):
        """Test invalid choice."""
        with pytest.raises(DataValidationError, match="must be one of"):
            validate_choice("d", ["a", "b", "c"])


class TestValidateDictStructure:
    """Test dictionary structure validation."""

    def test_valid_structure(self):
        """Test valid structure."""
        data = {"required1": "a", "required2": "b"}
        result = validate_dict_structure(data, ["required1", "required2"])
        assert result == data

    def test_missing_required_field(self):
        """Test missing required field."""
        data = {"required1": "a"}
        with pytest.raises(DataValidationError, match="Missing required fields"):
            validate_dict_structure(data, ["required1", "required2"])

    def test_unexpected_field(self):
        """Test unexpected field."""
        data = {"required1": "a", "unexpected": "x"}
        with pytest.raises(DataValidationError, match="Unexpected fields"):
            validate_dict_structure(data, ["required1"], optional_fields=[])

    def test_optional_fields(self):
        """Test optional fields are allowed."""
        data = {"required1": "a", "optional1": "x"}
        result = validate_dict_structure(data, ["required1"], optional_fields=["optional1"])
        assert result == data


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_safe_filename(self):
        """Test already safe filename."""
        result = sanitize_filename("report_2024.txt")
        assert result == "report_2024.txt"

    def test_spaces_replaced(self):
        """Test spaces are replaced."""
        result = sanitize_filename("my report.txt")
        assert result == "my_report.txt"

    def test_special_chars_removed(self):
        """Test special characters are removed."""
        result = sanitize_filename("file@#$%name.txt")
        assert result == "file____name.txt"

    def test_too_long_truncated(self):
        """Test long filename is truncated."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_empty_after_sanitize(self):
        """Test filename that's empty after sanitization."""
        with pytest.raises(DataValidationError, match="only invalid characters"):
            sanitize_filename("@#$%")


class TestValidateJsonSerializable:
    """Test JSON serialization validation."""

    def test_dict_serializable(self):
        """Test dictionary is serializable."""
        data = {"key": "value", "number": 123}
        result = validate_json_serializable(data)
        assert result == data

    def test_list_serializable(self):
        """Test list is serializable."""
        data = [1, 2, 3, "a", "b"]
        result = validate_json_serializable(data)
        assert result == data

    def test_non_serializable(self):
        """Test non-serializable object."""

        class NotSerializable:
            pass

        with pytest.raises(DataValidationError, match="not JSON serializable"):
            validate_json_serializable(NotSerializable())


class TestValidatorChaining:
    """Test chainable Validator class."""

    def test_valid_chain(self):
        """Test valid validation chain."""
        value = Validator("hello", "name").is_required().is_string().min_length(3).max_length(10).validate()

        assert value == "hello"

    def test_required_fails(self):
        """Test required validation fails."""
        with pytest.raises(DataValidationError, match="Validation failed"):
            Validator("", "name").is_required().validate()

    def test_multiple_errors(self):
        """Test multiple validation errors."""
        with pytest.raises(DataValidationError) as exc_info:
            Validator("hi", "name").is_required().min_length(5).validate()

        # Check that the details contain the error information
        assert exc_info.value.details is not None
        assert "errors" in exc_info.value.details

    def test_pattern_matching(self):
        """Test pattern matching."""
        value = (
            Validator("test@example.com", "email")
            .is_string()
            .matches_pattern(r"^[a-z]+@[a-z]+\.[a-z]+$", "email format")
            .validate()
        )

        assert value == "test@example.com"

    def test_is_one_of(self):
        """Test is_one_of validation."""
        value = Validator("option1", "choice").is_one_of(["option1", "option2", "option3"]).validate()

        assert value == "option1"
