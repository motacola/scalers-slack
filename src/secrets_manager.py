"""
Secrets Manager
Secure handling of sensitive configuration and API keys.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Any

from src.error_handler import ConfigurationError


class SecretsManager:
    """Manage secrets and sensitive configuration securely."""

    # Pattern to detect potential secrets in strings
    SECRET_PATTERNS = {
        "aws_key": r"AKIA[0-9A-Z]{16}",
        "api_key": r"sk-[a-zA-Z0-9]{32,}",
        "slack_bot_token": r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}",
        "slack_user_token": r"xoxp-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}",
        "github_token": r"ghp_[a-zA-Z0-9]{36,}",
        "anthropic_key": r"sk-ant-[a-zA-Z0-9\-]{95,}",
        "generic_secret": r"['\"]?secret['\"]?\s*[:=]\s*['\"]([^'\"]{20,})['\"]",
    }

    def __init__(self, env_file: str | Path | None = None):
        """
        Initialize secrets manager.

        Args:
            env_file: Path to .env file (defaults to .env in project root)
        """
        if env_file is None:
            # Default to .env in project root
            self.env_file = Path(__file__).parent.parent / ".env"
        else:
            self.env_file = Path(env_file)

        self._loaded_secrets: dict[str, str] = {}
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load secrets from .env file."""
        if not self.env_file.exists():
            warnings.warn(f".env file not found at {self.env_file}. Secrets will be loaded from environment only.")
            return

        try:
            # Try using python-dotenv if available
            from dotenv import load_dotenv

            load_dotenv(self.env_file, override=False)
        except ImportError:
            # Manual .env parsing if python-dotenv not installed
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Only set if not already in environment
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = value.strip().strip("\"'")

    def get_secret(self, key: str, required: bool = True, default: str | None = None) -> str | None:
        """
        Get a secret value from environment.

        Args:
            key: Environment variable name
            required: Whether the secret is required
            default: Default value if not found

        Returns:
            Secret value or None if not found and not required

        Raises:
            ConfigurationError: If required secret is missing
        """
        value = os.getenv(key, default)

        if value is None and required:
            raise ConfigurationError(
                f"Required secret '{key}' not found in environment",
                details={
                    "key": key,
                    "env_file": str(self.env_file),
                    "suggestion": f"Add {key}=your-value to {self.env_file}",
                },
            )

        if value:
            # Cache for later validation
            self._loaded_secrets[key] = value

        return value

    def get_slack_token(self) -> str:
        """Get Slack bot token."""
        token = self.get_secret("SLACK_BOT_TOKEN")
        if token and not token.startswith("xoxb-"):
            warnings.warn("SLACK_BOT_TOKEN doesn't start with 'xoxb-'. Expected format for bot tokens is 'xoxb-...'")
        return token or ""

    def get_notion_key(self) -> str:
        """Get Notion API key."""
        key = self.get_secret("NOTION_API_KEY")
        if key and not (key.startswith("secret_") or key.startswith("ntn_")):
            warnings.warn("NOTION_API_KEY format is unusual. Expected format is 'secret_...' or 'ntn_...'")
        return key or ""

    def get_openai_key(self) -> str | None:
        """Get OpenAI API key (optional)."""
        key = self.get_secret("OPENAI_API_KEY", required=False)
        if key and not key.startswith("sk-"):
            warnings.warn("OPENAI_API_KEY doesn't start with 'sk-'. Expected format is 'sk-...'")
        return key

    def get_anthropic_key(self) -> str | None:
        """Get Anthropic API key (optional)."""
        key = self.get_secret("ANTHROPIC_API_KEY", required=False)
        if key and not key.startswith("sk-ant-"):
            warnings.warn("ANTHROPIC_API_KEY doesn't start with 'sk-ant-'. Expected format is 'sk-ant-...'")
        return key

    def validate_secrets(self) -> list[str]:
        """
        Validate all loaded secrets.

        Returns:
            List of validation warnings
        """
        warnings_list = []

        for key, value in self._loaded_secrets.items():
            # Check if value looks like a placeholder
            if value in ["your-key-here", "changeme", "TODO", "xxx", ""]:
                warnings_list.append(f"{key} appears to be a placeholder value: '{value}'")

            # Check minimum length for API keys
            if "API_KEY" in key or "TOKEN" in key:
                if len(value) < 20:
                    warnings_list.append(f"{key} seems too short for an API key ({len(value)} chars)")

        return warnings_list

    def mask_secret(self, secret: str, show_chars: int = 4) -> str:
        """
        Mask a secret for safe display.

        Args:
            secret: The secret to mask
            show_chars: Number of characters to show at the end

        Returns:
            Masked string like "sk-***xyz"
        """
        if not secret or len(secret) <= show_chars:
            return "***"

        # Show prefix (up to first dash or 4 chars) and last few chars
        if "-" in secret:
            prefix = secret.split("-")[0] + "-"
            suffix = secret[-show_chars:]
            return f"{prefix}***{suffix}"
        else:
            suffix = secret[-show_chars:]
            return f"***{suffix}"

    def redact_secrets_in_text(self, text: str) -> str:
        """
        Redact potential secrets from text for safe logging.

        Args:
            text: Text that might contain secrets

        Returns:
            Text with secrets redacted
        """
        redacted = text

        # Redact known secrets
        for key, value in self._loaded_secrets.items():
            if value and len(value) > 10:
                redacted = redacted.replace(value, f"[REDACTED:{key}]")

        # Redact patterns that look like secrets
        for pattern_name, pattern in self.SECRET_PATTERNS.items():
            redacted = re.sub(pattern, f"[REDACTED:{pattern_name}]", redacted)

        return redacted

    @staticmethod
    def check_for_secrets_in_code(file_path: Path) -> list[tuple[int, str, str]]:
        """
        Scan a file for potential hardcoded secrets.

        Args:
            file_path: Path to file to scan

        Returns:
            List of (line_number, pattern_name, matched_text) tuples
        """
        findings: list[tuple[int, str, str]] = []

        if not file_path.exists() or file_path.suffix != ".py":
            return findings

        with open(file_path) as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue

                for pattern_name, pattern in SecretsManager.SECRET_PATTERNS.items():
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        findings.append((line_num, pattern_name, match.group(0)))

        return findings


class SecureConfig:
    """Wrapper for configuration with secret masking."""

    def __init__(self, config: dict[str, Any], secrets_manager: SecretsManager):
        self._config = config
        self._secrets = secrets_manager

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Get configuration value using dict syntax."""
        return self._config[key]

    def __repr__(self) -> str:
        """Safe representation with secrets masked."""
        safe_config: dict[str, Any] = {}
        for key, value in self._config.items():
            if isinstance(value, str) and any(
                secret_key in key.upper() for secret_key in ["KEY", "TOKEN", "SECRET", "PASSWORD"]
            ):
                safe_config[key] = self._secrets.mask_secret(value)
            elif isinstance(value, dict):
                # Recursively mask nested dicts
                safe_config[key] = self._mask_dict(value)
            else:
                safe_config[key] = value
        return f"SecureConfig({safe_config})"

    def _mask_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        """Recursively mask secrets in nested dictionaries."""
        masked: dict[str, Any] = {}
        for key, value in d.items():
            if isinstance(value, str) and any(
                secret_key in key.upper() for secret_key in ["KEY", "TOKEN", "SECRET", "PASSWORD"]
            ):
                masked[key] = self._secrets.mask_secret(value)
            elif isinstance(value, dict):
                masked[key] = self._mask_dict(value)
            else:
                masked[key] = value
        return masked


# Global instance for convenient access
_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Get or create global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager
