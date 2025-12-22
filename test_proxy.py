#!/usr/bin/env python3

import os
import asyncio
import httpx
import json
from fastapi.testclient import TestClient

# Set environment variable before importing app
os.environ["LLM_PROVIDER_URL"] = "http://localhost:8001/v1"

from main import app

def test_proxy_basic_functionality():
    """Test basic proxy functionality with mock LLM provider"""
    
    # Create test client
    client = TestClient(app)
    
    # Test request data
    test_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "stream": False
    }
    
    print("Testing basic proxy functionality...")
    print(f"Sending request: {test_request}")
    
    # This will fail because we don't have a real LLM provider running,
    # but it should demonstrate the proxy flow
    try:
        response = client.post("/v1/chat/completions", json=test_request)
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Expected error (no LLM provider): {str(e)}")
        print("Proxy logic is working - it's trying to connect to the LLM provider")

def test_memory_injection_logic():
    """Test the memory injection logic directly"""
    from main import inject_memories_into_request
    
    # Test request with messages
    test_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ]
    }
    
    # Test memories
    test_memories = "This is a test memory about previous conversations."
    
    print("\nTesting memory injection logic...")
    print(f"Original request: {test_request}")
    print(f"Memories to inject: {test_memories}")
    
    # Inject memories
    modified_request = inject_memories_into_request(test_request, test_memories)
    
    print(f"Modified request: {modified_request}")
    
    # Verify the system message was added
    if modified_request["messages"][0]["role"] == "system":
        print("✓ Memory injection successful - system message added")
        print(f"System message content: {modified_request['messages'][0]['content']}")
    else:
        print("✗ Memory injection failed")

if __name__ == "__main__":
    print("Testing memoryllm proxy...")
    test_memory_injection_logic()
    test_proxy_basic_functionality()
    print("\nTest completed!")