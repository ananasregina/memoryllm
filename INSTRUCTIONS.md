memmoryllm is a proxy to OpenAI compatible LLMs that injects user's memories

# Features
- Transparent drop in to any OpenAI endpoint -- just replace the URL
- No fancy stuff. Requests are sent as they are, without any type of validation (with the added memories)
- The system will process the request via the memory provider

# Memory providers
- We will use Cognee as our memory provider
- Docs: https://docs.cognee.ai/guides/search-basics

# Tech stack
- Because Cognee's best client is Python, we ourselves will use Python
- use uv for virtual environments and dependencies

# Configuration
- There's only two parameters needed to interact with Cognee: the database location and the dataset name. Read them from the system environment. 
- memoryllm needs to know what the real URL for the LLM provider is (e.g. OpenRouter or Azure) ... that's a system config var too
- If the system env config is not set, give up and exit the process
- Any other config needed to interact with the LLM must be provided by the caller (e.g. API keys), memoryllm will be a transparent proxy and let them go through

# Logging
- We will initially log everything (including the request body and the request sent to the LLM) for debug purposes
- I will manually enable/disable this setting in the code. No need for fany config flags. 

# Future enhancements
- Cache the search results so that we don't hit Cognee each time (slow)
