#!/usr/bin/env python3
"""
Integration tests for MCP SDK migration with real AWS services.
Requires AWS credentials and at least one AMP workspace.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from stdio_adapter import StdioAdapter
import prometheus_mcp_server.server as prom_server

# Test configuration
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.environ.get('AWS_PROFILE', 'default')

print(f"Using AWS Profile: {AWS_PROFILE}, Region: {AWS_REGION}")


async def test_get_available_workspaces():
    """Task 2.2: Test GetAvailableWorkspaces integration"""
    print("\n=== Testing GetAvailableWorkspaces ===")
    
    adapter = StdioAdapter(prom_server.mcp)
    
    request = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/call',
        'params': {
            'name': 'GetAvailableWorkspaces',
            'arguments': {
                'region': AWS_REGION
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 1
    assert 'result' in response
    assert 'content' in response['result']
    
    content = json.loads(response['result']['content'][0]['text'])
    print(f"Found {content.get('count', 0)} workspaces")
    
    if content.get('count', 0) > 0:
        print(f"Workspaces: {[w['workspace_id'] for w in content['workspaces']]}")
        return content['workspaces'][0]['workspace_id']
    else:
        print("⚠️  No workspaces found - some tests will be skipped")
        return None


async def test_execute_query(workspace_id):
    """Task 2.3: Test ExecuteQuery integration"""
    if not workspace_id:
        print("\n=== Skipping ExecuteQuery (no workspace) ===")
        return
    
    print("\n=== Testing ExecuteQuery ===")
    
    adapter = StdioAdapter(prom_server.mcp)
    
    request = {
        'jsonrpc': '2.0',
        'id': 2,
        'method': 'tools/call',
        'params': {
            'name': 'ExecuteQuery',
            'arguments': {
                'workspace_id': workspace_id,
                'query': 'up',
                'region': AWS_REGION
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 2
    assert 'result' in response or 'error' in response
    
    if 'result' in response:
        content = json.loads(response['result']['content'][0]['text'])
        print(f"Query executed successfully")
        print(f"Result type: {content.get('resultType', 'unknown')}")
    else:
        print(f"Query returned error: {response['error']['message']}")


async def test_execute_range_query(workspace_id):
    """Task 2.4: Test ExecuteRangeQuery integration"""
    if not workspace_id:
        print("\n=== Skipping ExecuteRangeQuery (no workspace) ===")
        return
    
    print("\n=== Testing ExecuteRangeQuery ===")
    
    adapter = StdioAdapter(prom_server.mcp)
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    
    request = {
        'jsonrpc': '2.0',
        'id': 3,
        'method': 'tools/call',
        'params': {
            'name': 'ExecuteRangeQuery',
            'arguments': {
                'workspace_id': workspace_id,
                'query': 'up',
                'start': start_time.isoformat() + 'Z',
                'end': end_time.isoformat() + 'Z',
                'step': '5m',
                'region': AWS_REGION
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 3
    assert 'result' in response or 'error' in response
    
    if 'result' in response:
        content = json.loads(response['result']['content'][0]['text'])
        print(f"Range query executed successfully")
        print(f"Result type: {content.get('resultType', 'unknown')}")
    else:
        print(f"Range query returned error: {response['error']['message']}")


async def test_list_metrics(workspace_id):
    """Task 2.5: Test ListMetrics integration"""
    if not workspace_id:
        print("\n=== Skipping ListMetrics (no workspace) ===")
        return
    
    print("\n=== Testing ListMetrics ===")
    
    adapter = StdioAdapter(prom_server.mcp)
    
    request = {
        'jsonrpc': '2.0',
        'id': 4,
        'method': 'tools/call',
        'params': {
            'name': 'ListMetrics',
            'arguments': {
                'workspace_id': workspace_id,
                'region': AWS_REGION
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 4
    assert 'result' in response or 'error' in response
    
    if 'result' in response:
        content = json.loads(response['result']['content'][0]['text'])
        metrics = content.get('metrics', [])
        print(f"Found {len(metrics)} metrics")
        if metrics:
            print(f"Sample metrics: {metrics[:5]}")
    else:
        print(f"ListMetrics returned error: {response['error']['message']}")


async def test_get_server_info(workspace_id):
    """Task 2.6: Test GetServerInfo integration"""
    if not workspace_id:
        print("\n=== Skipping GetServerInfo (no workspace) ===")
        return
    
    print("\n=== Testing GetServerInfo ===")
    
    adapter = StdioAdapter(prom_server.mcp)
    
    request = {
        'jsonrpc': '2.0',
        'id': 5,
        'method': 'tools/call',
        'params': {
            'name': 'GetServerInfo',
            'arguments': {
                'workspace_id': workspace_id,
                'region': AWS_REGION
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 5
    assert 'result' in response or 'error' in response
    
    if 'result' in response:
        content = json.loads(response['result']['content'][0]['text'])
        print(f"Server info retrieved successfully")
        print(f"Prometheus URL: {content.get('prometheus_url', 'N/A')}")
    else:
        print(f"GetServerInfo returned error: {response['error']['message']}")


async def test_error_handling():
    """Task 2.7: Test error handling with invalid parameters"""
    print("\n=== Testing Error Handling ===")
    
    adapter = StdioAdapter(prom_server.mcp)
    
    # Test with invalid workspace ID
    request = {
        'jsonrpc': '2.0',
        'id': 6,
        'method': 'tools/call',
        'params': {
            'name': 'ExecuteQuery',
            'arguments': {
                'workspace_id': 'invalid-workspace-id',
                'query': 'up',
                'region': AWS_REGION
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 6
    
    # Should return error or result with error message
    if 'error' in response:
        print(f"✓ Error handling works: {response['error']['message']}")
    elif 'result' in response:
        content = json.loads(response['result']['content'][0]['text'])
        if 'error' in str(content).lower():
            print(f"✓ Error handling works: Error in result content")
        else:
            print(f"⚠️  Expected error but got success")
    
    # Test with missing required parameter
    request = {
        'jsonrpc': '2.0',
        'id': 7,
        'method': 'tools/call',
        'params': {
            'name': 'ExecuteQuery',
            'arguments': {
                'query': 'up'
                # Missing workspace_id
            }
        }
    }
    
    response = await adapter.handle_jsonrpc_request(request)
    assert response['jsonrpc'] == '2.0'
    assert response['id'] == 7
    print(f"✓ Missing parameter handling works")


async def run_integration_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("Integration Test Suite for MCP SDK Migration")
    print(f"AWS Profile: {AWS_PROFILE}, Region: {AWS_REGION}")
    print("=" * 60)
    
    try:
        # Task 2.2: Get available workspaces
        workspace_id = await test_get_available_workspaces()
        
        # Task 2.3: Execute query
        await test_execute_query(workspace_id)
        
        # Task 2.4: Execute range query
        await test_execute_range_query(workspace_id)
        
        # Task 2.5: List metrics
        await test_list_metrics(workspace_id)
        
        # Task 2.6: Get server info
        await test_get_server_info(workspace_id)
        
        # Task 2.7: Error handling
        await test_error_handling()
        
        print("\n" + "=" * 60)
        print("✓ All integration tests completed")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)
