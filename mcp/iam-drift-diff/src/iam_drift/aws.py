"""AWS access layer: exhaustive IAM read + private S3 snapshot storage.

Read-only against IAM. The only writes are the server's own snapshot objects
(and a small baseline pointer) to its own private, encrypted S3 bucket in the
same account. Nothing here mutates customer IAM.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import boto3


# The one valid snapshot id shape, matching put()'s "%Y%m%dT%H%M%SZ". ASCII
# digits only ([0-9], not \d, which also matches non-ASCII digits). Anything
# else under the prefix ("zzz", "../x", "a/b", "99999999T999999Z") is ignored on
# read and rejected as input, so it can never become "latest" or reach an S3 key.
SNAPSHOT_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z")
SNAPSHOT_ID_FORMAT = "%Y%m%dT%H%M%SZ"

# Retention can never go below this many snapshots.
MIN_RETAIN = 4


class InvalidSnapshotId(ValueError):
    """Raised when a snapshot id is not a well-formed capture timestamp."""


def validate_snapshot_id(snapshot_id: Any) -> str:
    """Return snapshot_id if it is a real capture timestamp, else raise.

    Shape alone is not enough: "99999999T999999Z" matches the pattern but is not
    a real time, and a forged key like that would otherwise sort as "latest"
    forever. Parsing it as a UTC timestamp rejects it.
    """
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        raise InvalidSnapshotId(
            "snapshot_id must look like 20261102T120000Z (UTC capture time)"
        )
    try:
        datetime.strptime(snapshot_id, SNAPSHOT_ID_FORMAT)
    except ValueError as exc:
        raise InvalidSnapshotId(
            "snapshot_id is not a valid UTC capture time"
        ) from exc
    return snapshot_id


def snapshot_time(snapshot_id: str) -> datetime:
    """Capture time encoded in a (validated) snapshot id."""
    return datetime.strptime(validate_snapshot_id(snapshot_id),
                             SNAPSHOT_ID_FORMAT).replace(tzinfo=timezone.utc)


def _is_valid_id(stem: str) -> bool:
    try:
        validate_snapshot_id(stem)
        return True
    except InvalidSnapshotId:
        return False


# iam:GetAccountAuthorizationDetails returns every principal type in one
# paginated API. Requesting all filters gives roles, users, groups, and
# (local) managed policies together, which also closes the ListGroups /
# ListPolicies blind spot seen when those were denied individually.
_AUTH_FILTERS = ["User", "Role", "Group", "LocalManagedPolicy"]


def capture_authorization_details(iam_client) -> dict[str, Any]:
    """Exhaustively page through GetAccountAuthorizationDetails.

    Completeness is a correctness requirement: we follow every Marker to the
    end and count pages. If a call raises AccessDenied (or any ClientError), we
    record it in `denied` and mark the capture incomplete rather than returning
    a partial result that looks whole.
    """
    merged: dict[str, list] = {
        "UserDetailList": [],
        "RoleDetailList": [],
        "GroupDetailList": [],
        "Policies": [],
    }
    pages_fetched = 0
    truncated = False
    denied: list[str] = []

    marker = None
    try:
        while True:
            kwargs = {"Filter": _AUTH_FILTERS, "MaxItems": 1000}
            if marker:
                kwargs["Marker"] = marker
            resp = iam_client.get_account_authorization_details(**kwargs)
            pages_fetched += 1
            for key in merged:
                merged[key].extend(resp.get(key, []))
            if resp.get("IsTruncated"):
                marker = resp.get("Marker")
                if not marker:
                    # IsTruncated true but no marker -> cannot continue safely
                    truncated = True
                    break
            else:
                break
    except Exception as exc:  # boto3 ClientError and friends
        # Record the failure honestly; do not pretend the read completed.
        denied.append(f"get_account_authorization_details: {type(exc).__name__}: {exc}")
        truncated = True

    return {
        "auth_details": merged,
        "pages_fetched": pages_fetched,
        "truncated": truncated,
        "denied": denied,
    }


class SnapshotStore:
    """Private, encrypted S3 storage for snapshots, in the customer account.

    Keys are time-sortable so "previous" is unambiguous. No cross-account, no
    export (Tenets 1 and 6). The bucket itself is created by the SAM template
    with Block Public Access on and SSE enabled; this class only reads/writes
    objects.

    Hardening (threat model T001/T004):
    - Only keys whose stem is a real, non-future capture timestamp are listed;
      anything else under the prefix is ignored, so a foreign or forged object
      cannot become "latest" or push real snapshots out through pruning.
    - Ids passed in by callers are validated before they reach an S3 key.
    - A baseline pointer records the (before, after) pair of the last complete
      default diff. Default diffs compare against its `after` (not merely the
      previous capture), and pruning never deletes either side.
    """

    # Not a valid snapshot id, so list_ids() never treats it as a snapshot.
    BASELINE_STEM = "_baseline"
    # Tolerated clock skew when rejecting future-dated ids.
    FUTURE_SKEW_SECONDS = 300

    def __init__(self, bucket: str, prefix: str = "snapshots/", s3_client=None,
                 clock=None):
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/"
        self._s3 = s3_client or boto3.client("s3")
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # ---- keys ---------------------------------------------------------------
    def _key(self, snapshot_id: str) -> str:
        return f"{self._prefix}{validate_snapshot_id(snapshot_id)}.json"

    def _baseline_key(self) -> str:
        return f"{self._prefix}{self.BASELINE_STEM}.json"

    # ---- snapshots ----------------------------------------------------------
    def put(self, snapshot: dict[str, Any]) -> str:
        """Store a snapshot; return its snapshot_id (the time-sortable key stem)."""
        snapshot_id = self._now().strftime(SNAPSHOT_ID_FORMAT)
        body = dict(snapshot)
        body["snapshot_id"] = snapshot_id  # lets get() detect a moved/copied object
        self._s3.put_object(
            Bucket=self._bucket,
            Key=self._key(snapshot_id),
            Body=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )
        return snapshot_id

    def get(self, snapshot_id: str) -> dict[str, Any]:
        """Read one snapshot. Raises InvalidSnapshotId / ValueError if the id is
        malformed or the stored object is not a well-formed snapshot for it."""
        obj = self._s3.get_object(Bucket=self._bucket, Key=self._key(snapshot_id))
        snap = json.loads(obj["Body"].read())
        if (not isinstance(snap, dict) or not isinstance(snap.get("entities"), dict)
                or not isinstance(snap.get("coverage"), dict)):
            raise ValueError(f"object for snapshot {snapshot_id} is not a well-formed snapshot")
        embedded = snap.get("snapshot_id")
        if embedded is not None and embedded != snapshot_id:
            raise ValueError(
                f"object for snapshot {snapshot_id} claims to be {embedded}; refusing to use it")
        return snap

    def list_ids(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return valid snapshot ids newest-first. Ignores any key under the
        prefix whose stem is not a real capture time, or is dated in the future."""
        latest_allowed = self._now().timestamp() + self.FUTURE_SKEW_SECONDS
        paginator = self._s3.get_paginator("list_objects_v2")
        ids: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                k = obj["Key"]
                if not k.endswith(".json"):
                    continue
                stem = k[len(self._prefix):-len(".json")]
                if not _is_valid_id(stem):
                    continue
                if snapshot_time(stem).timestamp() > latest_allowed:
                    continue
                ids.append(stem)
        ids.sort(reverse=True)
        return [{"snapshot_id": sid} for sid in ids[:max(0, limit)]]

    def latest_two(self) -> tuple[str | None, str | None]:
        """Return (current_latest, previous) snapshot ids, or Nones."""
        ids = [x["snapshot_id"] for x in self.list_ids(limit=2)]
        latest = ids[0] if len(ids) >= 1 else None
        previous = ids[1] if len(ids) >= 2 else None
        return latest, previous

    # ---- baseline pointer ---------------------------------------------------
    def now(self) -> datetime:
        return self._now()

    def get_baseline(self) -> dict[str, str] | None:
        """The (before, after) pair of the last complete default diff, or None.

        Returns None if the pointer is absent or malformed, so a tampered
        pointer degrades to the plain latest-vs-previous behavior instead of
        steering the diff."""
        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=self._baseline_key())
            data = json.loads(obj["Body"].read())
            return {"before": validate_snapshot_id(data.get("before")),
                    "after": validate_snapshot_id(data.get("after"))}
        except Exception:
            return None

    def set_baseline(self, before_id: str, after_id: str) -> None:
        body = {"before": validate_snapshot_id(before_id),
                "after": validate_snapshot_id(after_id)}
        self._s3.put_object(
            Bucket=self._bucket,
            Key=self._baseline_key(),
            Body=json.dumps(body).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )

    # ---- retention ----------------------------------------------------------
    def prune(self, keep: int = 12, protect: tuple[str | None, ...] = ()) -> list[str]:
        """Delete all but the newest `keep` snapshots (never fewer than
        MIN_RETAIN), never deleting any id in `protect` (the last reported
        before/after pair).
        Returns deleted ids."""
        keep = max(MIN_RETAIN, int(keep))
        protected = {p for p in protect if p}
        ids = [x["snapshot_id"] for x in self.list_ids(limit=10_000)]
        to_delete = [sid for sid in ids[keep:] if sid not in protected]
        for sid in to_delete:
            self._s3.delete_object(Bucket=self._bucket, Key=self._key(sid))
        return to_delete
