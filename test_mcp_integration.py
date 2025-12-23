#!/usr/bin/env python3

import os
import asyncio
import logging
from mcp import ClientSession
from mcp.client.sse import sse_client

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_mcp")

# Configuration
COGNEE_MCP_URL = os.getenv("COGNEE_MCP_URL", "http://127.0.0.1:9998/sse")

async def test_mcp_connection():
    """Test connection to Cognee MCP server"""
    logger.info(f"Connecting to Cognee MCP server at {COGNEE_MCP_URL}...")
    
    try:
        async with sse_client(COGNEE_MCP_URL) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.info("✓ Connected and initialized Cognee MCP session")
                
                # List tools to verify we see 'search'
                tools = await session.list_tools()
                logger.info(f"Available tools: {[t.name for t in tools.tools]}")
                
                tool_names = [t.name for t in tools.tools]
                if "search" in tool_names:
                    logger.info("✓ 'search' tool found")
                else:
                    logger.error("✗ 'search' tool NOT found")
                    return

                # Test search
                query = "test query"
                logger.info(f"Testing search with query: '{query}'")
                
                # Test search
                query = "test query"
                logger.info(f"Testing search with query: '{query}'")
                
                try:
                    result = await session.call_tool("search", arguments={"search_query": query, "search_type": "CHUNKS"})
                    
                    if result.content:
                        logger.info("✓ Search returned content")
                        for content in result.content:
                            if hasattr(content, "text"):
                                logger.info(f"Text: {content.text[:200]}...")
                    else:
                        logger.info("✓ Search returned empty result (possibly no matching chunks)")
                        
                except Exception as e:
                    logger.error(f"Search failed: {e}")

                # Test list_data
                logger.info("\nTesting list_data...")
                try:
                    result = await session.call_tool("list_data", arguments={})
                    if result.content:
                        logger.info("✓ list_data returned content")
                        for content in result.content:
                            if hasattr(content, "text"):
                                logger.info(f"Data: {content.text}")
                except Exception as e:
                    logger.error(f"✗ list_data failed: {e}")

    except Exception as e:
        logger.error(f"✗ Failed to connect or interact with MCP server: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(test_mcp_connection())
    except KeyboardInterrupt:
        pass
