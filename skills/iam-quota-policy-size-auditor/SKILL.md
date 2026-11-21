---
name: iam-quota-policy-size-auditor
description: >-
  Use this skill for ANY request to audit, review, or health-check IAM for
  objects approaching their limits — including plainly phrased ones like "audit
  my IAM roles and policies for anything close to a limit" or "give me a plan to
  fix my IAM limit risks", with NO need for the user to name the specific limit
  types. Also activate when a deployment or operation fails on an IAM entity or
  policy-size limit: LimitExceeded for managed policies per role/user, policy
  document too large, trust policy too large, or entities-per-account quota. Any
  mention of IAM together with "limit", "quota", "approaching", "near", "close
  to", "too many policies", or "policy too large" should trigger this skill.
  The skill is READ-ONLY and REPORT-ONLY: it computes distance-to-limit
  deterministically and recommends consolidate-vs-increase, but never writes,
  merges, or rewrites a policy and never submits a quota increase.
metadata:
  author: saadnu-aws
  version: "1.0.0"
  summary: "Read-only audit of IAM roles, users and policies against their limits, with a consolidate-or-increase plan. Never edits a policy or requests a quota increase."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS IAM, AWS Service Quotas"
  aws-devops-agent-skills.technical-domains: "Security, Operations, Capacity Planning"
---

# IAM Quota & Policy-Size Auditor

Audit an AWS account's IAM roles, users, and policies for objects approaching
their IAM limits, and produce a prioritized, deterministic remediation plan.
This skill does the limit math the base agent does not: it measures each
object's distance to its specific IAM limit and classifies each at-risk object
as a consolidation candidate or an adjustable-quota increase candidate.

> **Report-only by construction.** This skill never authors, merges, collapses,
> or rewrites policy JSON, and never submits a quota increase. "Consolidate
> these policies" is a recommendation to the operator, not a generated
> document. All limit math is deterministic (same input → same output); the
> model only orders and narrates the already-computed findings. This is the
> design that avoids non-deterministic IAM recommendations widening
> permissions or dropping `Condition` blocks.

## When to Use This Skill

- A deployment fails on an IAM limit: too many managed policies attached to a
  role/user, a policy document exceeding its size limit, a trust policy over
  2,048 characters, or the account entity count at quota.
- Proactive IAM-limit health check across roles, users, and policies.
- Before a large IaC rollout that will attach policies or create entities.

## Prerequisites

Read-only IAM and Service Quotas permissions only (no write actions):

- `iam:ListRoles`, `iam:ListPolicies`, `iam:ListUsers`
- `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`
- `iam:ListAttachedUserPolicies`, `iam:ListUserPolicies`
- `iam:GetPolicy`, `iam:GetPolicyVersion`
- `iam:GetRolePolicy`, `iam:GetUserPolicy`
- `iam:GetRole` (trust policy / `AssumeRolePolicyDocument`)
- `iam:GetAccountSummary` (entity-count limits)
- `iam:GetAccountAuthorizationDetails` (optional; one paginated call returns every role, its attached policies, and customer-managed policy documents)
- `servicequotas:GetServiceQuota`, `servicequotas:ListServiceQuotas` (adjustable-limit lookup; drafting only)

IAM is global; run once per account (not per region).

## The IAM limits this skill measures

| Object | Limit | Adjustable? |
|---|---|---|
| Managed policies attached per role | 20 (default); resolve live via Service Quotas | Yes (Service Quotas) |
| Managed policies attached per user | 20 (default); resolve live via Service Quotas | Yes |
| Customer-managed policy document size | 6,144 characters | No |
| Inline policy size (per role/user/group) | 10,240 characters | No |
| Role trust policy (`AssumeRolePolicyDocument`) | 2,048 characters | No |
| Managed policy versions | 5 | No |
| Roles per account / policies per account | account quota | Yes |
| Role name length | 64 | No |
| Role path length | 512 | No |

> **AWS-managed policies are excluded from size flagging.** The 6,144-char
> limit applies to customer-managed policies only; some AWS-managed policies
> (e.g. `ReadOnlyAccess`) already exceed it legitimately.

> **Resolve the LIVE limit from Service Quotas — never score against a
> model-recalled number.** For every adjustable limit, query the value that
> actually applies to THIS account before computing a percentage:
>
> ```bash
> aws service-quotas get-service-quota --service-code iam --quota-code L-0DA4ABF3 \
>   --query 'Quota.Value' --output text   # managed policies per role
> ```
>
> Use the returned `Applied` value as the denominator. The AWS-wide default for
> managed-policies-per-role (`L-0DA4ABF3`) is currently **20** (accounts may
> have a higher applied value), so a 9-attachment role is **9/20 = 45% = OK** —
> do NOT assume the legacy default of 10 and flag it as High. Only if the
> `service-quotas` call is denied (permission gap) may you fall back to a
> documented default, and when you do you MUST state the denominator you used
> and that it is unverified. Scoring against a stale or assumed limit — in
> either direction — is a defect, not a judgment call.

## Workflow

Copy this checklist and work through it in order. Each step is detailed in the
section of the same number below.

- [ ] Step 1: Enumerate IAM objects (roles, users, managed and inline policies).
- [ ] Step 2: Measure each object deterministically against its limit.
- [ ] Step 3: Compute distance to limit and flag by severity.
- [ ] Step 4: Recommend consolidate vs. request-increase. Never execute either.
- [ ] Step 5: Produce the prioritized remediation plan.
- [ ] Step 6: Validate before presenting: re-check that each flagged count/size came from a measurement in Step 2 (not an estimate), that each denominator is the live quota where available, and that any enumeration gap is stated and scopes the conclusion.

## Step 1: Enumerate IAM objects

Prefer one bulk call over per-role loops. It returns every role with its
attached managed policies, plus every customer-managed policy document:

```bash
aws iam get-account-authorization-details \
  --filter Role User LocalManagedPolicy --output json
aws iam get-account-summary
```

Count `AttachedManagedPolicies` per role/user from that output, and measure the
default version of each `LocalManagedPolicy`. This avoids hundreds of
`list-attached-role-policies` calls on large accounts.

If `get-account-authorization-details` is denied, fall back to per-object calls:

```bash
aws iam list-roles --query 'Roles[].{Name:RoleName,Arn:Arn}'
aws iam list-users --query 'Users[].{Name:UserName,Arn:Arn}'
aws iam list-policies --scope Local --query 'Policies[].{Name:PolicyName,Arn:Arn,Versions:DefaultVersionId}'
aws iam get-account-summary
```

`--scope Local` restricts to customer-managed policies (never AWS-managed).

> **Fallback when `iam:ListPolicies` is denied.** Do not stop. Build the
> customer-managed policy list from what you can already see: collect every
> policy ARN returned by `list-attached-role-policies` and
> `list-attached-user-policies`, keep only ARNs that do NOT start with
> `arn:aws:iam::aws:policy/`, then run `get-policy` and `get-policy-version`
> on each unique ARN and measure it. State in the report that this covers
> attached policies only: unattached customer-managed policies are not
> visible without `iam:ListPolicies`, so the size conclusion is scoped to
> attached ones. A denied call narrows the scope of the finding; it never
> ends the audit.
>
> A second way to list customer-managed policies, if AWS Resource Explorer is
> enabled, is a search for `resourcetype:iam:policy` excluding the
> `arn:aws:iam::aws:policy/` prefix. If you use it, say so, and say whether
> the result covers unattached policies too.

> **Finish the audit in this turn.** Do the enumeration and measurement
> yourself and present the full result before ending the turn. Never end with
> "I'm running the audit now", "I'll report back when it finishes" or any
> promise of later results, and never hand the work to a background task or
> subagent. A reply with no measured numbers is a failed audit. If the
> user scoped the request (for example to roles with a given name prefix),
> enumerate that scope exhaustively and say what the scope was.

> **Enumerate exhaustively — never sample.** You MUST measure the
> attached-policy count for EVERY role returned, not a sample or a spot-check.
> A single role one attachment from its limit is exactly what this audit
> exists to catch, and it will not appear in a sampled subset. Do not conclude
> "nothing is at risk" from a partial pass; if a permission gap blocks full
> enumeration, say so explicitly and scope the conclusion to what was actually
> measured. "I sampled N roles and the max was 4" is a failure mode, not a
> result.

## Step 2: Measure each object deterministically

For each role: count attached managed policies; fetch and measure the trust
policy and each inline policy. For each customer-managed policy: fetch the
default version and measure it.

**Measurement rule (critical for accuracy):** IAM returns policy documents
**URL-encoded**, and the IAM size limits are measured with **whitespace
excluded**. Always URL-decode first, then remove all whitespace (spaces, tabs, newlines)
before counting characters. State in the report that you measured this way; if
you could only measure with whitespace included, say the figure overstates the
size.
Measuring raw or encoded JSON overstates the size.

```bash
# Attached managed policy count for a role
aws iam list-attached-role-policies --role-name "$ROLE" \
  --query 'length(AttachedPolicies)'

# Trust policy (URL-decode before measuring)
aws iam get-role --role-name "$ROLE" \
  --query 'Role.AssumeRolePolicyDocument' --output text
```

## Step 3: Compute distance to limit and flag by severity

```
distance_pct = (current / limit) × 100
```

| Distance | Severity |
|---|---|
| < 70% | OK |
| 70–89% | Warning |
| 90–99% | High |
| ≥ 100% | Blocking |

Produce a table, highest severity first:

```
┌────────────────────────────────────┬────────────────────────┬───────┬───────┬──────────┐
│ Object                              │ Limit                  │ Value │ %     │ Status   │
├────────────────────────────────────┼────────────────────────┼───────┼───────┼──────────┤
│ role/app-exec  (attached policies)  │ 20 managed/role (live) │ 18    │ 90%   │ ⚠️ HIGH  │
│ policy/big-read (customer-managed)  │ 6144 chars             │ 5980  │ 97%   │ ⚠️ HIGH  │
│ role/legacy    (trust policy)       │ 2048 chars             │ 1500  │ 73%   │ WARN     │
└────────────────────────────────────┴────────────────────────┴───────┴───────┴──────────┘
```

## Step 4: Recommend consolidate vs. request-increase (never execute)

For each flagged object, pick exactly one recommendation:

- **Adjustable limit** (managed-policies-per-role/user, account entity counts):
  recommend a Service Quotas increase and **draft** the request. State the
  current and desired values. Do **not** submit it — `servicequotas:RequestServiceQuotaIncrease`
  is a write action this skill does not hold.
- **Fixed limit** (policy/inline/trust size, versions, name/path length):
  recommend consolidation and **state the tradeoff explicitly** — e.g. merging
  policies frees attachment slots but grows policy size and consumes one of the
  5 managed-policy versions. Never present a merge as free.

**Where the fix must land:** point recommendations at the IaC source of truth
(CloudFormation / CDK / Terraform), not the console, since console edits drift.
Always say this explicitly in the final answer, even when you cannot identify
which template or repo owns the object (check the `aws:cloudformation:stack-name`
tag or `aws:cdk` tags if present, otherwise ask). When the user asks you to
make the change yourself, decline, explain this skill is report-only, and name
the IaC source as the place the change belongs. Never suggest editing in the
console.
Flag `AWSReservedSSO_*` roles as IAM Identity Center–managed (fix on the
permission set, not the role).

## Step 5: Produce the remediation plan

Output a prioritized plan: each flagged object, its distance-to-limit, the
chosen recommendation (consolidate or draft-increase), the tradeoff where
relevant, and the IaC pointer. The plan is a report — nothing is applied.

## Relationship to existing tooling

- **Trusted Advisor** already alerts at 80% for account-wide IAM entity
  *counts* on every support plan. This skill's distinct coverage is what TA
  does not do: **managed policies attached per role/user, inline/managed/trust
  policy byte size, and versions per policy.**
- The published `service-quota-check` skill and `Service Quotas Monitor` agent
  cover *generic* Service Quotas, not IAM entity counts or policy-size byte
  limits — the distinct, high-volume failure class this skill targets.

## Scope — what this skill does NOT do

- Does not write, merge, collapse, or rewrite any policy document.
- Does not submit a quota increase (drafts only).
- Does not flag AWS-managed policies for size.
- Does not modify roles, users, or attachments.
