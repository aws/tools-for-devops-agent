# Finding Schema and Report Format

This file defines the **output contract** every Amazon SageMaker check must
produce and the **report** you assemble at the end.

## Finding schema

Every check emits one finding object per applicable region with exactly these
fields:

| Field | Type | Rules |
|---|---|---|
| `Check_ID` | string | Must match `^SM-\d{2}$` (e.g. `SM-01`, `SM-25`). |
| `Finding` | string | Short title of the check (non-empty). |
| `Finding_Details` | string | What was observed and why it matters (non-empty). Include the resource identifiers evaluated and, for Heuristic checks, the concrete evidence (resource id, field value, counts). |
| `Resolution` | string | Remediation guidance. May be empty for `Passed`. Required for `N/A` produced by a Prescribe-only aspect. |
| `Reference` | string | Documentation URL. **Must start with `https`.** |
| `Severity` | enum | One of `High`, `Medium`, `Low`, `Informational`. |
| `Status` | enum | One of `Failed`, `Passed`, `N/A`. |
| `Verifiability` | enum | One of `Verifiable`, `Heuristic`, `Prescribe-only` (from `references/sagemaker-checks.md`). |
| `Region` | string | AWS region (e.g. `us-east-1`). All SageMaker checks are regional. |
| `Account` | string | *(Optional; include for multi-account runs.)* The 12-digit AWS account ID. |

### Status semantics

- **Failed** — a security issue was identified that needs remediation.
- **Passed** — the assessed resources met the best practice at scan time.
- **N/A** — nothing to assess (no matching resources), SageMaker unavailable in
  the region, state indeterminate/access-denied, or a Prescribe-only aspect.

### Verifiability → Status rules (determinism contract)

- **Verifiable** — set `Passed`/`Failed`/`N/A` strictly from the returned data.
- **Heuristic** — apply the check's rule exactly and cite the evidence in
  `Finding_Details`. If evidence is ambiguous or the read is denied, emit `N/A`
  (reason in `Finding_Details`) — **never guess `Passed`**.
- **Prescribe-only** — emit `N/A` with the recommended configuration in
  `Resolution`. **Never `Passed`/`Failed`.** For `SM-02`, the stale-access and
  IAM Identity Center aspects are Prescribe-only: never mark them Passed, and do
  not call `iam:GenerateServiceLastAccessedDetails`.

When read access is denied for any check, `Status` is `N/A` with reason
`AccessDenied` — never `Passed`.

### Example finding

```json
{
  "Check_ID": "SM-09",
  "Finding": "Notebook Root Access",
  "Finding_Details": "Region us-east-1: notebook instance 'ds-nb-01' has RootAccess=Enabled.",
  "Resolution": "Set RootAccess=Disabled on the notebook instance to prevent privilege escalation.",
  "Reference": "https://docs.aws.amazon.com/sagemaker/latest/dg/nbi-root-access.html",
  "Severity": "High",
  "Status": "Failed",
  "Verifiability": "Verifiable",
  "Region": "us-east-1"
}
```

## Region resolution

1. **No region specified / single-region:** assess the current session region only.
2. **Explicit list** (comma- or space-separated): assess exactly those regions.
3. **"all":** the union of regions where `sagemaker` is available. If discovery is
   not possible, fall back to the current region.

All SageMaker checks are regional; for a region where SageMaker has no matching
resources or is unavailable, still emit the checks as `N/A` for that region.

## Account resolution (multi-account)

Cross-account access is provided by the **Agent Space associations** — the DevOps
Agent service assumes the read-only monitoring role in each associated account
directly. The skill never calls `AssumeRole` itself.

1. **Single-account (default):** assess the primary account only.
2. **Explicit account list:** assess exactly the account IDs the user names.
3. **"all accounts"/"the organization":** assess every associated account.

When more than one account is in scope, iterate account × region, scope every
read-only call to the target account, and set the `Account` field on every
finding. If a requested account is not reachable, emit its checks as `N/A` with
the reason.

## Report format

### 1. Header
- Account ID(s), timestamp (UTC), regions scanned, read-only confirmation.

### 2. Executive summary
- **By severity:** counts of `Failed` findings High/Medium/Low, plus totals of
  Passed / N/A.
- **By region:** Failed count per region.
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

- Every `Check_ID` matches `^SM-\d{2}$`.
- Every `Reference` starts with `https`.
- Every `Severity`, `Status`, and `Verifiability` is an allowed enum value.
- No `Heuristic` finding is `Passed` without cited evidence in `Finding_Details`.
- `SM-02` never reports its stale-access or IAM Identity Center aspects as
  `Passed`, and `iam:GenerateServiceLastAccessedDetails` was not called.
- Counts in the executive summary reconcile with the findings table.
