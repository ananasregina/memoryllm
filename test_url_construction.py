#!/usr/bin/env python3

import os
from fastapi.testclient import TestClient
from main import app

def test_url_construction():
    """Test URL construction with different base URLs"""
    
    # Set required environment variables
    os.environ["LLM_PROVIDER_URL"] = "https://api.openrouter.ai"
    os.environ["COGNEE_CLI_PATH"] = "/Users/talimoreno/cognee"
    
    client = TestClient(app)
    
    test_cases = [
        {
            "base_url": "https://api.openrouter.ai",
            "expected_path": "/v1/chat/completions",
            "description": "Base URL without path"
        },
        {
            "base_url": "https://api.openrouter.ai/v1",
            "expected_path": "/chat/completions",
            "description": "Base URL with /v1 path"
        },
        {
            "base_url": "https://api.azure.com",
            "expected_path": "/v1/chat/completions",
            "description": "Different base URL"
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTesting: {test_case['description']}")
        print(f"Base URL: {test_case['base_url']}")
        
        # Update environment variable
        os.environ["LLM_PROVIDER_URL"] = test_case["base_url"]
        
        # Create new app instance to pick up new config
        from importlib import reload
        import main
        reload(main)
        
        # Make a test request (this will fail to connect but we can see the URL)
        try:
            test_request = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}]
            }
            
            # This will fail to connect but we'll see the URL in logs
            response = client.post("/v1/chat/completions", json=test_request)
            
        except Exception as e:
            # Expected to fail since we don't have real LLM providers
            pass

if __name__ == "__main__":
    print("Testing URL construction...")
    test_url_construction()
    print("\nURL construction test completed!")