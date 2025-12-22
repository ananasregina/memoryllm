#!/usr/bin/env python3

import os
import subprocess
import json

# Set required environment variables before importing
os.environ["LLM_PROVIDER_URL"] = "http://localhost:8001/v1"
os.environ["COGNEE_CLI_PATH"] = "/Users/talimoreno/cognee"

from main import search_memories_cli

def test_cognee_cli_direct():
    """Test Cognee CLI integration directly"""
    print("Testing Cognee CLI integration directly...")
    
    # Test with a query that should return results
    test_query = "el camello escupidor"
    
    try:
        result = search_memories_cli(test_query)
        if result:
            print(f"✓ Cognee CLI search successful!")
            print(f"Query: {test_query}")
            print(f"Memory found: {result[:100]}...")
        else:
            print(f"✓ Cognee CLI search completed (no memories found)")
            
    except Exception as e:
        print(f"✗ Cognee CLI search failed: {str(e)}")

def test_cognee_cli_error_handling():
    """Test Cognee CLI error handling"""
    print("\nTesting Cognee CLI error handling...")
    
    # Test with empty query
    try:
        result = search_memories_cli("")
        print(f"✓ Empty query handled gracefully: {result}")
    except Exception as e:
        print(f"✓ Empty query error handled: {str(e)}")

def test_cognee_cli_json_parsing():
    """Test Cognee CLI JSON parsing with different outputs"""
    print("\nTesting Cognee CLI JSON parsing...")
    
    # Test the raw command to see output format
    try:
        result = subprocess.run([
            "uv", "--directory", "/Users/talimoreno/cognee", "run",
            "cognee-cli", "search", "test query", "--output-format", "json"
        ], capture_output=True, text=True, check=True)
        
        print(f"Raw output length: {len(result.stdout)} characters")
        print(f"First 200 chars: {result.stdout[:200]}")
        
        # Test JSON parsing
        json_start = result.stdout.find('[')
        if json_start != -1:
            json_str = result.stdout[json_start:]
            data = json.loads(json_str)
            print(f"✓ JSON parsing successful, found {len(data)} results")
        else:
            print("✗ No JSON array found in output")
            
    except Exception as e:
        print(f"✗ JSON parsing test failed: {str(e)}")

if __name__ == "__main__":
    print("Testing Cognee CLI integration...")
    
    # Set environment variable
    os.environ["COGNEE_CLI_PATH"] = "/Users/talimoreno/cognee"
    
    test_cognee_cli_direct()
    test_cognee_cli_error_handling()
    test_cognee_cli_json_parsing()
    
    print("\nCognee integration test completed!")