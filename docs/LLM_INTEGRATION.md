# LLM Integration Guide

This project supports multiple LLM providers for AI-powered features like task summarization, content analysis, and automated responses.

## Supported Providers

- **OpenAI** (GPT-4, GPT-3.5, etc.)
- **Anthropic** (Claude 3.5 Sonnet, Claude 3 Opus, etc.)
- **Ollama** (Local LLMs: Llama 2, Mistral, etc.)
- **Custom** (Bring your own API-compatible service)

## Quick Start

### 1. Set Up API Keys

Add to your `.env` file:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-...

# Or use Ollama (no API key needed, runs locally)
# Install: https://ollama.ai
```

### 2. Configure LLM in Code

```python
from src.llm_client import create_llm_client, LLMConfig, get_default_llm

# Option 1: Use default (auto-detects from env)
llm = get_default_llm()

# Option 2: Specify provider
llm = create_llm_client(LLMConfig(
    provider="openai",
    model="gpt-4o",
    temperature=0.7,
    max_tokens=4000
))

# Option 3: Use Anthropic Claude
llm = create_llm_client(LLMConfig(
    provider="anthropic",
    model="claude-3-5-sonnet-20241022",
    temperature=0.7
))

# Option 4: Use Ollama (local)
llm = create_llm_client(LLMConfig(
    provider="ollama",
    model="llama2",
    base_url="http://localhost:11434"
))
```

### 3. Generate Text

```python
# Simple generation
response = llm.generate(
    prompt="Summarize this Slack thread...",
    system_prompt="You are a helpful assistant that summarizes conversations."
)

# With conversation context
messages = [
    {"role": "user", "content": "What's in this thread?"},
    {"role": "assistant", "content": "This thread discusses..."},
    {"role": "user", "content": "Can you elaborate?"}
]
response = llm.generate_with_context(
    messages=messages,
    system_prompt="You are a helpful assistant."
)
```

## Configuration Options

```python
LLMConfig(
    provider="openai",          # Provider: openai, anthropic, ollama
    model="gpt-4o",             # Model name
    api_key="sk-...",           # API key (or set via env var)
    base_url=None,              # Custom API endpoint (optional)
    temperature=0.7,            # Creativity (0.0-1.0)
    max_tokens=4000,            # Max response length
    timeout=60                  # Request timeout in seconds
)
```

## Using with Slack Automation

### Summarize Slack Threads

```python
from src.llm_client import get_default_llm

llm = get_default_llm()

# Build prompt from thread
thread_text = "\n".join([f"{msg['user']}: {msg['text']}" for msg in thread])
prompt = f"Summarize this Slack conversation:\n\n{thread_text}"

summary = llm.generate(
    prompt=prompt,
    system_prompt="You are a Slack assistant. Provide concise summaries."
)
```

### Extract Action Items

```python
system_prompt = """You are a task extraction assistant.
Extract action items from Slack conversations.
Format: - [ ] Task description (@owner)"""

action_items = llm.generate(
    prompt=thread_text,
    system_prompt=system_prompt
)
```

### Categorize Messages

```python
system_prompt = """Categorize this message as:
- urgent: Needs immediate attention
- important: Should be addressed today
- fyi: For information only
- noise: Not actionable

Return only the category."""

category = llm.generate(
    prompt=message_text,
    system_prompt=system_prompt
)
```

## Provider-Specific Notes

### OpenAI
- **Models**: `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`
- **Pricing**: Pay per token
- **API Key**: Get from https://platform.openai.com/api-keys
- **Rate Limits**: Depends on tier (free tier is limited)

### Anthropic (Claude)
- **Models**: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`
- **Pricing**: Pay per token
- **API Key**: Get from https://console.anthropic.com/
- **Context Window**: Up to 200K tokens
- **Best for**: Long conversations, complex reasoning

### Ollama (Local)
- **Models**: Download from https://ollama.ai/library
  - `llama2`: Good general purpose
  - `mistral`: Fast and efficient
  - `codellama`: Great for code
  - `phi`: Lightweight, runs on low-end hardware
- **Pricing**: FREE (runs locally)
- **Setup**:
  ```bash
  # Install Ollama
  curl -fsSL https://ollama.ai/install.sh | sh

  # Pull a model
  ollama pull llama2

  # Start server (usually auto-starts)
  ollama serve
  ```
- **Best for**: Privacy, no API costs, offline use

## Advanced Usage

### Custom System Prompts

```python
SUMMARIZER_PROMPT = """You are an expert at summarizing Slack conversations.

Guidelines:
- Extract key decisions and action items
- Highlight important information
- Ignore small talk and greetings
- Use bullet points for clarity
- Keep summaries under 200 words"""

summary = llm.generate(thread_text, system_prompt=SUMMARIZER_PROMPT)
```

### Error Handling

```python
try:
    response = llm.generate(prompt)
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install openai  # or anthropic")
except Exception as e:
    print(f"LLM error: {e}")
    # Fallback to rule-based approach
    response = simple_summarize(text)
```

### Token Management

```python
# Estimate tokens (rough approximation)
def estimate_tokens(text: str) -> int:
    return len(text.split()) * 1.3  # ~1.3 tokens per word

# Truncate if needed
MAX_TOKENS = 3000
if estimate_tokens(thread_text) > MAX_TOKENS:
    # Take most recent messages
    thread_text = "\n".join(messages[-20:])
```

## Configuration in config.json

Add LLM settings to your `config/config.json`:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4000,
    "timeout": 60,
    "features": {
      "summarize_threads": true,
      "extract_action_items": true,
      "categorize_messages": true
    }
  }
}
```

## Best Practices

1. **Choose the Right Model**
   - Long threads → Claude (200K context)
   - Quick summaries → GPT-3.5-turbo (fast, cheap)
   - Privacy-sensitive → Ollama (local)

2. **Optimize Costs**
   - Use smaller models for simple tasks
   - Cache results when possible
   - Truncate very long threads

3. **Handle Failures Gracefully**
   - Always have a fallback (rule-based)
   - Retry with exponential backoff
   - Log errors for debugging

4. **Respect Rate Limits**
   - Add delays between requests
   - Use batch processing when possible
   - Monitor usage to avoid overages

## Examples

See `examples/llm_usage.py` for complete examples:
- Thread summarization
- Action item extraction
- Sentiment analysis
- Auto-responses

## Troubleshooting

### "No API key found"
- Ensure `.env` file exists
- Check `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set
- Or use Ollama (no key needed)

### "Module not found: openai"
```bash
pip install openai anthropic
```

### "Ollama connection refused"
```bash
# Start Ollama
ollama serve

# Or install first
curl -fsSL https://ollama.ai/install.sh | sh
```

### "Rate limit exceeded"
- Wait a few minutes and retry
- Upgrade API plan
- Switch to Ollama for unlimited local use

## Future Enhancements

- [ ] Streaming responses
- [ ] Function calling / tool use
- [ ] Vector embeddings for semantic search
- [ ] Fine-tuning on your Slack data
- [ ] Multi-agent workflows
