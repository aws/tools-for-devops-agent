"""Deterministic set-difference between two IAM snapshots.

This is the capability the base agent could not do reliably: an exact, complete
comparison of prior vs. current IAM state across every principal. It is pure
data math -- no model, no judgment, no risk scoring. The agent consumes the
structured result and supplies the judgment/recommendations.

Classification here is intentionally mechanical (added / removed / changed per
field). The "is this risk-increasing?" judgment is left to the agent, EXCEPT we
emit a neutral `direction` hint per change using unambiguous rules, because the
agent asked for a precomputed diff it can classify -- the hint is advisory and
the agent may override it.
"""

from __future__ import annotations

from typing import Any

from iam_drift.snapshot import _doc_hash


def _field_set_diff(before: list, after: list) -> tuple[list, list]:
    """Return (added, removed) for two order-independent lists.

    Lists here are already sorted canonical forms (ARN strings, or
    [name, hash] pairs). Comparison is literal: membership in a set. A detach
    shows up as an entry present in `before` and absent from `after` -- it
    cannot be glossed over, which is exactly the prompt-only failure this
    replaces.
    """
    # entries may be lists (e.g. [name, hash] pairs) -> make hashable
    b = {tuple(x) if isinstance(x, list) else x for x in (before or [])}
    a = {tuple(x) if isinstance(x, list) else x for x in (after or [])}
    added = sorted(a - b, key=lambda v: str(v))
    removed = sorted(b - a, key=lambda v: str(v))
    return (
        [list(x) if isinstance(x, tuple) else x for x in added],
        [list(x) if isinstance(x, tuple) else x for x in removed],
    )


def _entity_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compute per-field changes for one principal present in both snapshots."""
    changes: dict[str, Any] = {}

    # attached managed policies
    if "attached" in before or "attached" in after:
        add, rem = _field_set_diff(before.get("attached", []), after.get("attached", []))
        if add:
            changes["attached_added"] = add
        if rem:
            changes["attached_removed"] = rem

    # inline policies: separate (a) whole policies added/removed by NAME from
    # (b) body changes on a policy present on both sides. Body changes are
    # re-hashed from stored docs under current canonicalization (no false drift
    # from older snapshots) and explained as actions added/removed.
    if "inline" in before or "inline" in after:
        b_names = {n for n, _ in (before.get("inline") or [])}
        a_names = {n for n, _ in (after.get("inline") or [])}
        b_hash = dict(tuple(x) for x in (before.get("inline") or []))
        a_hash = dict(tuple(x) for x in (after.get("inline") or []))
        b_docs = before.get("inline_docs") or {}
        a_docs = after.get("inline_docs") or {}
        if a_names - b_names:
            changes["inline_policies_added"] = sorted(a_names - b_names)
        if b_names - a_names:
            changes["inline_policies_removed"] = sorted(b_names - a_names)
        body = []
        for n in sorted(a_names & b_names):
            if n in b_docs and n in a_docs:
                if _doc_hash(b_docs[n]) == _doc_hash(a_docs[n]):
                    continue  # identical under current canonicalization
                body.append({"policy": n, **_policy_body_change(b_docs[n], a_docs[n])})
            elif b_hash.get(n) != a_hash.get(n):
                # older snapshot without stored docs: changed, but unexplainable
                body.append({"policy": n, "direction": "lateral",
                             "note": "baseline predates stored policy documents; "
                                     "content not comparable this run"})
        if body:
            changes["inline_body_changed"] = body

    # customer-managed policy document (default version)
    if before.get("type") == "policy" and after.get("type") == "policy":
        bd, ad = before.get("doc"), after.get("doc")
        if bd is not None and ad is not None:
            if _doc_hash(bd) != _doc_hash(ad):
                changes["policy_body_changed"] = _policy_body_change(bd, ad)
        elif before.get("doc_hash") != after.get("doc_hash"):
            changes["policy_body_changed"] = {
                "direction": "lateral",
                "note": "baseline predates stored policy documents; content not comparable this run"}

    # groups (users)
    if "groups" in before or "groups" in after:
        add, rem = _field_set_diff(before.get("groups", []), after.get("groups", []))
        if add:
            changes["groups_added"] = add
        if rem:
            changes["groups_removed"] = rem

    # trust policy: return the actual before/after documents plus a structured
    # analysis, so a widening (new principal, "*", removed condition) is visible
    # and classifiable -- not hidden behind a hash change.
    # Compare trust docs by re-hashing with the CURRENT canonicalization (not the
    # stored hash), so older snapshots taken before a canonicalization fix don't
    # produce one round of false "changed" noise.
    def _th(e):
        t = e.get("trust")
        return _doc_hash(t) if t is not None else e.get("trust_hash")
    if ("trust_hash" in before or "trust_hash" in after) and _th(before) != _th(after):
        arn = after.get("arn") or before.get("arn") or ""
        parts = arn.split(":")
        own = parts[4] if len(parts) > 4 else None
        changes["trust_changed"] = _trust_analysis(before.get("trust"), after.get("trust"), own)

    # scalar hashes / fields where any change is notable
    for field in ("permissions_boundary",):
        if before.get(field) != after.get(field) and (field in before or field in after):
            changes[field + "_changed"] = {
                "before": before.get(field),
                "after": after.get(field),
            }

    return changes


def _principals(doc: Any) -> set[str]:
    """Flatten every Allow-statement Principal value into 'type:value' strings."""
    out: set[str] = set()
    if not isinstance(doc, dict):
        return out
    for stmt in doc.get("Statement", []) or []:
        if not isinstance(stmt, dict) or stmt.get("Effect") != "Allow":
            continue
        p = stmt.get("Principal")
        if p == "*":
            out.add("*")
        elif isinstance(p, dict):
            for ptype, vals in p.items():
                for v in (vals if isinstance(vals, list) else [vals]):
                    out.add("*" if v == "*" else f"{ptype}:{v}")
    return out


def _grants(doc: Any) -> set[str]:
    """Allow-statement grants as 'action @ resource' strings (order-independent).
    Coarse but exact: any new grant string = something broadened; any missing
    grant string = something narrowed."""
    out: set[str] = set()
    if not isinstance(doc, dict):
        return out
    for s in doc.get("Statement", []) or []:
        if not isinstance(s, dict) or s.get("Effect") != "Allow":
            continue
        acts = s.get("Action", [])
        res = s.get("Resource", "*")
        acts = acts if isinstance(acts, list) else [acts]
        res = res if isinstance(res, list) else [res]
        cond = "" if not s.get("Condition") else " (conditioned)"
        for a in acts:
            for r in res:
                out.add(f"{a} @ {r}{cond}")
    return out


def _policy_body_change(before_doc: Any, after_doc: Any) -> dict[str, Any]:
    b, a = _grants(before_doc), _grants(after_doc)
    added, removed = sorted(a - b), sorted(b - a)
    if added and removed:
        direction = "mixed"
    elif added:
        direction = "up"
    elif removed:
        direction = "down"
    else:
        direction = "lateral"  # e.g. Deny/condition/NotAction edits
    return {"grants_added": added, "grants_removed": removed, "direction": direction}


def _unguarded_principals(doc: Any) -> set[str]:
    """Principals granted by at least one Allow statement that has NO Condition."""
    out: set[str] = set()
    if not isinstance(doc, dict):
        return out
    for stmt in doc.get("Statement", []) or []:
        if not isinstance(stmt, dict) or stmt.get("Effect") != "Allow" or stmt.get("Condition"):
            continue
        out |= _principals({"Statement": [stmt]})
    return out


def _account_of(principal: str) -> str | None:
    """'AWS:arn:aws:iam::123456789012:root' -> '123456789012'; bare 'AWS:1234...' too."""
    if not principal.startswith("AWS:"):
        return None
    v = principal[4:]
    if v.isdigit() and len(v) == 12:
        return v
    parts = v.split(":")
    return parts[4] if len(parts) > 4 and parts[4].isdigit() else None


def _condition_count(doc: Any) -> int:
    if not isinstance(doc, dict):
        return 0
    return sum(
        1 for s in (doc.get("Statement", []) or [])
        if isinstance(s, dict) and s.get("Effect") == "Allow" and s.get("Condition")
    )


def _trust_analysis(before_doc: Any, after_doc: Any, own_account: str | None = None) -> dict[str, Any]:
    """Explain a trust-policy change and give it a direction.

    up   = a principal was added, a wildcard "*" appeared, or a condition was
           removed (any of which widens who can assume the role)
    down = principals only removed, conditions not reduced
    lateral = changed but neither of the above (e.g. condition values edited)
    """
    b, a = _principals(before_doc), _principals(after_doc)
    added, removed = sorted(a - b), sorted(b - a)
    wildcard_new = "*" in a and "*" not in b
    conditions_removed = _condition_count(after_doc) < _condition_count(before_doc)
    if added or wildcard_new or conditions_removed:
        direction = "up"
    elif removed:
        direction = "down"
    else:
        direction = "lateral"
    # Deterministic high-risk flag (so the model doesn't have to judge it):
    # a wildcard principal, a removed condition, or a newly added principal
    # from ANOTHER account granted by an unconditioned statement (no
    # ExternalId / OrgID / SourceArn guard). Guarded additions -- typical of
    # platform-managed roles -- are 'up' but not high risk.
    unguarded = _unguarded_principals(after_doc)
    unguarded_external_added = sorted(
        p for p in added
        if p in unguarded and _account_of(p) and _account_of(p) != own_account
    )
    high_risk = bool(wildcard_new or conditions_removed or unguarded_external_added)
    return {
        "principals_added": added,
        "principals_removed": removed,
        "wildcard_principal_added": wildcard_new,
        "conditions_removed": conditions_removed,
        "unguarded_external_principals_added": unguarded_external_added,
        "high_risk": high_risk,
        "direction": direction,
        "before": before_doc,
        "after": after_doc,
    }


# Fields whose ADDITION tends to increase permission, for the advisory hint.
_RISK_UP_ON_ADD = {"attached_added", "inline_policies_added", "groups_added"}
_RISK_DOWN_ON = {"attached_removed", "inline_policies_removed", "groups_removed"}


def _direction_hint(changes: dict[str, Any], entity_after: dict | None) -> str:
    """Neutral, mechanical direction hint. The agent may override.

    up   = something was added that generally grants more
    down = something was removed that generally grants less
    lateral = only a body/boundary/trust hash changed with no clear direction
    mixed = both up and down signals present
    """
    up = any(k in changes for k in _RISK_UP_ON_ADD)
    down = any(k in changes for k in _RISK_DOWN_ON)
    sub_dirs = [changes.get("trust_changed", {}).get("direction"),
                changes.get("policy_body_changed", {}).get("direction")]
    sub_dirs += [b.get("direction") for b in changes.get("inline_body_changed", [])]
    up = up or any(d in ("up", "mixed") for d in sub_dirs)
    down = down or any(d in ("down", "mixed") for d in sub_dirs)
    # A changed policy body / trust is ambiguous in direction on its own.
    if up and down:
        return "mixed"
    if up:
        return "up"
    if down:
        return "down"
    return "lateral"


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Literal diff of two snapshots produced by snapshot.build_snapshot.

    Returns added principals, removed principals, and per-principal field
    changes, each with a neutral direction hint. Also surfaces the coverage of
    BOTH snapshots so a consumer knows whether the comparison rests on complete
    reads -- if either side is incomplete, `comparison_complete` is False.
    """
    b_entities = before.get("entities", {})
    a_entities = after.get("entities", {})

    b_arns = set(b_entities)
    a_arns = set(a_entities)

    added_principals = []
    for arn in sorted(a_arns - b_arns):
        e = a_entities[arn]
        # A new customer principal: trust surface alone makes it risk-up even
        # with no grants. A new AWS service-linked/service role is created by
        # AWS when a service is enabled -- informational, not customer drift.
        hint = "info" if e.get("aws_managed") else "up"
        added_principals.append({
            "arn": arn,
            "type": e.get("type"),
            "name": e.get("name"),
            "entity": e,
            "direction": hint,
        })

    removed_principals = []
    for arn in sorted(b_arns - a_arns):
        e = b_entities[arn]
        removed_principals.append({
            "arn": arn,
            "type": e.get("type"),
            "name": e.get("name"),
            "direction": "down",
        })

    changed = []
    for arn in sorted(a_arns & b_arns):
        ch = _entity_changes(b_entities[arn], a_entities[arn])
        if ch:
            changed.append({
                "arn": arn,
                "type": a_entities[arn].get("type"),
                "name": a_entities[arn].get("name"),
                "changes": ch,
                "direction": _direction_hint(ch, a_entities[arn]),
            })

    b_cov = before.get("coverage", {})
    a_cov = after.get("coverage", {})
    comparison_complete = bool(b_cov.get("complete")) and bool(a_cov.get("complete"))

    return {
        "schema": 1,
        "added_principals": added_principals,
        "removed_principals": removed_principals,
        "changed_principals": changed,
        "summary": {
            "added": len(added_principals),
            "removed": len(removed_principals),
            "changed": len(changed),
            # each principal counted in exactly one bucket
            "up": sum(1 for c in changed if c["direction"] == "up")
                  + sum(1 for p in added_principals if p["direction"] == "up"),
            "mixed": sum(1 for c in changed if c["direction"] == "mixed"),
            "info": sum(1 for p in added_principals if p["direction"] == "info"),
            "down": sum(1 for c in changed if c["direction"] == "down")
                    + len(removed_principals),
            "lateral": sum(1 for c in changed if c["direction"] == "lateral"),
        },
        "comparison_complete": comparison_complete,
        "baseline_coverage": b_cov,
        "current_coverage": a_cov,
    }
