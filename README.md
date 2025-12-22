# memoryllm

A transparent proxy to OpenAI-compatible LLMs that injects user memories via Cognee.

## Features

- **Transparent Proxy**: Drop-in replacement for OpenAI endpoints
- **Universal Compatibility**: Proxies all endpoints (`/v1/models`, `/v1/embeddings`, etc.) transparently
- **Memory Injection**: Automatically adds relevant memories as system messages to chat completions
- **Streaming Support**: Full support for `stream=True` responses
- **Intelligent Search**: Optimizes Cognee queries by focusing on the latest user interaction
- **Zero Validation**: Passes through all requests unchanged if parsing fails
- **OpenRouter Ready**: Authenticates and routes to OpenRouter by default

## Quick Start

### Prerequisites

- Python 3.12 (Cognee requirement)
- [uv](https://github.com/astral-sh/uv) for virtual environment management

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/memoryllm.git
cd memoryllm

# Set up virtual environment
uv sync

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
```

### Configuration

Create a `.env` file with the following variables:

```env
# LLM Provider BASE URL
# Defaults to https://openrouter.ai/api/v1 if not set
# IMPORTANT: Only include the base URL, NOT the full path
LLM_PROVIDER_URL="https://openrouter.ai/api/v1"

# Cognee CLI Configuration
# Path to your Cognee CLI installation directory
COGNEE_CLI_PATH="/Users/talimoreno/cognee"
```

### Running the Proxy

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the proxy server
python main.py

# The proxy will be available at http://localhost:8000/v1/chat/completions
```

### Usage

Point your OpenAI client to the memoryllm proxy:

```python
from openai import OpenAI

# Instead of pointing directly to OpenRouter/Azure/etc.
client = OpenAI(base_url="http://localhost:8000/v1")

# Use normally - memories will be automatically injected
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What did we discuss last time?"}]
)
```

## Architecture

```
Client → memoryllm Proxy → LLM Provider
                     ↓
               Cognee Memory Search
```

1. Client sends request to memoryllm proxy
2. Proxy extracts query text from user messages
3. Proxy searches Cognee for relevant memories
4. If memories found, injects them as system message
5. Proxy forwards modified request to actual LLM provider
6. LLM response returned to client

## Memory Injection

Memories are injected as system messages at the beginning of the messages array:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Relevant memories:\n\nMemory 1 content...\n\nMemory 2 content..."
    },
    {
      "role": "user",
      "content": "Original user message..."
    }
  ]
}
```

## Error Handling

The proxy is designed to be resilient:

- **Cognee failures**: If memory search fails, request continues without memories
- **Request parsing failures**: If request can't be parsed, original request is passed through
- **LLM provider failures**: Proper error responses are returned to client

All failures are logged with detailed information for debugging.

## Development

### Running Tests

```bash
source .venv/bin/activate
python test_proxy.py
```

### Project Structure

```
memoryllm/
├── main.py                # Main proxy server
├── test_proxy.py          # Test scripts
├── .env.example           # Example environment file
├── pyproject.toml         # Python project configuration
├── README.md              # This file
└── .gitignore             # Git ignore rules
```

## Future Enhancements

- [ ] Real Cognee integration for memory search
- [ ] Configuration for Cognee database and dataset
- [ ] Caching mechanism for Cognee search results
- [x] Streaming support for chat completions
- [x] Additional OpenAI endpoint support

## License

MIT

## Contributing

Pull requests welcome! Please follow the existing code style and add tests for new features.

---

**Note**: This is v0.1 - a minimal working version. Cognee integration is planned for the next phase.