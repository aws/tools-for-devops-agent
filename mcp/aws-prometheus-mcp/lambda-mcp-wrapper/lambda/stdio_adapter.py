"""
STDIO to HTTP Adapter for MCP Server in Lambda.

This adapter bridges the gap between:
- MCP SDK's STDIO transport (expects stdin/stdout communication)
- AWS Lambda's HTTP-based API Gateway events

The adapter simulates STDIO by:
1. Converting API Gateway events to JSON-RPC messages
2. Feeding them to the MCP server via simulated stdin
3. Capturing the server's stdout responses
4. Converting responses back to API Gateway format
"""

import asyncio
import json
import sys
import logging
from io import StringIO
from typing import Any, Dict
from contextlib import redirect_stdout, redirect_stderr

logger = logging.getLogger(__name__)


class MockContext:
    """Minimal Context mock for Lambda environment."""
    
    def __init__(self, request_id: str):
        self.request_id = request_id
    
    async def log(self, level: str, message: str, **kwargs):
        """Log to CloudWatch instead of MCP session."""
        log_func = getattr(logger, level, logger.info)
        log_func(f"[{self.request_id}] {message}")
    
    async def debug(self, message: str, **kwargs):
        await self.log("debug", message, **kwargs)
    
    async def info(self, message: str, **kwargs):
        await self.log("info", message, **kwargs)
    
    async def warning(self, message: str, **kwargs):
        await self.log("warning", message, **kwargs)
    
    async def error(self, message: str, **kwargs):
        await self.log("error", message, **kwargs)


class StdioAdapter:
    """Adapter to run STDIO-based MCP server in Lambda HTTP context."""
    
    def __init__(self, mcp_server):
        """Initialize the adapter with an MCP server instance.
        
        Args:
            mcp_server: The FastMCP server instance from prometheus_mcp_server
        """
        self.mcp_server = mcp_server
        
    async def handle_jsonrpc_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC request by routing it through the MCP server.
        
        Args:
            request: JSON-RPC request dict with 'method', 'params', 'id', etc.
            
        Returns:
            JSON-RPC response dict
        """
        method = request.get('method')
        params = request.get('params', {})
        request_id = request.get('id')
        
        # Route to appropriate handler based on method
        if method == 'initialize':
            return await self._handle_initialize(request_id)
        elif method == 'notifications/initialized':
            return {'jsonrpc': '2.0'}
        elif method == 'tools/list':
            return await self._handle_tools_list(request_id)
        elif method == 'tools/call':
            return await self._handle_tools_call(request_id, params)
        else:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }
    
    async def _handle_initialize(self, request_id: Any) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'protocolVersion': '2024-11-05',
                'capabilities': {'tools': {}},
                'serverInfo': {
                    'name': 'awslabs-prometheus-mcp-server',
                    'version': '1.0.0'
                }
            }
        }
    
    async def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list by extracting tool definitions from MCP server."""
        tools = []
        
        # Extract tool definitions from the MCP server's ToolManager
        if hasattr(self.mcp_server, '_tool_manager'):
            tool_list = self.mcp_server._tool_manager.list_tools()
            for tool in tool_list:
                tool_def = {
                    'name': tool.name,
                    'description': tool.description or '',
                    'inputSchema': tool.parameters_json_schema if hasattr(tool, 'parameters_json_schema') else {
                        'type': 'object',
                        'properties': {}
                    }
                }
                tools.append(tool_def)
        
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'tools': tools
            }
        }
    
    async def _handle_tools_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call by invoking the actual MCP tool.
        
        Args:
            request_id: JSON-RPC request ID
            params: Tool call parameters with 'name' and 'arguments'
            
        Returns:
            JSON-RPC response with tool result
        """
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        if not tool_name:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32602,
                    'message': 'Missing tool name'
                }
            }
        
        try:
            # Use the ToolManager to call the tool
            if not hasattr(self.mcp_server, '_tool_manager'):
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32603,
                        'message': 'Tool manager not found'
                    }
                }
            
            # Call the tool through the ToolManager
            # The ToolManager handles context injection and execution
            print(f"DEBUG: Calling tool {tool_name} with arguments: {arguments}")
            
            # Create minimal context for logging
            mock_ctx = MockContext(request_id=str(request_id))
            
            result = await self.mcp_server._tool_manager.call_tool(
                name=tool_name,
                arguments=arguments,
                context=mock_ctx,
                convert_result=True
            )
            print(f"DEBUG: Tool {tool_name} returned: {type(result)} - {result}")
            
            # Handle None result (FastMCP returns None on some errors)
            if result is None:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32603,
                        'message': f'Tool {tool_name} returned None - likely missing required parameters or configuration error'
                    }
                }
            
            # Format the result according to MCP protocol
            # FastMCP returns (content, metadata) tuple
            if isinstance(result, tuple) and len(result) == 2:
                content_list, metadata = result
                # Convert content items to dicts
                content = []
                for item in content_list:
                    if hasattr(item, 'model_dump'):
                        content.append(item.model_dump())
                    elif hasattr(item, 'type') and hasattr(item, 'text'):
                        content.append({'type': item.type, 'text': item.text})
                    else:
                        content.append(item)
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {'content': content}
                }
            
            # If result is a Pydantic model, convert to dict
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            
            # If result is already a list of content items, use it directly
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'type') and hasattr(first_item, 'text'):
                    # Already in MCP content format, extract text
                    content = []
                    for item in result:
                        if hasattr(item, 'model_dump'):
                            content.append(item.model_dump())
                        elif hasattr(item, 'type') and hasattr(item, 'text'):
                            content.append({'type': item.type, 'text': item.text})
                        else:
                            content.append(item)
                    return {
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'result': {'content': content}
                    }
            
            # Wrap result in MCP content format
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'content': [{
                        'type': 'text',
                        'text': json.dumps(result, indent=2)
                    }]
                }
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32603,
                    'message': f'Tool execution failed: {str(e)}'
                }
            }
