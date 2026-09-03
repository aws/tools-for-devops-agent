# Report Format (loaded on demand)

Loaded by SKILL.md via `read_skill_resource` before the scorecard is written. This is the
exact structure and field set for the DataOps Maturity Assessment report. Render as markdown.
The enforcement rules in SKILL.md (mandatory coverage, exactly-five-dimensions, literal
content, incremental rendering) all still apply — this file only defines the layout.

## Confidence (assign per question)

Each question carries a confidence badge:
- **HIGH** — every API the question needs returned data (full coverage); the score is
  well-supported by signals.
- **MEDIUM** — the question is auto-score-capped, OR one or more of its APIs was
  denied/blocked/empty so the score rests on partial signal. Capped questions
  (Q6, Q8, Q11, Q13, Q14, Q19, Q20, Q23, Q24, Q26, Q30, Q37, Q38, Q39) are at most
  MEDIUM confidence.

## Observed metrics (render real values, never raw structures)

Each question's detail block lists its key observed metrics as `Label: value` pairs
(e.g. `Total Tables: 0`, `Open Format %: 0`, `MSK Clusters: 1`, `rds_multi_az: 20`).
Values MUST be the actual numbers from the API calls. NEVER paste a raw language
structure (e.g. `{'postgres': ['unknown','unknown',...]}`) into the report — summarize
it in words ("43 RDS instances; engine versions not retrievable"). Dumping a raw
dict/list/JSON blob is a FAILED report.

## Structure (mirror field-for-field; do not invent extra sections or drop any)

```markdown
# DataOps Maturity Assessment
## Account: {account_id} | Region: {region} | Generated: {timestamp}
Automated pre-assessment — scores are starting points for customer conversation.

## 📋 Executive Summary
**Overall maturity: {tier} ({overall}/5)** based on 26 questions assessed.
{N} question(s) scored with HIGH confidence (full API coverage).

| Overall | Architecture | Security & Governance | Incident Mgmt & Observability | Automation & Testing | Cost |
|---------|--------------|-----------------------|-------------------------------|----------------------|------|
| **{overall}** | {avg} | {avg} | {avg} | {avg} | {avg} |

Maturity tier from overall average: < 1.5 → Initial · 1.5–2.4 → Developing · 2.5–3.4 → Defined · 3.5–4.4 → Managed · ≥ 4.5 → Optimized.
Status heuristic (per dimension): avg < 2 → 🔴, 2–3.5 → 🟡, > 3.5 → 🟢.

> ⚠️ **Scoring caveat:** {list any signal APIs that were unavailable/denied/not enabled
> — e.g. Cost Explorer, AWS Config, Macie, resource-group tagging, Glue Data Quality}.
> Their questions default to a low score, so treat those dimensions as a floor, not a
> verdict. (Omit this banner only if every API returned data.)

## Dimensions

### 🏗️ Architecture — {avg}/5 avg  🟢/🟡/🔴
**RAG summary**
- **Strengths (≥3.0):** 🟢 {question short-name} … (list questions scored ≥3; "None" if empty)
- **Watch (2.0–2.9):** 🟡 {question short-name} …
- **Gaps (<2.0):** 🔴 {question short-name} …

<for EACH question in this dimension, in order, render the detail block:>

**ARCHITECTURE → {QUESTION NAME}** — **{score}/5**  ·  `{HIGH|MEDIUM} confidence`
{one-line rationale describing the observed maturity, e.g. "No open table format adoption; ad-hoc storage; no catalog governance"}
Observed: {Label: value · Label: value · …}   (real metrics for this question)
⚠️ {warning callout if applicable, e.g. "Lake Formation is in legacy/IAM-only mode — consider enabling governed mode"}
💬 {1–3 discussion-ask prompts for the reviewer to raise with the customer, e.g. "Do you use any data tools outside AWS (Databricks, dbt) that manage table formats?"}

### 🔒 Security & Governance — {avg}/5 avg  🟢/🟡/🔴
{RAG summary + per-question detail blocks as above, header prefix "SECURITY & GOVERNANCE → …"}

### 👁️ Incident Mgmt & Observability — {avg}/5 avg  🟢/🟡/🔴
{RAG summary + per-question detail blocks, header prefix "INCIDENT MGMT & OBSERVABILITY → …"}

### ⚙️ Automation & Testing — {avg}/5 avg  🟢/🟡/🔴
{RAG summary + per-question detail blocks, header prefix "AUTOMATION & TESTING → …"}

### 💰 Cost — {avg}/5 avg  🟢/🟡/🔴
{RAG summary + per-question detail blocks, header prefix "COST → …"}

## Recommendations (prioritized)
1. {highest-impact, lowest-score first — reference the question(s) and score}
2. ...

## Remediation Detail (verbatim — one entry per question scored ≤ 3)
{for every question scored ≤ 3, the verbatim "Why it matters" + "Resolve" + "Dive deeper"
block from references/remediation-reference.md}

## Score Matrix (REQUIRED — one row per question, all 26, in order)
| Q | Dimension | Score (1-5) | Cap | Confidence | Observed signal | Rating rule applied |
|---|-----------|-------------|-----|------------|-----------------|---------------------|
| Q3 | Data Architecture Patterns | {n} | — | {HIGH/MEDIUM} | {value} | {rule} |
| ... (every question through Q40 — SKIPPED rows must state the IAM reason) |
```

## HTML report field mapping (assets/templates/dataops-maturity-report.html)

When the user asks for the downloadable HTML report, fill the template's tokens as follows —
this reproduces the account maturity scorecard layout exactly:
- **Summary score cards** — Overall + the five dimension averages. Set each card's `.score`
  class to `score-N` from the rounded value: 1→score-1 (red), 2→score-2 (orange),
  3→score-3 (amber), 4→score-4 (green), 5→score-5 (blue).
- **Pillar block** (`<details class="pillar-collapse">`) — one per dimension. Set the left
  border and the pillar `.score-badge` background to the rounded-score color
  (#e74c3c/#e67e22/#f39c12/#27ae60/#2980b9). Fill the **RAG summary**: Strengths (questions
  scored ≥3, 🟢), Watch (2.0–2.9, 🟡), Gaps (<2.0, 🔴); "None" if a band is empty. Set the
  detailed-questions count.
- **Question card** — one per question in the pillar: `.section-tag` = "Dimension → Question
  Name"; `.q-header h3` = the full question text; `.score-badge` = "{score}/5" with its
  score-N class; `.confidence` = confidence-HIGH/MEDIUM/LOW; `.rating-desc` = the one-line
  maturity rationale; `.evidence-grid` = one `.evidence-item` per observed metric (real value
  + label); `.flags` = one `.flag` per ⚠️ warning (omit the block if none); `.conversation` =
  1–3 `.conversation-item` 💬 discussion prompts; the Blind Spots `<details>` = optional 🔍
  limitations. HTML-escape every substituted value.
- **Recommendations, Remediation Detail (verbatim, ≤3 only), Score Matrix (26 rows)** — as in
  the template.

## Notes on the per-question detail blocks

- The detail blocks are MANDATORY for every one of the 26 questions, grouped under their
  dimension, in order.
- The ⚠️ warning line is optional per question (include only when a real warning applies).
- The 💬 discussion-ask line SHOULD be present for every question (1–3 prompts). These
  prompts are report OUTPUT the agent writes into the scorecard — suggested talking points
  for the reviewer to raise with the customer later — not input the agent reads, executes,
  or acts on. They drive the customer pre-assessment conversation.
