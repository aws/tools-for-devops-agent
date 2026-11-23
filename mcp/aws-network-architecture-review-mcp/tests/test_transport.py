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


# ── Test-N11: local-mode DNS-rebinding guard ────────────────────────────────
# The local server (python server.py) has no SigV4 boundary. The __main__ path
# turns on host/origin protection with a loopback allowlist. This builds the
# same guarded app and checks a foreign Host header is rejected while loopback
# still works, so a rebound browser origin cannot drive the local tools.

@pytest.fixture(scope="module")
def local_guarded_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = server.mcp.http_app(
        **server.local_host_origin_guard(),
        **server.http_transport_options(),
    )
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp", port
    srv.should_exit = True
    thread.join(timeout=5)


def test_local_mode_rejects_foreign_host(local_guarded_url):
    url, port = local_guarded_url
    foreign = httpx.post(url, headers={**HEADERS, "Host": "attacker.example"}, json=INIT, timeout=10)
    assert foreign.status_code in (400, 403, 421), foreign.status_code
    loopback = httpx.post(url, headers={**HEADERS, "Host": f"127.0.0.1:{port}"}, json=INIT, timeout=10)
    assert loopback.status_code == 200


# ── Test-N13: invoker-role allowlist (T-004 / M-005) ────────────────────────
# With ALLOWED_INVOKER_ROLE_ARN set, only a session of that role (as reported in
# the Lambda Web Adapter's x-amzn-request-context header) is served. Every other
# caller, and any request whose caller is missing or ambiguous, gets 403.

ROLE = "arn:aws:iam::111122223333:role/service-role/DevOpsAgentNetArchReviewMCP-prod"
AGENT = "arn:aws:sts::111122223333:assumed-role/DevOpsAgentNetArchReviewMCP-prod/aidevops-session"


def _ctx(user_arn):
    return json.dumps({"authorizer": {"iam": {"userArn": user_arn}}})


@pytest.fixture
def allowlisted(base_url, monkeypatch):
    monkeypatch.setenv("ALLOWED_INVOKER_ROLE_ARN", ROLE)
    return base_url


def test_allowlisted_role_session_is_served(allowlisted):
    resp = httpx.post(allowlisted, headers={**HEADERS, "x-amzn-request-context": _ctx(AGENT)},
                      json=INIT, timeout=10)
    assert resp.status_code == 200


@pytest.mark.parametrize("caller", [
    "arn:aws:iam::111122223333:user/someone-with-invoke-on-star",
    "arn:aws:sts::111122223333:assumed-role/OtherRole/session",
    "arn:aws:sts::111122223333:assumed-role/DevOpsAgentNetArchReviewMCP-prodEvil/s",
    "arn:aws:sts::444455556666:assumed-role/DevOpsAgentNetArchReviewMCP-prod/s",
])
def test_other_callers_are_rejected(allowlisted, caller):
    resp = httpx.post(allowlisted, headers={**HEADERS, "x-amzn-request-context": _ctx(caller)},
                      json=INIT, timeout=10)
    assert resp.status_code == 403


def test_missing_or_garbled_caller_is_rejected(allowlisted):
    assert httpx.post(allowlisted, headers=HEADERS, json=INIT, timeout=10).status_code == 403
    garbled = httpx.post(allowlisted, headers={**HEADERS, "x-amzn-request-context": "not json"},
                         json=INIT, timeout=10)
    assert garbled.status_code == 403


def test_duplicate_context_header_is_rejected(allowlisted):
    # Two context headers is ambiguous (one could be client-supplied): fail closed.
    headers = list(HEADERS.items()) + [("x-amzn-request-context", _ctx(AGENT))] * 2
    resp = httpx.post(allowlisted, headers=headers, json=INIT, timeout=10)
    assert resp.status_code == 403


def test_misconfigured_allowlist_fails_closed(base_url, monkeypatch):
    monkeypatch.setenv("ALLOWED_INVOKER_ROLE_ARN", "not-an-arn")
    resp = httpx.post(base_url, headers={**HEADERS, "x-amzn-request-context": _ctx(AGENT)},
                      json=INIT, timeout=10)
    assert resp.status_code == 403


def test_allowlist_off_when_unset(base_url, monkeypatch):
    monkeypatch.delenv("ALLOWED_INVOKER_ROLE_ARN", raising=False)
    assert httpx.post(base_url, headers=HEADERS, json=INIT, timeout=10).status_code == 200


# ── Caller attribution in logs (BSC40 / T-011 / M-013) ──────────────────────


def test_method_log_names_the_caller(base_url, monkeypatch, capfd):
    monkeypatch.delenv("ALLOWED_INVOKER_ROLE_ARN", raising=False)
    httpx.post(base_url, headers={**HEADERS, "x-amzn-request-context": _ctx(AGENT)}, json=INIT, timeout=10)
    httpx.post(base_url, headers=HEADERS, json=INIT, timeout=10)
    out = capfd.readouterr().out
    assert f"mcp method=initialize caller={AGENT}" in out
    assert "mcp method=initialize caller=-" in out


def test_rejected_line_names_the_caller_and_cannot_be_forged(allowlisted, capfd):
    forged = "arn:aws:sts::111122223333:assumed-role/OtherRole/s\nmcp method=tools/call tool=x caller=" + AGENT
    resp = httpx.post(allowlisted, headers={**HEADERS, "x-amzn-request-context": _ctx(forged)},
                      json=INIT, timeout=10)
    assert resp.status_code == 403
    lines = [l for l in capfd.readouterr().out.splitlines() if l.startswith("mcp ")]
    assert lines == ["mcp rejected caller=arn:aws:sts::111122223333:assumed-role/OtherRole/s"
                     "mcpmethod=tools/calltool=xcaller=" + AGENT + " not in ALLOWED_INVOKER_ROLE_ARN"]
