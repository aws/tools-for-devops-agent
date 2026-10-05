# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Transport tests: the Streamable HTTP behaviours Lambda depends on.

Runs the same app the Lambda entry point serves (server.http_transport_options)
on a loopback port, then checks the behaviours that broke in DevOps Agent chat
before they were fixed: stateless handling, the Mcp-Session-Id header, and
responses that terminate under Lambda Web Adapter response streaming.
"""

import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import server  # noqa: E402

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}}}


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = server.mcp.http_app(**server.http_transport_options())
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    srv.should_exit = True
    thread.join(timeout=5)


def _sse_json(resp):
    data = [line[5:].strip() for line in resp.text.splitlines() if line.startswith("data:")]
    return json.loads(data[-1] if data else resp.text)


def test_initialize_returns_session_id_header(base_url):
    resp = httpx.post(base_url, headers=HEADERS, json=INIT, timeout=10)
    assert resp.status_code == 200
    assert resp.headers.get("mcp-session-id")
    assert _sse_json(resp)["result"]["capabilities"]["tools"] is not None


def test_session_id_is_echoed_when_client_sends_one(base_url):
    resp = httpx.post(base_url, headers={**HEADERS, "mcp-session-id": "client-abc"}, json=INIT, timeout=10)
    assert resp.headers.get("mcp-session-id") == "client-abc"


def test_stateless_tools_list_works_with_unknown_session_id(base_url):
    # A request carrying a session ID no instance created must still succeed,
    # because Lambda may route it to a fresh execution environment.
    resp = httpx.post(base_url, headers={**HEADERS, "mcp-session-id": "never-issued"},
                      json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout=10)
    assert resp.status_code == 200
    assert len(_sse_json(resp)["result"]["tools"]) == 13


def test_notification_202_has_a_terminating_one_byte_body(base_url):
    # An empty body never terminates under Lambda Web Adapter response_stream.
    resp = httpx.post(base_url, headers={**HEADERS, "mcp-session-id": "x"},
                      json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=10)
    assert resp.status_code == 202
    assert resp.headers.get("content-length") == "1"
    assert resp.content == b"\n"


def test_delete_returns_200_with_body(base_url):
    resp = httpx.delete(base_url, headers={"mcp-session-id": "x"}, timeout=10)
    assert resp.status_code == 200
    assert resp.headers.get("content-length") == "1"


def test_get_stream_is_declined_with_405(base_url):
    # 405 tells the client no server-to-client stream is offered. An empty 200
    # stream instead makes clients reconnect in a tight loop.
    resp = httpx.get(base_url, headers={"Accept": "text/event-stream"}, timeout=10)
    assert resp.status_code == 405
