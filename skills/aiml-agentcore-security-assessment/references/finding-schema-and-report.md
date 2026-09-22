# Finding Schema and Report Format

This file defines the **output contract** every Amazon Bedrock AgentCore check
must produce and the **report** you assemble at the end.

## Finding schema

Every check emits one finding object per applicable region with exactly these
fields:

| Field | Type | Rules |
|---|---|---|
| `Check_ID` | string | Must match `^AC-\d{2}$` (e.g. `AC-01`, `AC-17`). |
| `Finding` | string | Short title of the check (non-empty). |
| `Finding_Details` | string | What was observed and why it matters (non-empty). Include the resource identifiers evaluated and, for Heuristic checks, the concrete evidence (resource id, ARN, field value). |
| `Resolution` | string | Remediation guidance. May be empty for `Passed`. Required for `Prescribe-only`. |
| `Reference` | string | Documentation URL. **Must start with `https`.** |
| `Severity` | enum | One of `High`, `Medium`, `Low`, `Informational`. |
| `Status` | enum | One of `Failed`, `Passed`, `N/A`. |
| `Verifiability` | enum | One of `Verifiable`, `Heuristic`, `Prescribe-only` (from `references/agentcore-checks.md`). |
| `Region` | string | AWS region (e.g. `us-east-1`) or `Global` for IAM/account-derived checks (`AC-02`, `AC-03`, `AC-09`). |
| `Account` | string | *(Optional; include for multi-account runs.)* The 12-digit AWS account ID. |

### Status semantics

- **Failed** — a security issue was identified that needs remediation.
- **Passed** — the assessed resources met the best practice at scan time.
- **N/A** — nothing to assess (no matching resources), AgentCore unavailable in
  the region, state indeterminate/access-denied, or the check is `Prescribe-only`.

### Verifiability → Status rules (determinism contract)

- **Verifiable** — set `Passed`/`Failed`/`N/A` strictly from the returned data.
- **Heuristic** — apply the check's rule exactly and cite the evidence in
  `Finding_Details`. If evidence is ambiguous or the read is denied, emit `N/A`
  (reason in `Finding_Details`) — **never guess `Passed`**.
- **Prescribe-only** — **always `N/A`**; put the recommended configuration in
  `Resolution`. **Never `Passed`/`Failed`.** In this skill that is `AC-03`.

When read access is denied for any check, `Status` is `N/A` with reason
`AccessDenied` — never `Passed`.

### Example finding

```json
{
  "Check_ID": "AC-14",
  "Finding": "Gateway Inbound Authorization",
  "Finding_Details": "Region us-east-1: gateway 'orders-gw' (id gw-abc123) has authorizer type NONE.",
  "Resolution": "Configure AWS_IAM or CUSTOM_JWT inbound authorization on the gateway.",
  "Reference": "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-security.html",
  "Severity": "High",
  "Status": "Failed",
  "Verifiability": "Verifiable",
  "Region": "us-east-1"
}
```

Prescribe-only example (`AC-03`), always `N/A`:

```json
{
  "Check_ID": "AC-03",
  "Finding": "Stale Access",
  "Finding_Details": "Cannot be evaluated read-only: iam:GenerateServiceLastAccessedDetails is a Generate* verb blocked by the DevOps Agent read-only guardrail.",
  "Resolution": "Out of band, review IAM Access Advisor for AgentCore-permissioned principals and remove permissions unused for 60+ days.",
  "Reference": "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_last-accessed.html",
  "Severity": "Low",
  "Status": "N/A",
  "Verifiability": "Prescribe-only",
  "Region": "Global"
}
```

## Region resolution

1. **No region specified / single-region:** assess the current session region only
   (the primary region).
2. **Explicit list** (comma- or space-separated): assess exactly those regions in
   order; the first is primary.
3. **"all":** the union of regions where `bedrock-agentcore` is available. If
   discovery is not possible, fall back to the current region.

Emit **global** checks (`AC-02`, `AC-03`, `AC-09`) once, on the primary region,
with `Region: "Global"`. Emit regional checks per region; for a region where
AgentCore has no resources or is unavailable, still emit the regional checks as
`N/A`.

## Account resolution (multi-account)

Cross-account access is provided by the **Agent Space associations** — the DevOps
Agent service assumes the read-only monitoring role in each associated account
directly. The skill never calls `AssumeRole` itself.

1. **Single-account (default):** assess the primary account only.
2. **Explicit account list:** assess exactly the account IDs the user names.
3. **"all accounts"/"the organization":** assess every associated account.

When more than one account is in scope, iterate account × region, scope every
read-only call to the target account, set the `Account` field on every finding,
and emit each global check **once per account**. If a requested account is not
reachable, emit its checks as `N/A` with the reason.

## Report format

### 1. Header
- Account ID(s), timestamp (UTC), regions scanned, read-only confirmation.

### 2. Executive summary
- **By severity:** counts of `Failed` findings High/Medium/Low, plus totals of
  Passed / N/A.
- **By region / scope:** Failed count per region and for `Global`.
- **By verifiability:** counts of Verifiable / Heuristic / Prescribe-only, and how
  many controls are reported `N/A` because they were prescribe-only or
  access-denied (so the reader knows what was *not* provable).
- **By account (multi-account only):** Failed/Passed/N/A per account.

### 3. Priority recommendations
- Every **High-severity `Failed`** finding first (Check_ID, Finding, Region,
  one-line resolution), then Medium `Failed`.

### 4. Findings table
Columns: `Check_ID | Finding | Region | Severity | Status | Verifiability | Resolution`.
For multi-account runs add an `Account` column first and sort by Account, then
Severity (High→Info), then Check_ID. Include all findings.

### 5. Machine-readable output
Emit a single fenced JSON array of every finding object (all statuses), each
conforming to the schema above (including `Verifiability`).

## Self-check before returning

- Every `Check_ID` matches `^AC-\d{2}$`.
- Every `Reference` starts with `https`.
- Every `Severity`, `Status`, and `Verifiability` is an allowed enum value.
- `AC-03` is always `N/A` (Prescribe-only) — never Passed/Failed — and
  `iam:GenerateServiceLastAccessedDetails` was not called.
- `AC-04` does not appear in the findings (observability is owned by
  `agentcore-observability-setup`).
- No `Heuristic` finding is `Passed` without cited evidence in `Finding_Details`.
- Global checks (`AC-02`, `AC-03`, `AC-09`) appear once (Region `Global`) — once
  per account in multi-account runs.
- Counts in the executive summary reconcile with the findings table.
