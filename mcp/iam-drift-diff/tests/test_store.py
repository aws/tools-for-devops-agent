"""Tests for the snapshot store, capture throttle, baseline pointer, and the
server-boundary validation added for threat-model findings T001, T004, T011.

A small in-memory fake stands in for S3 and IAM; no AWS access is needed.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from iam_drift.aws import (MIN_RETAIN, BaselinePointerUnreadable, InvalidSnapshotId, SnapshotStore,
                           validate_snapshot_id)
from iam_drift.ops import run_capture, run_diff

ACCT = "111122223333"
ADMIN = "arn:aws:iam::aws:policy/AdministratorAccess"
BUCKET = "test-bucket"


# ---- fakes ------------------------------------------------------------------
class _NoSuchKey(Exception):
    def __init__(self, key):
        super().__init__(f"NoSuchKey: {key}")
        self.response = {"Error": {"Code": "NoSuchKey"}}


class _ClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail_keys: dict[str, Exception] = {}
        self.owners: list[tuple[str, str | None]] = []  # (call, ExpectedBucketOwner)

    def put_object(self, Bucket, Key, Body, **kw):
        self.owners.append(("put", kw.get("ExpectedBucketOwner")))
        self.calls.append(("put", Key))
        self.objects[Key] = Body if isinstance(Body, bytes) else Body.encode()

    def get_object(self, Bucket, Key, **kw):
        self.owners.append(("get", kw.get("ExpectedBucketOwner")))
        self.calls.append(("get", Key))
        if Key in self.fail_keys:
            raise self.fail_keys[Key]
        if Key not in self.objects:
            raise _NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key, **kw):
        self.owners.append(("delete", kw.get("ExpectedBucketOwner")))
        self.calls.append(("delete", Key))
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        fake = self

        class _P:
            def paginate(self, Bucket, Prefix, **kw):
                fake.owners.append(("list", kw.get("ExpectedBucketOwner")))
                yield {"Contents": [{"Key": k} for k in sorted(fake.objects) if k.startswith(Prefix)]}
        return _P()


class FakeIAM:
    def __init__(self, roles):
        self.roles = roles
        self.calls = 0

    def get_account_authorization_details(self, **_):
        self.calls += 1
        return {"RoleDetailList": self.roles, "UserDetailList": [], "GroupDetailList": [],
                "Policies": [], "IsTruncated": False}


class Clock:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t = self.t + timedelta(**kw)


def _role(name, attached=()):
    return {
        "RoleName": name, "Arn": f"arn:aws:iam::{ACCT}:role/{name}", "Path": "/",
        "CreateDate": "2026-10-01T00:00:00Z",
        "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": [{
            "Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{ACCT}:root"},
            "Action": "sts:AssumeRole"}]},
        "AttachedManagedPolicies": [{"PolicyArn": a} for a in attached],
        "RolePolicyList": [],
    }


def _snap_body(sid=None, complete=True):
    body = {"schema": 1, "entities": {}, "coverage": {"complete": complete}}
    if sid:
        body["snapshot_id"] = sid
    return json.dumps(body).encode()


START = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)


def _store(clock=None):
    s3 = FakeS3()
    return SnapshotStore(BUCKET, s3_client=s3, clock=clock or Clock(START)), s3


def _seed(s3, sid, complete=True):
    s3.objects[f"snapshots/{sid}.json"] = _snap_body(sid, complete)


# ---- T001: forged / foreign keys and path-like ids -------------------------
def test_list_ids_ignores_forged_and_foreign_keys():
    store, s3 = _store()
    real = ["20261101T000000Z", "20261102T110000Z"]
    for sid in real:
        _seed(s3, sid)
    for k in ["snapshots/zzz.json", "snapshots/99999999T999999Z.json",
              "snapshots/20991231T235959Z.json",            # future-dated
              "snapshots/a/20261101T000000Z.json",           # nested
              "snapshots/_baseline.json", "snapshots/20261101T000000Z.txt",
              "snapshots/20261301T000000Z.json"]:            # month 13
        s3.objects[k] = _snap_body()
    assert [x["snapshot_id"] for x in store.list_ids()] == list(reversed(real))
    assert store.latest_two() == ("20261102T110000Z", "20261101T000000Z")


@pytest.mark.parametrize("bad", ["../x", "20261101T000000Z/../../x", "a/b", "", None,
                                 "20261101T000000", "20261301T000000Z", " 20261101T000000Z",
                                 "２０２６1101T000000Z"])
def test_get_and_key_reject_path_like_ids(bad):
    store, s3 = _store()
    with pytest.raises(InvalidSnapshotId):
        store.get(bad)
    assert s3.calls == []  # rejected before any S3 key is built


def test_get_rejects_object_claiming_a_different_id():
    store, s3 = _store()
    s3.objects["snapshots/20261102T110000Z.json"] = _snap_body("20261101T000000Z")
    with pytest.raises(ValueError):
        store.get("20261102T110000Z")


def test_forged_future_key_does_not_cause_real_snapshots_to_be_pruned():
    store, s3 = _store()
    for h in range(MIN_RETAIN + 2):
        _seed(s3, (START - timedelta(hours=h + 1)).strftime("%Y%m%dT%H%M%SZ"))
    s3.objects["snapshots/20991231T235959Z.json"] = _snap_body()
    deleted = store.prune(keep=MIN_RETAIN)
    assert len(deleted) == 2
    assert "20991231T235959Z" not in deleted
    assert len(store.list_ids()) == MIN_RETAIN


# ---- T004: throttle, retention floor, baseline anchor ----------------------
def test_capture_throttle_returns_latest_and_writes_nothing():
    clock = Clock(START)
    store, s3 = _store(clock)
    _seed(s3, (START - timedelta(seconds=60)).strftime("%Y%m%dT%H%M%SZ"))
    iam = FakeIAM([_role("app")])
    s3.calls.clear()
    out = run_capture(store, iam, retain=12, min_interval_seconds=300)
    assert out["throttled"] is True
    assert out["snapshot_id"] == "20261102T115900Z"
    assert out["retry_after_seconds"] == 240
    assert out["pruned"] == []
    assert iam.calls == 0
    assert not [c for c in s3.calls if c[0] in ("put", "delete")]


def test_capture_after_interval_writes_and_reports_coverage():
    clock = Clock(START)
    store, s3 = _store(clock)
    _seed(s3, (START - timedelta(seconds=301)).strftime("%Y%m%dT%H%M%SZ"))
    out = run_capture(store, FakeIAM([_role("app")]), retain=12, min_interval_seconds=300)
    assert out["throttled"] is False
    assert out["snapshot_id"] == "20261102T120000Z"
    assert out["coverage"]["complete"] is True
    assert json.loads(s3.objects["snapshots/20261102T120000Z.json"])["snapshot_id"] == out["snapshot_id"]


def test_prune_never_goes_below_retain_floor():
    store, s3 = _store()
    for h in range(10):
        _seed(s3, (START - timedelta(hours=h)).strftime("%Y%m%dT%H%M%SZ"))
    store.prune(keep=1)
    assert len(store.list_ids()) == MIN_RETAIN


def test_prune_keeps_the_reported_baseline_pair():
    store, s3 = _store()
    ids = [(START - timedelta(hours=h)).strftime("%Y%m%dT%H%M%SZ") for h in range(20)]
    for sid in ids:
        _seed(s3, sid)
    oldest, second_oldest = ids[-1], ids[-2]
    store.set_baseline(oldest, second_oldest)
    deleted = store.prune(keep=MIN_RETAIN, protect=(oldest, second_oldest))
    remaining = {x["snapshot_id"] for x in store.list_ids(limit=100)}
    assert oldest in remaining and second_oldest in remaining
    assert len(remaining) == MIN_RETAIN + 2
    assert len(deleted) == 20 - MIN_RETAIN - 2


def _capture(store, clock, roles, **adv):
    clock.advance(**adv)
    return run_capture(store, FakeIAM(roles), retain=12, min_interval_seconds=300)["snapshot_id"]


def test_out_of_band_capture_after_a_change_does_not_hide_it():
    """The T004 attack: change IAM, then capture so the next scheduled run would
    compare two post-change snapshots. The default diff must still report it."""
    clock = Clock(START)
    store, _ = _store(clock)
    s0 = _capture(store, clock, [_role("quiet")], seconds=0)
    s1 = _capture(store, clock, [_role("quiet")], days=7)
    first = run_diff(store, record_baseline=True)              # weekly run 1
    assert (first["before_id"], first["after_id"]) == (s0, s1)
    assert first["baseline_advanced"] is True

    _capture(store, clock, [_role("quiet", [ADMIN])], days=3)   # attacker: change + capture
    _capture(store, clock, [_role("quiet", [ADMIN])], hours=1)  # ...and again
    s2 = _capture(store, clock, [_role("quiet", [ADMIN])], days=4)
    weekly = run_diff(store, record_baseline=True)             # weekly run 2
    assert weekly["before_id"] == s1 and weekly["after_id"] == s2
    assert weekly["baseline_source"] == "last_reported"
    assert weekly["intervening_snapshots"] == 2
    attached = [c for c in weekly["changed_principals"] if c.get("changes", {}).get("attached_added")]
    assert attached, weekly


def test_exploratory_default_diff_does_not_move_baseline():
    """An ad-hoc default diff between scheduled runs must have no side effects:
    the next scheduled report still compares against the last recorded one."""
    clock = Clock(START)
    store, _ = _store(clock)
    _capture(store, clock, [_role("quiet")], seconds=0)
    s1 = _capture(store, clock, [_role("quiet")], days=7)
    run_diff(store, record_baseline=True)                      # scheduled run 1
    _capture(store, clock, [_role("quiet", [ADMIN])], days=2)  # change, then capture
    adhoc = run_diff(store)                                    # exploratory diff
    assert adhoc["before_id"] == s1 and adhoc["baseline_advanced"] is False
    s2 = _capture(store, clock, [_role("quiet", [ADMIN])], days=5)
    weekly = run_diff(store, record_baseline=True)             # scheduled run 2
    assert (weekly["before_id"], weekly["after_id"]) == (s1, s2)
    assert weekly["intervening_snapshots"] == 1
    assert any(c["changes"].get("attached_added") for c in weekly["changed_principals"])


def test_default_diff_without_record_flag_never_writes_pointer():
    store, s3 = _store()
    for sid in ["20261101T000000Z", "20261102T000000Z"]:
        _seed(s3, sid)
    out = run_diff(store)
    assert out["baseline_advanced"] is False and store.get_baseline() is None
    assert not [c for c in s3.calls if c == ("put", "snapshots/_baseline.json")]


def test_repeat_diff_without_new_snapshot_repeats_last_report():
    clock = Clock(START)
    store, _ = _store(clock)
    _capture(store, clock, [_role("quiet")], seconds=0)
    s1 = _capture(store, clock, [_role("quiet", [ADMIN])], days=7)
    first = run_diff(store, record_baseline=True)
    throttled = run_capture(store, FakeIAM([_role("quiet", [ADMIN])]), retain=12,
                            min_interval_seconds=300)
    assert throttled["throttled"] is True and throttled["snapshot_id"] == s1
    again = run_diff(store, record_baseline=True)
    assert again["baseline_source"] == "repeat_of_last_report"
    assert (again["before_id"], again["after_id"]) == (first["before_id"], first["after_id"])
    assert again["summary"] == first["summary"]
    assert again["baseline_advanced"] is False


def test_incomplete_comparison_does_not_advance_baseline():
    store, s3 = _store()
    _seed(s3, "20261101T000000Z")
    _seed(s3, "20261102T000000Z", complete=False)
    out = run_diff(store, record_baseline=True)
    assert out["comparison_complete"] is False
    assert out["baseline_advanced"] is False
    assert store.get_baseline() is None


def test_explicit_ids_do_not_move_baseline():
    store, s3 = _store()
    for sid in ["20261101T000000Z", "20261102T000000Z", "20261103T000000Z"]:
        _seed(s3, sid)
    out = run_diff(store, before_id="20261101T000000Z", after_id="20261102T000000Z",
                   record_baseline=True)
    assert out["baseline_source"] == "explicit" and out["baseline_advanced"] is False
    assert store.get_baseline() is None


def test_tampered_baseline_pointer_falls_back_to_previous():
    store, s3 = _store()
    for sid in ["20261101T000000Z", "20261102T000000Z"]:
        _seed(s3, sid)
    s3.objects["snapshots/_baseline.json"] = json.dumps({"before": "../x", "after": "zzz"}).encode()
    out = run_diff(store)
    assert out["before_id"] == "20261101T000000Z"
    assert out["baseline_source"] == "baseline_pointer_invalid"


def test_missing_baseline_snapshot_is_reported():
    store, s3 = _store()
    for sid in ["20261101T000000Z", "20261102T000000Z"]:
        _seed(s3, sid)
    store.set_baseline("20261020T000000Z", "20261025T000000Z")  # both gone
    out = run_diff(store)
    assert out["baseline_source"] == "previous_baseline_missing"
    assert out["before_id"] == "20261101T000000Z"


def test_first_run_needs_two_snapshots():
    store, s3 = _store()
    _seed(s3, "20261101T000000Z")
    assert "error" in run_diff(store)


def test_validate_snapshot_id_accepts_real_capture_time():
    assert validate_snapshot_id("20261102T120000Z") == "20261102T120000Z"


# ---- server boundary --------------------------------------------------------
@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("ALLOWED_ACCOUNTS", ACCT)
    monkeypatch.setenv("SNAPSHOT_BUCKET", BUCKET)
    monkeypatch.setenv("SNAPSHOT_RETAIN", "1")
    import importlib
    import server as srv
    srv = importlib.reload(srv)
    store, s3 = _store()
    monkeypatch.setattr(srv, "_store", lambda owner=None: store)
    monkeypatch.setattr(srv, "_guard_account", lambda: ACCT)
    return srv, store, s3


def test_server_record_baseline_is_opt_in(server):
    srv, store, s3 = server
    for sid in ["20261101T000000Z", "20261102T000000Z"]:
        _seed(s3, sid)
    assert srv.iam_snapshot_diff()["baseline_advanced"] is False
    assert store.get_baseline() is None
    assert srv.iam_snapshot_diff(record_baseline=True)["baseline_advanced"] is True
    assert store.get_baseline() == {"before": "20261101T000000Z", "after": "20261102T000000Z"}


def test_server_retain_minimum_is_enforced(server):
    srv, _, _ = server
    assert srv.RETAIN == MIN_RETAIN


def test_server_rejects_path_like_ids_with_friendly_error(server):
    srv, _, s3 = server
    assert "error" in srv.iam_snapshot_diff(before_id="../etc", after_id="20261101T000000Z")
    assert "error" in srv.iam_snapshot_get_entity("a/b", "arn:aws:iam::111122223333:role/x")
    assert not [c for c in s3.calls if c[0] == "get" and "etc" in c[1]]


def test_server_list_limit_is_clamped(server):
    srv, _, s3 = server
    for d in range(1, 29):
        for h in (0, 12):
            _seed(s3, f"202610{d:02d}T{h:02d}0000Z")
    assert len(srv.iam_snapshot_list(limit=10_000)["snapshots"]) == srv.LIST_LIMIT_MAX
    assert len(srv.iam_snapshot_list(limit=-5)["snapshots"]) == 1


def test_server_audit_line_has_no_policy_content(server):
    import logging
    srv, _, s3 = server
    _seed(s3, "20261101T000000Z")
    _seed(s3, "20261102T000000Z")
    lines: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())
    h = _Collect()
    srv._audit.addHandler(h)
    try:
        srv.iam_snapshot_diff()
    finally:
        srv._audit.removeHandler(h)
    line = [l for l in lines if '"event":"tool_call"' in l][-1]
    rec = json.loads(line)
    assert rec["tool"] == "iam_snapshot_diff"
    assert rec["before_id"] == "20261101T000000Z" and rec["after_id"] == "20261102T000000Z"
    assert "entities" not in line and "Statement" not in line


# ---- baseline pointer read errors fail closed ----------------------------
POINTER = "snapshots/_baseline.json"
DAYS = ["20261027T000000Z", "20261028T000000Z", "20261029T000000Z", "20261030T000000Z",
        "20261031T000000Z", "20261101T000000Z"]  # all before the fake clock (START)


@pytest.mark.parametrize("code", ["AccessDenied", "KMS.ThrottlingException", "InternalError",
                                  "SlowDown"])
def test_pointer_read_error_fails_closed_on_diff(code):
    store, s3 = _store()
    for sid in DAYS:
        _seed(s3, sid)
    store.set_baseline(DAYS[0], DAYS[1])  # changes in DAYS[2..4] are unreported
    s3.fail_keys[POINTER] = _ClientError(code)
    s3.calls.clear()
    with pytest.raises(BaselinePointerUnreadable):
        run_diff(store, record_baseline=True)
    assert not [c for c in s3.calls if c[0] in ("put", "delete")]
    del s3.fail_keys[POINTER]
    assert store.get_baseline() == {"before": DAYS[0], "after": DAYS[1]}


def test_pointer_read_error_capture_writes_and_prunes_nothing():
    clock = Clock(START)
    store, s3 = _store(clock)
    for sid in DAYS:
        _seed(s3, sid)
    store.set_baseline(DAYS[0], DAYS[1])
    s3.fail_keys[POINTER] = _ClientError("AccessDenied")
    iam = FakeIAM([_role("app")])
    s3.calls.clear()
    with pytest.raises(BaselinePointerUnreadable):
        run_capture(store, iam, retain=MIN_RETAIN, min_interval_seconds=0)
    assert iam.calls == 0
    assert not [c for c in s3.calls if c[0] in ("put", "delete")]


def test_missing_pointer_is_still_a_first_run():
    store, s3 = _store()
    for sid in DAYS[:2]:
        _seed(s3, sid)
    out = run_diff(store, record_baseline=True)
    assert out["baseline_source"] == "previous" and out["baseline_advanced"] is True


def test_invalid_pointer_diffs_from_oldest_and_capture_skips_prune():
    clock = Clock(START)
    store, s3 = _store(clock)
    for sid in DAYS:
        _seed(s3, sid)
    s3.objects[POINTER] = b"not json"
    out = run_diff(store, record_baseline=True)
    assert out["baseline_source"] == "baseline_pointer_invalid"
    assert out["before_id"] == DAYS[0] and out["after_id"] == DAYS[-1]
    assert out["intervening_snapshots"] == len(DAYS) - 2
    s3.objects[POINTER] = b"not json"
    cap = run_capture(store, FakeIAM([_role("app")]), retain=MIN_RETAIN, min_interval_seconds=0)
    assert cap["pruned"] == [] and "note" in cap
    assert all(f"snapshots/{sid}.json" in s3.objects for sid in DAYS)


def test_server_pointer_unreadable_returns_retryable_error(server):
    srv, store, s3 = server
    for sid in DAYS[:2]:
        _seed(s3, sid)
    s3.fail_keys[POINTER] = _ClientError("AccessDenied")
    for out in (srv.iam_snapshot_diff(record_baseline=True), srv.iam_snapshot_capture()):
        assert out["retryable"] is True and "no drift" in out["error"]
    assert srv.iam_snapshot_list()["baseline_error"] == "unreadable"


def test_missing_pointer_snapshots_diff_from_oldest_retained():
    store, s3 = _store()
    for sid in DAYS:
        _seed(s3, sid)
    store.set_baseline("20261001T000000Z", "20261002T000000Z")  # both deleted out of band
    out = run_diff(store, record_baseline=True)
    assert out["baseline_source"] == "previous_baseline_missing"
    assert out["before_id"] == DAYS[0] and out["after_id"] == DAYS[-1]
    assert out["intervening_snapshots"] == len(DAYS) - 2


# ---- every S3 call is pinned to the server's own account --------------------
def test_every_s3_call_pins_expected_bucket_owner():
    s3 = FakeS3()
    store = SnapshotStore(BUCKET, s3_client=s3, clock=Clock(START), expected_owner=ACCT)
    for sid in DAYS:
        _seed(s3, sid)
    store.set_baseline(DAYS[0], DAYS[1])
    run_diff(store, record_baseline=True)
    run_capture(store, FakeIAM([_role("app")]), retain=MIN_RETAIN, min_interval_seconds=0)
    kinds = {k for k, _ in s3.owners}
    assert {"put", "get", "list", "delete"} <= kinds
    assert all(owner == ACCT for _, owner in s3.owners)


def test_server_store_is_pinned_to_guarded_account(monkeypatch):
    monkeypatch.setenv("ALLOWED_ACCOUNTS", ACCT)
    monkeypatch.setenv("SNAPSHOT_BUCKET", BUCKET)
    import importlib
    import server as srv
    srv = importlib.reload(srv)
    seen = {}
    monkeypatch.setattr(srv, "SnapshotStore", lambda **kw: seen.update(kw) or kw)
    srv._store(ACCT)
    assert seen == {"bucket": BUCKET, "expected_owner": ACCT}


# ---- malformed request-context header never breaks a tool -------------------
@pytest.mark.parametrize("raw", ["[1, 2]", '"x"', "7", "not json", '{"authorizer": "x"}',
                                 '{"authorizer": {"iam": 5}}', '{"authorizer": null}'])
def test_caller_tolerates_malformed_request_context(server, monkeypatch, raw):
    import fastmcp.server.dependencies as deps
    srv, store, s3 = server
    monkeypatch.setattr(deps, "get_http_headers",
                        lambda include_all=True: {"x-amzn-request-context": raw})
    assert srv._caller() == {"request_id": None, "caller_account": None, "caller_arn": None}
    for sid in DAYS[:2]:
        _seed(s3, sid)
    out = srv.iam_snapshot_diff(record_baseline=True)
    assert "error" not in out and out["baseline_advanced"] is True


# ---- capture errors return the AWS error code only (threat model M20) -------
class _FailingIAM:
    def get_account_authorization_details(self, **_):
        err = _ClientError("AccessDenied")
        err.args = ("User: arn:aws:iam::111122223333:role/x is not authorized to perform "
                    "iam:GetAccountAuthorizationDetails",)
        raise err


def test_capture_error_returns_code_not_message():
    store, s3 = _store(Clock(START))
    out = run_capture(store, _FailingIAM(), retain=MIN_RETAIN, min_interval_seconds=0)
    assert out["coverage"]["denied_calls"] == ["get_account_authorization_details: AccessDenied"]
    assert out["coverage"]["complete"] is False


# ---- per-call account gate and its audit line (M25, M26) --------------------
def _collect_audit(srv):
    import logging
    lines: list[dict] = []
    class _H(logging.Handler):
        def emit(self, record):
            lines.append(json.loads(record.getMessage()))
    h = _H()
    srv._audit.addHandler(h)
    return lines, h


def test_every_tool_refuses_a_foreign_account_and_logs_it(monkeypatch):
    monkeypatch.setenv("ALLOWED_ACCOUNTS", ACCT)
    monkeypatch.setenv("SNAPSHOT_BUCKET", BUCKET)
    import importlib
    import server as srv
    srv = importlib.reload(srv)
    touched = []
    class _STS:
        def get_caller_identity(self):
            return {"Account": "444455556666"}
    def _client(name, *a, **k):
        touched.append(name)
        if name != "sts":
            raise AssertionError(f"{name} must not be called when the gate refuses")
        return _STS()
    monkeypatch.setattr(srv.boto3, "client", _client)
    monkeypatch.setattr(srv, "_store", lambda owner=None: (_ for _ in ()).throw(
        AssertionError("store must not be built when the gate refuses")))
    lines, h = _collect_audit(srv)
    try:
        calls = [lambda: srv.iam_snapshot_capture(), lambda: srv.iam_snapshot_diff(),
                 lambda: srv.iam_snapshot_list(),
                 lambda: srv.iam_snapshot_get_entity("20261101T000000Z", "arn:aws:iam::111122223333:role/x")]
        for call in calls:
            with pytest.raises(RuntimeError, match="not in ALLOWED_ACCOUNTS"):
                call()
    finally:
        srv._audit.removeHandler(h)
    assert set(touched) == {"sts"}
    assert [l["tool"] for l in lines] == ["iam_snapshot_capture", "iam_snapshot_diff",
                                          "iam_snapshot_list", "iam_snapshot_get_entity"]
    assert all(l["error"] == "account_guard_failed" for l in lines)


def test_unexpected_error_still_writes_an_audit_line(server):
    srv, store, s3 = server
    for sid in DAYS[:2]:
        _seed(s3, sid)
    s3.fail_keys[f"snapshots/{DAYS[0]}.json"] = _ClientError("InternalError")
    lines, h = _collect_audit(srv)
    try:
        with pytest.raises(_ClientError):
            srv.iam_snapshot_diff(before_id=DAYS[0], after_id=DAYS[1])
    finally:
        srv._audit.removeHandler(h)
    assert lines[-1]["tool"] == "iam_snapshot_diff" and lines[-1]["error"] == "unexpected"


# ---- execution-role scope cannot widen unnoticed (M23) ----------------------
def _load_template():
    import pathlib
    import yaml
    class _Loader(yaml.SafeLoader):
        pass
    def _any_tag(loader, suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return {suffix: loader.construct_scalar(node)}
        if isinstance(node, yaml.SequenceNode):
            return {suffix: loader.construct_sequence(node, deep=True)}
        return {suffix: loader.construct_mapping(node, deep=True)}
    _Loader.add_multi_constructor("!", _any_tag)
    path = pathlib.Path(__file__).resolve().parents[1] / "template.yaml"
    return yaml.load(path.read_text(), Loader=_Loader)


def test_execution_role_stays_read_only_and_scoped():
    tpl = _load_template()
    stmts = [s for p in tpl["Resources"]["IamDriftDiffFunction"]["Properties"]["Policies"]
             for s in p["Statement"]]
    actions = {a for s in stmts for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])}
    assert {a for a in actions if a.startswith("iam:")} == {"iam:GetAccountAuthorizationDetails"}
    assert actions <= {"iam:GetAccountAuthorizationDetails", "s3:GetObject", "s3:PutObject",
                       "s3:DeleteObject", "s3:ListBucket", "kms:GenerateDataKey", "kms:Decrypt"}
    assert not any("*" in a for a in actions)
    for s in stmts:
        if s.get("Resource") == "*":
            assert s["Action"] == ["iam:GetAccountAuthorizationDetails"], s
    assert all(s["Effect"] == "Allow" for s in stmts)


# ---- availability alarms exist and notify only when a topic is given (M33) --
def test_template_alarms_cover_errors_throttles_and_duration():
    tpl = _load_template()
    res = tpl["Resources"]
    alarms = {k: v["Properties"] for k, v in res.items() if v["Type"] == "AWS::CloudWatch::Alarm"}
    metrics = {p["MetricName"] for p in alarms.values()}
    assert metrics == {"Errors", "Throttles", "Duration"}
    for p in alarms.values():
        assert p["Namespace"] == "AWS/Lambda"
        assert p["Dimensions"] == [{"Name": "FunctionName", "Value": {"Ref": "IamDriftDiffFunction"}}]
        assert p["AlarmActions"] == {"If": ["HasAlarmTopic", [{"Ref": "AlarmTopicArn"}], {"Ref": "AWS::NoValue"}]}
    duration = next(p for p in alarms.values() if p["MetricName"] == "Duration")
    timeout_ms = tpl["Globals"]["Function"]["Timeout"] * 1000
    assert duration["Threshold"] < timeout_ms
    assert tpl["Parameters"]["AlarmTopicArn"]["Default"] == ""
