# OpsAI Guardrail Posture Report

Fill in every `<placeholder>`. Delete a row only when the check genuinely does not apply,
and when you do, say why in **Scope not covered**. Never leave a placeholder unresolved in
a delivered report. Never reproduce blocked prompt/completion text; never print a raw
12-digit account ID.

**The final chat answer is this report.** When a sub-agent gathered the evidence, transcribe its
table in full — every row, every cell — never a summary of it.

When you delegate the evidence gathering, paste the Findings header row below and each check's
remediation text from `references/guardrails/checks-guardrails.md` into the sub-agent's prompt, so that it
returns all eight columns.

## Scope

- **Region examined:** `<region>`
- **Guardrails examined:** `<guardrail-ids-or-names, account segment masked>`
- **Production paths examined:** `<agent alias / flow node / RetrieveAndGenerate / app InvokeModel-Converse>`
- **Enforcement origin:** `<REQUEST | ACCOUNT_ENFORCED | ORGANIZATION_ENFORCED | none>` (from `ListEnforcedGuardrailsConfiguration`, `DescribeEffectivePolicy BEDROCK_POLICY`, and trace `appliedGuardrailDetails.guardrailOrigin`; "not read" if denied)
- **Enforced version per path:** `<path → guardrailVersion actually pinned (NOT DRAFT)>`

## Verdict

Overall responsible-AI posture: **`<ADEQUATE | GAPS FOUND | CRITICAL EXPOSURE>`**

Deciding finding: `<name the single highest-severity check that decided it, with its check-id>`.

## Findings

| check-id | Severity | Observed value | Window | Source API | Remediation owner | AWS doc | Remediation |
|---|---|---|---|---|---|---|---|
| `<LLM-GRD-NNN>` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<measured <value> / no-datapoints / not-queried>` | `<start → end UTC, or "config read at <timestamp>">` | `<the read-only API that produced it>` | `<guardrails / agent-runtime / retrieval / bedrock-configuration / caller>` | `<the catalog row's AWS-doc citation URL>` | `<read-only command or IaC change to confirm/fix>` |

Every row cites a `check-id` from `references/guardrails/checks-guardrails.md`. No freelance findings.
`workload-specific` checks with no AWS-published number are reported `INFO`. A check that was
evaluated and not raised has `Not raised` in the Severity cell; never print the catalog severity for it.

**This table is a COPY-FORWARD of the gatherer's table, not a summary of it.** If a sub-agent
returned `rows: M`, this section carries all M rows with their cells intact (observed-value prefix and
`workload-specific` label included), or prints each shortfall as its own line, so that
`N + dropped == M` is visible:

```
Findings (N carried of M gatherer rows)
dropped from the gatherer's report: <row or cell> — because <reason>
```

**All eight columns are mandatory and the first seven are the gate.** A user's list of columns is a
minimum, never a replacement: add it to these eight. The observed-value cell begins with one of
`measured `, `no-datapoints`, `not-queried`; a bare number there is malformed. The
`check-id` and its `Severity` must sit in the **same row** — a severity collected into a trailing
summary does not count. `AWS doc` is the catalog citation for that check-id; a finding row without
one is not ready to present. A finding that cannot name its window, the API that produced it, and an
AWS doc is not ready to present: either fill the row or say in **Scope not covered** why the signal
is unavailable. Do not substitute prose for the table.

## Enforced-version evidence (LLM-GRD-006)

| path | version referenced | DRAFT? | origin | note |
|---|---|---|---|---|
| `<path>` | `<numeric version / DRAFT / omitted>` | `<yes/no>` | `<REQUEST / ACCOUNT_ENFORCED / ORGANIZATION_ENFORCED>` | `<a strong DRAFT is irrelevant if production pins an older version>` |

## Validation evidence (LLM-GRD-007)

- Prior validation found: `<yes — record / no evidence>`
- Result (policy fired + counts, never content): `<e.g. prompt-attack filter intervened on 3/5 injection samples>`

## Prescription

Mandatory in every full report, also when the request lists other sections.

- `<the specific guardrail change, as a CLI/IaC recommendation the user runs>`
- `<attach guardrail + pinned version to each unprotected production path>`

## Scope not covered

- Regions skipped: `<regions / none>` (`none` only if every enabled Region was queried; a Region you did not query is skipped)
- Paths skipped: `<paths / none>`
- Checks blocked by permissions: `<API + resource you could not read / none>`
- Enforcement reads not possible: `<ListEnforcedGuardrailsConfiguration / DescribeEffectivePolicy (not in an Organization or denied) / none>`
- Region-unsupported guardrail features: `<features / none>`
- Other disclosed assumptions: `<budget bound, etc. / none>`
