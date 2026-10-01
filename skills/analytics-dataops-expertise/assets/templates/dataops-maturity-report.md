<!--
  DataOps Maturity Assessment — Markdown report template
  ======================================================
  Companion to dataops-maturity-report.html, mirroring its structure
  section-for-section. THIS is the in-chat output — always produced. Placeholder
  tokens only, no example/customer data. Fill every {{token}} with values
  collected live via read-only AWS control-plane APIs. Markdown renders < > & "
  literally, so no HTML-escaping is needed here (unlike the HTML template).
-->
# DataOps Maturity Assessment
## Account: {{account_id}} | Region: {{region}} | Generated: {{timestamp}}
Automated pre-assessment — scores are starting points for customer conversation.

## 📋 Executive Summary
**Overall maturity: {{maturity_tier}} ({{overall_avg}}/5)** based on 26 questions assessed.
{{high_confidence_count}} question(s) scored with HIGH confidence (full API coverage).

| Overall | Architecture | Security & Governance | Incident Mgmt & Observability | Automation & Testing | Cost |
|---------|--------------|-----------------------|-------------------------------|----------------------|------|
| **{{overall_avg}}** | {{arch_avg}} | {{sec_avg}} | {{obs_avg}} | {{auto_avg}} | {{cost_avg}} |

Maturity tier: <1.5 Initial · 1.5–2.4 Developing · 2.5–3.4 Defined · 3.5–4.4 Managed · ≥4.5 Optimized.
Per-dimension status: avg <2 🔴 · 2–3.5 🟡 · >3.5 🟢.

> ⚠️ **Scoring caveat:** {{scoring_caveat_text}} — their questions default to a low score, so treat those dimensions as a floor, not a verdict. (Omit only if every API returned data.)

## Dimensions

<!-- REPEAT per dimension, in order: Architecture, Security & Governance,
     Incident Mgmt & Observability, Automation & Testing, Cost -->
### {{dim_emoji}} {{dim_name}} — {{dim_avg}}/5 avg  {{dim_rag_emoji}}
**RAG summary**
- **Strengths (≥3.0):** {{dim_strengths}}
- **Watch (2.0–2.9):** {{dim_watch}}
- **Gaps (<2.0):** {{dim_gaps}}

<!-- REPEAT per question in this dimension, in order -->
**{{dim_name}} → {{question_name}}** — **{{q_score}}/5** · `{{q_confidence}} confidence`
{{question_text}}
_{{q_rating_desc}}_
Observed: {{observed_metrics_inline}}
⚠️ {{flag_text}}   <!-- include one per real warning; omit if none -->
💬 {{conversation_prompt}}   <!-- 1–3 discussion-ask prompts -->
🔍 {{blind_spot_text}}   <!-- optional: blind spots / limitations -->

## Recommendations (prioritized)
1. {{recommendation}}   <!-- highest-impact, lowest-score first; REPEAT -->

## Remediation Detail (verbatim — one entry per question scored ≤ 3)
<!-- REPEAT per question scored <= 3 -->
#### {{rem_question_name}} (score {{rem_score}})
**Why it matters:** {{rem_why}}
**Resolve:** {{rem_resolve}}
**Dive deeper:** {{rem_links}}

## Score Matrix (all 26 questions, in order)
| Q | Dimension | Score (1-5) | Cap | Confidence | Observed signal | Rating rule applied |
|---|-----------|-------------|-----|------------|-----------------|---------------------|
| {{q_id}} | {{q_dimension}} | {{q_score}} | {{q_cap}} | {{q_confidence}} | {{q_observed}} | {{q_rule}} |
<!-- REPEAT for all 26 rows Q3..Q40 -->
