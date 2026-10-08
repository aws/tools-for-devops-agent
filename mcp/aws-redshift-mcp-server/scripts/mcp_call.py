"""Generic SigV4 MCP tool-call helper for the API Gateway deployment of
the Redshift MCP server.

Usage:
    export MCP_FUNCTION_URL="https://<api-id>.execute-api.<region>.amazonaws.com/Prod/mcp"
    export AWS_REGION="us-east-1"          # optional, defaults to us-east-1
    export AWS_PROFILE="your-profile"      # optional, uses default chain if unset

    python mcp_call.py list_clusters
    python mcp_call.py execute_query '{"cluster_identifier": "my-cluster", "database_name": "dev", "sql": "SELECT 1"}'
"""

import boto3
import json
import os
import sys
import urllib.error
import urllib.request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

URL = os.environ.get('MCP_FUNCTION_URL')
REGION = os.environ.get('AWS_REGION', 'us-east-1')
# SigV4 signing service for the target endpoint. The deployed endpoint is
# API Gateway, so this defaults to 'execute-api' (the same service AWS
# DevOps Agent's SigV4 auth signs for).
SERVICE = os.environ.get('MCP_SIGV4_SERVICE', 'execute-api')


def call(tool_name, arguments):
    if not URL:
        raise SystemExit('Set MCP_FUNCTION_URL to the API Gateway MCP endpoint (ending in /mcp).')

    session = boto3.Session(profile_name=os.environ.get('AWS_PROFILE'))
    credentials = session.get_credentials().get_frozen_credentials()

    body = json.dumps(
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': tool_name, 'arguments': arguments},
        }
    )
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
    }
    request = AWSRequest(method='POST', url=URL, data=body, headers=headers)
    SigV4Auth(credentials, SERVICE, REGION).add_auth(request)
    prepared_headers = dict(request.headers)

    req = urllib.request.Request(URL, data=body.encode('utf-8'), headers=prepared_headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python mcp_call.py <tool_name> [json_arguments]')
        raise SystemExit(1)
    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    status, text = call(tool, args)
    print(f'HTTP {status}')
    print(text)
