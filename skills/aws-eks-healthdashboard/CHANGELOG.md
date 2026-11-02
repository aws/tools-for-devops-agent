# Changelog

## 1.0.0

Close the metric-coverage gaps against the AWS [EKS essential metrics guide](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/best-practices-metrics-collection/),
adding only customer-accessible metrics (etcd server internals behind the managed `:2379` boundary
are documented as out of scope, not added):

- **Control plane — CP-M7/CP-M8/CP-M9** (API server `/metrics`): write-path/verb latency
  (`apiserver_request_duration_seconds` by verb), apiserver outbound-client errors (`rest_client_*`
  to aggregated APIs / webhooks), and watch pressure (`apiserver_registered_watchers`). CP-M is now
  CP-M1–CP-M9.
- **Node & data-plane — NH-P depth series** (kube-state-metrics / node-exporter / kubelet): NH-P1
  kubelet running pods, NH-P2 true allocatable headroom, NH-P6 `MemAvailable`, NH-P7 NIC-level
  errors, NH-P9 node `Ready=Unknown`, NH-P10 Failed-pod accumulation, NH-P11 PVC stuck Pending —
  each with a "distinct from" note vs the existing NH row it complements.
- **VPC CNI — NET series** (`cni-metrics-helper`, previously zero coverage): NET-P1 IP-address
  exhaustion, NET-P2 allocation error rate, NET-P3 stuck IPAMD — the most common silent
  scheduling-failure blind spot.
- **`metric-sources.md`:** added kube-state-metrics, prometheus-node-exporter, kubelet/cadvisor, and
  the VPC CNI metrics helper to the source matrix + detection logic, and a new §4.7 with the
  PromQL for each. An absent NH-P/NET source is ⚪ N/A **and** an observability-gap finding.
- **etcd observability boundary note** added to `control-plane-health.md`: the etcd-client view
  (CP1/CP2/CP-M1/CP-M5) is reachable; `etcd_server_*`/`etcd_disk_*`/`etcd_mvcc_*`/`etcd_network_peer_*`/
  `etcd_snap_*` on `:2379` are not, so they are intentionally excluded rather than rendered as N/A.
- Threshold rows + override keys for all new checks; FP11 extended to NH-P*/NET*; SKILL.md,
  report-format.md, and README updated (CP-M1–CP-M9, NH-P/NET sources, coverage-line examples).
- **Findings-analysis contract** added to `report-format.md` §7 (+ SKILL.md Step 5): the agent must
  *reason* each ❌/⚠️ finding from the observed evidence — implication, symptoms, ranked probable
  causes, cascade risk, confidence — using its own EKS knowledge, instead of reciting per-metric
  definitions. Thresholds, metric names, source routing, and the managed-EKS boundary stay
  hard-coded (never free-reasoned); meaning and causation are the agent's job at runtime. This
  fixes the uneven, one-liner findings seen in earlier runs without pre-defining metric semantics.
- **CP-M source-fallback rule** (`control-plane-health.md` + `metric-sources.md` §4.3 + SKILL.md
  Step 3): CloudWatch vends only a curated subset of the API server `/metrics`, so CP-M3/M5/M6/M8/M9
  were falsely marked ⚪ N/A in a test after checking CloudWatch only. The agent must now follow the
  order CloudWatch → **Prometheus/AMP (mandatory when detected)** → **raw API server `/metrics`
  (`use_kubectl get --raw /metrics`)** → N/A, and only N/A after all are attempted (citing the
  raw-`/metrics` RBAC/tool error if denied — never "not queried in this pass").
- **Always query Prometheus/AMP when present.** Source detection (§3) now also finds in-cluster
  Prometheus (kube-prometheus-stack) and treats AMP/Prometheus as **required** for every
  metric-native (CP-M / NH-P) check — it carries the full apiserver metric set (including the
  histograms CloudWatch omits). An empty Prometheus result for a metric that should exist is graded
  a **scrape-coverage gap** (histograms dropped / apiserver job not scraped), never a PASS, with an
  actionable pipeline recommendation (extend the ADOT/Prometheus scrape keep-list / scrape the
  `kubernetes-apiservers` job). A histogram check is not gauge-substituted to PASS.

## 1.3.0

Port the grading rigor from the `aws-eks-operations-review` control-plane pillar so the dashboard
grades PASS/FAIL/N/A with the same false-positive protection as the full review:

- **New `grading-guards.md`** — the false-positive controls (FP1–FP12), the empty-result rule, and
  the confidence contract, remapped to this skill's CA/CP/CP-M/CPM/NH check IDs. Kept local so the
  skill is self-contained (uploadable/zippable standalone), mirroring the review skill's canonical
  guards. FP11 (empty query / no-datapoint result is *unknown*, never an automatic PASS) and FP6 (a
  429 spike is not "scale the control plane") were previously unstated here. Wired into the CP/CP-M
  scorecards, node-health, report-format, and SKILL.md.
- **`control-plane-health.md`:** added per-row *Applicability / N/A predicate* and *Guards* columns
  to the CP1–CP11 and CP-M1–CP-M6 scorecards; added the missing **severity column to the CPM1–CPM3**
  manual/AWS-API table; wired the guards + confidence contract into "How to grade".
- **`queries.md`:** CP19–CP25 now carry an explicit **"When to run"** trigger — they are diagnostic,
  not scorecard rows, and must not be run unconditionally (each is a billable Logs Insights scan).
- **`node-health.md` / `report-format.md` / `SKILL.md`:** reference the guards file; detailed
  findings now record the applied guard ID + confidence level.

## 1.2.0

Close CloudWatch Logs Insights query gaps found against the EKS audit-log query cookbook (re:Post
"Retrieve control plane logs", EKS Auditing & Logging best practices, GuardDuty security guidance):

- **CP19 — denied / forbidden requests** (403 + authenticator "denied"): broken RBAC access or probing.
- **CP20 — slow mutating (write-path) requests**: create/update/patch/delete p99 latency (etcd apply /
  slow admission webhook) — complements the LIST-only latency in CP2–CP4.
- **CP21 — recent changes to core add-ons / DaemonSets** (kube-system): change-correlation for RCA.
- **CP22 — aws-auth / access mutations**: explains sudden cluster-wide auth breakage.
- **CP23 — WATCH request volume by user agent**: apiserver connection / watch-cache pressure.
- **CP24 — mutations by user (attribution)**: "who wrote to the API" for RCA/audit.
- **CP25 — anonymous / unauthenticated access**: critical security red flag (GuardDuty AnonymousAccessGranted).
- Added matching threshold lines (thresholds.md "additional diagnostics") and updated the query
  index + SKILL.md reference. CP1–CP18 remain the core set; CP19–CP25 are additional diagnostics.

## 1.1.1

- **CA14 — all installed add-ons & controllers Ready**, not just EKS managed add-ons (CA6) or the
  fixed core set (CA9). Enumerates every deployed controller/operator across kube-system and common
  add-on namespaces (AWS Load Balancer Controller, Karpenter, Cluster Autoscaler, metrics-server,
  cert-manager, ExternalDNS, Secrets Store CSI, Fluent Bit / CloudWatch agent, ADOT/OpenTelemetry,
  Node Monitoring Agent, GuardDuty agent, service mesh, GitOps, GPU/Neuron device plugins, self-
  managed CSI) and flags any that aren't fully Ready (CrashLoop/ImagePull/scaled-to-0/pending),
  labeling each managed vs self-managed. SKILL.md Step 2 and report-format §4 updated.

## 1.1.0

Add the Cluster / Version / Add-on health domain (AWS-side control-plane-object health that
kubectl and CloudWatch metrics don't show), sourced from AWS Knowledge MCP research:

- **New `cluster-addon-health.md` (CA1–CA13):** cluster `status` + `health.issues` (ClusterIssue
  codes), control-plane logging, Kubernetes version & **extended-support** state (standard vs
  extended, cost/auto-upgrade implications), EKS managed add-on health (`DEGRADED`/`CREATE_FAILED`/
  `UPDATE_FAILED` + `health.issues` codes like `InsufficientNumberOfReplicas`/`ConfigurationConflict`/
  `AccessDenied`), add-on version compatibility, core components actually running (CoreDNS/kube-proxy/
  VPC CNI/CSI), EKS Cluster Insights (upgrade/config/rollback), and Node Monitoring Agent enablement.
- **`node-health.md` extended:** Node Monitoring Agent conditions (NH29–NH33: ContainerRuntime/
  Networking/Storage/Kernel/AcceleratedHardware Ready) and a workload/pod health rollup (NH34–NH38:
  CrashLoopBackOff, ImagePullBackOff, Pending, OOMKilled, Warning events).
- **SKILL.md** now grades three domains (added Step 2 — cluster/version/add-on health) and reports
  Cluster Insights as CA10–CA12, never as `CP*`. **`report-format.md`** gains the Cluster/Version/
  Add-on scorecard section.

## 1.0.0

Initial release — a focused, read-only EKS health dashboard skill, factored out of the
`aws-eks-operations-review` skill's health-monitoring material.

- **Control Plane Health** (CP1–CP11 + metric-native CP-M1–CP-M6): etcd size/growth/write-
  concentration, APF throttling, API-server 5xx + LIST latency, KCM QPS, scheduler lag, eviction
  stalls. Reuses the control-plane reference set verbatim: `queries.md` (CP1–CP18 CloudWatch Logs
  Insights), `metric-sources.md` (source detection + per-source queries), `thresholds.md`,
  `procedures.md`, `control-plane-health.md`, `remediations-etcd.md` / `-apf.md` / `-apiserver.md`,
  and `alerting.md`.
- **New `node-health.md`** (NH-series): node conditions (kubectl), node & pod utilization
  (Container Insights), EC2 status, ENA network allowances, EBS volume performance, NAT gateway,
  CoreDNS, Karpenter controller, and AWS-side nodegroup / registration / AMI-age / auto-repair
  facts.
- **New `report-format.md`** — the two-domain health dashboard artifact (overall status, sources &
  coverage, Control Plane scorecard, Node & Data-Plane scorecard, detailed findings, recommended
  CloudWatch alarms, what-was-not-assessed).
- SKILL.md wires the workflow (confirm cluster → detect sources → grade CP → grade NH → dashboard),
  names the tools (`use_kubectl`, `use_aws`, `query_cloudwatch_logs`, `create_or_update_artifact`),
  and keeps the read-only contract. Frontmatter is `name` + `description` only (DevOps Agent upload
  compliance).
