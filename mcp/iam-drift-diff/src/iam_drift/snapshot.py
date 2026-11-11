"""Deterministic IAM snapshot capture and normalization.

This module turns the output of iam:GetAccountAuthorizationDetails into a
compact, normalized, order-independent fingerprint of every principal and
customer-managed policy in the account. The whole point is that the comparison
downstream (see diff.py) is literal set/hash math over this structure -- the
language model never performs the comparison, so a detach cannot "match" a
baseline the way it did in the prompt-only drift runs (2026-10-20).

Read-only: nothing in this module mutates IAM.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_json(obj: Any) -> str:
    """Stable JSON for hashing: sorted keys, no insignificant whitespace.

    IAM policy documents are semantically order-independent in several places
    (statement lists, action lists). We sort what is safe to sort before
    hashing so that a cosmetic reordering by AWS does not register as drift.
    """
    return json.dumps(_sort_policy(obj), sort_keys=True, separators=(",", ":"))


def _sort_policy(obj: Any) -> Any:
    """Recursively sort order-independent policy elements.

    Action, Resource, and Principal values may be a string or a list; when a
    list, order is not semantically meaningful, so we sort to a canonical form.
    Statement lists are sorted by their canonical serialization. We do NOT
    reorder anything whose order could matter.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("Action", "NotAction", "Resource", "NotResource") and isinstance(v, list):
                out[k] = sorted(str(x) for x in v)
            elif k in ("Principal", "NotPrincipal") and isinstance(v, dict):
                # {"AWS": [b, a]} == {"AWS": [a, b]}; also "x" == ["x"]
                out[k] = {
                    pt: (sorted(str(x) for x in pv) if isinstance(pv, list) else pv)
                    for pt, pv in v.items()
                }
            elif k == "Condition" and isinstance(v, dict):
                # condition operator -> key -> value(s); value lists are unordered
                out[k] = {
                    op: {
                        ck: (sorted(str(x) for x in cv) if isinstance(cv, list) else cv)
                        for ck, cv in (kv.items() if isinstance(kv, dict) else [])
                    } if isinstance(kv, dict) else kv
                    for op, kv in v.items()
                }
            elif k == "Statement" and isinstance(v, list):
                sorted_stmts = [_sort_policy(s) for s in v]
                sorted_stmts.sort(key=lambda s: json.dumps(s, sort_keys=True, separators=(",", ":")))
                out[k] = sorted_stmts
            else:
                out[k] = _sort_policy(v)
        return out
    if isinstance(obj, list):
        return [_sort_policy(x) for x in obj]
    return obj


def _as_doc(document: Any) -> Any:
    """IAM may return policy documents as URL-encoded JSON strings; boto3
    usually decodes them, but handle the string form defensively."""
    if isinstance(document, str):
        from urllib.parse import unquote
        try:
            return json.loads(unquote(document))
        except (ValueError, TypeError):
            return document
    return document


def _doc_hash(document: Any) -> str:
    """SHA-256 of a canonicalized policy document.

    Storing a hash (not the full document) keeps snapshots compact while making
    any change to a policy body show up as a changed hash. Drill-down to the
    actual document is a separate, on-demand read (see get_entity).
    """
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def _is_aws_managed_role(arn: str, path: str) -> bool:
    """Service-linked / AWS-managed roles are AWS-controlled, not customer drift
    surface. We record them by name/presence only and skip their policy bodies.
    Identified by the reserved path prefixes.
    """
    return path.startswith("/aws-service-role/") or path.startswith("/service-role/")


def _inline_docs(policies: list) -> dict[str, Any]:
    """{policy name: canonical document} -- stored so a diff can re-hash under
    current rules and report which actions were added/removed."""
    return {
        pol["PolicyName"]: _sort_policy(_as_doc(pol["PolicyDocument"]))
        for pol in policies
    }


def normalize_role(role: dict[str, Any]) -> dict[str, Any]:
    """Normalize one RoleDetailList entry into a fingerprint.

    Customer roles get full attached-ARN sets, inline name+hash sets, and a
    trust-policy hash. AWS-managed/service-linked roles are recorded by
    presence only (aws_managed=True) with no policy bodies.
    """
    arn = role["Arn"]
    path = role.get("Path", "/")
    aws_managed = _is_aws_managed_role(arn, path)

    fp: dict[str, Any] = {
        "type": "role",
        "name": role["RoleName"],
        "arn": arn,
        "path": path,
        "created": str(role.get("CreateDate", "")),
        "aws_managed": aws_managed,
    }
    # Trust policy is a drift surface even for empty roles; always fingerprint it
    # for customer roles.
    if not aws_managed:
        trust = _as_doc(role.get("AssumeRolePolicyDocument"))
        fp["trust_hash"] = _doc_hash(trust) if trust else None
        # Store the canonical trust document itself (small) so a diff can show
        # exactly WHAT changed -- a hash alone would hide a widening to
        # Principal:"*" or a removed condition.
        fp["trust"] = _sort_policy(trust) if trust else None
        fp["permissions_boundary"] = (
            role.get("PermissionsBoundary", {}).get("PermissionsBoundaryArn")
        )
        fp["attached"] = sorted(
            p["PolicyArn"] for p in role.get("AttachedManagedPolicies", [])
        )
        fp["inline"] = sorted(
            {pol["PolicyName"]: _doc_hash(_as_doc(pol["PolicyDocument"]))
             for pol in role.get("RolePolicyList", [])}.items()
        )
        fp["inline_docs"] = _inline_docs(role.get("RolePolicyList", []))
    return fp


def normalize_user(user: dict[str, Any]) -> dict[str, Any]:
    """Normalize one UserDetailList entry. Access-key STATE/age is in scope;
    last-used is intentionally out (keeps the call count bounded -- key metadata
    comes from GetAccountAuthorizationDetails + optional ListAccessKeys, never a
    per-key GetAccessKeyLastUsed fan-out here)."""
    fp: dict[str, Any] = {
        "type": "user",
        "name": user["UserName"],
        "arn": user["Arn"],
        "path": user.get("Path", "/"),
        "created": str(user.get("CreateDate", "")),
        "permissions_boundary": (
            user.get("PermissionsBoundary", {}).get("PermissionsBoundaryArn")
        ),
        "attached": sorted(p["PolicyArn"] for p in user.get("AttachedManagedPolicies", [])),
        "inline": sorted(
            {pol["PolicyName"]: _doc_hash(_as_doc(pol["PolicyDocument"]))
             for pol in user.get("UserPolicyList", [])}.items()
        ),
        "inline_docs": _inline_docs(user.get("UserPolicyList", [])),
        "groups": sorted(user.get("GroupList", [])),
    }
    return fp


def normalize_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "group",
        "name": group["GroupName"],
        "arn": group["Arn"],
        "path": group.get("Path", "/"),
        "attached": sorted(p["PolicyArn"] for p in group.get("AttachedManagedPolicies", [])),
        "inline": sorted(
            {pol["PolicyName"]: _doc_hash(_as_doc(pol["PolicyDocument"]))
             for pol in group.get("GroupPolicyList", [])}.items()
        ),
        "inline_docs": _inline_docs(group.get("GroupPolicyList", [])),
    }


def normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Customer-managed policy. We fingerprint the DEFAULT version's document."""
    default_doc = None
    for v in policy.get("PolicyVersionList", []):
        if v.get("IsDefaultVersion"):
            default_doc = v.get("Document")
            break
    return {
        "type": "policy",
        "name": policy["PolicyName"],
        "arn": policy["Arn"],
        "path": policy.get("Path", "/"),
        "default_version": policy.get("DefaultVersionId"),
        "attachment_count": policy.get("AttachmentCount", 0),
        "doc_hash": _doc_hash(_as_doc(default_doc)) if default_doc else None,
        "doc": _sort_policy(_as_doc(default_doc)) if default_doc else None,
    }


def build_snapshot(
    auth_details: dict[str, list],
    *,
    pages_fetched: int,
    truncated: bool,
    denied: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble a full snapshot from accumulated GetAccountAuthorizationDetails
    pages.

    `auth_details` is the merged result with keys RoleDetailList,
    UserDetailList, GroupDetailList, Policies (customer-managed only -- the
    caller filters Scope=Local).

    The coverage block is machine-readable and load-bearing: `complete` is False
    whenever a page was truncated or a required call was denied, so a downstream
    consumer can never truthfully claim "everything matches" over a partial read.
    """
    roles = [normalize_role(r) for r in auth_details.get("RoleDetailList", [])]
    users = [normalize_user(u) for u in auth_details.get("UserDetailList", [])]
    groups = [normalize_group(g) for g in auth_details.get("GroupDetailList", [])]
    policies = [normalize_policy(p) for p in auth_details.get("Policies", [])]

    customer_roles = [r for r in roles if not r.get("aws_managed")]
    denied = denied or []

    entities = {}
    for e in roles + users + groups + policies:
        entities[e["arn"]] = e

    coverage = {
        "roles_seen": len(roles),
        "customer_roles_seen": len(customer_roles),
        "users_seen": len(users),
        "groups_seen": len(groups),
        "policies_seen": len(policies),
        "pages_fetched": pages_fetched,
        "truncated": truncated,
        "denied_calls": denied,
        # complete is the single honest signal: the model is told to trust it,
        # not to assert coverage on its own.
        "complete": (not truncated) and (len(denied) == 0),
    }

    return {
        "schema": 1,
        "entities": entities,
        "coverage": coverage,
    }
