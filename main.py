#!/usr/bin/env python3

import os
import logging
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from dotenv import load_dotenv
import ast
import re

from mcp import ClientSession
from mcp.client.sse import sse_client

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration constants
# Default to Cognee MCP server running locally
COGNEE_MCP_URL = os.getenv("COGNEE_MCP_URL", "http://127.0.0.1:9998/sse")
# We still support LLM_PROVIDER_URL
LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL")

# Global reference to MCP session
mcp_session: Optional[ClientSession] = None
mcp_cleanup: Optional[callable] = None

# Validate required configuration
if not LLM_PROVIDER_URL:
    logger.warning("LLM_PROVIDER_URL not set, defaulting to OpenRouter (https://openrouter.ai/api/v1)")

logger.info(f"Configuration loaded: Cognee MCP={COGNEE_MCP_URL}, LLM={LLM_PROVIDER_URL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the lifecycle of the MCP client session.
    """
    global mcp_session, mcp_cleanup
    logger.info(f"Connecting to Cognee MCP server at {COGNEE_MCP_URL}...")
    
    try:
        # We need to manually manage the async generator for sse_client
        # because we want to keep the session open for the lifetime of the app
        sse_cm = sse_client(COGNEE_MCP_URL)
        read_stream, write_stream = await sse_cm.__aenter__()
        
        session_cm = ClientSession(read_stream, write_stream)
        mcp_session = await session_cm.__aenter__()
        
        await mcp_session.initialize()
        logger.info("Connected and initialized Cognee MCP session")
        
        yield
        
        # Cleanup
        logger.info("Closing Cognee MCP session...")
        await session_cm.__aexit__(None, None, None)
        await sse_cm.__aexit__(None, None, None)
        
    except Exception as e:
        logger.error(f"Failed to connect to Cognee MCP server: {e}")
        logger.warning("Application starting without Cognee integration")
        yield


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

async def search_memories_mcp(query_text: str) -> Optional[str]:
    """
    Search memories using Cognee MCP server.
    """
    global mcp_session
    
    if not mcp_session:
        logger.warning("MCP session not available, skipping memory search")
        return None
        
    try:
        logger.info(f"Searching memories using Cognee MCP for query: {query_text}")
        
        # Call the 'search' tool on the MCP server
        # arguments={"query": query_text} based on Cognee MCP docs/expectations
        # In the tools list provided earlier: "search: Retrieve relevant memories using semantic search"
        # We assume the argument name is 'query' or similar.
        # Based on standard practices, we'll try 'query'. If it fails, we might need to adjust.
        # Although the CLI command was just `cognee-cli search query -...`
        
        # Call the 'search' tool on the MCP server
        # We use GRAPH_COMPLETION for better context, as requested
        result = await mcp_session.call_tool("search", arguments={"search_query": query_text, "search_type": "GRAPH_COMPLETION"})
        
        # result is a CallToolResult
        # It has a content list (TextContent or ImageContent)
        if not result.content:
            logger.info("No content returned from Cognee search")
            return None
            
        # Concatenate all text content
        # The result from Cognee MCP (GRAPH_COMPLETION) often comes as a string representation of a dict
        # e.g., "{'search_result': ['The context...'], 'dataset_id': UUID(...)}"
        memory_content = ""
        
        for item in result.content:
            if hasattr(item, 'text'):
                raw_text = item.text
                
                # Try to parse if it looks like a dict string
                if "search_result" in raw_text:
                    try:
                        # Handle UUIDs which cause json.loads/ast.literal_eval to fail if not handled
                        # Simple hack: replace UUID('...') with just the string '...'
                        clean_text = re.sub(r"UUID\('([^']+)'\)", r"'\1'", raw_text)
                        parsed = ast.literal_eval(clean_text)
                        
                        if isinstance(parsed, dict) and "search_result" in parsed:
                            results = parsed["search_result"]
                            if isinstance(results, list):
                                memory_content += "\n".join(results) + "\n"
                            else:
                                memory_content += str(results) + "\n"
                        else:
                            # Fallback if parsing structure isn't exactly as expected
                            memory_content += raw_text + "\n"
                    except Exception as e:
                        logger.warning(f"Failed to parse structured memory response: {e}")
                        # If parsing fails, use the raw text but maybe try to clean it
                        memory_content += raw_text + "\n"
                else:
                    memory_content += raw_text + "\n"
        
        if memory_content.strip():
            # Implement "modesty" - limit the amount of context we inject
            # 4000 chars is roughly 1000 tokens, which is a reasonable safety margin
            MAX_MEMORY_LENGTH = 4000
            
            final_memory = memory_content.strip()
            if len(final_memory) > MAX_MEMORY_LENGTH:
                logger.info(f"Memory content too long ({len(final_memory)} chars), truncating to {MAX_MEMORY_LENGTH}")
                final_memory = final_memory[:MAX_MEMORY_LENGTH] + "\n...(memories truncated for brevity)..."
                
            logger.info(f"Found memory for query: {query_text}")
            logger.info(f"Memory content: {final_memory}")
            return final_memory
        else:
            logger.info("No text content in Cognee response")
            return None

    except Exception as e:
        logger.error(f"Error calling Cognee MCP tool: {str(e)}")
        return None

async def search_memories(query_text: str) -> Optional[str]:
    """
    Wrapper for memory search.
    """
    return await search_memories_mcp(query_text)

def inject_memories_into_request(request_data: Dict[str, Any], memories: str) -> Dict[str, Any]:
    """
    Inject memories as a system role message at the beginning of the messages array.
    If the request doesn't have a messages array or can't be parsed, return original request.
    """
    try:
        # Check if this is a chat completion request with messages
        if "messages" not in request_data or not isinstance(request_data["messages"], list):
            logger.warning("Request doesn't contain valid messages array - cannot inject memories")
            return request_data
            
        # Create system message with memories
        system_message = {
            "role": "system",
            "content": f"Relevant memories:\n\n{memories}"
        }
        
        # Insert system message at the beginning
        modified_messages = [system_message] + request_data["messages"]
        modified_request = request_data.copy()
        modified_request["messages"] = modified_messages
        
        logger.info("Successfully injected memories as system message")
        logger.debug(f"Modified messages count: {len(modified_messages)}")
        
        return modified_request
        
    except Exception as e:
        logger.error(f"Failed to inject memories into request: {str(e)}")
        logger.info("Returning original request without memory injection")
        return request_data

async def proxy_request_to_llm(request_data: Dict[str, Any], llm_url: str, headers: Dict[str, str]) -> Any:
    """
    Proxy the request to the actual LLM provider.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(llm_url, json=request_data, headers=headers)
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM provider returned error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error(f"Failed to proxy request to LLM: {str(e)}")
        raise HTTPException(status_code=502, detail="Failed to connect to LLM provider")

def get_llm_base_url():
    if not LLM_PROVIDER_URL:
        # Fallback hardcoded as requested
        return "https://openrouter.ai/api/v1"
    else:
        return str(LLM_PROVIDER_URL).rstrip('/')

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Handle chat completions with memory injection.
    """
    try:
        # Parse the incoming request
        request_data = await request.json()
        logger.info("Received chat completion request")
        logger.debug(f"Original request: {request_data}")
        
        # Extract query text for memory search (use LAST user message)
        query_text = ""
        if "messages" in request_data and isinstance(request_data["messages"], list):
            # Iterate in reverse to find the most recent user message
            for message in reversed(request_data["messages"]):
                if message.get("role") == "user" and "content" in message:
                    query_text = message["content"]
                    break
        
        if not query_text:
            query_text = "general conversation"  # Fallback query
            
        # Search for relevant memories
        search_query = f"I am searching for relevant memories to provide context for an LLM response to the following user message: {query_text}"
        memories = await search_memories(search_query)
        
        # Inject memories into request if found
        final_request_data = request_data
        if memories:
            final_request_data = inject_memories_into_request(request_data, memories)
        else:
            logger.info("No memories to inject - sending original request")
            
    # Proxy to LLM provider
        # Use configured URL or fallback to OpenRouter
        base_url = get_llm_base_url()

        # Simple straightforward proxying
        # If the request matches /v1/chat/completions, we target that on the provider
        if request.url.path.endswith("/chat/completions"):
            target_url = f"{base_url}/chat/completions"
        else:
            # Generic fallback for other paths if needed
            request_path = request.url.path.lstrip('/')
            target_url = f"{base_url}/{request_path}"
            
        # Extract and filter headers
        excluded_headers = {'host', 'content-length', 'connection', 'accept-encoding'}
        proxy_headers = {
            k: v for k, v in request.headers.items() 
            if k.lower() not in excluded_headers
        }
        
        logger.info(f"Proxying request to LLM provider: {target_url}")
        logger.debug(f"Proxying headers: {proxy_headers.keys()}")
        
        # Handle streaming requests
        if final_request_data.get("stream", False):
            async def stream_generator():
                try:
                    async with httpx.AsyncClient() as client:
                        async with client.stream("POST", target_url, json=final_request_data, headers=proxy_headers, timeout=60.0) as response:
                            response.raise_for_status()
                            async for chunk in response.aiter_bytes():
                                yield chunk
                except Exception as e:
                    logger.error(f"Streaming error: {str(e)}")
                    # We can't easily return a 500 here if streaming already started, but we can log it
                    # If it happens at start, the client will get a connection error or partial content

            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
        # Handle non-streaming requests
        llm_response = await proxy_request_to_llm(final_request_data, target_url, proxy_headers)
        
        logger.info("Successfully processed chat completion request")
        return llm_response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_generic(request: Request, path: str):
    """
    Catch-all proxy for any other endpoints (embeddings, models, etc).
    Forward unmodified.
    """
    # Avoid double-matching the explicit chat completion route if for some reason it falls through
    if path == "v1/chat/completions" and request.method == "POST":
         # This should ideally be handled by the explicit route above, but just in case
         return await chat_completions(request)
         
    try:
        base_url = get_llm_base_url()
        # Ensure path doesn't have leading slash when joining
        clean_path = path.lstrip('/')
        
        # If base_url ends in /v1 and path starts with v1/, strip it from path to avoid duplication
        # e.g. base=.../v1, path=v1/models -> .../v1/models
        if base_url.endswith("/v1") and clean_path.startswith("v1/"):
            clean_path = clean_path[3:]
            
        target_url = f"{base_url}/{clean_path}"
        
        logger.info(f"Generic proxying {request.method} request to: {target_url}")
        
        # Extract headers (same logic as before)
        excluded_headers = {'host', 'content-length', 'connection', 'accept-encoding'}
        proxy_headers = {
            k: v for k, v in request.headers.items() 
            if k.lower() not in excluded_headers
        }
        
        # Read body if it exists
        body = await request.body()
        
        # Prepare client request for generic proxy
        client = httpx.AsyncClient()
        req = client.build_request(
            request.method,
            target_url,
            headers=proxy_headers,
            content=body,
            timeout=60.0
        )
        
        try:
            r = await client.send(req, stream=True)
        except Exception as e:
            await client.aclose()
            raise e
            
        excluded_response_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
        response_headers = {k: v for k, v in r.headers.items() if k.lower() not in excluded_response_headers}
        
        async def cleanup_generator():
            try:
                async for chunk in r.aiter_bytes():
                    yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {e}")
            finally:
                await r.aclose()
                await client.aclose()
                
        return StreamingResponse(
            cleanup_generator(),
            status_code=r.status_code,
            headers=response_headers,
            background=None
        )

    except Exception as e:
        logger.error(f"Generic proxy error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting memoryllm proxy server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="debug"
    )
