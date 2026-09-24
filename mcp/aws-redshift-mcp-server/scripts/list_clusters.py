"""Quick smoke test: list Redshift clusters/workgroups via SigV4 against the
API Gateway deployment of the Redshift MCP server.

Usage:
    export MCP_FUNCTION_URL="https://<api-id>.execute-api.<region>.amazonaws.com/Prod/mcp"
    export AWS_REGION="us-east-1"          # optional, defaults to us-east-1
    export AWS_PROFILE="your-profile"      # optional, uses default chain if unset
    python list_clusters.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mcp_call import call  # noqa: E402

status, text = call('list_clusters', {})
print(f'HTTP {status}')
if status != 200:
    print(text[:1000])
    raise SystemExit(1)

data = json.loads(text)
items = data['result']['content']
print(f'\nFound {len(items)} clusters/workgroups:\n')
for item in items:
    c = json.loads(item['text'])
    print(f"- {c['identifier']:45s} type={c['type']:12s} status={c['status']}")
