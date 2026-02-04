"""
Input Validation Helpers
Provides validation functions for user inputs, API responses, and data structures.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from src.error_handler import DataValidationError


def validate_url(url: str, require_https: bool = False) -> str:
    """
    Validate and normalize a URL.

    Args:
        url: URL to validate
        require_https: Whether to require HTTPS protocol

    Returns:
        Normalized URL

    Raises:
        DataValidationError: If URL is invalid
    """
    if not url or not isinstance(url, str):
        raise DataValidationError("URL cannot be empty", details={"url": url})

    try:
        parsed = urlparse(url)

        if not parsed.scheme:
            raise DataValidationError("URL must include a protocol (http:// or https://)", details={"url": url})

        if require_https and parsed.scheme != "https":
            raise DataValidationError("URL must use HTTPS protocol", details={"url": url, "scheme": parsed.scheme})

        if not parsed.netloc:
            raise DataValidationError("URL must include a domain", details={"url": url})

        return url

    except Exception as e:
        if isinstance(e, DataValidationError):
            raise
        raise DataValidationError(f"Invalid URL format: {e}", details={"url": url})


def validate_email(email: str) -> str:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        Normalized email (lowercase)

    Raises:
        DataValidationError: If email is invalid
    """
    if not email or not isinstance(email, str):
        raise DataValidationError("Email cannot be empty", details={"email": email})

    # Basic email regex
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(pattern, email):
        raise DataValidationError("Invalid email format", details={"email": email})

    return email.lower()


def validate_slack_channel_id(channel_id: str) -> str:
    """
    Validate Slack channel ID format.

    Args:
        channel_id: Slack channel ID (should start with C or D)

    Returns:
        Validated channel ID

    Raises:
        DataValidationError: If channel ID is invalid
    """
    if not channel_id or not isinstance(channel_id, str):
        raise DataValidationError("Channel ID cannot be empty", details={"channel_id": channel_id})

    # Slack channel IDs start with C (channel) or D (DM) followed by alphanumeric
    pattern = r"^[CD][A-Z0-9]{8,}$"

    if not re.match(pattern, channel_id):
        raise DataValidationError(
            "Invalid Slack channel ID format (should start with C or D)",
            details={"channel_id": channel_id, "pattern": pattern},
        )

    return channel_id


def validate_notion_id(notion_id: str, id_type: str = "page") -> str:
    """
    Validate Notion ID format (page, database, block, etc.).

    Args:
        notion_id: Notion ID (32 hex characters, may include dashes)
        id_type: Type of Notion object (for error messages)

    Returns:
        Normalized Notion ID (without dashes)

    Raises:
        DataValidationError: If Notion ID is invalid
    """
    if not notion_id or not isinstance(notion_id, str):
        raise DataValidationError(f"Notion {id_type} ID cannot be empty", details={"notion_id": notion_id})

    # Remove dashes
    normalized = notion_id.replace("-", "")

    # Should be exactly 32 hex characters
    if len(normalized) != 32:
        raise DataValidationError(
            f"Notion {id_type} ID must be 32 characters (got {len(normalized)})",
            details={"notion_id": notion_id, "normalized": normalized},
        )

    if not re.match(r"^[a-f0-9]{32}$", normalized):
        raise DataValidationError(
            f"Notion {id_type} ID must contain only hexadecimal characters",
            details={"notion_id": notion_id, "normalized": normalized},
        )

    return normalized


def validate_positive_int(value: Any, name: str = "value", min_value: int = 1) -> int:
    """
    Validate that a value is a positive integer.

    Args:
        value: Value to validate
        name: Name of the value (for error messages)
        min_value: Minimum allowed value (default: 1)

    Returns:
        Validated integer

    Raises:
        DataValidationError: If value is not a positive integer
    """
    try:
        int_value = int(value)
    except (TypeError, ValueError) as e:
        raise DataValidationError(f"{name} must be an integer", details={"value": value, "error": str(e)})

    if int_value < min_value:
        raise DataValidationError(
            f"{name} must be at least {min_value}",
            details={"value": int_value, "min_value": min_value},
        )

    return int_value


def validate_string_length(value: str, name: str = "value", min_length: int = 1, max_length: int | None = None) -> str:
    """
    Validate string length.

    Args:
        value: String to validate
        name: Name of the value (for error messages)
        min_length: Minimum length (default: 1)
        max_length: Maximum length (optional)

    Returns:
        Validated string

    Raises:
        DataValidationError: If string length is invalid
    """
    if not isinstance(value, str):
        raise DataValidationError(f"{name} must be a string", details={"value": value, "type": type(value).__name__})

    if len(value) < min_length:
        raise DataValidationError(
            f"{name} must be at least {min_length} characters",
            details={"value": value, "length": len(value), "min_length": min_length},
        )

    if max_length is not None and len(value) > max_length:
        raise DataValidationError(
            f"{name} must be at most {max_length} characters",
            details={"value": value, "length": len(value), "max_length": max_length},
        )

    return value


def validate_choice(value: Any, choices: list[Any], name: str = "value") -> Any:
    """
    Validate that a value is one of the allowed choices.

    Args:
        value: Value to validate
        choices: List of allowed values
        name: Name of the value (for error messages)

    Returns:
        Validated value

    Raises:
        DataValidationError: If value is not in choices
    """
    if value not in choices:
        raise DataValidationError(
            f"{name} must be one of: {', '.join(str(c) for c in choices)}",
            details={"value": value, "choices": choices},
        )

    return value


def validate_dict_structure(
    data: dict[str, Any], required_fields: list[str], optional_fields: list[str] | None = None
) -> dict[str, Any]:
    """
    Validate dictionary has required structure.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        optional_fields: List of optional field names

    Returns:
        Validated dictionary

    Raises:
        DataValidationError: If structure is invalid
    """
    if not isinstance(data, dict):
        raise DataValidationError("Data must be a dictionary", details={"type": type(data).__name__})

    # Check required fields
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise DataValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields, "data_keys": list(data.keys())},
        )

    # Check for unexpected fields
    if optional_fields is not None:
        allowed_fields = set(required_fields + optional_fields)
        unexpected_fields = [field for field in data.keys() if field not in allowed_fields]
        if unexpected_fields:
            raise DataValidationError(
                f"Unexpected fields: {', '.join(unexpected_fields)}",
                details={"unexpected_fields": unexpected_fields, "allowed_fields": list(allowed_fields)},
            )

    return data


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe filesystem usage.

    Args:
        filename: Original filename
        max_length: Maximum length (default: 255)

    Returns:
        Sanitized filename

    Raises:
        DataValidationError: If filename cannot be sanitized
    """
    if not filename:
        raise DataValidationError("Filename cannot be empty")

    # Remove or replace unsafe characters
    # Keep alphanumeric, dash, underscore, dot
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Remove leading/trailing dots, spaces, and underscores
    sanitized = sanitized.strip(". _")

    # Ensure it's not empty after sanitization
    if not sanitized or sanitized == "":
        raise DataValidationError("Filename contains only invalid characters", details={"original": filename})

    # Truncate if too long (preserve extension if possible)
    if len(sanitized) > max_length:
        if "." in sanitized:
            name, ext = sanitized.rsplit(".", 1)
            max_name_len = max_length - len(ext) - 1
            sanitized = f"{name[:max_name_len]}.{ext}"
        else:
            sanitized = sanitized[:max_length]

    return sanitized


def validate_json_serializable(data: Any, name: str = "data") -> Any:
    """
    Validate that data is JSON serializable.

    Args:
        data: Data to validate
        name: Name of the data (for error messages)

    Returns:
        Validated data

    Raises:
        DataValidationError: If data is not JSON serializable
    """
    import json

    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError) as e:
        raise DataValidationError(
            f"{name} is not JSON serializable", details={"error": str(e), "type": type(data).__name__}
        )


class Validator:
    """Chainable validator for complex validation scenarios."""

    def __init__(self, value: Any, name: str = "value"):
        self.value = value
        self.name = name
        self.errors: list[str] = []

    def is_required(self) -> Validator:
        """Validate value is not None or empty."""
        if self.value is None or (isinstance(self.value, str) and not self.value.strip()):
            self.errors.append(f"{self.name} is required")
        return self

    def is_string(self) -> Validator:
        """Validate value is a string."""
        if not isinstance(self.value, str):
            self.errors.append(f"{self.name} must be a string")
        return self

    def min_length(self, length: int) -> Validator:
        """Validate minimum length."""
        if isinstance(self.value, (str, list, dict)) and len(self.value) < length:
            self.errors.append(f"{self.name} must be at least {length} characters/items")
        return self

    def max_length(self, length: int) -> Validator:
        """Validate maximum length."""
        if isinstance(self.value, (str, list, dict)) and len(self.value) > length:
            self.errors.append(f"{self.name} must be at most {length} characters/items")
        return self

    def matches_pattern(self, pattern: str, description: str = "") -> Validator:
        """Validate value matches regex pattern."""
        if isinstance(self.value, str) and not re.match(pattern, self.value):
            msg = f"{self.name} has invalid format"
            if description:
                msg += f" ({description})"
            self.errors.append(msg)
        return self

    def is_one_of(self, choices: list[Any]) -> Validator:
        """Validate value is one of the choices."""
        if self.value not in choices:
            self.errors.append(f"{self.name} must be one of: {', '.join(str(c) for c in choices)}")
        return self

    def validate(self) -> Any:
        """
        Perform validation and return value or raise error.

        Returns:
            Validated value

        Raises:
            DataValidationError: If validation fails
        """
        if self.errors:
            raise DataValidationError(
                f"Validation failed for {self.name}",
                details={"errors": self.errors, "value": str(self.value)[:100]},
            )
        return self.value
