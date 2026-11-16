"""Acceptance tests for the deterministic snapshot + diff logic.

These are the acceptance tests for the drift-diff engine, run against the pure
logic with synthetic GetAccountAuthorizationDetails data -- no AWS needed. The
headline is test_unused_detach_is_caught: the exact change the prompt-only
drift runs missed twice (shared-readonly detached from an otherwise-empty role)
MUST show up here as attached_removed.
"""

from __future__ import annotations

import copy

from iam_drift.snapshot import build_snapshot
from iam_drift.diff import diff_snapshots


ACCT = "111122223333"
SHARED_POLICY = f"arn:aws:iam::{ACCT}:policy/test-shared-readonly"
ADMIN = "arn:aws:iam::aws:policy/AdministratorAccess"


def _trust_account_root():
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{ACCT}:root"},
            "Action": "sts:AssumeRole",
        }],
    }


def _role(name, attached=None, inline=None, path="/"):
    return {
        "RoleName": name,
        "Arn": f"arn:aws:iam::{ACCT}:role/{name}",
        "Path": path,
        "CreateDate": "2026-10-01T00:00:00Z",
        "AssumeRolePolicyDocument": _trust_account_root(),
        "AttachedManagedPolicies": [{"PolicyArn": a} for a in (attached or [])],
        "RolePolicyList": [
            {"PolicyName": n, "PolicyDocument": d} for n, d in (inline or {}).items()
        ],
    }


def _user(name, attached=None, keys=None, groups=None):
    return {
        "UserName": name,
        "Arn": f"arn:aws:iam::{ACCT}:user/{name}",
        "Path": "/",
        "CreateDate": "2026-10-01T00:00:00Z",
        "AttachedManagedPolicies": [{"PolicyArn": a} for a in (attached or [])],
        "UserPolicyList": [],
        "GroupList": groups or [],
    }


def _auth(roles=None, users=None, groups=None, policies=None):
    return {
        "RoleDetailList": roles or [],
        "UserDetailList": users or [],
        "GroupDetailList": groups or [],
        "Policies": policies or [],
    }


def _snap(auth, pages=1, truncated=False, denied=None):
    return build_snapshot(auth, pages_fetched=pages, truncated=truncated, denied=denied)


# ---- Test 1: the regression we own -----------------------------------------
def test_unused_detach_is_caught():
    """shared-readonly detached from an otherwise-empty role MUST be caught.

    This is the exact change the prompt-only agent missed twice on 2026-10-20.
    """
    before = _snap(_auth(roles=[
        _role("test-unused", attached=[SHARED_POLICY]),
    ]))
    after = _snap(_auth(roles=[
        _role("test-unused", attached=[]),
    ]))
    d = diff_snapshots(before, after)
    changed = {c["name"]: c for c in d["changed_principals"]}
    assert "test-unused" in changed, "detach was missed"
    ch = changed["test-unused"]["changes"]
    assert ch["attached_removed"] == [SHARED_POLICY]
    assert changed["test-unused"]["direction"] == "down"
    assert d["comparison_complete"] is True


# ---- Test 2: positive control (inline PassRole add) ------------------------
def test_inline_passrole_add_is_caught():
    passrole_doc = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "iam:PassRole", "Resource": "*"}],
    }
    before = _snap(_auth(roles=[_role("test-scoped-reader",
                                       attached=[SHARED_POLICY])]))
    after = _snap(_auth(roles=[_role("test-scoped-reader",
                                      attached=[SHARED_POLICY],
                                      inline={"drift-test-passrole": passrole_doc})]))
    d = diff_snapshots(before, after)
    changed = {c["name"]: c for c in d["changed_principals"]}
    c = changed["test-scoped-reader"]
    assert c["changes"]["inline_policies_added"] == ["drift-test-passrole"]
    assert c["direction"] == "up"


# ---- Test 3: pure no-change -> empty, complete -----------------------------
def test_no_change_is_empty_and_complete():
    auth = _auth(roles=[_role("r1", attached=[SHARED_POLICY])],
                 users=[_user("u1")])
    before = _snap(copy.deepcopy(auth))
    after = _snap(copy.deepcopy(auth))
    d = diff_snapshots(before, after)
    assert d["summary"] == {"added": 0, "removed": 0, "changed": 0,
                            "up": 0, "mixed": 0, "info": 0, "down": 0, "lateral": 0}
    assert d["comparison_complete"] is True


# ---- Test 4: attach AdministratorAccess on a quiet role (silent-miss case) --
def test_admin_attach_on_quiet_role_is_up():
    before = _snap(_auth(roles=[_role("quiet-role", attached=[])]))
    after = _snap(_auth(roles=[_role("quiet-role", attached=[ADMIN])]))
    d = diff_snapshots(before, after)
    c = {x["name"]: x for x in d["changed_principals"]}["quiet-role"]
    assert c["changes"]["attached_added"] == [ADMIN]
    assert c["direction"] == "up"


# ---- Test 5: new / removed principal, key state, trust change --------------
def test_new_principal_flagged_up_even_without_grants():
    before = _snap(_auth(roles=[]))
    after = _snap(_auth(roles=[_role("brand-new-role", attached=[])]))
    d = diff_snapshots(before, after)
    assert d["summary"]["added"] == 1
    assert d["added_principals"][0]["name"] == "brand-new-role"
    # trust surface alone makes a new empty role risk-up, not lateral
    assert d["added_principals"][0]["direction"] == "up"


def test_removed_principal_is_down():
    before = _snap(_auth(roles=[_role("going-away")]))
    after = _snap(_auth(roles=[]))
    d = diff_snapshots(before, after)
    assert d["summary"]["removed"] == 1
    assert d["removed_principals"][0]["direction"] == "down"


def test_trust_policy_change_is_detected():
    before = _snap(_auth(roles=[_role("r")]))
    after_role = _role("r")
    after_role["AssumeRolePolicyDocument"] = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"AWS": "*"},
                       "Action": "sts:AssumeRole"}],
    }
    after = _snap(_auth(roles=[after_role]))
    d = diff_snapshots(before, after)
    c = {x["name"]: x for x in d["changed_principals"]}["r"]
    t = c["changes"]["trust_changed"]
    # widened to everyone: must be visible and classified up, with the docs
    assert t["wildcard_principal_added"] is True
    assert t["direction"] == "up"
    assert c["direction"] == "up"
    assert t["after"] is not None and t["before"] is not None


def test_trust_condition_removed_is_up():
    def role_with(cond):
        r = _role("r")
        stmt = {"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{ACCT}:root"},
                "Action": "sts:AssumeRole"}
        if cond:
            stmt["Condition"] = {"StringEquals": {"sts:ExternalId": "abc"}}
        r["AssumeRolePolicyDocument"] = {"Version": "2012-10-17", "Statement": [stmt]}
        return r
    before = _snap(_auth(roles=[role_with(True)]))
    after = _snap(_auth(roles=[role_with(False)]))
    d = diff_snapshots(before, after)
    t = {x["name"]: x for x in d["changed_principals"]}["r"]["changes"]["trust_changed"]
    assert t["conditions_removed"] is True
    assert t["direction"] == "up"


def test_trust_principal_removed_is_down():
    two = _role("r")
    two["AssumeRolePolicyDocument"] = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": [f"arn:aws:iam::{ACCT}:root", "arn:aws:iam::444455556666:root"]},
        "Action": "sts:AssumeRole"}]}
    before = _snap(_auth(roles=[two]))
    after = _snap(_auth(roles=[_role("r")]))
    d = diff_snapshots(before, after)
    t = {x["name"]: x for x in d["changed_principals"]}["r"]["changes"]["trust_changed"]
    assert t["principals_removed"] == ["AWS:arn:aws:iam::444455556666:root"]
    assert t["direction"] == "down"


def test_new_service_linked_role_is_info_not_up():
    slr = _role("AWSServiceRoleForComputeOptimizer",
                path="/aws-service-role/compute-optimizer.amazonaws.com/")
    before = _snap(_auth(roles=[]))
    after = _snap(_auth(roles=[slr]))
    d = diff_snapshots(before, after)
    assert d["added_principals"][0]["direction"] == "info"
    assert d["summary"]["up"] == 0
    assert d["summary"]["info"] == 1


# ---- Test 6: completeness honesty ------------------------------------------
def test_incomplete_capture_marks_not_complete():
    snap = _snap(_auth(roles=[_role("r")]), truncated=True)
    assert snap["coverage"]["complete"] is False


def test_denied_call_marks_not_complete():
    snap = _snap(_auth(roles=[_role("r")]), denied=["get_account_authorization_details: AccessDenied"])
    assert snap["coverage"]["complete"] is False


def test_diff_incomplete_when_either_side_incomplete():
    before = _snap(_auth(roles=[_role("r")]), truncated=True)
    after = _snap(_auth(roles=[_role("r")]))
    d = diff_snapshots(before, after)
    assert d["comparison_complete"] is False


# ---- cosmetic changes ignored ----------------------------------------------
def test_cosmetic_order_difference_is_not_drift():
    """Attached policies in different order must NOT register as drift."""
    before = _snap(_auth(roles=[_role("r", attached=[SHARED_POLICY, ADMIN])]))
    after = _snap(_auth(roles=[_role("r", attached=[ADMIN, SHARED_POLICY])]))
    d = diff_snapshots(before, after)
    assert d["summary"]["changed"] == 0


def test_statement_reorder_in_policy_body_is_not_drift():
    """Reordered statements in an inline doc must hash equal (no false drift)."""
    doc_a = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"},
        {"Effect": "Allow", "Action": "logs:GetLogEvents", "Resource": "*"},
    ]}
    doc_b = {"Version": "2012-10-17", "Statement": list(reversed(doc_a["Statement"]))}
    before = _snap(_auth(roles=[_role("r", inline={"p": doc_a})]))
    after = _snap(_auth(roles=[_role("r", inline={"p": doc_b})]))
    d = diff_snapshots(before, after)
    assert d["summary"]["changed"] == 0


# ---- service-linked roles recorded by presence only ------------------------
def test_service_linked_role_body_skipped():
    slr = _role("AWSServiceRoleForFoo", attached=["arn:aws:iam::aws:policy/foo"],
                path="/aws-service-role/foo.amazonaws.com/")
    snap = _snap(_auth(roles=[slr]))
    ent = snap["entities"][f"arn:aws:iam::{ACCT}:role/AWSServiceRoleForFoo"]
    assert ent["aws_managed"] is True
    assert "attached" not in ent  # body not fingerprinted


# ---- trust high_risk: platform churn vs. real widening ---------------------
def _role_trust(stmts):
    r = _role("r")
    r["AssumeRolePolicyDocument"] = {"Version": "2012-10-17", "Statement": stmts}
    return r


_SELF = {"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{ACCT}:root"},
         "Action": "sts:AssumeRole"}


def test_guarded_external_principal_added_is_up_but_not_high_risk():
    """Platform-managed churn: new outside principal WITH ExternalId guard."""
    guarded = {"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::444455556666:root"},
               "Action": "sts:AssumeRole",
               "Condition": {"StringEquals": {"sts:ExternalId": "x"}}}
    before = _snap(_auth(roles=[_role_trust([_SELF])]))
    after = _snap(_auth(roles=[_role_trust([_SELF, guarded])]))
    t = {x["name"]: x for x in diff_snapshots(before, after)["changed_principals"]}["r"]["changes"]["trust_changed"]
    assert t["direction"] == "up"
    assert t["high_risk"] is False
    assert t["unguarded_external_principals_added"] == []


def test_unguarded_external_principal_added_is_high_risk():
    unguarded = {"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::444455556666:root"},
                 "Action": "sts:AssumeRole"}
    before = _snap(_auth(roles=[_role_trust([_SELF])]))
    after = _snap(_auth(roles=[_role_trust([_SELF, unguarded])]))
    t = {x["name"]: x for x in diff_snapshots(before, after)["changed_principals"]}["r"]["changes"]["trust_changed"]
    assert t["high_risk"] is True
    assert t["unguarded_external_principals_added"] == ["AWS:arn:aws:iam::444455556666:root"]


def test_wildcard_trust_is_high_risk():
    star = {"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "sts:AssumeRole"}
    before = _snap(_auth(roles=[_role_trust([_SELF])]))
    after = _snap(_auth(roles=[_role_trust([star])]))
    t = {x["name"]: x for x in diff_snapshots(before, after)["changed_principals"]}["r"]["changes"]["trust_changed"]
    assert t["high_risk"] is True


def test_trust_principal_and_condition_reorder_is_not_drift():
    """Reordered principal lists / condition value lists must not register."""
    a = {"Effect": "Allow",
         "Principal": {"AWS": ["arn:aws:iam::123456789012:root", "arn:aws:iam::123456789010:root"]},
         "Action": "sts:AssumeRole",
         "Condition": {"StringEquals": {"sts:ExternalId": ["x", "y"]}}}
    b = {"Effect": "Allow",
         "Principal": {"AWS": ["arn:aws:iam::123456789010:root", "arn:aws:iam::123456789012:root"]},
         "Action": "sts:AssumeRole",
         "Condition": {"StringEquals": {"sts:ExternalId": ["y", "x"]}}}
    before = _snap(_auth(roles=[_role_trust([a])]))
    after = _snap(_auth(roles=[_role_trust([b])]))
    assert diff_snapshots(before, after)["summary"]["changed"] == 0


# ---- inline policy BODY changes: explained, not falsely "mixed" ------------
def _doc(*stmts):
    return {"Version": "2012-10-17", "Statement": list(stmts)}


def test_inline_body_broadened_is_up_with_grants():
    b = _doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"})
    a = _doc({"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "*"})
    d = diff_snapshots(_snap(_auth(roles=[_role("r", inline={"p": b})])),
                       _snap(_auth(roles=[_role("r", inline={"p": a})])))
    c = {x["name"]: x for x in d["changed_principals"]}["r"]
    body = c["changes"]["inline_body_changed"][0]
    assert body["grants_added"] == ["s3:PutObject @ *"]
    assert body["grants_removed"] == []
    assert c["direction"] == "up"
    assert "inline_policies_added" not in c["changes"]  # same policy, not a new one


def test_inline_body_condition_reorder_is_not_drift():
    b = _doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*",
              "Condition": {"StringEquals": {"aws:PrincipalOrgID": ["o-1", "o-2"]}}})
    a = _doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*",
              "Condition": {"StringEquals": {"aws:PrincipalOrgID": ["o-2", "o-1"]}}})
    d = diff_snapshots(_snap(_auth(roles=[_role("r", inline={"p": b})])),
                       _snap(_auth(roles=[_role("r", inline={"p": a})])))
    assert d["summary"]["changed"] == 0


def test_mixed_body_counted_once():
    b = _doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"})
    a = _doc({"Effect": "Allow", "Action": "s3:PutObject", "Resource": "*"})
    d = diff_snapshots(_snap(_auth(roles=[_role("r", inline={"p": b})])),
                       _snap(_auth(roles=[_role("r", inline={"p": a})])))
    s = d["summary"]
    assert s["mixed"] == 1 and s["up"] == 0 and s["down"] == 0


# ---- /service-role/ is a customer path ----------------------------------
_OUTSIDE = "arn:aws:iam::444455556666:root"


def test_service_role_path_role_is_fully_diffed():
    before_role = _role("svc", path="/service-role/")
    after_role = _role("svc", attached=[ADMIN], inline={"all": {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}},
        path="/service-role/")
    after_role["AssumeRolePolicyDocument"]["Statement"].append(
        {"Effect": "Allow", "Principal": {"AWS": _OUTSIDE}, "Action": "sts:AssumeRole"})
    before = _snap(_auth(roles=[before_role]))
    after = _snap(_auth(roles=[after_role]))
    ent = after["entities"][f"arn:aws:iam::{ACCT}:role/svc"]
    assert ent["aws_managed"] is False and ent["attached"] == [ADMIN]
    d = diff_snapshots(before, after)
    assert d["summary"]["changed"] == 1 and d["comparison_complete"] is True
    c = d["changed_principals"][0]
    assert c["direction"] == "up"
    assert c["changes"]["attached_added"] == [ADMIN]
    assert c["changes"]["trust_changed"]["high_risk"] is True


def test_new_service_role_path_role_is_up_not_info():
    before = _snap(_auth(roles=[]))
    after = _snap(_auth(roles=[_role("svc", attached=[ADMIN], path="/service-role/")]))
    d = diff_snapshots(before, after)
    assert d["added_principals"][0]["direction"] == "up"
    assert d["summary"]["up"] == 1 and d["summary"]["info"] == 0


def test_upgrade_from_presence_only_service_role_is_info_once():
    """A schema-1 snapshot recorded /service-role/ roles by presence only. The
    first diff after upgrade reports a scope change (info), not false grants."""
    arn = f"arn:aws:iam::{ACCT}:role/svc"
    after = _snap(_auth(roles=[_role("svc", attached=[ADMIN], path="/service-role/")]))
    before = copy.deepcopy(after)
    before["schema"] = 1
    before["entities"][arn] = {k: v for k, v in after["entities"][arn].items()
                               if k in ("type", "name", "arn", "path", "created")}
    before["entities"][arn]["aws_managed"] = True
    d = diff_snapshots(before, after)
    c = d["changed_principals"][0]
    assert c["direction"] == "info" and "fingerprint_scope_changed" in c["changes"]
    assert d["summary"]["up"] == 0 and d["summary"]["info"] == 1
    assert diff_snapshots(after, copy.deepcopy(after))["summary"]["changed"] == 0


# ---- trust: per-principal conditions, federated principals, Deny -----------
_EXT = "arn:aws:iam::444455556666:root"
_EXT_GUARDED = {"Effect": "Allow", "Principal": {"AWS": _EXT}, "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"sts:ExternalId": "example-id"}}}
_OIDC = f"arn:aws:iam::{ACCT}:oidc-provider/token.actions.githubusercontent.com"


def _trust_change(before_stmts, after_stmts):
    d = diff_snapshots(_snap(_auth(roles=[_role_trust(before_stmts)])),
                       _snap(_auth(roles=[_role_trust(after_stmts)])))
    c = d["changed_principals"][0]
    return c, c["changes"]["trust_changed"]


def test_condition_moved_off_external_principal_is_high_risk():
    """Same number of conditioned statements, but the outside principal lost
    its ExternalId guard (it moved to the self statement)."""
    self_conditioned = dict(_SELF, Condition={"Bool": {"aws:MultiFactorAuthPresent": "true"}})
    ext_open = {"Effect": "Allow", "Principal": {"AWS": _EXT}, "Action": "sts:AssumeRole"}
    c, t = _trust_change([_SELF, _EXT_GUARDED], [self_conditioned, ext_open])
    assert t["principal_conditions_lost"] == {f"AWS:{_EXT}": ["StringEquals:sts:externalid"]}
    assert t["high_risk"] is True and c["direction"] in ("up", "mixed")


def test_external_id_swapped_for_weaker_key_is_high_risk():
    weaker = dict(_EXT_GUARDED, Condition={"Bool": {"aws:SecureTransport": "true"}})
    _, t = _trust_change([_SELF, _EXT_GUARDED], [_SELF, weaker])
    assert "StringEquals:sts:externalid" in t["principal_conditions_lost"][f"AWS:{_EXT}"]
    assert t["high_risk"] is True


def test_unconditioned_federated_principal_added_is_high_risk():
    oidc = {"Effect": "Allow", "Principal": {"Federated": _OIDC},
            "Action": "sts:AssumeRoleWithWebIdentity"}
    _, t = _trust_change([_SELF], [_SELF, oidc])
    assert t["unguarded_federated_principals_added"] == [f"Federated:{_OIDC}"]
    assert t["high_risk"] is True


def test_guarded_federated_principal_added_is_up_not_high_risk():
    oidc = {"Effect": "Allow", "Principal": {"Federated": _OIDC},
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {"StringEquals": {"token.actions.githubusercontent.com:sub": "repo:example/x:ref:refs/heads/main"}}}
    c, t = _trust_change([_SELF], [_SELF, oidc])
    assert t["unguarded_federated_principals_added"] == [] and t["high_risk"] is False
    assert c["direction"] == "up"


def test_trust_deny_removed_is_high_risk():
    org_deny = {"Effect": "Deny", "Principal": "*", "Action": "sts:AssumeRole",
                "Condition": {"StringNotEquals": {"aws:PrincipalOrgID": "o-example"}}}
    c, t = _trust_change([_SELF, org_deny], [_SELF])
    assert t["deny_statements_removed"] == 1 and t["high_risk"] is True
    assert c["direction"] == "up"


# ---- policy bodies: NotAction / NotResource / Deny ------------------------
def _body_change(b, a):
    d = diff_snapshots(_snap(_auth(roles=[_role("r", inline={"p": b})])),
                       _snap(_auth(roles=[_role("r", inline={"p": a})])))
    c = d["changed_principals"][0]
    return c, c["changes"]["inline_body_changed"][0]


def test_allow_notaction_is_reported_as_a_grant():
    base = _doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"})
    broad = _doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"},
                 {"Effect": "Allow", "NotAction": ["organizations:*", "iam:*"], "Resource": "*"})
    c, body = _body_change(base, broad)
    assert body["grants_added"] == ["NOT[iam:*,organizations:*] @ *"]
    assert c["direction"] == "up"


def test_policy_deny_removed_is_up_and_added_is_down():
    allow = {"Effect": "Allow", "Action": "s3:*", "Resource": "*"}
    guard = {"Effect": "Deny", "Action": "s3:DeleteBucket", "Resource": "*"}
    c, body = _body_change(_doc(allow, guard), _doc(allow))
    assert body["denies_removed"] == ["s3:DeleteBucket @ *"] and body["grants_added"] == []
    assert c["direction"] == "up"
    c, body = _body_change(_doc(allow), _doc(allow, guard))
    assert body["denies_added"] == ["s3:DeleteBucket @ *"] and c["direction"] == "down"


def test_notresource_is_explicit():
    a = _doc({"Effect": "Allow", "Action": "s3:GetObject", "NotResource": "arn:aws:s3:::secret/*"})
    c, body = _body_change(_doc({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::pub/*"}), a)
    assert "s3:GetObject @ NOT[arn:aws:s3:::secret/*]" in body["grants_added"]
