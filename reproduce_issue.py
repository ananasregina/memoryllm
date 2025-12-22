
import asyncio
import httpx
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

async def test_connection():
    # Test the local proxy generic endpoint (e.g. models)
    target_url = "http://localhost:8000/v1/models"
    print(f"Target URL: {repr(target_url)}")

    try:
        async with httpx.AsyncClient() as client:
            print(f"Attempting GET connection to {target_url}...")
            
            response = await client.get(
                target_url, 
                headers={
                    "Authorization": "Bearer sk-dummy-key-for-testing", 
                    "HTTP-Referer": "http://localhost:8000",
                },
                timeout=30.0
            )
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {response.headers}")
            # We expect a 401 from OpenRouter (since key is dummy) or 200 if key was valid. 
            # Crucially, we expect a response from OpenRouter, not a 404 from our server.
            print(f"Response body: {response.text[:200]}")
                    
    except Exception as e:
        print(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
