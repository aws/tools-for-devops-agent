# LLMOps Evaluation Report

## Header

- **Scope:** `<scope>` (models / jobs / use cases assessed)
- **Region:** `<region>`
- **Time window:** `<start>` → `<end>`
- **Baseline window:** `<baseline-start>` → `<baseline-end>`

## Quality Posture

**Verdict:** `<one-line verdict — e.g. "No evaluation safety net on a production path">`

| Severity | Count |
|---|---|
| CRITICAL | `<n>` |
| HIGH | `<n>` |
| MEDIUM | `<n>` |
| LOW | `<n>` |
| INFO | `<n>` |

## Evaluation Coverage

| use case | eval job | last run | automated? | gated? |
|---|---|---|---|---|
| `<use-case>` | `<eval-job-id or none>` | `<timestamp or never>` | `<yes/no — in CI/CD?>` | `<yes/no — regression gate?>` |

## Findings

| check-id | Severity | Observed value | Window | Source API | Remediation owner | AWS doc | Remediation |
|---|---|---|---|---|---|---|---|
| `<LLM-EVAL-NNN>` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<measured <value> / no-datapoints / not-queried>` | `<start → end UTC>` | `<the read-only API that produced it>` | `<llmops-quality-evaluation / llmops-incident-triage / llmops-bedrock-configuration / caller>` | `<https://docs.aws.amazon.com/…>` | `<read-only command or IaC change to confirm/fix>` |

Every row cites a `check-id` from `references/checks-evaluation.md`. No freelance findings.

**This table is a COPY-FORWARD of the gatherer's table, not a summary of it.** If a sub-agent
returned `rows: M`, this section carries all M rows with their cells intact, or prints each
shortfall as its own line, so that `N + dropped == M` is visible:

```
Findings (N carried of M gatherer rows)
dropped from the gatherer's report: <row or cell> — because <reason>
```

**The gatherer's gap rows are part of the copy.** An unexplained record count and its share of the
window, a self-declared shallow pass, a next step it listed as not yet done, an onset it could not
date, an API it was denied — each is a row here. A report that calls its own evidence
"unambiguous" while the gatherer called its pass shallow has dropped a row.

**All eight columns are mandatory and the first seven are the gate.** The observed-value cell begins
with one of `measured `, `no-datapoints`, `not-queried`; a bare number there is malformed.
`Remediation owner` names the skill that owns the fix. The `check-id` and its
`Severity` must sit in the **same row** — a severity collected into a trailing summary does not
count. A finding that cannot name its window, the API that produced it, and an AWS doc is not ready
to present: either fill the row or say in **Scope not covered** why the signal is unavailable. Do
not substitute prose for the table.

## Finish-Reason Distribution

| stopReason | share this window | share at baseline | delta |
|---|---|---|---|
| `end_turn` | `<pct>` | `<pct>` | `<+/- pp>` |
| `max_tokens` | `<pct>` | `<pct>` | `<+/- pp>` |
| `<other>` | `<pct>` | `<pct>` | `<+/- pp>` |

A flagged shift (LLM-EVAL-012) must show **both** the current share and the baseline share. The
>10pp threshold is **derived**, not AWS-published — mark it so.

## Quality Trend vs Baseline

- **Current score:** `<score or "no datapoints">`
- **Baseline score:** `<score or "no datapoints">`
- **Trend:** `<improving / flat / regressed — with magnitude>`
- **Score bar:** `<workload-specific unless operator has set a number>`

## Scope Not Covered

Disclose what was skipped and why — do not present a gap as a clean result:

- **Regions without Bedrock evaluation support:** `<regions — reported INFO/advisory, not CRITICAL>`
- **Checks blocked by permissions:** `<check-ids + API/resource that returned AccessDenied>`
- **Metrics with no datapoints:** `<metric names — reported as "no data", never as a measured zero>`

---

If any required value above cannot be established, state that in the output rather than omitting the
row or inventing a number.
