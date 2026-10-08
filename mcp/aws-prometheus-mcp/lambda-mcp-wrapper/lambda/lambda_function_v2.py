"""
Lambda handler using official MCP SDK with STDIO adapter.

This version replaces the manual JSON-RPC implementation with:
- Official awslabs.prometheus_mcp_server
- STDIO adapter to bridge Lambda HTTP and MCP STDIO transport
"""

import json
import os
import sys
from datetime import datetime

# Add lambda directory to path to import local modules
sys.path.insert(0, os.path.dirname(__file__))

# Import the official Prometheus MCP server
from awslabs.prometheus_mcp_server.server import mcp as prometheus_mcp_server
from stdio_adapter import StdioAdapter


# Initialize the adapter with the official MCP server
adapter = StdioAdapter(prometheus_mcp_server)


def handler(event, context):
    """Lambda handler for Prometheus MCP server using official SDK."""
    
    try:
        # Parse the event
        if isinstance(event, str):
            event = json.loads(event)
        
        print(f"DEBUG: Received event: {json.dumps(event, default=str)}")
        
        # Check if this is an API Gateway event
        if 'httpMethod' in event:
            # Handle API Gateway health check
            if event.get('httpMethod') == 'GET' and '/health' in event.get('path', ''):
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'status': 'healthy',
                        'service': 'prometheus-mcp-lambda',
                        'version': '2.0-sdk',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                }
            
            # Handle API Gateway MCP requests
            if event.get('httpMethod') == 'POST' and '/mcp' in event.get('path', ''):
                # Extract MCP request from API Gateway body
                body = event.get('body', '{}')
                if event.get('isBase64Encoded'):
                    import base64
                    body = base64.b64decode(body).decode('utf-8')
                
                try:
                    mcp_request = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': 'Invalid JSON in request body'})
                    }
                
                # Process the MCP request using the adapter
                import asyncio
                mcp_response = asyncio.run(adapter.handle_jsonrpc_request(mcp_request))
                
                # Return API Gateway compatible response
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps(mcp_response) if not isinstance(mcp_response, str) else mcp_response
                }
            
            # Unknown API Gateway request
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Not found'})
            }
        
        # Direct MCP call (not through API Gateway)
        import asyncio
        return asyncio.run(adapter.handle_jsonrpc_request(event))
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
