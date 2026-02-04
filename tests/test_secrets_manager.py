"""Tests for secrets manager module."""

from __future__ import annotations

import pytest

from src.error_handler import ConfigurationError
from src.secrets_manager import SecretsManager, SecureConfig


class TestSecretsManager:
    """Test SecretsManager class."""

    def test_init_with_env_file(self, tmp_path):
        """Test initialization with custom env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=test_value\n")

        manager = SecretsManager(env_file)
        assert manager.env_file == env_file

    def test_get_secret_from_env(self, monkeypatch):
        """Test getting secret from environment."""
        monkeypatch.setenv("TEST_SECRET", "secret_value")

        manager = SecretsManager()
        value = manager.get_secret("TEST_SECRET")

        assert value == "secret_value"

    def test_get_secret_required_missing(self):
        """Test getting required secret that's missing raises error."""
        manager = SecretsManager()

        with pytest.raises(ConfigurationError, match="Required secret"):
            manager.get_secret("NONEXISTENT_SECRET", required=True)

    def test_get_secret_optional_missing(self):
        """Test getting optional secret returns None."""
        manager = SecretsManager()
        value = manager.get_secret("NONEXISTENT_SECRET", required=False)

        assert value is None

    def test_get_secret_with_default(self):
        """Test getting secret with default value."""
        manager = SecretsManager()
        value = manager.get_secret("NONEXISTENT_SECRET", required=False, default="default_value")

        assert value == "default_value"

    def test_mask_secret(self):
        """Test secret masking."""
        manager = SecretsManager()

        # Test with dashed secret (like API keys)
        masked = manager.mask_secret("sk-1234567890abcdefghijklmnop", show_chars=4)
        assert masked == "sk-***mnop"

        # Test with non-dashed secret
        masked = manager.mask_secret("abcdefghijklmnop", show_chars=4)
        assert masked == "***mnop"

        # Test short secret
        masked = manager.mask_secret("abc", show_chars=4)
        assert masked == "***"

    def test_redact_secrets_in_text(self, monkeypatch):
        """Test redacting secrets from text."""
        monkeypatch.setenv("API_KEY", "sk-test123456789")

        manager = SecretsManager()
        manager.get_secret("API_KEY")

        text = "The API key is sk-test123456789 and it should be hidden"
        redacted = manager.redact_secrets_in_text(text)

        assert "sk-test123456789" not in redacted
        assert "[REDACTED:API_KEY]" in redacted

    def test_validate_secrets_placeholder(self, monkeypatch):
        """Test validation catches placeholder values."""
        monkeypatch.setenv("TEST_API_KEY", "your-key-here")

        manager = SecretsManager()
        manager.get_secret("TEST_API_KEY")

        warnings = manager.validate_secrets()

        assert len(warnings) > 0
        assert any("placeholder" in w.lower() for w in warnings)

    def test_validate_secrets_too_short(self, monkeypatch):
        """Test validation catches suspiciously short API keys."""
        monkeypatch.setenv("TEST_API_KEY", "short")

        manager = SecretsManager()
        manager.get_secret("TEST_API_KEY")

        warnings = manager.validate_secrets()

        assert len(warnings) > 0
        assert any("too short" in w.lower() for w in warnings)

    def test_check_for_secrets_in_code(self, tmp_path):
        """Test scanning code for hardcoded secrets."""
        code_file = tmp_path / "test.py"
        code_file.write_text(
            """
# This is safe
API_KEY = os.getenv("API_KEY")

# This is NOT safe
hardcoded_key = "sk-1234567890abcdefghijklmnopqrstuv"
"""
        )

        findings = SecretsManager.check_for_secrets_in_code(code_file)

        assert len(findings) > 0
        assert any("api_key" in finding[1] for finding in findings)

    def test_get_slack_token(self, monkeypatch):
        """Test getting Slack token."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-123-456-abc")

        manager = SecretsManager()
        token = manager.get_slack_token()

        assert token == "xoxb-123-456-abc"

    def test_get_notion_key(self, monkeypatch):
        """Test getting Notion key."""
        monkeypatch.setenv("NOTION_API_KEY", "secret_abc123")

        manager = SecretsManager()
        key = manager.get_notion_key()

        assert key == "secret_abc123"

    def test_get_openai_key_optional(self):
        """Test getting OpenAI key when not set."""
        manager = SecretsManager()
        key = manager.get_openai_key()

        # Returns None when not set (optional)
        assert key is None or key == ""

    def test_get_anthropic_key_optional(self):
        """Test getting Anthropic key when not set."""
        manager = SecretsManager()
        key = manager.get_anthropic_key()

        # Returns None when not set (optional)
        assert key is None or key == ""


class TestSecureConfig:
    """Test SecureConfig class."""

    def test_get_value(self):
        """Test getting configuration value."""
        config = {"key": "value"}
        manager = SecretsManager()
        secure_config = SecureConfig(config, manager)

        assert secure_config.get("key") == "value"
        assert secure_config["key"] == "value"

    def test_repr_masks_secrets(self):
        """Test repr masks sensitive values."""
        config = {"api_key": "sk-secret123456789", "normal": "value"}
        manager = SecretsManager()
        secure_config = SecureConfig(config, manager)

        repr_str = repr(secure_config)

        assert "sk-secret123456789" not in repr_str
        assert "***" in repr_str
        assert "value" in repr_str
