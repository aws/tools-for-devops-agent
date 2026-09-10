# Finding Schema and Report Format

This file defines the **output contract** every Amazon Bedrock check must produce
and the **report** you assemble at the end.

## Finding schema

Every check emits one finding object per applicable region with exactly these
fields:

| Field | Type | Rules |
|---|---|---|
| `Check_ID` | string | Must match `^BR-\d{2}$` (e.g. `BR-01`, `BR-33`). |
| `Finding` | string | Short title of the check (non-empty). |
| `Finding_Details` | string | What was observed and why it matters (non-empty). Include the resource identifiers evaluated and, for Heuristic checks, the concrete evidence (policy name, ARN, field value). |
| `Resolution` | string | Remediation guidance. May be empty for `Passed`. Required for `Prescribe-only`. |
| `Reference` | string | Documentation URL. **Must start with `https://`.** |
| `Severity` | enum | One of `High`, `Medium`, `Low`, `Informational`. |
| `Status` | enum | One of `Failed`, `Passed`, `N/A`. |
| `Verifiability` | enum | One of `Verifiable`, `Heuristic`, `Prescribe-only` (from `references/bedrock-checks.md`). |
| `Region` | string | AWS region (e.g. `us-east-1`) or `Global` for IAM/Organizations-derived checks. |
| `Account` | string | *(Optional; include for multi-account runs.)* The 12-digit AWS account ID. Omit or set to the primary account for single-account runs. |

### Status semantics

- **Failed** — a security issue was identified that needs remediation.
- **Passed** — the assessed resources met the best practice at scan time.
- **N/A** — nothing to assess (no matching resources), Bedrock unavailable in the
  region, state indeterminate/access-denied, or the check is `Prescribe-only`.

### Verifiability → Status rules (determinism contract)

Honor the `Verifiability` of each check (see `SKILL.md` → "Verify vs. prescribe"):

- **Verifiable** — set `Passed`/`Failed`/`N/A` strictly from the returned data.
- **Heuristic** — apply the check's rule exactly and cite the evidence in
  `Finding_Details`. If evidence is ambiguous or the read is denied, emit `N/A`
  (reason in `Finding_Details`) — **never guess `Passed`**.
- **Prescribe-only** — **always `N/A`**; put the recommended configuration in
  `Resolution`. **Never `Passed`/`Failed`.** (v1: `BR-14`.)

When read access is denied for any check, `Status` is `N/A` with reason
`AccessDenied` — never `Passed`.

### Example finding

```json
{
  "Check_ID": "BR-05",
  "Finding": "Guardrail Configuration",
  "Finding_Details": "Region us-east-1: bedrock:ListGuardrails returned an empty list; Bedrock resources are in use without any guardrail.",
  "Resolution": "Configure content filters (hate, insults, sexual, violence) on all guardrails and attach them to model/agent invocations.",
  "Reference": "https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html",
  "Severity": "High",
  "Status": "Failed",
  "Verifiability": "Verifiable",
  "Region": "us-east-1"
}
```

Prescribe-only example (`BR-14`), always `N/A`:

```json
{
  "Check_ID": "BR-14",
  "Finding": "Stale Bedrock Access",
  "Finding_Details": "Cannot be evaluated read-only: iam:GenerateServiceLastAccessedDetails is a Generate* verb blocked by the DevOps Agent read-only guardrail.",
  "Resolution": "Out of band, review IAM Access Advisor last-accessed data for Bedrock-permissioned principals and remove permissions unused for 90+ days.",
  "Reference": "https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_last-accessed.html",
  "Severity": "Medium",
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
3. **"all":** the union of regions where `bedrock` is available. If discovery is
   not possible, fall back to the current region.

Emit **global** checks (`BR-01`, `BR-03`, `BR-14`, `BR-15`) once, on the primary
region, with `Region: "Global"`. Emit regional checks per region; for a region
where Bedrock has no resources or is unavailable, still emit the regional checks
as `N/A`.

## Account resolution (multi-account)

Cross-account access is provided by the **Agent Space associations** — the DevOps
Agent service assumes the read-only monitoring role in each associated account
directly. The skill never calls `AssumeRole` itself.

1. **Single-account (default):** assess the **primary** account only.
2. **Explicit account list:** assess exactly the account IDs the user names.
3. **"all accounts"/"the organization":** assess every associated account.

When more than one account is in scope, iterate **account × region**, scope every
read-only call to the target account, set the `Account` field on every finding,
and emit each global check **once per account**. If a requested account is not
reachable, emit that account's checks as `N/A` with the reason.

## Report format

### 1. Header
- Account ID(s), timestamp (UTC), regions scanned, read-only confirmation.

### 2. Executive summary
- **By severity:** counts of `Failed` findings High/Medium/Low, plus totals of
  Passed / N/A.
- **By region / scope:** Failed count per region and for `Global`.
- **By verifiability:** counts of Verifiable / Heuristic / Prescribe-only, and how
  many Prescribe-only + AccessDenied controls are reported `N/A` (so the reader
  knows what was *not* provable rather than assumed passing).
- **By account (multi-account only):** Failed/Passed/N/A per account.

### 3. Priority recommendations
- Every **High-severity `Failed`** finding first (Check_ID, Finding, Region,
  one-line resolution), then Medium `Failed`.

### 4. Findings table
Columns: `Check_ID | Finding | Region | Severity | Status | Verifiability | Resolution`.
For multi-account runs add an `Account` column first and sort by Account, then
Severity (High→Info), then Check_ID. Include all findings (Failed, Passed, N/A).

### 5. Machine-readable output
Emit a single fenced JSON array of every finding object (all statuses), each
conforming to the schema above (including `Verifiability`).

## Self-check before returning

- Every `Check_ID` matches `^BR-\d{2}$`.
- Every `Reference` starts with `https://`.
- Every `Severity`, `Status`, and `Verifiability` is an allowed enum value.
- Every `Prescribe-only` finding has `Status: "N/A"` (never Passed/Failed) — in v1
  that is `BR-14`.
- No `Heuristic` finding is `Passed` without cited evidence in `Finding_Details`.
- Global checks appear once (Region `Global`) — and once per account in
  multi-account runs.
- Counts in the executive summary reconcile with the findings table.
