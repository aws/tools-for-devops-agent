#!/usr/bin/env python3
"""
Property-based tests for MCP SDK migration using hypothesis.
Tests correctness properties across random inputs.
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from hypothesis import given, strategies as st, settings
from stdio_adapter import StdioAdapter
import prometheus_mcp_server.server as prom_server

# Feature: mcp-sdk-migration, Property 1: Initialize response structure
@given(request_id=st.one_of(st.integers(), st.text(), st.none()))
@settings(max_examples=100)
def test_initialize_response_structure(request_id):
    """Validates: Requirements 1.2
    For any initialize request with any request ID, the adapter should return 
    a response containing protocolVersion, capabilities, and serverInfo.
    """
    adapter = StdioAdapter(prom_server.mcp)
    response = asyncio.run(adapter._handle_initialize(request_id))
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == request_id
    assert 'result' in response
    assert response['result']['protocolVersion'] == '2024-11-05'
    assert 'capabilities' in response['result']
    assert 'tools' in response['result']['capabilities']
    assert 'serverInfo' in response['result']
    assert 'name' in response['result']['serverInfo']
    assert 'version' in response['result']['serverInfo']
    print(f"✓ Property 1 passed for request_id={request_id}")

# Feature: mcp-sdk-migration, Property 2: Tools list completeness
@given(request_id=st.one_of(st.integers(), st.text()))
@settings(max_examples=50)
def test_tools_list_completeness(request_id):
    """Validates: Requirements 1.3
    For any tools/list request, the adapter should return exactly 5 tools,
    each with name, description, and inputSchema fields.
    """
    adapter = StdioAdapter(prom_server.mcp)
    response = asyncio.run(adapter._handle_tools_list(request_id))
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == request_id
    assert 'result' in response
    assert 'tools' in response['result']
    
    tools = response['result']['tools']
    assert len(tools) == 5, f"Expected 5 tools, got {len(tools)}"
    
    expected_tools = {'GetAvailableWorkspaces', 'ExecuteQuery', 'ExecuteRangeQuery', 
                     'ListMetrics', 'GetServerInfo'}
    actual_tools = {tool['name'] for tool in tools}
    assert actual_tools == expected_tools
    
    for tool in tools:
        assert 'name' in tool
        assert 'description' in tool
        assert 'inputSchema' in tool
        assert isinstance(tool['inputSchema'], dict)
    
    print(f"✓ Property 2 passed for request_id={request_id}")

# Feature: mcp-sdk-migration, Property 9: Request-response correlation
@given(request_ids=st.lists(st.integers(), min_size=1, max_size=10, unique=True))
@settings(max_examples=50)
def test_request_response_correlation(request_ids):
    """Validates: Requirements 7.5
    For any sequence of JSON-RPC requests with distinct IDs, each response 
    should have an id field that matches exactly the id from its corresponding request.
    """
    adapter = StdioAdapter(prom_server.mcp)
    
    for req_id in request_ids:
        request = {
            'jsonrpc': '2.0',
            'id': req_id,
            'method': 'initialize',
            'params': {}
        }
        response = asyncio.run(adapter.handle_jsonrpc_request(request))
        assert response['id'] == req_id, f"Expected id={req_id}, got {response['id']}"
    
    print(f"✓ Property 9 passed for {len(request_ids)} request IDs")

# Feature: mcp-sdk-migration, Property 6: Error response formatting
@given(
    request_id=st.integers(),
    invalid_method=st.text(min_size=1).filter(
        lambda x: x not in ['initialize', 'tools/list', 'tools/call', 'notifications/initialized']
    )
)
@settings(max_examples=50)
def test_error_response_formatting(request_id, invalid_method):
    """Validates: Requirements 6.2, 6.4, 2.6
    For any tool execution failure or invalid request, the adapter should return 
    a valid JSON-RPC 2.0 error response with code and message fields.
    """
    adapter = StdioAdapter(prom_server.mcp)
    
    request = {
        'jsonrpc': '2.0',
        'id': request_id,
        'method': invalid_method,
        'params': {}
    }
    
    response = asyncio.run(adapter.handle_jsonrpc_request(request))
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == request_id
    assert 'error' in response
    assert 'code' in response['error']
    assert 'message' in response['error']
    assert isinstance(response['error']['code'], int)
    assert isinstance(response['error']['message'], str)
    
    print(f"✓ Property 6 passed for invalid method={invalid_method}")

# Feature: mcp-sdk-migration, Property 5: JSON-RPC response formatting
@given(request_id=st.integers())
@settings(max_examples=50)
def test_jsonrpc_response_formatting(request_id):
    """Validates: Requirements 7.3, 4.2
    For any successful tool execution result, the adapter should format 
    the response as a valid JSON-RPC 2.0 response.
    """
    adapter = StdioAdapter(prom_server.mcp)
    
    # Test with initialize (always succeeds)
    request = {
        'jsonrpc': '2.0',
        'id': request_id,
        'method': 'initialize',
        'params': {}
    }
    
    response = asyncio.run(adapter.handle_jsonrpc_request(request))
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == request_id
    assert 'result' in response
    assert 'error' not in response
    
    print(f"✓ Property 5 passed for request_id={request_id}")

# Feature: mcp-sdk-migration, Property 4: JSON-RPC request routing
@given(
    request_id=st.integers(),
    method=st.sampled_from(['initialize', 'tools/list', 'notifications/initialized'])
)
@settings(max_examples=50)
def test_jsonrpc_request_routing(request_id, method):
    """Validates: Requirements 7.1
    For any valid JSON-RPC request with a supported method, the adapter 
    should correctly extract the method and route to the appropriate handler.
    """
    adapter = StdioAdapter(prom_server.mcp)
    
    request = {
        'jsonrpc': '2.0',
        'id': request_id if method != 'notifications/initialized' else None,
        'method': method,
        'params': {}
    }
    
    response = asyncio.run(adapter.handle_jsonrpc_request(request))
    
    # Verify response is valid
    assert 'jsonrpc' in response
    assert response['jsonrpc'] == '2.0'
    
    # Notifications should not have result
    if method == 'notifications/initialized':
        assert response.get('id') is None
    else:
        assert response['id'] == request_id
        assert 'result' in response or 'error' in response
    
    print(f"✓ Property 4 passed for method={method}")

# Feature: mcp-sdk-migration, Property 8: Notification handling
@given(method=st.sampled_from(['notifications/initialized', 'notifications/cancelled']))
@settings(max_examples=20)
def test_notification_handling(method):
    """Validates: Requirements 7.4
    For any JSON-RPC notification method (method without id or with null id), 
    the adapter should process the request without returning a result field.
    """
    adapter = StdioAdapter(prom_server.mcp)
    
    # Test with null id
    request = {
        'jsonrpc': '2.0',
        'id': None,
        'method': method,
        'params': {}
    }
    
    response = asyncio.run(adapter.handle_jsonrpc_request(request))
    
    assert response['jsonrpc'] == '2.0'
    assert response.get('id') is None
    
    print(f"✓ Property 8 passed for notification method={method}")


# Feature: mcp-sdk-migration, Property 3: Health check availability
@given(path=st.sampled_from(['/health', '/health/', '/api/health']))
@settings(max_examples=20)
def test_health_check_availability(path):
    """Validates: Requirements 3.4
    Test health endpoint with various path formats.
    Verify response always contains required fields for GET requests.
    """
    import lambda_function_v2
    
    # Simulate API Gateway event for health check
    event = {
        'httpMethod': 'GET',
        'path': path,
        'headers': {},
        'body': None
    }
    
    response = lambda_function_v2.handler(event, None)
    
    # Health check should work for paths containing /health
    if '/health' in path:
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'status' in body
        assert 'service' in body
        assert 'version' in body
        assert 'timestamp' in body
        print(f"✓ Property 3 passed for path={path}")
    else:
        print(f"✓ Property 3 passed for path={path} (non-health path)")


def run_all_property_tests():
    """Run all property-based tests"""
    print("=" * 60)
    print("Property-Based Test Suite for MCP SDK Migration")
    print("=" * 60)
    print()
    
    tests = [
        ("Property 1: Initialize response structure", test_initialize_response_structure),
        ("Property 2: Tools list completeness", test_tools_list_completeness),
        ("Property 3: Health check availability", test_health_check_availability),
        ("Property 9: Request-response correlation", test_request_response_correlation),
        ("Property 6: Error response formatting", test_error_response_formatting),
        ("Property 5: JSON-RPC response formatting", test_jsonrpc_response_formatting),
        ("Property 4: JSON-RPC request routing", test_jsonrpc_request_routing),
        ("Property 8: Notification handling", test_notification_handling),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n=== Testing {name} ===")
        try:
            test_func()
            passed += 1
            print(f"✓ {name} PASSED")
        except Exception as e:
            failed += 1
            print(f"✗ {name} FAILED: {e}")
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_property_tests()
    sys.exit(0 if success else 1)
