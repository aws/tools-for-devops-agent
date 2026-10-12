# Report format — EKS final Markdown response

The review is delivered directly in the final AWS DevOps Agent response. Do not create or claim to save a Markdown, JSON, checkpoint, or sidecar file.

## Transport

Two delivery surfaces are permitted, and the section contract below is identical on both.

- **In-conversation Markdown (default).** One complete message containing every section.
- **Cumulative artifact,** where the runtime provides one. Exactly one artifact per review run. It may be assembled by ordered appends — creating it with the first group of elements and adding the rest in later calls — because a single oversized call times out. The appends are transport: the artifact's **final state must contain every mandatory section**, in order, and is the deliverable. Intermediate versions are expected and are not "parts."

Under either surface: never spread one review across two messages or two artifacts, never present the review as a numbered series the reader must reassemble, and never report a run complete while the final state is missing sections. Do not create inventory, checkpoint, or sidecar files on any surface.

**This file is authoritative for EKS delivery.** It may borrow the shared `operations-review-report-format` skill's visual conventions (severity tiers, finding-block shape, scorecard columns), but that skill never overrides the section set, the section order, or the delivery mechanics defined here. Where the two disagree — including any instruction to write a report file to an output location, name a file, or build the report across multiple messages — this file wins. Never consult the shared skill for whether to save a file.

## EKS adapter contract

| Variable | EKS value |
|---|---|
| Service/resource | EKS cluster (cluster name / ARN) |
| Units | Nine pillars plus AWS-API & Cluster Insights; fired cross-cutting checklists |
| ID schemes | Op/OpM, R/RM, S/SM, Sc/ScM, P/PM, O/OM, N/NM, A/AM, CP/CP-M/CPM, AX, and conditional U/W/H/M |
| Alarm source | `metrics-thresholds.md` |
| Remediation source | FAIL-only mappings in `remediations/index.md` and the mapped remediation references |
| Delivery | Complete Markdown rendered in the final response after S7 QA PASS |

## Mandatory response sections

All eight sections plus the header are required in this order. Nothing may be omitted, renamed, reordered, folded into another section, or deferred to a follow-up message — not for a single-pillar review, not under context pressure. A section with nothing to report still appears with an explicit `None` line and the reason.

1. **Executive summary** — posture, descriptive-severity counts, PASS/FAIL/N/A totals, and one line per selected unit.
2. **Cluster snapshot** — identity, version/support, footprint, workload health, detected tooling, and 7-day telemetry when collected.
3. **Prioritized action plan** — every FAIL ordered Critical → High → Medium → Low.
4. **Detailed findings** — one evidence-backed block per FAIL.
5. **Scorecards** — every selected canonical ID with PASS/FAIL/N/A and bounded evidence.
6. **Recommended alarms** — required for IDR/CWR; mark existing versus missing.
7. **What was not assessed** — all N/A IDs and exact source/access reasons.
8. **Appendix** — scope, discovery coverage, source attempts, conditional gates, reference-load audit, and QA reconciliation.

Sections 1–7 carry the review. Section 8 is internal bookkeeping: a delivered review consisting of a load audit, a QA reconciliation, a coverage-metadata table, or any combination of those without sections 1–7 is invalid, not merely short — this is the single most common render failure. Assemble top-down in report order; never lead with the appendix and backfill.

## Render skeleton

Reproduce this heading set verbatim, in order:

```text
# EKS Operations Review — {cluster name / ARN}
Account / Region: {…}   Environment: {prod | non-prod}   Scope: {all namespaces | namespace X}
Pillars graded: {list}   Cross-cutting: {upgrade / windows / hybrid / aiml, if fired}
Discovery window: {UTC range}   Context source: {DevOps Agent topology/investigations summary}

## 1. Executive summary
## 2. Cluster snapshot
## 3. Prioritized action plan
## 4. Detailed findings
## 5. Scorecards
## 6. Recommended alarms
## 7. What was not assessed
## 8. Appendix
```

Minimum substance per section: §1 is 2–4 sentences plus the severity and PASS/FAIL/N/A count lines plus one line per graded unit; §2 populates the snapshot fields below; §3 has exactly one row per FAIL; §4 has exactly one block per FAIL; §5 has one table per graded unit whose rows equal that unit's selected IDs; §6 lists alarms with existing/missing status or one explicit skipped line; §7 lists every N/A ID; §8 holds the audit, gates, and QA PASS.

## Severity model

Use descriptive customer-facing tiers only:

| Tier | EKS examples |
|---|---|
| Critical | Public endpoint broadly exposed; anonymous access; non-system cluster-admin; imminent removed-API upgrade blocker; outage-level single failure domain. |
| High | Missing production availability controls; privileged workloads; no network isolation; competing autoscalers; sustained critical control-plane pressure. |
| Medium | Governance, topology, right-sizing, or hardening gaps with bounded current impact. |
| Low | Optimization opportunities such as adoption, tagging, or tuning without present impairment. |

Healthy/non-actionable signals are informational, not findings. Adjust baseline severity only using observed blast radius.
## Cluster snapshot fields

Include Kubernetes version/support type, platform version, node count and OS/accelerator/hybrid breakdown, AZ spread, namespace/pod/workload/service counts, CNI configuration, autoscaling, mesh, GitOps, ingress/gateway, observability, security tooling, storage, and pending/crashloop/imagepull/OOM counts. When collected, include 7-day node/pod CPU and memory average/max, filesystem pressure, failed-node count, and restart trends.

## Detailed finding block

For every FAIL include:

- Check ID, title, pillar, and descriptive severity.
- Quoted observed value with source and time window.
- A severity rationale tied to this cluster's blast radius.
- Customer impact.
- Detailed human-approved remediation from the mapped reference.
- Authoritative AWS or Kubernetes links.
- Stable fingerprint and canonical resource ID in the compact appendix data.

Do not expose internal tools, employee aliases, or unsupported internal evidence. If evidence is insufficient, use N/A rather than a finding.

## CloudWatch data and alarms

Historical telemetry must be visible in the snapshot, applicable scorecard rows, and findings. If unavailable, state the source failure once in "What was not assessed" and keep dependent rows N/A.

For IDR/CWR, populate alarms from `metrics-thresholds.md` with namespace, threshold, period, datapoints, and existing/missing status. Skip the alarms section only for a plain best-practices audit.

## EKS coverage gate

Before rendering the response, confirm:

- All eight mandatory sections plus the header are present, in order, and non-empty; §3 row count and §4 block count each equal the FAIL count; §5 row count equals the selected ID count.
- All 49 discovery areas have exactly one status.
- A full review includes all **288 core rows**: Operations 41, Resilience 26, Security 46, Scalability 30, Performance 19, Observability 26, Networking 33, Cost 33, Control Plane 20, AWS API 14.
- Cost is A1–A26 + AM1–AM7. Control Plane is CP1–CP11 + CP-M1–CP-M6 + CPM1–CPM3. CP1–CP25 query IDs do not become rows; Cluster Insights is AX1.
- All nine pillars are graded for a full review, including mandatory Control Plane Health and Networking.
- Each selected unit's non-kubectl source attempts are represented.
- Every conditional checklist has either its complete expected rows or an explicit false-gate line.
- Every FAIL has a complete mapped finding block.
- The common-check crosswalk and recommended alarms are complete when applicable.
- S7 QA is PASS.

## Source links

Prefer curated links already present in canonical pillar/remediation references, then the [EKS Best Practices Guide](https://docs.aws.amazon.com/eks/latest/best-practices/), then Kubernetes upstream documentation for Kubernetes-native concepts. Never invent a URL.