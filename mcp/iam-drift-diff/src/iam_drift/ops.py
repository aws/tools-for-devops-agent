"""Tool behavior, independent of the MCP transport, so it can be unit-tested.

server.py is a thin FastMCP wrapper around these two functions.

Capture throttle + baseline (threat model T004): a caller who can invoke the
server could otherwise make a malicious IAM change, then capture (once, or
repeatedly) so the next scheduled run's default "latest vs previous" diff
compares two post-change snapshots and reports nothing. Two controls close
that:

1. Captures closer together than `min_interval_seconds` do not write: they
   return the latest existing snapshot with `throttled: true`.
2. The default diff compares against the last *reported* snapshot, not merely
   the previous capture, and reports how many snapshots were captured in
   between. Only a diff that asks for it (`record_baseline=True`, which the
   scheduled drift run passes) moves that pointer, so ad-hoc diffs have no side
   effects. Pruning never deletes the reported pair.
"""

from __future__ import annotations

import math
from typing import Any

from .aws import (
    InvalidSnapshotId,
    SnapshotStore,
    capture_authorization_details,
    snapshot_time,
    validate_snapshot_id,
)
from .diff import diff_snapshots
from .snapshot import build_snapshot


def run_capture(store: SnapshotStore, iam_client, *, retain: int,
                min_interval_seconds: int) -> dict[str, Any]:
    """Capture + persist + prune, unless throttled."""
    latest, _ = store.latest_two()
    if latest and min_interval_seconds > 0:
        age = (store.now() - snapshot_time(latest)).total_seconds()
        if age < min_interval_seconds:
            return {
                "throttled": True,
                "snapshot_id": latest,
                "retry_after_seconds": max(1, math.ceil(min_interval_seconds - age)),
                "coverage": store.get(latest).get("coverage", {}),
                "pruned": [],
                "note": ("A snapshot was captured less than the minimum interval ago; "
                         "returning it instead of writing a new one. Nothing was written "
                         "or pruned."),
            }

    raw = capture_authorization_details(iam_client)
    snap = build_snapshot(
        raw["auth_details"],
        pages_fetched=raw["pages_fetched"],
        truncated=raw["truncated"],
        denied=raw["denied"],
    )
    snapshot_id = store.put(snap)
    pointer = store.get_baseline()
    deleted = store.prune(keep=retain,
                          protect=((pointer or {}).get("before"), (pointer or {}).get("after")))
    return {
        "throttled": False,
        "snapshot_id": snapshot_id,
        "coverage": snap["coverage"],
        "pruned": deleted,
    }


def run_diff(store: SnapshotStore, before_id: str | None = None,
             after_id: str | None = None, record_baseline: bool = False) -> dict[str, Any]:
    """Diff two snapshots. With no ids, compare the latest against the last
    reported snapshot. Only when `record_baseline` is True (the scheduled report)
    and the comparison is complete is the new pair recorded as the baseline."""
    if before_id is not None:
        validate_snapshot_id(before_id)
    if after_id is not None:
        validate_snapshot_id(after_id)
    defaulted = before_id is None and after_id is None

    ids = [x["snapshot_id"] for x in store.list_ids(limit=10_000)]  # newest first
    present = set(ids)
    latest = ids[0] if ids else None
    previous = ids[1] if len(ids) > 1 else None

    after_id = after_id or latest
    baseline_source = "explicit" if before_id else None
    pointer = store.get_baseline() if before_id is None else None

    if before_id is None:
        p_before = (pointer or {}).get("before")
        p_after = (pointer or {}).get("after")
        if p_after and after_id == p_after and p_before in present:
            # Nothing new since the last report (e.g. a throttled capture or a
            # retry): repeat that report rather than claim "no drift".
            before_id, baseline_source = p_before, "repeat_of_last_report"
        elif p_after in present and after_id and p_after < after_id:
            before_id, baseline_source = p_after, "last_reported"
        else:
            if after_id == latest:
                before_id = previous
            else:
                older = [i for i in ids if after_id and i < after_id]
                before_id = older[0] if older else None
            baseline_source = "previous_baseline_missing" if pointer else "previous"

    if before_id is None or after_id is None:
        return {
            "error": "need two snapshots to diff; capture at least twice first",
            "available": store.list_ids(limit=5),
        }

    result = diff_snapshots(store.get(before_id), store.get(after_id))
    result["before_id"] = before_id
    result["after_id"] = after_id
    result["baseline_source"] = baseline_source
    lo, hi = sorted((before_id, after_id))
    result["intervening_snapshots"] = sum(1 for i in ids if lo < i < hi)

    advanced = (record_baseline is True and defaulted
                and result.get("comparison_complete") is True
                and baseline_source != "repeat_of_last_report")
    if advanced:
        store.set_baseline(before_id, after_id)
    result["baseline_advanced"] = advanced
    return result


__all__ = ["run_capture", "run_diff", "InvalidSnapshotId"]
