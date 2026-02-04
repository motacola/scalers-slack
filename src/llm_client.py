"""
LLM Client Abstraction Layer
Supports multiple LLM providers: OpenAI, Anthropic, Ollama, etc.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    provider: str = "openai"  # openai, anthropic, ollama, custom
    model: str = "gpt-4"
    api_key: str = ""
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: int = 60


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text from prompt."""
        pass

    @abstractmethod
    def generate_with_context(
        self, messages: list[dict[str, Any]], system_prompt: str | None = None
    ) -> str:
        """Generate text with conversation context."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import openai

            self.client = openai.OpenAI(
                api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
                base_url=config.base_url,
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        content = response.choices[0].message.content
        return str(content) if content else ""

    def generate_with_context(
        self, messages: list[dict[str, Any]], system_prompt: str | None = None
    ) -> str:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        content = response.choices[0].message.content
        return str(content) if content else ""


class AnthropicClient(LLMClient):
    """Anthropic (Claude) API client."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import anthropic

            self.client = anthropic.Anthropic(
                api_key=config.api_key or os.getenv("ANTHROPIC_API_KEY"),
                base_url=config.base_url,
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from first content block (safely handle different block types)
        first_block = response.content[0]
        if hasattr(first_block, "text"):
            return str(first_block.text)
        return ""

    def generate_with_context(
        self, messages: list[dict[str, Any]], system_prompt: str | None = None
    ) -> str:
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt or "",
            messages=messages,  # type: ignore[arg-type]
        )
        # Extract text from first content block (safely handle different block types)
        first_block = response.content[0]
        if hasattr(first_block, "text"):
            return str(first_block.text)
        return ""


class OllamaClient(LLMClient):
    """Ollama local LLM client."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        import requests

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
            },
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        return str(response.json()["message"]["content"])

    def generate_with_context(
        self, messages: list[dict[str, Any]], system_prompt: str | None = None
    ) -> str:
        import requests

        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
            },
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        return str(response.json()["message"]["content"])


def create_llm_client(config: LLMConfig) -> LLMClient:
    """Factory function to create appropriate LLM client."""
    from typing import Type

    providers: dict[str, Type[LLMClient]] = {
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "claude": AnthropicClient,  # Alias
        "ollama": OllamaClient,
    }

    client_class = providers.get(config.provider.lower())
    if not client_class:
        raise ValueError(
            f"Unsupported LLM provider: {config.provider}. "
            f"Supported: {', '.join(providers.keys())}"
        )

    return client_class(config)


# Convenience function for quick setup
def get_default_llm() -> LLMClient:
    """Get default LLM client from environment variables."""
    # Check for available API keys in order of preference
    if os.getenv("OPENAI_API_KEY"):
        return create_llm_client(
            LLMConfig(provider="openai", model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY", ""))
        )
    elif os.getenv("ANTHROPIC_API_KEY"):
        return create_llm_client(
            LLMConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            )
        )
    else:
        # Default to Ollama (local)
        return create_llm_client(LLMConfig(provider="ollama", model="llama2", api_key=""))
