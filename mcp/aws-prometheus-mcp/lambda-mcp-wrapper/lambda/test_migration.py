"""
Test script to verify the MCP SDK migration works correctly.
"""

import asyncio
import json
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(__file__))

from awslabs.prometheus_mcp_server.server import mcp as prometheus_mcp_server
from stdio_adapter import StdioAdapter


async def test_tools_list():
    """Test that tools/list returns the correct schema."""
    print("\n=== Testing tools/list ===")
    
    adapter = StdioAdapter(prometheus_mcp_server)
    
    request = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/list',
        'params': {}
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    print(f"Response: {json.dumps(response, indent=2)}")
    
    # Verify response structure
    assert response.get('jsonrpc') == '2.0'
    assert response.get('id') == 1
    assert 'result' in response
    assert 'tools' in response['result']
    
    tools = response['result']['tools']
    print(f"\nFound {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool['name']}: {tool.get('description', 'No description')[:80]}")
    
    # Verify expected tools exist
    tool_names = [t['name'] for t in tools]
    expected_tools = [
        'GetAvailableWorkspaces',
        'ExecuteQuery',
        'ExecuteRangeQuery',
        'ListMetrics',
        'GetServerInfo'
    ]
    
    for expected in expected_tools:
        assert expected in tool_names, f"Missing expected tool: {expected}"
    
    print("\n✓ tools/list test passed!")
    return tools


async def test_initialize():
    """Test the initialize handshake."""
    print("\n=== Testing initialize ===")
    
    adapter = StdioAdapter(prometheus_mcp_server)
    
    request = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {
                'name': 'test-client',
                'version': '1.0.0'
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    print(f"Response: {json.dumps(response, indent=2)}")
    
    assert response.get('jsonrpc') == '2.0'
    assert response.get('id') == 1
    assert 'result' in response
    assert 'serverInfo' in response['result']
    assert response['result']['serverInfo']['name'] == 'awslabs-prometheus-mcp-server'
    
    print("\n✓ initialize test passed!")


async def test_tool_schema():
    """Test that tool schemas are properly formatted."""
    print("\n=== Testing tool schemas ===")
    
    tools = await test_tools_list()
    
    # Check GetAvailableWorkspaces schema
    workspace_tool = next((t for t in tools if t['name'] == 'GetAvailableWorkspaces'), None)
    assert workspace_tool is not None, "GetAvailableWorkspaces tool not found"
    
    print(f"\nGetAvailableWorkspaces schema:")
    print(json.dumps(workspace_tool['inputSchema'], indent=2))
    
    # Check ExecuteQuery schema
    query_tool = next((t for t in tools if t['name'] == 'ExecuteQuery'), None)
    assert query_tool is not None, "ExecuteQuery tool not found"
    
    print(f"\nExecuteQuery schema:")
    print(json.dumps(query_tool['inputSchema'], indent=2))
    
    print("\n✓ tool schema test passed!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("MCP SDK Migration Test Suite")
    print("=" * 60)
    
    try:
        await test_initialize()
        await test_tools_list()
        await test_tool_schema()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
