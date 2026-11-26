# RDS WAR — Combined Report Structure (authoritative template)

This file defines the **exact structure** of the consolidated RDS/Aurora
Well-Architected Review report produced by the `rds-well-architected-review` skill. The agent MUST open
and follow this template when generating the report (see Step 8 in `SKILL.md`). Do not
improvise a different layout, and do not drop any section or table.

Behavioral contracts that govern how the report is filled — artifact saving, per-pillar
scoring + weighted methodology, and the findings-completeness / reconciliation rules —
live in `SKILL.md` (Steps 8a, 8b, 8c-bis) and always apply alongside this template.

## Format adaptivity (render in the host runtime's native artifact format)
This template defines the report's **content, section order, and completeness** — not a
single fixed file format. Render it in whatever artifact format the host runtime
supports, while preserving the same section order, every table, and the completeness /
reconciliation rules:
- **File-artifact runtimes (e.g., AWS DevOps Agent):** save a Markdown file with the
  structure below and embed the PNG charts via `![alt](<file>.png)` links (the default
  shown here). This is the primary/example format.
- **Structured-element runtimes (compose typed artifacts):** emit the equivalent native
  elements — `text` for narrative sections, `data_table` for every table, and `chart`
  for the visualizations (scorecard, findings-by-severity, and the per-pillar charts) —
  in the same order. Markdown tables map 1:1 to `data_table` elements; the PNG chart
  catalog maps to `chart` elements.

Either way: same sections, same order, every finding present (all severities,
per-resource), and the 8c-bis reconciliation must hold. Do not drop or reorder content
to fit a format.

## Report Structure

```markdown
# AWS RDS / Aurora — Well-Architected Health Check Report
Account: <id> | Region(s): <regions> | Date: <YYYY-MM-DD>
Observation window: <e.g., 15-day>

## Executive Summary

### Overview
<1–2 sentences: what was assessed, how many resources, which pillars.>

### Resources in Scope
| Resource | Engine | Version | Instance Class | Instances | Status |
|----------|--------|---------|----------------|-----------|--------|
| <id> | <engine> | <version> | <class / ACU range> | <n> | ✅/⚠️ |
<note any resource included in cost-only scope, and any Region only partially covered.>

### Overall Health Score: <n> / 100 — <✅ Good / ⚠️ Needs Work / ❌ Poor>
Weighted average across all five pillars (methodology below):

| Pillar | Weight | Score /100 | Weighted Contribution |
|--------|--------|-----------|-----------------------|
| Performance Efficiency | 25% | <n> | <w> |
| Security | 20% | <n> | <w> |
| Reliability | 20% | <n> | <w> |
| Cost Optimization | 20% | <n> | <w> |
| Operational Excellence | 15% | <n> | <w> |
| **Overall** | 100% | **<n>** | — |

Score methodology: qualitative assessments informed by evidence (configuration
compliance, observed metrics, best-practice alignment), averaged across resources and
weighted by finding severity — not algorithmic outputs.

### Per-Cluster Health Summary (fleet reviews)
| Resource | Avg Score | Verdict (one line) |
|----------|-----------|--------------------|
| <id> | <n>/100 | ✅/⚠️/❌ <verdict> |

### Critical Findings
1. ❌ <resource> — <finding + observed value>
   ...

### Top Cost Savings Opportunities
| Opportunity | Action | Monthly Savings |
|-------------|--------|-----------------|

### Per-pillar status legend
Reliability ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL · Security ✅ SECURE / ⚠️ WARNINGS / ❌ CRITICAL ISSUES · Operational Excellence ✅ EXCELLENT / ⚠️ GAPS / ❌ CRITICAL GAPS · Performance ✅ HEALTHY / ⚠️ DEGRADED / ❌ CRITICAL · Cost ✅ OPTIMIZED / ⚠️ OPPORTUNITIES / ❌ SIGNIFICANT WASTE
- Finding counts by severity: CRITICAL <n> / HIGH <n> / MEDIUM <n> / LOW <n> / INFO <n>
- Estimated monthly spend: $<X> | Total potential savings: $<Y>/month

![Pillar scorecard](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-scorecard.png)
![Findings by severity](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-findings-by-severity.png)

## Scope Covered
- Resources reviewed: <ids/engines/regions>
- Metric window: <e.g., 15-day, Period=6h>
- Checks skipped and why: <e.g., Performance Insights/Database Insights not enabled; log exports disabled; RDS Data API unavailable — data-plane checks limited>

## 1. Reliability
Reliability Status: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL

### High Availability Assessment
| Aspect | Configuration | Assessment |
|--------|---------------|------------|
| Multi-AZ | yes/no | — |
| Read replicas | count, AZ distribution | — |
| Failover configuration | — | — |

### Backup & Recovery
| Setting | Value | Assessment |
|---------|-------|------------|
| Retention period | X days | — |
| Backup window | HH:MM-HH:MM | — |
| Automated backups | enabled/disabled | — |
| Manual snapshots | count, oldest age | — |
| Deletion protection | yes/no | — |

### Version Lifecycle
| Attribute | Value |
|-----------|-------|
| Current version | X.Y.Z |
| Latest minor | X.Y.W |
| Latest major | A.B.C |
| Standard support end | YYYY-MM-DD |
| Extended support charges | $X/vCPU/hr |
| Valid upgrade targets | <minor / major targets> |
| New features/benefits of target | <cite release notes> |

### Transaction ID Wraparound Risk (PostgreSQL)
| Database | Age | Remaining | Risk Level |
|----------|-----|-----------|------------|

### Connection & Timeout Configuration
| Parameter | Current | Recommended | Assessment |
|-----------|---------|-------------|------------|

### Disaster Recovery
| Capability | Status | Details |
|------------|--------|---------|
| Cross-region replica | yes/no | — |
| Global Database | yes/no | — |
| Point-in-time recovery | yes/no | retention |

### Maintenance Windows
| Setting | Value | Assessment |
|---------|-------|------------|

### Reliability Visualizations
![Replica lag](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-replica-lag.png)
![Backup retention vs target](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-backup-retention.png)

### Reliability Findings
| # | Finding | Severity | Pillar Area | Evidence |
|---|---------|----------|-------------|----------|

### Reliability Recommendations
| # | Action | Priority | Expected Impact |
|---|--------|----------|-----------------|

### Reliability Pillar Score: <n>/100
Rationale: <cite specific evidence>

## 2. Security
Security Status: ✅ SECURE / ⚠️ WARNINGS / ❌ CRITICAL ISSUES

### Encryption Assessment
| Aspect | Status | Details |
|--------|--------|---------|
| At rest | ✅/❌ | KMS key type, key ARN |
| In transit | ✅/❌ | SSL enforcement, TLS version |
| Cipher suites | — | Configured ciphers |

### Authentication & Access Control
| User/Role | Privileges | Auth Method | Assessment |
|-----------|-----------|-------------|------------|

### Network Security
| Security Group | Rule | Port | Source | Assessment |
|----------------|------|------|--------|------------|

### Audit Logging Review
| Log Type | Enabled | Exported to CW | Compliance Impact |
|----------|---------|----------------|-------------------|

### Security Parameters
| Parameter | Current Value | Recommended | Severity |
|-----------|---------------|-------------|----------|

### Security Visualizations
![Network exposure](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-network-exposure.png)
![Encryption posture](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-encryption-posture.png)

### Security Findings
| # | Finding | Severity | Evidence |
|---|---------|----------|----------|

### Security Recommendations
| # | Action | Priority | Expected Impact |
|---|--------|----------|-----------------|

### Security Pillar Score: <n>/100
Rationale: <cite specific evidence>

## 3. Operational Excellence
Operational Status: ✅ EXCELLENT / ⚠️ GAPS / ❌ CRITICAL GAPS

### Logging Assessment
#### CloudWatch Log Exports
| Resource | postgresql | error | audit | slowquery | general | iam-db-auth-error | instance |
|----------|-----------|-------|-------|-----------|---------|-------------------|----------|
(mark ✅/— per engine's applicable log types)

#### Database Logging Parameters (from parameter group / pg_settings)
PostgreSQL:
| Parameter | <resource…> | Recommended |
|-----------|-------------|-------------|
| log_connections | on/off | on |
| log_disconnections | on/off | on |
| log_checkpoints | on/off | on |
| log_statement | value | ddl |
| log_min_duration_statement | value | 1000ms |
| log_autovacuum_min_duration | value | 250ms |

MySQL:
| Parameter | <resource…> | Recommended |
|-----------|-------------|-------------|
| slow_query_log | 0/1 | 1 |
| long_query_time | value | 1 |
| general_log | 0/1 | 0 (prod) |
| innodb_print_all_deadlocks | 0/1 | 1 |

#### Log Retention
| Log Group | Retention (days) | Assessment |
|-----------|------------------|------------|
(flag "never expires" as unbounded cost)

### Monitoring & Alerting
| Metric | Alarm Exists | Threshold | Assessment |
|--------|--------------|-----------|------------|

#### Recommended CloudWatch Alarms
| Metric | Threshold | Period | Action |
|--------|-----------|--------|--------|

### Observability (Database Insights)
| Component | State | Assessment |
|-----------|-------|------------|
| CloudWatch Database Insights | Standard/Advanced/off | — |
| Enhanced Monitoring | interval / off | — |
| Performance Insights migration (EOL 2026-06-30) | done/pending | — |

### Maintenance Configuration
#### Autovacuum (PostgreSQL) / InnoDB (MySQL)
| Parameter | Current Value | Recommended | Assessment |
|-----------|---------------|-------------|------------|

#### Effectiveness
| Table | Last Vacuum | Last Analyze | Age | Assessment |
|-------|-------------|--------------|-----|------------|

### Extensions & Libraries
| Extension/Plugin | Installed | Recommended | Purpose |
|------------------|-----------|-------------|---------|

### Log Analysis Findings (7-Day)
| Pattern | Occurrences | Severity | Assessment |
|---------|-------------|----------|------------|

### Change Management
| Aspect | Configuration | Assessment |
|--------|---------------|------------|
| Parameter group | custom/default | — |
| Maintenance window | schedule | — |
| Auto minor upgrade | yes/no | — |

#### Parameter Group Configuration (from `DescribeDB[Cluster]Parameters`)
| Parameter | <resource…> | Recommended | Assessment |
|-----------|-------------|-------------|------------|
(key non-default / security- and performance-relevant parameters; note static params pending reboot; flag `default.*` groups)

### Engine Version
| Attribute | Value |
|-----------|-------|
| Current | X.Y.Z |
| Latest minor | X.Y.W |
| Latest major | A.B.C |
| EOL risk | — |

### Operational Excellence Visualizations
![Alarm coverage](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-alarm-coverage.png)
![Log export coverage](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-log-exports.png)

### Operational Excellence Findings
| # | Finding | Severity | Evidence |
|---|---------|----------|----------|

### Operational Excellence Recommendations
| # | Action | Priority | Expected Impact |
|---|--------|----------|-----------------|

### Operational Excellence Pillar Score: <n>/100
Rationale: <cite specific evidence>

## 4. Performance Efficiency
Performance Status: ✅ HEALTHY / ⚠️ DEGRADED / ❌ CRITICAL

### Metrics Summary Table
| Metric | 15-Day Avg | 15-Day Max/Min | Threshold | Assessment |
|--------|-----------|----------------|-----------|------------|

### Configuration Review
| Parameter | Current Value | Recommended | Rationale |
|-----------|---------------|-------------|-----------|

### Query Performance Analysis
| Rank | Query (truncated) | CPU% | I/O Reads | Avg Duration | Assessment |
|------|-------------------|------|-----------|--------------|------------|

### Index Analysis
(duplicate, unused, missing indexes)
| Type | Table | Index | Size | Assessment |
|------|-------|-------|------|------------|

### Table Health
| Table | Size | Bloat % | Last Vacuum | Last Autovacuum | Assessment |
|-------|------|---------|-------------|-----------------|------------|

### Temporary Space Usage
| Query | Temp Reads | Temp Writes | work_mem Assessment |
|-------|-----------|-------------|---------------------|

### Database Insights Summary — DB Load (if enabled)
| Metric | Value | Assessment |
|--------|-------|------------|
| DB Load vs vCPU | X / Y | — |
| Top Wait Event | — | — |
| Top SQL | — | — |

### Performance Visualizations
![CPU / memory / IOPS](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-cpu-mem-iops.png)
![DB load vs vCPU](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-db-load-vs-vcpu.png)
![Read/Write latency](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-latency.png)

### Performance Findings
| # | Finding | Severity | Evidence (specific metric values) |
|---|---------|----------|-----------------------------------|

### Performance Recommendations
| # | Action | Priority | Expected Impact |
|---|--------|----------|-----------------|

### Performance Efficiency Pillar Score: <n>/100
Rationale: <cite specific evidence>

## 5. Cost Optimization
Cost Status: ✅ OPTIMIZED / ⚠️ OPPORTUNITIES / ❌ SIGNIFICANT WASTE
Estimated monthly spend: $X | Total potential savings: $Y/month

### Current Spend Breakdown
(cluster-scoped, last full month)
| Cost Component | Monthly Amount | % of Total |
|----------------|----------------|------------|

### I/O Cost Analysis
| Month | Read I/O Ops | Write I/O Ops | I/O Cost | % of Total |
|-------|--------------|---------------|----------|------------|
- Current storage tier: standard / aurora-iopt1
- Recommendation: [stay / switch] with cost comparison math

### Instance Right-Sizing
| Current | Recommended | Monthly Savings | Rationale |
|---------|-------------|-----------------|-----------|
- Graviton migration opportunity: $X/month savings
- Serverless v2 evaluation (Aurora only): ACU pricing analysis

### Storage Analysis
| Metric | Value | Trend | Assessment |
|--------|-------|-------|------------|
- Storage type optimization (gp2 → gp3)
- Growth trend and archiving candidates

### Backup Cost Review
| Aspect | Current | Recommendation |
|--------|---------|----------------|
- Retention policy assessment
- Manual snapshot inventory (age, size, still needed?)

### Commitment Coverage Analysis
| Type | Coverage % | Gap | Opportunity |
|------|-----------|-----|-------------|
- RI coverage and expiration dates
- Savings Plans utilization

### Savings Plans Recommendation
(Only after other optimizations are implemented)
- Database Savings Plans — verify current term(s), payment option(s), covered services, and savings % from the authoritative docs (see `references/cost-optimization-reference.md`); give per-instance-type estimates. Do not hardcode terms.

### Cost Visualizations
![Spend breakdown](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-spend-breakdown.png)
![Savings opportunities](rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-savings-opportunities.png)

### Cost Findings
| # | Finding | Severity | Current Cost Impact | Potential Savings |
|---|---------|----------|---------------------|-------------------|

### Cost Recommendations (Priority Order)
1. Immediate operational fixes (I/O tier, right-sizing, storage)
2. Then commitment-based savings (Savings Plans) — last

### Cost Optimization Pillar Score: <n>/100
Rationale: <cite specific evidence with dollar amounts>

## Consolidated Findings (all pillars, ranked by severity)
| # | Pillar | Finding | Severity | Evidence | Potential Savings |
|---|--------|---------|----------|----------|-------------------|

## Consolidated Recommendations (priority order)
1. Immediate operational/security/availability fixes (CRITICAL/HIGH)
2. Medium-term improvements (MEDIUM)
3. Then commitment-based savings (Savings Plans) — last
4. Low-priority hardening/optimization (LOW)

## Overall WAR Score
Overall score (average of the five pillar scores): <n>/100
Rationale: <cite the per-pillar scores and the dominant findings driving them>

## Artifacts
- Report: `rds-well-architected-review-review-<scope-label>-<YYYY-MM-DD>.md`
- Charts: list every generated `rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-<chart>.png` (scorecard, findings-by-severity, and the per-pillar charts produced)

## Implementation Roadmap
Group the actionable recommendations into phases (each item: resources affected,
action, and rationale). Provide the exact command/IaC snippet where relevant; a human
applies it (read-only skill).

### Immediate Actions (0–30 Days)
1. <action> — <resources> — <rationale>

### Short-Term Actions (1–3 Months)
<n>. <action> — <resources> — <rationale>

### Long-Term Actions (3–12 Months)
<n>. <action> — <resources> — <rationale>

## Appendix

### Data Sources
| Source | Details |
|--------|---------|
| AWS RDS API | `describe-db-clusters`, `describe-db-instances` (config), `describe-db[-cluster]-parameters` (parameter groups) |
| Amazon CloudWatch | 15-day metric history (list metrics used) |
| CloudWatch Logs Insights | 7-day log analysis across RDS log groups |
| AWS Cost Explorer | cost data by service/resource/region (state months) |
| AWS Pricing API | on-demand pricing for instance types / storage (region) |
| Database catalogs (RDS Data API, where reachable) | pg_settings/pg_stat_*, performance_schema/information_schema, pg_hba_file_rules |

### Assessment Limitations
- <e.g., RDS Data API not reachable for cluster X → parameter values from parameter group only>
- <e.g., resource with zero instances → config-only scoring, no metrics>
- <regions / resources partially covered; cost window length>

### References
| Topic | AWS Documentation |
|-------|-------------------|
| (cite the exact AWS doc URLs relevant to the findings — see the references/ files) |

## Disclaimer
Read-only assessment. Cost figures are estimates (Cost Explorer does not break RDS
spend down per database). Recommendations require human review before applying; no
mutating API is called and no safety protection is disabled.
```

> The per-pillar sections above reproduce, without omission, the report structure
> defined in each source pillar skill (Reliability, Security, Operational Excellence,
> Performance, Cost) — including each pillar's own status label wording, all tables,
> its Findings and **Recommendations** tables, and its `<Pillar> Pillar Score` line —
> plus the combined additions (Resources in Scope, weighted Overall Health Score,
> Per-Cluster Health Summary, Consolidated Findings/Recommendations, Implementation
> Roadmap, and Appendix). Do not drop any pillar section or table.


## Visualizations (PNG charts) — include what each pillar would produce
Produce the same visual output the individual skills' runs deliver: render PNG charts
from the collected data and embed them in the report next to the relevant pillar
section. Generate the images with a local plotting library (e.g., Python matplotlib)
and save them alongside the report artifact, then reference each with a markdown image
link `![alt](<file>.png)` in the pillar section it belongs to.

Naming: `rds-well-architected-review-<scope-label>-<YYYY-MM-DD>-<chart>.png`. At minimum produce these
charts (skip only when the underlying data is unavailable, and say so in Scope Covered):

| Pillar | Chart (PNG) | Data source |
|--------|-------------|-------------|
| Overall | `scorecard` — pillar scores bar/radar (0–100) | the five pillar scores |
| Overall | `findings-by-severity` — stacked bar of CRITICAL/HIGH/MEDIUM/LOW/INFO | consolidated findings |
| Reliability | `replica-lag` — ReplicaLag/AuroraReplicaLag over the window; `backup-retention` vs target | CloudWatch, config |
| Security | `network-exposure` / `encryption-posture` — pass/fail summary | SG rules, encryption/IAM config |
| Operational Excellence | `alarm-coverage` — required vs configured alarms; `log-exports` coverage | CloudWatch alarms, log exports |
| Performance | `cpu-mem-iops` — CPU %, FreeableMemory, IOPS over the window; `db-load-vs-vcpu`; `latency` read/write | CloudWatch (15-day), Database Insights |
| Cost | `spend-breakdown` — pie/bar by usage type; `savings-opportunities` — bar of $/month | Cost Explorer |

Rules:
- Charts **supplement**, never replace, the detail tables — always include both.
- Label axes/units and the window; annotate thresholds where relevant.
- If the plotting library or data is unavailable, note it in **Scope Covered** and keep the tables.
- List every generated `.png` under the report's **Artifacts** line and confirm their saved paths to the user.


