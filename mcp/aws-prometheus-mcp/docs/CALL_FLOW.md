# MCP Client to Server Call Flow

This document describes the complete request/response flow from an MCP client to the Prometheus MCP Lambda server.

## Architecture Overview

```
MCP Client → OAuth Token → API Gateway → JWT Authorizer → Lambda → FastMCP → AWS Prometheus
```

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          MCP CLIENT TO SERVER FLOW                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   MCP Client     │  1. Read mcp-server-config.json
│ (Strands/Cursor) │     - endpoint URL
└────────┬─────────┘     - OAuth credentials
         │
         │ 2. OAuth Token Request
         │    POST /oauth2/token
         │    grant_type=client_credentials
         ▼
┌──────────────────┐
│  AWS Cognito     │  3. Validate credentials
│   User Pool      │     - Check client_id/secret
└────────┬─────────┘     - Generate JWT token
         │
         │ 4. Return JWT
         │    {"access_token": "eyJ..."}
         ▼
┌──────────────────┐
│   MCP Client     │  5. MCP Request
│                  │     POST /prod/mcp
└────────┬─────────┘     Authorization: Bearer eyJ...
         │                Body: JSON-RPC request
         │
         │ 6. HTTP POST
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AWS API GATEWAY                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  7. Extract JWT from Authorization header                             │ │
│  │  8. Invoke JWT Authorizer Lambda                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└────────┬─────────────────────────────────────────────────────────────────────┘
         │
         │ 9. Validate Token
         ▼
┌──────────────────┐
│ JWT Authorizer   │  10. Download Cognito JWKS
│     Lambda       │  11. Verify JWT signature
└────────┬─────────┘  12. Check expiration & scope
         │            13. Return IAM policy
         │
         │ 14. IAM Policy (Allow/Deny)
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AWS API GATEWAY                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  15. If authorized, invoke MCP Lambda                                  │ │
│  │  16. Pass event with body, headers, context                            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└────────┬─────────────────────────────────────────────────────────────────────┘
         │
         │ 17. Lambda Event
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      MCP LAMBDA FUNCTION                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  lambda_function_v2.handler()                                          │ │
│  │  18. Parse event['body'] → JSON-RPC request                            │ │
│  │  19. Create StdioAdapter(prometheus_mcp_server)                        │ │
│  │  20. Call adapter.handle_jsonrpc_request(request)                      │ │
│  └────────┬───────────────────────────────────────────────────────────────┘ │
│           │                                                                  │
│           │ 21. Route by method                                              │
│           ▼                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  stdio_adapter.py                                                      │ │
│  │  ┌──────────────┬──────────────┬──────────────┐                       │ │
│  │  │ initialize   │ tools/list   │ tools/call   │                       │ │
│  │  └──────────────┴──────────────┴──────┬───────┘                       │ │
│  │                                        │                                │ │
│  │  22. Extract tool_name & arguments     │                                │ │
│  │  23. Call mcp_server._tool_manager.call_tool()                         │ │
│  └────────┬───────────────────────────────────────────────────────────────┘ │
│           │                                                                  │
│           │ 24. Validate & execute                                           │
│           ▼                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  FastMCP ToolManager                                                   │ │
│  │  25. Find tool by name                                                 │ │
│  │  26. Validate arguments against schema                                 │ │
│  │  27. Inject Context object                                             │ │
│  │  28. Call tool function: list_metrics(ctx, workspace_id, ...)         │ │
│  └────────┬───────────────────────────────────────────────────────────────┘ │
│           │                                                                  │
│           │ 29. Execute tool                                                 │
│           ▼                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  prometheus_mcp_server/server.py                                       │ │
│  │  @mcp.tool(name='ListMetrics')                                         │ │
│  │  async def list_metrics(...):                                          │ │
│  │    30. configure_workspace_for_request()                               │ │
│  │    31. Get workspace URL from DescribeWorkspace API                    │ │
│  │    32. PrometheusClient.make_request()                                 │ │
│  └────────┬───────────────────────────────────────────────────────────────┘ │
└───────────┼──────────────────────────────────────────────────────────────────┘
            │
            │ 33. AWS API Call (SigV4 signed)
            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    AMAZON MANAGED PROMETHEUS                                 │
│  34. GET /workspaces/ws-xxx/api/v1/label/__name__/values                    │
│  35. Query metrics database                                                  │
│  36. Return: {"status":"success","data":["metric1","metric2",...]}          │
└────────┬─────────────────────────────────────────────────────────────────────┘
         │
         │ 37. Response data
         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      RESPONSE FLOW (REVERSE)                                 │
│                                                                              │
│  38. list_metrics() → MetricsList(metrics=[...])                            │
│         ↓                                                                    │
│  39. ToolManager → (content_list, metadata) tuple                           │
│         ↓                                                                    │
│  40. stdio_adapter → JSON-RPC format:                                       │
│      {"jsonrpc":"2.0","id":1,"result":{"content":[...]}}                    │
│         ↓                                                                    │
│  41. lambda_function_v2 → HTTP response:                                    │
│      {"statusCode":200,"body":"..."}                                        │
│         ↓                                                                    │
│  42. API Gateway → Forward to client                                        │
│         ↓                                                                    │
│  43. MCP Client → Parse and display                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Detailed Call Flow

### Component Interaction Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │     │             │
│ MCP Client  │────▶│  Cognito    │     │ API Gateway │     │ JWT Auth    │
│             │     │  User Pool  │     │             │     │  Lambda     │
│             │◀────│             │     │             │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘     └──────┬──────┘
      │                                        │                    │
      │                                        │                    │
      │ ③ POST /mcp                            │ ④ Validate JWT     │
      │    + JWT Token                         │                    │
      └────────────────────────────────────────▶                    │
                                               │                    │
                                               └───────────────────▶│
                                                                    │
                                               ◀────────────────────┘
                                               │ ⑤ IAM Policy
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MCP LAMBDA FUNCTION                                │
│                                                                             │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐      │
│  │ lambda_function  │──▶│ stdio_adapter    │──▶│ FastMCP          │      │
│  │     _v2.py       │   │      .py         │   │ ToolManager      │      │
│  └──────────────────┘   └──────────────────┘   └────────┬─────────┘      │
│                                                           │                 │
│                                                           ▼                 │
│                                              ┌──────────────────┐          │
│                                              │ prometheus_mcp   │          │
│                                              │   _server        │          │
│                                              │   /server.py     │          │
│                                              └────────┬─────────┘          │
└─────────────────────────────────────────────────────┼─────────────────────┘
                                                      │
                                                      │ ⑥ AWS API Call
                                                      │    (SigV4)
                                                      ▼
                                          ┌──────────────────────┐
                                          │  Amazon Managed      │
                                          │  Prometheus (AMP)    │
                                          │                      │
                                          │  • Query Engine      │
                                          │  • Metrics Storage   │
                                          └──────────────────────┘
```

### Sequence Diagram

```
Client    Cognito    API-GW    JWT-Auth    Lambda    FastMCP    Prometheus
  │          │          │          │          │         │           │
  │──①──────▶│          │          │          │         │           │
  │  Token   │          │          │          │         │           │
  │  Request │          │          │          │         │           │
  │          │          │          │          │         │           │
  │◀─②───────│          │          │          │         │           │
  │  JWT     │          │          │          │         │           │
  │          │          │          │          │         │           │
  │──③──────────────────▶│          │          │         │           │
  │  POST /mcp          │          │          │         │           │
  │  + JWT              │          │          │         │           │
  │          │          │          │          │         │           │
  │          │          │──④──────▶│          │         │           │
  │          │          │ Validate │          │         │           │
  │          │          │          │          │         │           │
  │          │          │◀─⑤───────│          │         │           │
  │          │          │ Allow    │          │         │           │
  │          │          │          │          │         │           │
  │          │          │──⑥──────────────────▶│         │           │
  │          │          │  Invoke              │         │           │
  │          │          │                      │         │           │
  │          │          │                      │──⑦─────▶│           │
  │          │          │                      │ Route   │           │
  │          │          │                      │         │           │
  │          │          │                      │         │──⑧───────▶│
  │          │          │                      │         │  Query    │
  │          │          │                      │         │           │
  │          │          │                      │         │◀─⑨───────│
  │          │          │                      │         │  Data     │
  │          │          │                      │         │           │
  │          │          │                      │◀─⑩─────│           │
  │          │          │                      │ Result  │           │
  │          │          │                      │         │           │
  │          │          │◀─⑪──────────────────│         │           │
  │          │          │  Response            │         │           │
  │          │          │                      │         │           │
  │◀─⑫──────────────────│                      │         │           │
  │  JSON-RPC          │                      │         │           │
  │  Response          │                      │         │           │
  │          │          │                      │         │           │
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REQUEST TRANSFORMATION                          │
└─────────────────────────────────────────────────────────────────────────┘

① MCP Client Request
   ┌────────────────────────────────────────────────────────────┐
   │ {                                                          │
   │   "jsonrpc": "2.0",                                        │
   │   "id": 1,                                                 │
   │   "method": "tools/call",                                  │
   │   "params": {                                              │
   │     "name": "ListMetrics",                                 │
   │     "arguments": {"workspace_id": "ws-xxx"}                │
   │   }                                                        │
   │ }                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
② API Gateway Event
   ┌────────────────────────────────────────────────────────────┐
   │ {                                                          │
   │   "httpMethod": "POST",                                    │
   │   "path": "/mcp",                                          │
   │   "headers": {"Authorization": "Bearer eyJ..."},           │
   │   "body": "{\"jsonrpc\":\"2.0\",\"id\":1,...}"            │
   │ }                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
③ Lambda Handler Parsing
   ┌────────────────────────────────────────────────────────────┐
   │ request = json.loads(event['body'])                        │
   │ method = "tools/call"                                      │
   │ params = {"name": "ListMetrics", "arguments": {...}}       │
   └────────────────────────────────────────────────────────────┘
                              ↓
④ STDIO Adapter Routing
   ┌────────────────────────────────────────────────────────────┐
   │ tool_name = "ListMetrics"                                  │
   │ arguments = {"workspace_id": "ws-xxx"}                     │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑤ FastMCP Tool Call
   ┌────────────────────────────────────────────────────────────┐
   │ list_metrics(                                              │
   │   ctx=Context(),                                           │
   │   workspace_id="ws-xxx",                                   │
   │   region=None,                                             │
   │   profile=None                                             │
   │ )                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑥ AWS API Request
   ┌────────────────────────────────────────────────────────────┐
   │ GET https://aps-workspaces.us-east-1.amazonaws.com/       │
   │     workspaces/ws-xxx/api/v1/label/__name__/values         │
   │ Authorization: AWS4-HMAC-SHA256 ...                        │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑦ Prometheus Response
   ┌────────────────────────────────────────────────────────────┐
   │ {                                                          │
   │   "status": "success",                                     │
   │   "data": ["metric1", "metric2", "metric3"]                │
   │ }                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑧ Tool Return Value
   ┌────────────────────────────────────────────────────────────┐
   │ MetricsList(                                               │
   │   metrics=["metric1", "metric2", "metric3"]                │
   │ )                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑨ FastMCP Conversion
   ┌────────────────────────────────────────────────────────────┐
   │ (                                                          │
   │   [TextContent(type="text", text='{"metrics":[...]}')],    │
   │   {}                                                       │
   │ )                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑩ STDIO Adapter Formatting
   ┌────────────────────────────────────────────────────────────┐
   │ {                                                          │
   │   "jsonrpc": "2.0",                                        │
   │   "id": 1,                                                 │
   │   "result": {                                              │
   │     "content": [{                                          │
   │       "type": "text",                                      │
   │       "text": "{\"metrics\":[\"metric1\",...]}"            │
   │     }]                                                     │
   │   }                                                        │
   │ }                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑪ Lambda HTTP Response
   ┌────────────────────────────────────────────────────────────┐
   │ {                                                          │
   │   "statusCode": 200,                                       │
   │   "headers": {"Content-Type": "application/json"},         │
   │   "body": "{\"jsonrpc\":\"2.0\",\"id\":1,...}"            │
   │ }                                                          │
   └────────────────────────────────────────────────────────────┘
                              ↓
⑫ Client Receives Response
   ┌────────────────────────────────────────────────────────────┐
   │ Parsed metrics: ["metric1", "metric2", "metric3"]         │
   └────────────────────────────────────────────────────────────┘
```

## Detailed Call Flow

### 1. MCP Client Initialization

**Component**: MCP Client (Strands/Cursor/Cline)

The client reads the server configuration from `mcp-server-config.json`:

```json
{
  "endpoint": "https://EXAMPLEAPIID.execute-api.us-east-1.amazonaws.com/prod/mcp",
  "authorization_configuration": {
    "client_id": "EXAMPLECLIENTID",
    "client_secret": "EXAMPLECLIENTSECRET...",
    "exchange_url": "https://example-mcp-domain.auth.us-east-1.amazoncognito.com/oauth2/token"
  }
}
```

### 2. OAuth Token Request

**Component**: AWS Cognito User Pool

**Request**:
```http
POST https://cognito-domain.auth.us-east-1.amazoncognito.com/oauth2/token
Content-Type: application/x-www-form-urlencoded
Authorization: Basic <base64(client_id:client_secret)>

grant_type=client_credentials&scope=prometheus-mcp-server/read
```

**Response**:
```json
{
  "access_token": "eyJraWQiOiJ...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### 3. MCP Request

**Component**: MCP Client

**Request**:
```http
POST https://EXAMPLEAPIID.execute-api.us-east-1.amazonaws.com/prod/mcp
Authorization: Bearer eyJraWQiOiJ...
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ListMetrics",
    "arguments": {
      "workspace_id": "ws-cbfcf915-b52c-4bc0-9499-8f24e1b4a81d"
    }
  }
}
```

### 4. API Gateway Processing

**Component**: Amazon API Gateway

- Receives HTTP POST request
- Extracts JWT token from `Authorization` header
- Routes to JWT Authorizer Lambda for validation

### 5. JWT Authorization

**Component**: JWT Authorizer Lambda  
**Function**: `PrometheusLambdaMCPAPIGatewa-JWTAuthorizerE8D8D90E-Bq2yvKofVWmC`

**Process**:
1. Extracts JWT token from request
2. Downloads Cognito JWKS (JSON Web Key Set)
3. Validates JWT signature
4. Checks token expiration
5. Verifies required scope: `prometheus-mcp-server/read`
6. Returns IAM policy (Allow/Deny)

**IAM Policy Response**:
```json
{
  "principalId": "user",
  "policyDocument": {
    "Version": "2012-10-17",
    "Statement": [{
      "Action": "execute-api:Invoke",
      "Effect": "Allow",
      "Resource": "arn:aws:execute-api:us-east-1:123456789012:*/prod/POST/mcp"
    }]
  }
}
```

### 6. Lambda Invocation

**Component**: API Gateway

If authorized, API Gateway invokes the MCP Lambda function with the event:

```json
{
  "httpMethod": "POST",
  "path": "/mcp",
  "headers": {
    "Authorization": "Bearer eyJraWQiOiJ...",
    "Content-Type": "application/json"
  },
  "body": "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{...}}"
}
```

### 7. Lambda Handler Entry Point

**Component**: `lambda_function_v2.py`  
**Function**: `PrometheusLambdaMCPStack-MCPFunction073462F8-a8KZ6hV11SHt`  
**Handler**: `lambda_function_v2.handler`

```python
def handler(event, context):
    # Extract JSON-RPC request from API Gateway event
    body = json.loads(event.get('body', '{}'))
    
    # Create STDIO adapter instance
    adapter = StdioAdapter(prometheus_mcp_server)
    
    # Handle request asynchronously
    result = asyncio.run(adapter.handle_jsonrpc_request(body))
    
    # Return HTTP response
    return {
        'statusCode': 200,
        'body': json.dumps(result),
        'headers': {'Content-Type': 'application/json'}
    }
```

### 8. STDIO Adapter Routing

**Component**: `stdio_adapter.py`

```python
async def handle_jsonrpc_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
    method = request.get('method')
    
    # Route based on JSON-RPC method
    if method == 'initialize':
        return await self._handle_initialize(request_id)
    elif method == 'tools/list':
        return await self._handle_tools_list(request_id)
    elif method == 'tools/call':
        return await self._handle_tools_call(request_id, params)
```

### 9. Tool Execution

**Component**: `stdio_adapter._handle_tools_call()`

```python
async def _handle_tools_call(self, request_id, params):
    tool_name = params.get('name')  # "ListMetrics"
    arguments = params.get('arguments')  # {"workspace_id": "ws-xxx"}
    
    # Call FastMCP ToolManager
    result = await self.mcp_server._tool_manager.call_tool(
        name=tool_name,
        arguments=arguments,
        context=None,
        convert_result=True
    )
    
    # Handle None result (error case)
    if result is None:
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'error': {
                'code': -32603,
                'message': f'Tool {tool_name} returned None'
            }
        }
    
    # Format result as JSON-RPC response
    return format_response(result, request_id)
```

### 10. FastMCP Tool Manager

**Component**: FastMCP ToolManager

**Process**:
1. Finds registered tool by name (`ListMetrics`)
2. Validates arguments against tool schema
3. Injects `Context` object
4. Calls the actual tool function

### 11. Tool Implementation

**Component**: `prometheus_mcp_server/server.py`

```python
@mcp.tool(name='ListMetrics')
async def list_metrics(
    ctx: Context,
    workspace_id: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> MetricsList:
    # Configure workspace
    workspace_config = await configure_workspace_for_request(
        ctx, workspace_id, region, profile
    )
    
    # Make API request to Prometheus
    data = await PrometheusClient.make_request(
        prometheus_url=workspace_config['prometheus_url'],
        endpoint='label/__name__/values',
        params={},
        region=workspace_config['region'],
        profile=workspace_config['profile']
    )
    
    return MetricsList(metrics=sorted(data))
```

### 12. AWS API Call

**Component**: PrometheusClient

**Request**:
```http
GET https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-xxx/api/v1/label/__name__/values
Authorization: AWS4-HMAC-SHA256 Credential=...
X-Amz-Date: 20251204T185102Z
```

**Process**:
1. Uses AWS SigV4 signing
2. Authenticates with Lambda's IAM role
3. Queries Amazon Managed Prometheus

**Response**:
```json
{
  "status": "success",
  "data": [
    "scrape_duration_seconds",
    "scrape_samples_scraped",
    "up"
  ]
}
```

### 13. Response Flow Back

**Component**: Full stack (reverse order)

1. **Tool Function** returns `MetricsList(metrics=[...])`

2. **FastMCP ToolManager** converts to tuple:
   ```python
   (content_list, metadata)
   ```

3. **STDIO Adapter** wraps in JSON-RPC format:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "result": {
       "content": [{
         "type": "text",
         "text": "{\"metrics\": [\"scrape_duration_seconds\", ...]}"
       }]
     }
   }
   ```

4. **Lambda Handler** returns HTTP response:
   ```json
   {
     "statusCode": 200,
     "headers": {"Content-Type": "application/json"},
     "body": "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{...}}"
   }
   ```

5. **API Gateway** forwards response to client

6. **MCP Client** receives and parses response

## Error Handling

### Missing workspace_id

**Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ListMetrics",
    "arguments": {}
  }
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Tool ListMetrics returned None - likely missing required parameters or configuration error"
  }
}
```

### Invalid JWT Token

**Response**: HTTP 403 Forbidden from API Gateway (before reaching Lambda)

### Tool Execution Error

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Tool execution failed: Error listing metrics: ..."
  }
}
```

## Performance Characteristics

| Stage | Typical Latency |
|-------|----------------|
| OAuth Token Request | 100-200ms |
| API Gateway + JWT Auth | 50-100ms |
| Lambda Cold Start | 1-3s (first request) |
| Lambda Warm | 100-300ms |
| AWS Prometheus API | 200-500ms |
| **Total (Cold)** | **1.5-4s** |
| **Total (Warm)** | **450-1100ms** |

## Security Flow

```
Client Credentials → JWT Token → Signature Validation → Scope Check → IAM Policy → Lambda Execution
```

1. **Client Authentication**: OAuth 2.0 Client Credentials flow
2. **Token Validation**: JWT signature verification using Cognito JWKS
3. **Authorization**: Scope-based access control (`prometheus-mcp-server/read`)
4. **AWS Authentication**: Lambda IAM role with AMP permissions
5. **API Security**: SigV4 signed requests to Prometheus

## Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| MCP Client | Initiates requests | Strands/Cursor/Cline |
| Cognito | OAuth token provider | AWS Cognito User Pool |
| API Gateway | HTTP endpoint | AWS API Gateway REST API |
| JWT Authorizer | Token validation | Lambda (Python 3.11) |
| MCP Lambda | Request processing | Lambda (Python 3.11) |
| STDIO Adapter | Protocol bridge | Custom Python |
| FastMCP | Tool management | MCP SDK |
| Prometheus Client | AWS API calls | Custom Python + boto3 |
| Amazon Prometheus | Metrics storage | AWS Managed Service |

## Configuration Files

- **mcp-server-config.json**: Client configuration (endpoint, OAuth)
- **lambda_function_v2.py**: Lambda entry point
- **stdio_adapter.py**: JSON-RPC to FastMCP bridge
- **prometheus_mcp_server/server.py**: Tool implementations

## Monitoring

- **CloudWatch Logs**: `/aws/lambda/PrometheusLambdaMCPStack-MCPFunction073462F8-a8KZ6hV11SHt`
- **API Gateway Logs**: Request/response logging
- **JWT Authorizer Logs**: Authentication failures
- **Metrics**: Lambda invocations, duration, errors

## Related Documentation

- [Authentication Methods](./AUTHENTICATION_METHODS.md)
- [Architecture Diagram](./solution_architecture.png)
- [README](../README.md)
