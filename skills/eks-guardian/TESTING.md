# Testing & Validation Guide

## Overview

EKS Guardian is a DevOps Agent Skill — it contains no executable code, only Markdown instructions and reference data. Testing is performed two ways: an automated skill-evaluation harness (below) that measures the skill's contribution deterministically, and manual validation scenarios against known cluster state.

## Automated Skill Evaluation (`evals/`)

The `evals/` folder holds a lightweight, deterministic evaluation harness — no live cluster access required. It has two independent suites plus a shared fixture:

| File | Purpose |
|------|---------|
| `evals.json` | **Capability evals** — prompts with deterministic assertions (substring/regex). Each runs *with* and *without* the skill so the harness can measure the skill's contribution (the "delta"). |
| `eval_queries.json` | **Trigger evals** — prompts labelled `should_trigger` true/false, verifying the skill activates on EKS-review requests and stays quiet on unrelated ones. |
| `files/cluster-context.json` | Shared fixture: a single synthetic `demo-cluster` with a placeholder account ID (`123456789012`). Contains no real data. |
| `.skilleval.yaml` | Harness config (currently suppresses the `STR-016` structural-lint rule, since a `README.md` alongside `SKILL.md` is intentional). |

**What the capability evals check** (grounded in `SKILL.md`):
- `eks-guardian-smoke-test` — read the fixture and list cluster name / region / account.
- `eks-guardian-report-artifact-naming` — propose the report filename `eks-review-<cluster>-<YYYY-MM-DD>.md`.
- `eks-guardian-data-source-priority` — K8s API first, AWS API fallback, plus named K8s tools.
- `eks-guardian-severity-definitions` — CRITICAL / HIGH / MEDIUM / LOW / INFO.
- `eks-guardian-best-practices-sections` — Security, Reliability, Networking, Scalability, Upgrades, Cost, Karpenter.
- `eks-guardian-scorecard-grades` — the A–F scorecard scale (90–100 → A).

**Interpreting results:** a good run shows a high *with-skill* pass rate, a meaningful positive delta over *without-skill*, and trigger/no-trigger precision of 1.0. Generated report files (e.g. `benchmark.json`, `report.json`, `trigger_report.json`) are run **outputs**, not committed inputs — regenerate them locally and do not commit reports that embed absolute home-directory paths or other environment-specific details.

**Note:** the `evals/` folder and `.skilleval.yaml` are test assets and are **not** part of the uploaded skill bundle — the `zip` packaging command in `README.md` excludes them.

## Manual Validation Scenarios

Use these scenarios to validate EKS Guardian in your Agent Space after uploading.

### Scenario 1: Single Cluster Basic Review

**Prompt:** "Review my EKS cluster `test-cluster` in `us-east-1`"

**Expected behavior:**
- Report artifact generated named `eks-review-test-cluster-<date>.md`
- All 12 best-practice sections present
- Scorecard with grades per section and overall
- Executive summary with health status, key metrics, top 3 actions
- Priority matrix with all findings sorted by severity

**Validate:**
- Findings match known cluster state (no hallucinated resources)
- Severity assignments are reasonable for the cluster's actual configuration
- Metrics in the report match CloudWatch data (spot-check 2-3 values)

### Scenario 2: Empty/Minimal Cluster

**Prompt:** "Review cluster `empty-dev`" (a cluster with only system pods)

**Expected behavior:**
- INFO findings for missing workloads (no deployments to assess)
- No false CRITICAL/HIGH findings for features that are unused
- Security findings still present (endpoint access, encryption, logging)
- Cost section notes low utilization rather than flagging "waste"

**Validate:**
- Skill doesn't generate findings about workloads that don't exist
- Grade reflects the cluster's actual minimal state fairly

### Scenario 3: Multi-Cluster Comparison

**Prompt:** "Compare clusters `dev` and `prod`"

**Expected behavior:**
- Individual report per cluster
- Comparison table showing grades side by side
- Drift detection section highlighting inconsistencies
- Fleet summary if 3+ clusters

**Validate:**
- Drift findings correctly identify config present in one env but not the other
- Comparison grades match individual report grades

### Scenario 4: Upgrade Readiness

**Prompt:** "Check upgrade readiness for `prod-cluster`" (cluster on N-2 version)

**Expected behavior:**
- Version currency finding (HIGH for N-2)
- Upgrade readiness playbook generated with cluster-specific steps
- Deprecated API usage flagged (if any)
- Add-on compatibility checked

**Validate:**
- Playbook reflects the actual cluster state (Karpenter steps if Karpenter present, etc.)
- EKS Upgrade Insights are included

### Scenario 5: Compliance Mapping

**Prompt:** "Run a CIS compliance check on `prod-cluster`"

**Expected behavior:**
- Compliance mapping section with pass/fail per CIS control
- Compliance percentage calculated
- Findings mapped to specific CIS Benchmark controls

**Validate:**
- Control mappings are accurate (cross-reference with CIS EKS Benchmark)
- Pass/fail status matches actual cluster configuration

### Scenario 6: Error Handling — Insufficient Permissions

**Setup:** Remove the EKS access entry for the Agent Space role on a test cluster.

**Prompt:** "Review cluster `restricted-cluster`"

**Expected behavior:**
- Graceful error message indicating insufficient K8s API access
- Fallback to AWS APIs only
- Report generated with available data
- Warning banners on sections with missing data

**Validate:**
- No crash or empty report
- Clear indication of what data is missing and why
- Actionable guidance to fix permissions

### Scenario 7: Error Handling — Unreachable Cluster

**Setup:** Private-only endpoint with no VPC connectivity configured.

**Prompt:** "Review cluster `private-only`"

**Expected behavior:**
- Graceful degradation — AWS API data collected successfully
- K8s API data noted as unavailable
- Report produced with reduced coverage
- Specific note about private endpoint connectivity

**Validate:**
- AWS-sourced data (cluster config, node groups, add-ons) is present
- K8s-sourced data (workloads, RBAC, NetworkPolicies) is missing with explanation

### Scenario 8: Large Cluster (Scalability)

**Prompt:** "Review cluster `large-prod`" (100+ nodes, 500+ pods)

**Expected behavior:**
- Report completes without timeout
- All sections populated
- Metrics accurate (not truncated or sampled)
- No duplicate findings

**Validate:**
- Execution completes within 30 minutes
- Node count, pod count in report match actual cluster
- Resource utilization percentages are plausible

## Validation Checklist

After each test scenario, verify:

- [ ] Report artifact is properly named (`eks-review-<cluster>-<date>.md`)
- [ ] Executive summary is present and accurate
- [ ] Scorecard grades are calculated correctly (100 - deductions)
- [ ] All findings have severity, current state, and recommendation
- [ ] Priority matrix contains all findings sorted correctly
- [ ] Next steps are categorized by timeframe (7d / 30d / 90d)
- [ ] No hallucinated resources or fabricated metrics
- [ ] Error cases degrade gracefully with clear messaging

## Regression Testing

When updating the skill (new version upload), re-run scenarios 1, 3, and 6 at minimum to verify:
- Basic functionality is preserved
- Multi-cluster features work
- Error handling hasn't regressed
