"""Tests for LLM client abstraction."""

import pytest

from src.llm_client import LLMConfig, create_llm_client


def test_llm_config_defaults():
    """Test LLM config default values."""
    config = LLMConfig()
    assert config.provider == "openai"
    assert config.model == "gpt-4"
    assert config.temperature == 0.7
    assert config.max_tokens == 4000


def test_llm_config_custom():
    """Test LLM config with custom values."""
    config = LLMConfig(
        provider="anthropic", model="claude-3-5-sonnet-20241022", temperature=0.5, max_tokens=2000
    )
    assert config.provider == "anthropic"
    assert config.model == "claude-3-5-sonnet-20241022"
    assert config.temperature == 0.5
    assert config.max_tokens == 2000


def test_create_llm_client_unsupported_provider():
    """Test error handling for unsupported provider."""
    config = LLMConfig(provider="unsupported")
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_llm_client(config)


def test_openai_client_type():
    """Test OpenAI client creation."""
    from src.llm_client import OpenAIClient

    config = LLMConfig(provider="openai", api_key="test-key")
    try:
        client = create_llm_client(config)
        assert isinstance(client, OpenAIClient)
    except ImportError:
        pytest.skip("openai package not installed")


def test_anthropic_client_type():
    """Test Anthropic client creation."""
    from src.llm_client import AnthropicClient

    config = LLMConfig(provider="anthropic", api_key="test-key")
    try:
        client = create_llm_client(config)
        assert isinstance(client, AnthropicClient)
    except ImportError:
        pytest.skip("anthropic package not installed")


def test_ollama_client_type():
    """Test Ollama client creation."""
    from src.llm_client import OllamaClient

    config = LLMConfig(provider="ollama")
    client = create_llm_client(config)
    assert isinstance(client, OllamaClient)


def test_claude_alias():
    """Test 'claude' as alias for 'anthropic'."""
    from src.llm_client import AnthropicClient

    config = LLMConfig(provider="claude", api_key="test-key")
    try:
        client = create_llm_client(config)
        assert isinstance(client, AnthropicClient)
    except ImportError:
        pytest.skip("anthropic package not installed")
