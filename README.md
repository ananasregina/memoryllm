# memoryllm v0.2

A transparent proxy to OpenAI-compatible LLMs that injects user memories via the Cognee MCP server.

## Features

- **Transparent Proxy**: Drop-in replacement for OpenAI endpoints
- **Universal Compatibility**: Proxies all endpoints (`/v1/models`, `/v1/embeddings`, etc.) transparently
- **Memory Injection**: Automatically adds relevant memories as system messages to chat completions
- **Streaming Support**: Full support for `stream=True` responses
- **Intelligent Search**: Optimizes Cognee queries by focusing on the latest user interaction
- **Zero Validation**: Passes through all requests unchanged if parsing fails
- **OpenRouter Ready**: Authenticates and routes to OpenRouter by default
- **MCP Integration**: Connects directly to Cognee MCP server for low-latency memory retrieval

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for virtual environment management
- A running [Cognee MCP Server](https://docs.cognee.ai/cognee-mcp/mcp-quickstart) (default: `http://127.0.0.1:9998/sse`)

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

# Cognee MCP Configuration
# URL of your running Cognee MCP server (SSE endpoint)
COGNEE_MCP_URL="http://127.0.0.1:9998/sse"
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
                     ↕
               Cognee MCP Server
```

1. Client sends request to memoryllm proxy
2. Proxy extracts query text from user messages
3. Proxy calls `search` tool on Cognee MCP server
4. If memories found, injects them as system message
5. Proxy forwards modified request to actual LLM provider
6. LLM response returned to client

## Development

### Running Tests

```bash
# Integration test for MCP connection
uv run python test_mcp_integration.py
```

### Project Structure

```
memoryllm/
├── main.py                # Main proxy server
├── test_mcp_integration.py # MCP integration tests
├── .env.example           # Example environment file
├── pyproject.toml         # Python project configuration
├── README.md              # This file
└── .gitignore             # Git ignore rules
```

## Future Enhancements

- [ ] Configuration for Cognee database and dataset
- [ ] Caching mechanism for Cognee search results
- [x] Streaming support for chat completions
- [x] Additional OpenAI endpoint support
- [x] Cognee MCP Integration

## License

MIT