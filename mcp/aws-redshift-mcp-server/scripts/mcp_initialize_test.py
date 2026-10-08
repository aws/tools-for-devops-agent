"""Diagnostic: send a raw MCP 'initialize' request (the same handshake an
MCP client does when first connecting) against the API Gateway endpoint,
to isolate whether an "Internal server error" / "Failed to initialize"
DevOps Agent sees is an API Gateway integration problem vs. something in
the MCP server itself.

Usage:
    export AWS_PROFILE="your-profile"
    python mcp_initialize_test.py <url> [service]

    python mcp_initialize_test.py https://<api-id>.execute-api.<region>.amazonaws.com/Prod/mcp

`service` defaults to 'execute-api' (the deployed endpoint's signing
service) and normally doesn't need to be passed explicitly.
"""

import boto3
import json
import os
import sys
import urllib.error
import urllib.request
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = os.environ.get('AWS_REGION', 'us-east-1')


def call(url, service):
    session = boto3.Session(profile_name=os.environ.get('AWS_PROFILE'))
    credentials = session.get_credentials().get_frozen_credentials()

    body = json.dumps(
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2025-06-18',
                'capabilities': {},
                'clientInfo': {'name': 'diagnostic-test', 'version': '0.0.1'},
            },
        }
    )
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
    }
    request = AWSRequest(method='POST', url=url, data=body, headers=headers)
    SigV4Auth(credentials, service, REGION).add_auth(request)
    prepared_headers = dict(request.headers)

    req = urllib.request.Request(url, data=body.encode('utf-8'), headers=prepared_headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8', errors='replace')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python mcp_initialize_test.py <url> [service]')
        raise SystemExit(1)
    url = sys.argv[1]
    service = sys.argv[2] if len(sys.argv) > 2 else 'execute-api'
    status, headers, text = call(url, service)
    print(f'HTTP {status}')
    print('Headers:', json.dumps(headers, indent=2))
    print('Body:', text[:2000])
