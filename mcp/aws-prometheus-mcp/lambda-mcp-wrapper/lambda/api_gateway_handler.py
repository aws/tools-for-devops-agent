import json
import boto3
from datetime import datetime
from lambda_function import handler as mcp_handler

def handler(event, context):
    """API Gateway compatible handler for Prometheus MCP server"""
    
    try:
        print(f"DEBUG: API Gateway event: {json.dumps(event, default=str)}")
        
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
            
            # Call the original MCP handler
            mcp_response = mcp_handler(mcp_request, context)
            
            # Return API Gateway compatible response
            if isinstance(mcp_response, dict) and 'statusCode' in mcp_response:
                return mcp_response
            else:
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps(mcp_response) if not isinstance(mcp_response, str) else mcp_response
                }
        
        # Unknown request
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found'})
        }
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
