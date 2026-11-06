"""iam-drift-diff MCP server (Lambda Web Adapter entrypoint).

A read-only Model Context Protocol server that gives AWS DevOps Agent one
capability it cannot do reliably on its own: hold a prior IAM state and compute
an exact, complete set-difference against the current state across an entire
account. The model does not perform the comparison -- these tools do, as
deterministic data math -- and the model consumes the structured result to
judge risk and write recommendations.

Transport: Streamable HTTP, served at /mcp. In Lambda it runs behind the Lambda
Web Adapter (response_stream mode) fronted by a Function URL with AWS_IAM /
SigV4 auth -- service-to-service AWS auth, the paved path for an AWS-service
caller. This process performs NO auth of its own and MUST NOT be exposed
without that SigV4 layer; the SAM template wires it. The bind below is loopback:
the Lambda Web Adapter sidecar reaches the app over localhost inside the
function's own container, and the Function URL is the external boundary.

Read-only: no tool mutates IAM. The only writes are the agent's own snapshot
objects to its own private, encrypted S3 bucket in the same account.
"""

from __future__ import annotations

import json
import logging
import os
import sys

import boto3
from fastmcp import FastMCP

from iam_drift.aws import MIN_RETAIN, InvalidSnapshotId, SnapshotStore, validate_snapshot_id
from iam_drift.ops import run_capture, run_diff


# ---- startup safety gate (mirrors the accepted read-only MCP samples) -------
# Refuse to start without an explicit, non-wildcard account allowlist. This is a
# defense-in-depth guard; real authorization is the SigV4/AWS_IAM layer in front.
def _allowed_accounts() -> list[str]:
    raw = os.environ.get("ALLOWED_ACCOUNTS", "").strip()
    accounts = [a.strip() for a in raw.split(",") if a.strip()]
    if not accounts:
        sys.exit(
            "REFUSING TO START: ALLOWED_ACCOUNTS is required (comma-separated "
            "account IDs). This server will not run without an explicit allowlist."
        )
    if any(a == "*" or not a.isdigit() or len(a) != 12 for a in accounts):
        sys.exit(
            "REFUSING TO START: ALLOWED_ACCOUNTS must be explicit 12-digit "
            "account IDs, no wildcards."
        )
    return accounts


ALLOWED_ACCOUNTS = _allowed_accounts()
SNAPSHOT_BUCKET = os.environ.get("SNAPSHOT_BUCKET")
if not SNAPSHOT_BUCKET:
    sys.exit("REFUSING TO START: SNAPSHOT_BUCKET is required.")
# Retention never drops below MIN_RETAIN, whatever the environment says.
RETAIN = max(MIN_RETAIN, int(os.environ.get("SNAPSHOT_RETAIN", "12")))
# Captures closer together than this return the latest snapshot instead of
# writing a new one (threat model T004).
MIN_CAPTURE_INTERVAL = max(0, int(os.environ.get("MIN_CAPTURE_INTERVAL_SECONDS", "300")))
LIST_LIMIT_MAX = 50

mcp = FastMCP("iam-drift-diff")


# ---- audit log (threat model T015) ------------------------------------------
# One structured line per tool call: tool name, the invoking identity (from the
# Lambda Function URL request context forwarded by the Lambda Web Adapter), and
# snapshot ids. Never policy content and never principals from snapshots.
_audit = logging.getLogger("iam_drift.audit")
if not _audit.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    _audit.addHandler(_h)
    _audit.setLevel(logging.INFO)
    _audit.propagate = False


def _caller() -> dict:
    try:
        from fastmcp.server.dependencies import get_http_headers
        raw = get_http_headers(include_all=True).get("x-amzn-request-context")
        ctx = json.loads(raw) if raw else {}
    except Exception:
        ctx = {}
    iam = (ctx.get("authorizer") or {}).get("iam") or {}
    return {
        "request_id": ctx.get("requestId"),
        "caller_account": iam.get("accountId"),
        "caller_arn": iam.get("userArn"),
    }


def _log(tool: str, **fields) -> None:
    rec = {"event": "tool_call", "tool": tool, **_caller(), **fields}
    _audit.info(json.dumps(rec, default=str, separators=(",", ":")))


def _guard_account() -> str:
    """Confirm the live account is allowlisted. Returns the account id."""
    acct = boto3.client("sts").get_caller_identity()["Account"]
    if acct not in ALLOWED_ACCOUNTS:
        raise RuntimeError(
            f"Account {acct} is not in ALLOWED_ACCOUNTS; refusing to operate."
        )
    return acct


def _store() -> SnapshotStore:
    return SnapshotStore(bucket=SNAPSHOT_BUCKET)


def _not_found(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code")
    return code in ("NoSuchKey", "404", "NotFound")


@mcp.tool()
def iam_snapshot_capture() -> dict:
    """Capture the current IAM state of this account and store it.

    Exhaustively pages iam:GetAccountAuthorizationDetails (roles, users, groups,
    and customer-managed policies), normalizes every principal into an
    order-independent fingerprint, persists the snapshot, and returns the
    snapshot_id plus a machine-readable coverage block.

    If the latest snapshot is younger than the server's minimum capture
    interval, nothing is written: the response has `throttled: true` and the
    existing latest `snapshot_id`. A diff after a throttled capture still works.

    IMPORTANT for the caller: trust the returned `coverage.complete` flag. If it
    is false (a page truncated or a call was denied), the snapshot is partial --
    do not treat a later empty diff as "no drift." This tool never claims
    completeness it did not achieve.
    """
    _guard_account()
    result = run_capture(_store(), boto3.client("iam"), retain=RETAIN,
                         min_interval_seconds=MIN_CAPTURE_INTERVAL)
    _log("iam_snapshot_capture", snapshot_id=result["snapshot_id"],
         throttled=result["throttled"], pruned_count=len(result["pruned"]),
         complete=result["coverage"].get("complete"))
    return result


@mcp.tool()
def iam_snapshot_diff(before_id: str | None = None, after_id: str | None = None,
                      record_baseline: bool = False) -> dict:
    """Compute the exact set-difference between two stored snapshots.

    Defaults: after_id = the latest snapshot; before_id = the snapshot the last
    recorded report used (so captures made between scheduled runs do not hide a
    change), falling back to the previous snapshot until a report is recorded.
    `baseline_source` says which was used and `intervening_snapshots` counts
    snapshots captured in between -- report a non-zero count.

    Set `record_baseline` to true ONLY for the scheduled drift report: it records
    this pair as the new baseline (when no ids are given and the comparison is
    complete). Leave it false for ad-hoc or exploratory diffs so they have no
    side effects on the next report. Returns added
    principals, removed principals, and per-principal field changes
    (attached/inline/groups/trust/boundary), each with a neutral direction hint
    (up/down/lateral/mixed) the caller may override.

    IMPORTANT: check `comparison_complete`. It is true only when BOTH snapshots
    were complete captures. If it is false, an empty or small diff may be an
    artifact of a partial read, not real stability -- say so, do not report
    "no drift."
    """
    _guard_account()
    try:
        result = run_diff(_store(), before_id, after_id,
                          record_baseline=record_baseline is True)
    except InvalidSnapshotId as exc:
        _log("iam_snapshot_diff", error="invalid_snapshot_id")
        return {"error": str(exc)}
    except Exception as exc:
        if _not_found(exc):
            _log("iam_snapshot_diff", error="snapshot_not_found")
            return {"error": "snapshot not found"}
        raise
    _log("iam_snapshot_diff", before_id=result.get("before_id"),
         after_id=result.get("after_id"), baseline_source=result.get("baseline_source"),
         intervening_snapshots=result.get("intervening_snapshots"),
         record_baseline=record_baseline is True,
         baseline_advanced=result.get("baseline_advanced"), error=result.get("error"))
    return result


@mcp.tool()
def iam_snapshot_list(limit: int = 20) -> dict:
    """List stored snapshots, newest first, with their coverage summary.

    `limit` is clamped to 1..50. Lets the caller (and a human) see snapshot
    history and pick ids to diff.
    """
    _guard_account()
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    limit = min(max(1, limit), LIST_LIMIT_MAX)
    store = _store()
    ids = store.list_ids(limit=limit)
    out = []
    for item in ids:
        try:
            snap = store.get(item["snapshot_id"])
            out.append({
                "snapshot_id": item["snapshot_id"],
                "coverage": snap.get("coverage", {}),
            })
        except Exception:
            out.append({"snapshot_id": item["snapshot_id"], "coverage": None})
    _log("iam_snapshot_list", limit=limit, returned=len(out))
    return {"snapshots": out, "baseline": store.get_baseline()}


@mcp.tool()
def iam_snapshot_get_entity(snapshot_id: str, arn: str) -> dict:
    """Return one principal's normalized fingerprint from a stored snapshot.

    For drill-down (e.g. to show exactly what a flagged role looked like at a
    point in time) without re-reading the whole account.
    """
    _guard_account()
    try:
        validate_snapshot_id(snapshot_id)
        snap = _store().get(snapshot_id)
    except InvalidSnapshotId as exc:
        _log("iam_snapshot_get_entity", error="invalid_snapshot_id")
        return {"error": str(exc)}
    except Exception as exc:
        if _not_found(exc):
            _log("iam_snapshot_get_entity", snapshot_id=snapshot_id, error="snapshot_not_found")
            return {"error": "snapshot not found", "snapshot_id": snapshot_id}
        raise
    entity = snap.get("entities", {}).get(arn) if isinstance(arn, str) else None
    _log("iam_snapshot_get_entity", snapshot_id=snapshot_id, found=entity is not None)
    if entity is None:
        return {"error": f"arn not found in snapshot {snapshot_id}", "arn": arn}
    return {"snapshot_id": snapshot_id, "entity": entity}


# Served over Streamable HTTP at /mcp. The bind is loopback: in Lambda the
# Lambda Web Adapter sidecar reaches this over localhost inside the function
# container and the AWS_IAM Function URL is the external boundary; for local dev
# it is loopback-only. The port matches AWS_LWA_PORT in the template.
if __name__ == "__main__":
    port = int(os.environ.get("AWS_LWA_PORT", os.environ.get("PORT", "8000")))
    # stateless_http=True: Lambda has no sticky sessions, so an `initialize`
    # and the following `tools/list` / `tools/call` can land on different
    # containers. Stateful sessions (held in one container's memory) then fail
    # with "session not found". Stateless mode needs no session affinity. Every
    # tool here is self-contained (snapshots persist in S3, not in memory), so
    # nothing depends on per-session state.
    mcp.run(transport="http", host="127.0.0.1", port=port, path="/mcp",
            stateless_http=True)
