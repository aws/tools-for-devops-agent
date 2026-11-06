#!/usr/bin/env python3
"""SigV4 test client for the iam-drift-diff MCP server.

Calls the deployed MCP exactly the way DevOps Agent would (SigV4-signed,
Streamable HTTP, MCP initialize handshake), so the MCP can be validated
end-to-end WITHOUT DevOps Agent registration.

Usage (creds for the MCP's account must be active):
  python3 sigv4_client.py <endpoint-with-/mcp> list
  python3 sigv4_client.py <endpoint-with-/mcp> capture
  python3 sigv4_client.py <endpoint-with-/mcp> diff [before_id after_id]
  python3 sigv4_client.py <endpoint-with-/mcp> snapshots

Read-only against IAM: these tools only read IAM and write the server's own
snapshot objects.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = "us-east-1"
SERVICE = "lambda"  # Lambda Function URLs sign as service "lambda"
PROTOCOL_VERSION = "2025-06-18"


def _post(url: str, payload: dict, session_id: str | None) -> tuple[int, dict, str]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    headers["Mcp-Protocol-Version"] = PROTOCOL_VERSION

    creds = boto3.Session().get_credentials().get_frozen_credentials()
    req = AWSRequest(method="POST", url=url, data=body, headers=headers)
    SigV4Auth(creds, SERVICE, REGION).add_auth(req)

    http_req = urllib.request.Request(url, data=body, method="POST", headers=dict(req.headers))
    try:
        with urllib.request.urlopen(http_req, timeout=300) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", errors="replace")


def _parse(text: str) -> dict | None:
    """Response may be plain JSON or an SSE stream ('data: {...}' lines)."""
    text = text.strip()
    if not text:
        return None
    if text.startswith("{"):
        return json.loads(text)
    last = None
    for line in text.splitlines():
        if line.startswith("data:"):
            chunk = line[len("data:"):].strip()
            if chunk:
                last = json.loads(chunk)
    return last


def _session(url: str) -> str | None:
    status, headers, text = _post(url, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "sigv4-test-client", "version": "1.0"},
        },
    }, None)
    if status != 200:
        sys.exit(f"initialize failed: HTTP {status}: {text[:500]}")
    # A stateless server (stateless_http=True, as deployed on Lambda) returns no
    # session id; every request then stands alone.
    sid = next((v for k, v in headers.items() if k.lower() == "mcp-session-id"), None)
    _post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid


def _call(url: str, method: str, params: dict) -> dict:
    """Initialize + call; retry once with a fresh session if the container was cold."""
    for attempt in (1, 2):
        sid = _session(url)
        status, _, text = _post(url, {"jsonrpc": "2.0", "id": 2, "method": method, "params": params}, sid)
        if status == 200:
            return _parse(text) or {}
        if attempt == 1 and status in (400, 404):
            continue  # session landed on a different container; re-init once
        sys.exit(f"{method} failed: HTTP {status}: {text[:500]}")
    return {}


def _tool(url: str, name: str, args: dict | None = None) -> None:
    result = _call(url, "tools/call", {"name": name, "arguments": args or {}})
    if "error" in result:
        sys.exit(f"tool error: {json.dumps(result['error'], indent=2)}")
    content = result.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                print(json.dumps(json.loads(item["text"]), indent=2))
            except json.JSONDecodeError:
                print(item["text"])
    if not content:
        print(json.dumps(result.get("result", result), indent=2))


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    url, cmd = sys.argv[1], sys.argv[2]
    if not url.rstrip("/").endswith("/mcp"):
        sys.exit("endpoint must end with /mcp")
    url = url.rstrip("/")

    if cmd == "list":
        result = _call(url, "tools/list", {})
        for t in result.get("result", {}).get("tools", []):
            print(t["name"])
    elif cmd == "capture":
        _tool(url, "iam_snapshot_capture")
    elif cmd == "diff":
        ids = sys.argv[3:5]
        _tool(url, "iam_snapshot_diff",
              {"before_id": ids[0], "after_id": ids[1]} if len(ids) == 2 else None)
    elif cmd == "snapshots":
        _tool(url, "iam_snapshot_list")
    else:
        sys.exit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
