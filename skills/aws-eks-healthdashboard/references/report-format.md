# Health dashboard — report format

The dashboard artifact is a point-in-time health snapshot, not a best-practices audit. It has three
graded sections — **Cluster/Version/Add-on Health**, **Control Plane Health**, and **Node &
Data-Plane Health** — plus a top-line status, the sources that contributed, and recommended alarms. Keep it factual: every status cites
the query/metric it came from; never guess.

Default filename: `eks-health-{cluster}-{date}.md` (Markdown). Render DOCX/PDF only if asked.

## Severity → status labels (customer-facing)

Grade with internal tiers, render descriptive labels (no Sev numbers in customer output):

| Internal tier | Dashboard status |
|---------------|------------------|
| critical | ❌ Action required — impaired |
| high | ❌ Action required — saturation/health risk |
| medium | ⚠️ Attention — operational hygiene |
| informational / ok | ✅ Healthy |
| (unobservable) | ⚪ N/A — <reason> |

## Sections (in order)

### 1. Header
Cluster name · ARN · account · region · Kubernetes version + support status · timestamp (UTC).

### 2. Overall health
One line per domain plus a rolled-up status (`ok` < `attention` < `action_required`, worst wins):

| Domain | Status | Headline |
|--------|--------|----------|
| Cluster / version / add-ons | ✅/⚠️/❌ | e.g. "ACTIVE, no health issues; v1.30 in **extended support** (plan upgrade); vpc-cni DEGRADED" |
| Control Plane | ✅/⚠️/❌ | e.g. "etcd 78% of 8 GB quota, +9% / 7d; APF/API healthy" |
| Nodes & data plane | ✅/⚠️/❌ | e.g. "9/9 Ready; node CPU 41%; 1 volume low on burst balance; 0 CrashLoop" |

### 3. Observability Sources & coverage
Which observability sources contributed (`sources_detected`) and which were missing
(`sources_missing`), per [`metric-sources.md`](metric-sources.md) §3, with the per-signal
`confidence` (high/medium/low) from cross-validation. If control-plane logging is off or Container
Insights is absent, say so here and mark the dependent checks ⚪ N/A — do not silently drop them.

### 4. Cluster, Version & Add-on Health scorecard
Every **CA1–CA13** check from [`cluster-addon-health.md`](cluster-addon-health.md), each ✅/⚠️/❌/⚪
with observed value: cluster status + `health.issues`, control-plane logging, Kubernetes version &
**extended-support** state (call out the version, `supportType`, and days left in the current
period), managed add-on status + `health.issues` + version compatibility, core components running, **every
other installed add-on/controller** (self-managed/Helm/third-party) Ready (CA14), EKS Cluster
Insights (upgrade/config/rollback), and Node Monitoring Agent enablement. **Cluster
Insights are reported here (CA10–CA12), never relabeled as `CP*`.**

### 5. Control Plane Health scorecard
Every **CP1–CP11** check (etcd / APF / API-server / KCM / scheduler / eviction) and the
**CP-M1–CP-M9** metric-native checks (adds CP-M7 write-path/verb latency, CP-M8 apiserver outbound
client errors, CP-M9 watch pressure), each ✅/⚠️/❌/⚪ with the observed value, threshold, and
evidence (query ID from [`queries.md`](queries.md) or the metric name). Grade against
[`thresholds.md`](thresholds.md) using [`procedures.md`](procedures.md); definitions in
[`control-plane-health.md`](control-plane-health.md).
**CP checks are CP1–CP11** (from CloudWatch) — never relabel Cluster-Insights / upgrade items as `CP*`.
etcd server internals (`etcd_server_*`/`etcd_disk_*`/`etcd_mvcc_*`/etc.) are out of scope on managed
EKS — see the etcd observability boundary in [`control-plane-health.md`](control-plane-health.md).

### 6. Node & Data-Plane Health scorecard
Every **NH-series** check from [`node-health.md`](node-health.md), grouped by source (node
conditions, node util, pod util, EC2, ENA, EBS, NAT, CoreDNS, Karpenter, AWS-side node facts),
the **NH-P depth checks** (NH-P1/P2/P6/P7/P9/P10/P11 — kubelet running pods, true allocatable
headroom, `MemAvailable`, NIC errors, node `Ready=Unknown`, Failed-pod accumulation, PVC Pending),
and the **NET series** (NET-P1/P2/P3 — VPC CNI IP exhaustion / allocation errors / stuck IPAMD),
each ✅/⚠️/❌/⚪ with observed value + threshold. NH-P/NET checks whose source (KSM / node-exporter /
cni-metrics-helper) is absent are ⚪ N/A with the missing-source reason, listed in §9.

### 7. Detailed findings
One block per ❌/⚠️ (worst first): current state (quoted metric/kubectl/query value), impact,
and a **read-only remediation recommendation** with an authoritative AWS link. For control-plane
findings pull the playbook from `remediations-etcd.md` / `remediations-apf.md` /
`remediations-apiserver.md`; for node findings use the pointers in `node-health.md`.
State a **confidence** level (high/medium/low) per the confidence contract, and when a grading
guard was applied to reach the verdict, cite its ID (e.g. "graded ⚠️ not ❌ — FP6: low-tier 429s,
APF working as designed"). See [`grading-guards.md`](grading-guards.md).

#### Findings-analysis contract (reason; don't recite)

The check tables give you thresholds, metric names, and a one-line "why it matters" — they do **not**
give you the full implication of each finding, and they are not meant to. For every ❌/⚠️ finding
(and any ⚪ N/A that hides a real risk), **reason from the observed evidence using your own EKS
knowledge** and write a short, specific analysis with these facets:

- **What it means / what breaks** — the concrete failure this signal represents for *this* cluster, not a generic definition.
- **Symptoms to expect** — what the operator would observe elsewhere (kubectl behavior, app latency, deploy/HPA stalls, pod states) if this continues.
- **Probable causes, ranked** — the most likely root causes given the surrounding evidence (recent deploys, correlated checks, workload mix), most-likely first.
- **Cascade risk** — what this leads to if unaddressed, and which other checks it would trip next (cite the related CP/CP-M/NH/NET IDs).
- **Confidence + evidence** — the confidence level and the exact value/query/metric it rests on.

Rules for this analysis:

- **Ground every causal claim in observed evidence.** Correlate with the other checks in this run and the customer's recent changes; say "consistent with" / "likely" for inferences, and reserve definite language for what a query or metric actually confirmed. Correlation is not root cause (confidence contract).
- **Never invent numbers or metric names.** Thresholds, metric names, source routing, and the managed-EKS accessibility boundary come only from the reference files — do not free-reason those. Reason about *meaning and causation*; quote *values* verbatim.
- **Tailor depth to severity and evidence.** A critical finding with rich evidence gets a full multi-cause analysis; a thin-evidence ⚠️ gets a proportionate note plus what to collect next. Do not pad, and do not flatten every finding to one line — uneven, one-liner findings are a known failure mode.
- This is intentionally **not** a per-metric lookup table: the skill defines *what* to measure and *how* to grade; the reasoned implication/RCA is the agent's job at runtime.

### 8. Recommended CloudWatch alarms
The base + conditional alarm table (node/pod/EC2/EKS-control-plane/NAT, plus Karpenter/CoreDNS/ENA
when detected) with threshold · period · datapoints, marking which already exist vs are missing.
Source the set from `metrics` guidance; every alarm is customer-creatable.

### 9. What was not assessed
Every ⚪ N/A with the real reason (source unavailable, add-on absent, Fargate-only) + the follow-up
to enable it (e.g., enable control-plane logging, install the CloudWatch Observability add-on).

## Artifact element types

`create_or_update_artifact` renders a fixed set of element types. **Only four are supported:**

| Type | Use for |
|------|---------|
| `text` | Markdown-formatted text blocks — **headings, prose, and pipe tables all render inside this one type**. |
| `chart` | Line/bar charts for metrics or trends (requires the chart element's exact data schema). |
| `table` | Interactive/sortable tabular data (requires the table element's exact columns/rows schema). |
| `topology` | Resource-relationship diagrams. |

Deliver the entire dashboard as **a single `text` element** containing the Markdown below. Because
`text` is Markdown, the `##`/`###` section headers and the `|...|` scorecard tables render natively
inside it — do not split them into separate elements.

- **Never emit a `section` element.** It is not a supported type; the viewer logs *"Unknown artifact
  element type: section"* and drops the content. Use Markdown headings (`##`, `###`) for structure.
- **Do not hand-roll `table` elements for the scorecards.** Keep scorecards as Markdown pipe tables
  inside the `text` element. Only use a standalone `table`/`chart`/`topology` element when you
  deliberately want that interactive widget *and* populate its exact required schema — a malformed
  one triggers the same *"Unknown artifact element type"* error.

## Rules

- **Read-only.** Findings are recommendations; never mutate the cluster, node groups, or config.
- **Never echo Secret values.** Reference resources by name.
- Every status cites its query ID or metric name; a check with no data source is ⚪ N/A **with the
  reason**, never omitted and never "pending."
- Use the descriptive status labels above — no internal severity numbers in customer-facing output.
- **One `text` artifact element**, Markdown only — no `section` elements (see *Artifact element types*).
