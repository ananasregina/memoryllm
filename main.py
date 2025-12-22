#!/usr/bin/env python3

import os
import logging
import subprocess
import json
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from dotenv import load_dotenv

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration constants
COGNEE_CLI_PATH = os.getenv("COGNEE_CLI_PATH", "/Users/talimoreno/cognee")
LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL")

# Validate required configuration
# Strict check removed, will default to OpenRouter
if not LLM_PROVIDER_URL:
    logger.warning("LLM_PROVIDER_URL not set, defaulting to OpenRouter (https://openrouter.ai/api/v1)")

logger.info(f"Configuration loaded: Cognee CLI={COGNEE_CLI_PATH}, LLM={LLM_PROVIDER_URL}")

# Create FastAPI app
app = FastAPI()

def search_memories_cli(query_text: str) -> Optional[str]:
    """
    Search memories using Cognee CLI with resilience.
    Returns None if search fails, allowing the proxy to continue without memories.
    """
    try:
        logger.info(f"Searching memories using Cognee CLI for query: {query_text}")
        
        # Run Cognee CLI command with JSON output format
        result = subprocess.run([
            "uv", "--directory", COGNEE_CLI_PATH, "run",
            "cognee-cli", "search", query_text, "--output-format", "json"
        ], capture_output=True, text=True, check=True)
        
        # Parse clean JSON output from Cognee CLI
        try:
            # With --output-format json, we get JSON array but may have some logging text
            # Find the start of the JSON array
            json_start = result.stdout.find('[')
            if json_start == -1:
                logger.error("No JSON array found in Cognee CLI output")
                logger.debug(f"Full output: {result.stdout[:500]}...")
                return None
            
            json_str = result.stdout[json_start:]
            data = json.loads(json_str)
            
            # Cognee returns an array, get first result
            if data and len(data) > 0 and 'search_result' in data[0] and data[0]['search_result']:
                # Extract the actual memory content
                memory_content = data[0]['search_result'][0]
                logger.info(f"Found memory for query: {query_text}")
                logger.debug(f"Memory content: {str(memory_content)[:200]}...")
                return str(memory_content)
            else:
                logger.info("No memories found in Cognee response")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Cognee CLI JSON output: {str(e)}")
            logger.debug(f"Raw output: {result.stdout[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing Cognee CLI output: {str(e)}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Cognee CLI search failed: {str(e)}")
        logger.debug(f"Stderr: {e.stderr}")
        logger.info("Continuing without memory injection due to Cognee CLI failure")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in Cognee search: {str(e)}")
        logger.info("Continuing without memory injection")
        return None

async def search_memories(query_text: str) -> Optional[str]:
    """
    Async wrapper for memory search that can be used with either CLI or future API integration.
    """
    # Use CLI implementation
    return search_memories_cli(query_text)

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
        memories = await search_memories(query_text)
        
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

def get_llm_base_url():
    if not LLM_PROVIDER_URL:
        # Fallback hardcoded as requested
        return "https://openrouter.ai/api/v1"
    else:
        return str(LLM_PROVIDER_URL).rstrip('/')

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
        
        # Prepare client request
        # We need to define a generator to ensure the client stays open while streaming
        async def stream_generator():
            try:
                # Use a new client for the stream
                async with httpx.AsyncClient() as client:
                    req = client.build_request(
                        request.method,
                        target_url,
                        headers=proxy_headers,
                        content=body,
                        timeout=60.0
                    )
                    
                    # Send request with stream=True
                    r = await client.send(req, stream=True)
                    
                    # We can't return headers from here to the StreamingResponse constructor 
                    # because it requires them immediately.
                    # But we only get them after sending the request. 
                    # This is a limitation of simple proxying with FastAPI StreamingResponse.
                    # However, we can hack it or just accept that we need to fetch headers first?
                    # No, StreamingResponse takes a generator.
                    # If we want to set headers dynamically based on upstream, we might have a problem 
                    # if we wrap everything in the generator.
                    
                    # WAIT. The StreamingResponse headers are sent *before* the body.
                    # If we use a generator, the body starts yielding later.
                    # BUT `StreamingResponse` expects headers at construction time (or set on response object).
                    
                    # If we are inside the generator, headers are already sent by FastAPI!
                    
                    # Solution: We cannot easily forward upstream headers dynamically if we use `StreamingResponse` 
                    # AND need to keep the client open in a generator *unless* we construct the response *inside* 
                    # the generator (which we can't do, we return the response).
                    
                    # ALTERNATIVE: Don't use `async with client` context manager for the *return*?
                    # Or manually close client?
                    # `httpx.AsyncClient()` can be used without context manager, but needs `.aclose()`.
                    
                    # Let's try manual lifecycle management for the generic proxy
                    pass
            except Exception as e:
                logger.error(f"Stream error: {e}")

        # BETTER APPROACH matching typical FastAPI proxy patterns:
        
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
