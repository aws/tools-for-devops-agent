# EKS operations review operator guides

Consolidated human/operator background. Runtime authority remains in `../runtime/`, `../pillars/`, and the canonical root references; load only the relevant anchored section for an explicit operator question.

<a id="pillar-router-map"></a>

## Pillar router map (compatibility reference)

> Runtime routing, cluster gates, and scorecard identity are authoritative in `../runtime/router.md`, `../runtime/cluster-gates.md`, and `../runtime/check-manifest.md`. This document is for human browsing only; do not load it during normal runtime.

## Contents

- Router (pillar → discovery areas → data sources)
- What the AWS-API component adds over kubectl
- How to run a review
- Complete check inventory — grade EVERY ID (authoritative)
- Cross-cutting checklists (not pillars)
- Auto Mode handling (skip / N/A these checks)
- Cluster-type detection gates
- Discovery scale tiers
- Per-command robustness
- What kubectl discovery adds over the other sources

Discovery runs **once** (all 49 areas) and produces one bounded in-context inventory. Runtime selection uses [`../runtime/router.md`](../runtime/router.md); this document is a human compatibility view and is not runtime authority.

The kubectl discovery is the primary data source for an EKS review; the control-plane-health component adds a CloudWatch-based source for the Control Plane Health pillar; the AWS-API component adds an EKS/EC2/IAM + Cluster Insights source for facts kubectl can't see:

| Data source | How it sees the cluster |
|-------------|-------------------------|
| AWS-API & Cluster Insights component (`aws-api-checks.md`, AX-series) | EKS / EC2 / IAM describe calls + EKS Cluster Insights — access entries, nodegroup/addon health, Pod Identity, IAM, per-subnet IPs, node-join failures |
| Control-plane audit logs / metrics | CloudWatch — drives the **Control Plane Health** pillar (`pillars/control-plane.md` → `control-plane-health/`) |
| CloudWatch workload/node metrics + logs + CloudTrail | CloudWatch Container Insights + `AWS/EKS`/`AWS/EC2` + CloudTrail — feeds the **Observability / Performance / Cost / data-plane Resilience** pillars via `metrics-thresholds.md` (when Container Insights / control-plane logging is enabled) |
| **kubectl discovery (this skill)** | **live in-cluster state** |

## Router

| Pillar / component | File | Discovery areas | Key inventory signals | Other data sources (MUST also collect + grade) |
|--------|-------------|-----------------|----------------------|----------------------|
| Operations | `pillars/operations.md` | 1, 2, 16, 27, 28, 33, 44 | K8s/node version, addon presence, managed-vs-self-managed, Karpenter/CAS hygiene, CronJob schedules, SA hygiene | AWS-API (`aws-api-checks.md`): version support / Cluster Insights (AX1), addon + nodegroup health (AX4/AX5), deletion protection, control-plane logging (AX10) |
| Resilience & HA | `pillars/resilience.md` | 4, 5, 7, 14, 35, 36 | replicas, probe coverage, `pdb`/`workloads_without_pdb`/`pdb_blocking`, topology spread + `minDomains`, `rollout_maxunavail_risky`, singletons, `single_az_nodes`, EBS AZ alignment | CloudWatch (`metrics-thresholds.md`): 7-day node/pod health, container restarts, `StatusCheckFailed` (data-plane half of resilience) |
| Security | `pillars/security.md` | 21, 22, 24, 34, 39, 42, 43, 46 | `privileged_pods`, `privilege_escalation_allowed`, `hostnetwork/pid/ipc_pods`, `hostpath_pods`, `capabilities_not_dropped`, `seccomp_not_runtimedefault`, `readonly_rootfs_*`, `runasnonroot_true`, PSS labels, `features.security.*`, cluster-admin/wildcard RBAC, NetworkPolicy default-deny, webhook failurePolicy, `:latest` images | AWS-API (`aws-api-checks.md`): endpoint exposure (AX12), KMS encryption (AX11), auth mode (AX3), control-plane logging (AX10) |
| Scalability | `pillars/scalability.md` | 2, 8, 9, 18, 24, 26, 27, 37, 41 | size vs K8s thresholds, services-per-namespace, EndpointSlices, `secrets` vs 10k, webhooks-per-resource, CoreDNS scaling, instance diversity, T-series avoidance, DaemonSet rollout safety, PriorityClass, dedicated cluster-services capacity | CloudWatch (`metrics-thresholds.md`): API request/pending-pod metrics; AWS-API: nodegroup/NodePool limits |
| Performance Efficiency | `pillars/performance.md` | 4, 5, 11, 12, 13, 35, 36, 47 | requests/limits coverage, HPA/VPA/KEDA coverage, `qos_*`, ResourceQuota/LimitRange, Graviton, instance fit | CloudWatch (`metrics-thresholds.md`): usage-vs-requests right-sizing (PM1–PM3), EBS performance (P13); Compute Optimizer AWS-API (P12) |
| Observability | `pillars/observability.md` | 7, 19, 29 | `features.observability.*`, warning events, `pods_oomkilled`/`pods_crashloop`/`pods_imagepull` | CloudWatch (`metrics-thresholds.md`): 7-day signals (O12–O16), conditional telemetry/alarm coverage (O17–O20); **`cloudwatch.describeAlarms` → recommended-alarm coverage (O21) + the Recommended Alarms table for IDR/CWR** |
| Networking | `pillars/networking.md` | 8, 10, 25, 26, 41 | `features.cni.*` + `features.cni_config.*` (prefix delegation, custom networking, SG-for-pods, IPv6, SNAT), kube-proxy mode, LB controller + target-type, CoreDNS scaling, NodeLocal DNS, IP-exhaustion signals | AWS-API (`aws-api-checks.md`): per-subnet IP availability (AX7), LB-controller IAM (AX9), target-group health; CloudWatch (`metrics-thresholds.md`): ENA/DNS + NAT allowance (N21/N22) |
| Cost / Sustainability / Architectural | `pillars/cost-architecture.md` | 4, 5, 8, 10, 11, 12, 13, 20, 23, 28, 29, 32, 36, 47 | `spot_nodes`, Graviton, gp2→gp3, unused PVCs, cost tooling, HPA/VPA right-sizing, blocking-PDB scale-down leaks, EFS/instance-store, ingress consolidation, topology-aware routing, cross-AZ, telemetry cost | CloudWatch (`metrics-thresholds.md`): utilization / right-sizing / cross-AZ transfer; Compute Optimizer (AWS-API) |
| Control Plane Health | `pillars/control-plane.md` | — (CloudWatch, not kubectl) | etcd size/growth/write-concentration, APF 429s in `system`/`leader-election`, API 5xx + LIST latency, KCM QPS, scheduler/eviction backpressure, capacity mode. **MANDATORY for every operations review / CWR — always attempt CloudWatch logs + metrics collection; never skip or blanket-N/A.** | `control-plane-health/` (queries.md CP1–CP18 via `logs:StartQuery`; metric-sources/thresholds/procedures/remediations/alerting) + control-plane metrics (`GetMetricData`); Prometheus (AMP / in-cluster) or Datadog/New Relic/Dynatrace/Splunk connectors when present |
| AWS-API & Cluster Insights | `aws-api-checks.md` | — (EKS/EC2/IAM + Cluster Insights, not kubectl) | failing Cluster Insights, access entries w/o policy, auth mode, nodegroup/addon health + upgrade conflicts, unregistered EC2 instances, Pod Identity associations, controller IAM, per-subnet IP availability, control-plane logging/KMS/endpoint | — (this component IS the AWS-API source; run for any operations review / CWR when AWS-API access is available) |

> **The last column is not optional.** Every pillar's non-kubectl data (CloudWatch metrics/logs via `metrics-thresholds.md`, AWS-API facts via `aws-api-checks.md`, control-plane data via `control-plane-health/`) MUST be collected and graded alongside the kubectl areas. Scoping a pillar to its kubectl slice alone is the failure mode that drops the CloudWatch/alarms half of Observability, the metrics half of Performance/Cost/Resilience, and the AWS-side Networking facts. A check whose data source was genuinely unavailable is ⚪ N/A with the real reason — never silently omitted.

## What the AWS-API component adds over kubectl

The AWS-API & Cluster Insights component (`aws-api-checks.md`, AX-series) grades the layer kubectl and CloudWatch logs can't see — promoting the old "AWS-API follow-up" N/A rows to graded checks:

- **EKS Cluster Insights** (AX1) — the authoritative AWS upgrade-readiness + misconfiguration signal.
- **Access entries with no policy / auth mode** (AX2/AX3) — the silent-lockout class kubectl can't observe.
- **Nodegroup health + node-join failures** (AX4/AX8) — `CREATE_FAILED`, stuck rolling updates, bootstrap/AMI conflicts, and EC2 instances that launch but never register.
- **Managed addon health + upgrade conflicts** (AX5) — CoreDNS/VPC-CNI addon-upgrade failures and ConfigMap conflicts.
- **Pod Identity + controller IAM** (AX6/AX9) — agent presence, association status, and the LBC `elasticloadbalancing:*` permission gap.
- **Per-subnet IP availability** (AX7) — quantifies IP exhaustion kubectl can only infer.
- **Control-plane logging / KMS / endpoint exposure** (AX10/AX11/AX12) — confirm Security/Control-Plane N/A rows.

Run it for any "operations review" / CWR, or when the user asks about these AWS-side facts, **if AWS-API access is available**. Otherwise its checks stay N/A and are flagged for follow-up. See the full finding→check map in `aws-api-checks.md`.

## How to run a review

1. Discover once (`kubectl-discovery-commands.md` + `kubectl-discovery-commands-deep-dive.md`), assemble the inventory (`inventory-schema.md`).
2. For each requested pillar, read its `pillars/<pillar>.md` and grade its checks against the inventory + area detail.
3. AWS-side facts (Cluster Insights, access entries, nodegroup/addon health, Pod Identity, controller IAM, per-subnet IPs, control-plane logging/KMS/endpoint) are graded by the **AWS-API & Cluster Insights component** (`aws-api-checks.md`, AX-series) when AWS-API access is available. In kubectl-only mode the pillar files mark those checks `N/A` / manual and flag them for AWS-API follow-up — don't default them to PASS or FAIL.
4. Control-plane saturation (etcd/APF/API latency) is graded by the **Control Plane Health** pillar (`pillars/control-plane.md`), which reads CloudWatch via the `control-plane-health/` component rather than kubectl. **This pillar is mandatory for an operations review / CWR — always attempt the CP1–CP18 Logs Insights queries (when logging is enabled) plus control-plane metrics, and grade from metrics / Prometheus / connectors even when logging is off. Mark a check N/A only after attempting and finding no source for that signal — never defer with "pending query."**

## Complete check inventory — compatibility view

This table mirrors [`../runtime/check-manifest.md`](../runtime/check-manifest.md), which is authoritative for exact scorecard membership and counts. For an operations review / CWR, every selected ID appears as PASS / FAIL / N/A, including manual rows.

| Pillar / component | Check IDs (all required) | Count | Source |
|--------------------|--------------------------|-------|--------|
| Operations | Op1–Op32, OpM1–OpM9 | 41 | `pillars/operations.md` |
| Resilience & HA | R1–R22, RM1–RM4 | 26 | `pillars/resilience.md` |
| Security | S1–S39, SM1–SM7 | 46 | `pillars/security.md` |
| Scalability | Sc1–Sc23, ScM1–ScM7 | 30 | `pillars/scalability.md` |
| Performance Efficiency | P1–P16, PM1–PM3 | 19 | `pillars/performance.md` |
| Observability | O1–O22, OM1–OM4 | 26 | `pillars/observability.md` |
| Networking | N1–N26, NM1–NM7 | 33 | `pillars/networking.md` |
| Cost / Sustainability / Architectural | A1–A26, AM1–AM7 | 33 | `pillars/cost-architecture.md` |
| Control Plane Health | CP1–CP11, CP-M1–CP-M6, CPM1–CPM3 | 20 | `pillars/control-plane.md` (CloudWatch) |
| AWS-API & Cluster Insights | AX1–AX14 | 14 | `aws-api-checks.md` |
| **Core total (all 9 pillars + AX)** | | **288** | |

**Conditional checklists — grade in full only when their gate fires; otherwise one explicit `N/A — no <x>` line:**

| Checklist | Check IDs | Count | Gate |
|-----------|-----------|-------|------|
| Upgrade readiness | U1–U24 (incl. U5b/U5c/U5d), UM1–UM8 | 35 | pre-upgrade / pre-migration ask, or Extended-Support version |
| Windows workloads | W1–W18 | 18 | `windows_nodes > 0` |
| Hybrid nodes | H1–H12 | 12 | `hybrid_nodes > 0` |
| AI/ML workloads | M1–M16 | 16 | `gpu_nodes > 0` or `neuron_nodes > 0` |

**Critical ID-integrity rules:**
- **Cost checks are the `A`-series (A1–A26) + `AM1–AM7`** — *not* `C1/C2/…`. Never relabel them `C*`.
- **Control Plane checks are `CP1–CP11` + `CP-M1–CP-M6` (metric-native) + `CPM1–CPM3` (manual).** `CP1–CP25` in the four staged files under `control-plane-health/` are Logs Insights *query IDs*, not check IDs. Never substitute AX-series for CP; Cluster Insights is AX1.
- Each pillar file's manual (`OpM/RM/SM/ScM/PM/OM/NM/AM/CPM`) rows are real checks; in kubectl-only mode they are ⚪ N/A with a reason, but they still appear in the scorecard.

## Cross-cutting checklists (not pillars)

Some reviews span multiple pillars. Load these in addition to (or instead of) pillar files when the request matches:

| Checklist | File | Use when |
|-----------|------|----------|
| Upgrade readiness | `../upgrade-readiness.md` | "ready to upgrade?", pre-upgrade / pre-migration check. Pulls from Operations + Resilience + Scalability + AWS-API. Load [`../k8s-deprecated-apis.md`](../k8s-deprecated-apis.md) alongside for U5/U5b–U5d. |
| Windows workloads | `windows-workloads.md` | **only when the cluster has Windows nodes** (`windows_nodes > 0`). Windows-specific scheduling, memory (no OOM killer), single-ENI IP model, security, ops. Run alongside the pillars. |
| Hybrid nodes | `hybrid-nodes.md` | **only when the cluster has hybrid (on-prem/edge) nodes** (`hybrid_nodes > 0`). Network-disconnection resilience, pod failover, zone labels, host credentials. Run alongside the pillars. |
| AI/ML workloads | `aiml-workloads.md` | **only when the cluster runs accelerated workloads** (`gpu_nodes > 0` or `neuron_nodes > 0`). Device plugin, accelerator scheduling/isolation, GPU sharing, training resilience, EFA, model storage, GPU observability. Run alongside the pillars. |

## Auto Mode handling (skip / N/A these checks)

EKS **Auto Mode** manages the data plane, core networking, and several add-ons, so a number of checks misgrade an Auto Mode cluster (they flag AWS-managed defaults as "missing"). When discovery shows Auto Mode (`compute-type=auto` nodes / `features.autoscaling.eks_auto_mode`), mark these **N/A — managed by Auto Mode** rather than FAIL:

| Check(s) | Why N/A on Auto Mode |
|----------|----------------------|
| All Karpenter checks (Op10–Op13, Op20–Op22, Op27, Op28) | Auto Mode runs its own managed node provisioner — self-managed Karpenter shouldn't exist. |
| Op18 single-autoscaler / Op19 metrics-server, Op9/Op24 CAS | No self-managed autoscaler on Auto Mode; only flag leftover duplicates (Op17). |
| S28 (IMDSv2) / IRSA (S13 node-role path) | Node config + Pod Identity Agent are AWS-managed; node IAM uses the minimal managed policy. |
| Networking N2 (CNI version), N6 (WARM tuning), N9 (kube-proxy mode), N14 (LB target-type — managed LBC) | CNI / kube-proxy / LB wiring is AWS-managed. |
| Sc21 (cluster services on dedicated capacity) | Cluster-services capacity is AWS-managed on Auto Mode. |
| Resilience R15 kubelet-reserved, Security S24 container-OS, S25 node access | Node OS / kubelet / access are AWS-managed. |
| Upgrade U8 (managed nodes), U15 AL2 AMI | Auto Mode handles node AMIs/upgrades. |

Always still grade workload-level checks (probes, PDBs, topology spread, requests/limits, RBAC, NetworkPolicy, image hygiene) — those are the customer's responsibility regardless of Auto Mode. State explicitly in the report that a check was N/A because Auto Mode owns it, so the reader sees full coverage.

## Cluster-type detection gates (detect early, branch grading)

Beyond Auto Mode, several cluster shapes change which checks apply. **Detect these during discovery (Step 4) and branch** — grading the wrong checks against them produces false findings. Each gate marks a group of checks **N/A with a positive reason**, never silently dropped.

| Gate | Detect via | Effect on grading |
|------|-----------|-------------------|
| **EKS Anywhere / non-cloud** | node label `eks.amazonaws.com/compute-type` absent + `eksctl.io`/anywhere labels; no EKS control-plane AWS-API response | Mark the **entire AWS-API component (AX1–AX14)** and CloudWatch pillars **N/A ("EKS Anywhere — no AWS control-plane API")**. VPC CNI may be absent (see non-VPC-CNI gate). Grade the in-cluster pillars normally. |
| **IPv6-only cluster** | `features.cni_config.ipv6_cluster = true` | Mark IPv4-specific checks **N/A with a positive note**: N3 (IP exhaustion), N4 (prefix delegation — always on for IPv6), N5 (custom networking), N6 (WARM tuning), N8 (CNI metrics helper), **AX7** (per-subnet IPv4 availability), Sc11 pod-IP framing. Note IPv6 removes the RFC1918 exhaustion class. |
| **Fargate-only cluster** | no nodes / only `fargate` virtual nodes; no managed/self-managed nodegroups | Auto-**N/A the node-level checks**: kube-proxy mode (N9), CNI DaemonSet health specifics (N1 nuance), node OS/access (S24/S25/S28), kubelet-reserved (R15), node monitoring/repair + AMIs (Op8/Op26/Op29), Karpenter/CAS autoscaler checks (Op9–Op13, Op20–Op24, Op27, Op28), instance strategy (Sc4/Sc5/Sc11/Sc22), Graviton nodes (P9). Grade workload/security/observability checks normally (Op14–Op17 workload ops still apply). |
| **Non-VPC-CNI (Cilium/Calico)** | `cilium`/`calico-node` DaemonSet present, no `aws-node` | Mark **N1–N8 N/A ("uses `<CNI>`, not VPC CNI")**; grade S15 against the CNI's own policy CRDs (`CiliumNetworkPolicy`/Calico `GlobalNetworkPolicy`). See Networking currency-framing. |
| **Mixed Windows + Linux** | `windows_nodes > 0` alongside Linux | Auto-load `windows-workloads.md`. **Skip Linux-only pod checks on Windows pods** (by `nodeSelector`/`kubernetes.io/os=windows`): S5 seccomp, S6 readOnlyRootFilesystem, S7 non-root user, S4 drop-capabilities — they misfire on Windows. Grade them only on Linux pods. |

## Discovery scale tiers (protect the API server)

Discovery itself is the main API-server pressure risk on large clusters. Pick a strategy by size **before** the sweep (see also scaling guidance in [`kubectl-scaling-guidance.md`](kubectl-scaling-guidance.md)):

| Tier | Size | Strategy |
|------|------|----------|
| Small | < 100 nodes | Full sweep of all 49 areas. |
| Medium | 100–500 nodes | Full sweep, **sequential** (no parallel `-A -o json` storms). |
| Large | 500–2000 nodes | **Sample namespaces** + aggregate counts; avoid `kubectl get pods -A -o json` cluster-wide; prefer `-o custom-columns`/metadata. |
| XL | 2000+ nodes | Sample + lean heavily on CloudWatch/metrics for fleet-wide signals; per-namespace scoping only; never a full `-A -o json`. |

## Per-command robustness (don't let one area sink the run)

- **Timeout / partial failure:** if a single area's `kubectl` (via `use_kubectl`) times out or errors, record that area **N/A with the error** and continue — never abort the whole review.
- **Admission webhook blocking reads:** a `ValidatingWebhookConfiguration` with `failurePolicy: Fail` intercepting `GET`/`LIST` can 403/stall discovery. If an area returns 403 or hangs, mark it N/A ("blocked by admission webhook — see S16/S17"), note it as a finding, and move on.
- **Events correlation:** when grading pod/rollout failures, pull `kubectl get events --field-selector reason=<X>` with timestamps and correlate against recent deploys/rollouts (topology/investigation context from Step 1) — a spike that starts at a deploy time is the finding, not just the symptom.

## What kubectl discovery adds over the other sources

- **NetworkPolicy default-deny coverage** per namespace (areas 21/46) — not visible from AWS API.
- **CNI configuration** (prefix delegation, custom networking, SG-for-pods, IPv6) from the aws-node DaemonSet (area 25).
- **Installed controllers** with live pod evidence (areas 28–33) rather than CRD-only inference.
- **Karpenter AMI pinning / NodePool limits / controller placement** read directly from specs (area 28).
- **Live pod problem state** (CrashLoop/OOM/ImagePull/pending) at the moment of the run (area 7).

---

<a id="context-management"></a>

# Context management for long reviews

A full review can exceed comfortable working context. AWS DevOps Agent cannot create or store runtime files, so context control relies on progressive reference loading, bounded projections, and a transient in-conversation ledger.

## Non-negotiable runtime constraint

- Do not create JSON sidecars, Markdown reports, local checkpoints, or any other runtime file.
- Do not use filesystem paths, timestamps, or file existence as proof of progress.
- Do not promise disk-based continuation. A new execution may require evidence recollection when prior conversation context is unavailable.
- The complete customer report is rendered directly in the final response after QA passes.

## Transient ledger

Keep only the following in current execution context:

- Confirmed cluster identity, environment, scope, and event window.
- Area 1–49 status (`complete|partial|n/a`), source scope, reason, and bounded projections.
- Source attempts and availability for Kubernetes, CloudWatch, AWS APIs, Prometheus, and connectors.
- Gate decisions and evidence.
- Selected/completed units and exact PASS/FAIL/N/A verdicts.
- Every FAIL's bounded evidence, descriptive severity, canonical resource ID, fingerprint, and remediation mapping.
- Reference-load audit, QA result, and next unit.

Raw kubectl, metric, log, and API responses are discarded after all dependent projections are recorded.

## Progressive unit cycle

For each selected unit:

1. Load only its canonical definition from `../runtime/router.md`.
2. Grade every exact manifest ID.
3. Add scorecard rows, totals, and compact evidence to the transient ledger and in-context response draft.
4. Determine FAIL IDs, then consult `remediations/index.md`.
5. Load only mapped remediation references and signal-triggered decision trees.
6. Add complete FAIL blocks, then drop unit-only definitions, remediations, and raw evidence before the next unit.

Never hold multiple canonical pillar references at once. Load the discovery manifest during the Discovery phase and run commands only through `use_kubectl`; then load inventory schema in S4, router/gates in S5, grading guards in S6, manifest/QA in S7, and report contract in S8. These are workflow stages, not storage targets; never persist results to Amazon S3 or a file.

## Context budget guidance

| Stage | Target behavior |
|---|---|
| Discovery | Project each area immediately; retain 49 statuses and bounded facts, not raw responses. |
| Per unit | Keep exact verdicts; compress PASS/N/A evidence after the unit is complete. |
| FAIL handling | Keep quoted evidence, impact, severity rationale, remediation, and link. |
| QA | Reconcile exact sets/counts from the ledger and response draft. |
| Final response | Render from the QA-approved ledger without regrading. |
## Pressure protocol

When context pressure approaches an unsafe level:

1. Finish the current area or unit; never leave an ID half-graded.
2. Update the transient ledger and compact response draft.
3. Preserve identity, all area statuses, exact verdicts, FAIL details, gates, load audit, QA state, and next unit.
4. Compress PASS evidence to short observed values and N/A evidence to ID plus reason.
5. Drop raw outputs, verbose logs, duplicate reasoning, and completed reference content.
6. Continue only with sufficient headroom.

If continuation is unsafe, emit a user-visible checkpoint summary in the conversation:

> Completed {n}/{N} selected units for `{cluster}`. Discovery: {areas}/49 attempted. Core rows: {actual}/{expected}. Completed: {units}. Unassessed: {units}. QA: {not run|partial FAIL|PASS}. Next unit: {next}. No runtime files were created. Continue only if this conversation retains the evidence; otherwise recollect the required sources.

A partial checkpoint is not a final review. Mark every unfinished unit `not assessed — context limit`, never silently omit it, and do not claim overall QA PASS unless all selected units reconcile.

## Never skip under pressure

- All 49 discovery area statuses.
- Exact selected scorecard IDs and one verdict per ID.
- Complete evidence/remediation for each reported FAIL.
- Conditional and cluster-type gate decisions.
- Source failures and N/A reasons.
- The S7 QA gate before a complete final response.

## Continuation behavior

If a later turn still has the prior conversation and transient ledger, resume at the stated next unit without repeating completed work. If the evidence or exact verdict ledger is no longer available, say so and recollect it; never reconstruct verdicts from memory or imply that a hidden file exists.

---

<a id="best-practices-checklist"></a>

# EKS best practices — quick-reference checklist

A flat, scannable checklist aligned with the [EKS Best Practices Guide](https://docs.aws.amazon.com/eks/latest/best-practices/introduction.html), grouped by the skill's pillars. This is a **fast pre-flight / sanity list**, not runtime grading authority. Canonical definitions live in the [`../pillars/` definitions](../pillars/operations.md) and [`../aws-api-checks.md`](../aws-api-checks.md); use this guide only to communicate scope.

## Operations
- [ ] K8s version within N-2 of latest; on a supported (non-extended) version
- [ ] Managed node groups / Karpenter preferred over self-managed ASGs
- [ ] Add-ons present and current (VPC CNI, CoreDNS, kube-proxy, EBS CSI)
- [ ] Not running both Cluster Autoscaler and Karpenter on the same capacity
- [ ] Workloads off the `default` ServiceAccount; CronJobs have sane schedules

## Resilience & HA
- [ ] Liveness, readiness, and startup probes on production workloads
- [ ] PodDisruptionBudgets present and not blocking drains
- [ ] TopologySpreadConstraints (with `minDomains`) for HA
- [ ] Resource requests **and** limits set
- [ ] Nodes across ≥2 AZs (ideally 3); no critical singletons on single-AZ nodes
- [ ] Graceful shutdown (preStop, `terminationGracePeriodSeconds`)

## Security
- [ ] Authentication mode = API (not CONFIG_MAP); cluster-creator admin removed
- [ ] Access Entries used; no `system:masters` mappings in aws-auth
- [ ] No ClusterRoleBinding to `system:anonymous`; minimal cluster-admin / wildcard RBAC
- [ ] EKS Pod Identity (preferred) or IRSA, least-privilege roles
- [ ] No privileged pods; `allowPrivilegeEscalation=false`; capabilities dropped
- [ ] Read-only root filesystem; `runAsNonRoot`; seccomp `RuntimeDefault`
- [ ] Pod Security Standards enforced per namespace
- [ ] Default-deny NetworkPolicy per namespace
- [ ] No `:latest` image tags; ECR scan-on-push enabled
- [ ] KMS envelope encryption for secrets; private endpoint; IMDSv2 required
- [ ] All control-plane log types enabled

## Scalability
- [ ] Cluster size within K8s/EKS scalability thresholds (nodes, pods, services, secrets)
- [ ] CoreDNS scaled (and/or NodeLocal DNS for large clusters)
- [ ] Instance-type diversity; avoid T-series burstable in production
- [ ] DaemonSet rollouts use a safe `maxUnavailable`
- [ ] PriorityClasses for cluster-critical services; dedicated cluster-services capacity

## Performance Efficiency
- [ ] Requests/limits coverage high; QoS not accidentally BestEffort for critical pods
- [ ] HPA / VPA / KEDA where appropriate
- [ ] ResourceQuota / LimitRange per namespace
- [ ] Compute selection fits workload (Graviton where compatible, right instance family)

## Observability
- [ ] Metrics stack present (Container Insights / Prometheus / managed)
- [ ] Logging pipeline present; control-plane logs enabled
- [ ] Tracing where applicable
- [ ] No unaddressed CrashLoop / OOMKilled / ImagePull / pending pods or warning-event storms

## Networking
- [ ] VPC CNI version current; prefix delegation considered for IP density
- [ ] Subnet IP availability healthy (>20% free; no near-exhaustion)
- [ ] VPC CIDR sized for growth (/16 recommended)
- [ ] kube-proxy mode appropriate; AWS Load Balancer Controller with IP target-type
- [ ] CoreDNS scaling + NodeLocal DNS for DNS-heavy / large clusters

## Cost / Sustainability / Architectural
- [ ] Node CPU utilization in the 30–70% band (not idle, not saturated)
- [ ] Pod requests match actual usage (right-sized)
- [ ] Spot for stateless / fault-tolerant; Graviton where possible
- [ ] gp3 StorageClass (not gp2); no orphaned PVCs / 0-replica deployments
- [ ] Karpenter consolidation = `WhenEmptyOrUnderutilized`
- [ ] Topology-aware routing to cut cross-AZ traffic; ingress consolidation
- [ ] Cost allocation tags on clusters and node groups

## Control Plane Health (CloudWatch)
- [ ] etcd DB size well under the 8 GB ceiling; no runaway 7-day growth
- [ ] No sustained APF 429s in `system` / `leader-election`
- [ ] No sustained API 5xx; LIST latency within SLO
- [ ] No KCM/scheduler backpressure or stuck evictions
- See [`../control-plane-health/thresholds.md`](../control-plane-health/thresholds.md) for exact thresholds.

## Cluster Upgrades (cross-cutting)
- [ ] EKS Cluster Insights reviewed — no FAILING upgrade-readiness/misconfiguration insights
- [ ] Add-on compatibility verified for the target version
- [ ] No deprecated API usage (check control-plane 4xx churn)
- [ ] PDB coverage allows safe node drains; node-group update strategy defined
- See [`../upgrade-readiness.md`](../upgrade-readiness.md).

---

<a id="inventory-schema"></a>

# Inventory rollup schema

## Contents

- Top-level shape
- `counts.*` (incl. coverage-gap signal keys and autoscaler signal keys)
- `features.*` (grouped boolean flags)
- Assembly tips

After walking the discovery areas via kubectl MCP, the agent assembles a single machine-readable JSON object — the same rollup the original tool emitted as `SUMMARY_JSON`, but built from the MCP command results. This is the core of the deliverable: it captures the whole cluster footprint without re-reading every area.

## Top-level shape

```json
{
  "timestamp": "<UTC ISO8601>",
  "scope": "all namespaces | namespace: <ns>",
  "cluster": "<cluster name / context>",
  "counts": { ... },
  "features": { ... }
}
```

## `counts.*`

Resource counts and problem signals. Zeros are real (resource type absent or none found).

| Key | Meaning | Watch when |
|-----|---------|-----------|
| `nodes`, `namespaces`, `pods` | core inventory | — |
| `nodes_notready` | nodes not `Ready=True` | > 0 → lost/at-risk capacity |
| `nodes_diskpressure` | nodes with `DiskPressure=True` | > 0 → imminent pod eviction (disk) |
| `nodes_memorypressure` | nodes with `MemoryPressure=True` | > 0 → imminent pod eviction (memory) |
| `nodes_pidpressure` | nodes with `PIDPressure=True` | > 0 → PID exhaustion; raise `--pod-max-pids` / reduce density |
| `pods_pending` | pods stuck Pending | > 0 → scheduling pressure |
| `pods_failed` | Failed phase | > 0 |
| `pods_crashloop` | CrashLoopBackOff | > 0 → app/config failures |
| `pods_imagepull` | ImagePull/ErrImagePull | > 0 → registry/auth issues |
| `pods_oomkilled` | OOMKilled | > 0 → memory limits too low |
| `deployments`, `statefulsets`, `daemonsets` | workload controllers | — |
| `services`, `ingresses` | networking | — |
| `hpa`, `vpa`, `keda_scaledobjects` | autoscaling objects | — |
| `pdb` | PodDisruptionBudgets | low vs workload count → HA gap |
| `workloads_without_pdb` | multi-replica workloads lacking a matching PDB | > 0 → update-safety gap |
| `pdb_blocking` | PDBs with `maxUnavailable:0` / `minAvailable:100%` | > 0 → stalls drains, consolidation, node updates |
| `rollout_maxunavail_risky` | Deployments whose rollout can drop below required minimum (incl. `Recreate`) | > 0 → disruptive rollouts |
| `single_az_nodes` | nodes confined to a single AZ | true → AZ-failure exposure |
| `endpointslices_in_use` | services backed by EndpointSlices | false at scale → migrate off legacy Endpoints |
| `deploys_unbounded_history` | Deployments at default `revisionHistoryLimit=10` | high on large clusters → bound it |
| `service_links_enabled` | pods not setting `enableServiceLinks=false` | high with many services → disable where unneeded |
| `webhooks_on_pods` | mutating+validating webhooks intercepting pods | high → each adds API latency |
| `jobs`, `cronjobs` | batch | — |
| `configmaps`, `secrets` | config | high `secrets` → watch K8s 10k limit |
| `networkpolicies` | NetworkPolicies | 0 → no network isolation |
| `crds` | installed CRDs | ecosystem breadth |
| `pvs`, `pvcs` | storage claims | — |
| `mutating_webhooks`, `validating_webhooks` | admission webhooks | failurePolicy risk (area 24) |
| `privileged_pods` | privileged containers | > 0 → security review |
| `hostnetwork_pods`, `hostpid_pods`, `hostipc_pods` | host namespace usage | > 0 (outside system) → security review |
| `hostpath_pods` | pods mounting `hostPath` volumes | > 0 → restrict prefixes / make read-only |
| `privilege_escalation_allowed` | containers without `allowPrivilegeEscalation=false` | > 0 → set to false |
| `capabilities_not_dropped` | containers not dropping `ALL` capabilities | > 0 → drop ALL, add back only needed |
| `seccomp_not_runtimedefault` | pods/containers without `seccompProfile=RuntimeDefault` | high → apply RuntimeDefault |
| `readonly_rootfs_true` / `_false` | rootfs hardening coverage | low true → hardening gap |
| `runasnonroot_true` | runAsNonRoot coverage | — |
| `kyverno_policies`, `gatekeeper_constraints` | policy engine rules | 0 with engine present → unused |
| `resourcequotas`, `limitranges` | namespace governance | low vs namespace count |
| `priorityclasses` | scheduling priority | — |
| `containers_with_liveness` / `_without_liveness` | liveness probe coverage | high without → resilience gap |
| `containers_with_readiness` / `_without_readiness` | readiness probe coverage | high without → rollout risk |

Optional extra counts worth capturing when relevant: `karpenter_nodepools`, `karpenter_ec2nodeclasses`, `karpenter_nodeclaims`, `gpu_nodes`, `neuron_nodes`, `efa_nodes`, `coredns_replicas`, `node_azs`, `spot_nodes`, `ondemand_nodes`, `bottlerocket_nodes`, `windows_nodes`, `hybrid_nodes`, `storageclasses`.

Signal keys added for the coverage-gap checks (capture when the source area is walked; each maps to one check):

| Key | Check | Meaning |
|-----|-------|---------|
| `storageclasses_immediate_binding` | R19 | EBS StorageClasses using `Immediate` (not `WaitForFirstConsumer`) that back stateful workloads |
| `storageclasses_unencrypted` | S32 | provisioning StorageClasses without `parameters.encrypted: "true"` |
| `webhooks_high_timeout` | S33 | admission webhooks with `timeoutSeconds` > 10 (or mutating `reinvocationPolicy: IfNeeded`) |
| `webhooks_cabundle_expiring` | S34 | webhook configs whose `caBundle` cert is expired or < 30 days to expiry |
| `secrets_store_csi_rotation_off` | S35 | Secrets Store CSI driver present but rotation not enabled |
| `awsnode_uses_node_role` | S36 | `aws-node` SA has no dedicated IRSA/Pod-Identity role (falls back to node role) |
| `nodepools_overlap_unweighted` | Op27 | >1 Karpenter NodePool with overlapping requirements and no `spec.weight` |
| `spot_to_spot_consolidation_off` | Op28 | Spot NodePools exist but `SpotToSpotConsolidation` not enabled |
| `lbfronted_no_prestop` | R18 | LB-fronted pods without a `preStop` hook ≥ deregistration delay |
| `initcontainer_request_inflation` | P14 | pods whose init-container requests exceed the summed app-container requests |
| `hostnetwork_port_conflicts` | N25 | `hostNetwork` pods reusing the same `hostPort` across co-schedulable workloads |
| `gatewayapi_unhealthy` | N26 | GatewayClass/Gateway/HTTPRoute with a non-`Accepted`/non-`Programmed` status condition |

Autoscaler signal keys from area 28 (each maps to an Operations check):

| Key | Check | Meaning |
|-----|-------|---------|
| `karpenter_ami_latest` | Op11 | EC2NodeClass using the `@latest` AMI alias in prod |
| `karpenter_self_hosted` | Op20 | Karpenter controller running on a node it manages |
| `spot_nodepool_low_diversity` | Op22 | Spot NodePool with a narrow allowed instance set |
| `donotdisrupt_pods` | OpM8 | pods annotated `karpenter.sh/do-not-disrupt=true` |
| `cas_version_mismatch` | Op9 | CAS image minor ≠ cluster minor |
| `cas_autodiscovery` | Op24/OpM2 | `--node-group-auto-discovery` present on CAS |
| `automode_selfmanaged_dupes` | Op17 | self-managed Karpenter/LBC/EBS-CSI duplicating Auto Mode |
| `dual_autoscaler` | Op18 | CAS and Karpenter both active |

> These follow the same rule as every other count: capture only from an area actually walked; a skipped area is `null`/`unknown`, never `0`. Several also have an AWS-API confirmation leg (Sc22 EBS attachment count, Op26/Op29 nodegroup/AMI facts, AX14 EFS mount targets) that stays N/A in kubectl-only mode.

> **Conditional-checklist gates:** `windows_nodes > 0` → `../windows-workloads.md`; `hybrid_nodes > 0` → `../hybrid-nodes.md`; `gpu_nodes > 0` or `neuron_nodes > 0` → `../aiml-workloads.md`. All default to `0`/absent on a standard cluster.

## `features.*`

Boolean install-detection flags, grouped. `true` = detected in-cluster, `false` = not detected. Use these to describe the platform footprint fast.

| Group | Keys |
|-------|------|
| `autoscaling` | `hpa`, `vpa`, `keda`, `cluster_autoscaler`, `karpenter`, `eks_auto_mode` |
| `ingress_controllers` | `nginx`, `alb`, `traefik` |
| `cni` | `vpc_cni`, `calico`, `cilium`, `weave`, `flannel` |
| `cni_config` | `prefix_delegation`, `custom_networking`, `security_groups_for_pods`, `vpc_cni_network_policy`, `ipv6_cluster`, `external_snat`, `vpc_cni_version` |
| `networking` | `kube_proxy_mode` (iptables/ipvs), `aws_lb_controller`, `nodelocaldns`, `dns_autoscaler`, `external_dns` |
| `service_mesh` | `istio`, `linkerd`, `appmesh` |
| `observability` | `prometheus`, `grafana`, `opentelemetry`, `cloudwatch_agent`, `fluentbit`, `kube_state_metrics`, `metrics_server`, `cni_metrics_helper`, `node_exporter`, `adot`, `xray`, `vector`, `datadog`, `dynatrace`, `newrelic`, `splunk`, `elastic`, `alertmanager`, `dcgm_exporter` |
| `gitops` | `argocd`, `fluxcd` |
| `cost_optimization` | `kubecost`, `goldilocks`, `opencost` |
| `security` | `kyverno`, `gatekeeper`, `falco`, `guardduty`, `irsa`, `pod_identity`, `aws_auth_present` |
| `third_party_controllers` | `ack`, `external_secrets`, `cert_manager`, `aws_lb_controller`, `crossplane`, `sealed_secrets`, `reloader`, `velero` |
| `gateway_controllers` | `vpc_lattice`, `envoy_gateway`, `contour`, `kong`, `ambassador`, `apisix` |
| `dns` | `nodelocaldns`, `dns_autoscaler`, `external_dns` |
| `compute` | `fargate` |
| `karpenter` (counts) | `nodepools`, `ec2nodeclasses`, `nodeclaims`, `provisioners_legacy`, `awsnodetemplates_legacy` |

## Assembly tips

- A `false` feature flag means "not detected in-cluster." For AWS-managed features (control-plane logging, KMS encryption, cluster auth mode), use an AWS-side check; see [`resource-inventory.md`](resource-inventory.md) → "Not observable in-cluster." Mark unavailable facts `unknown`, not `false`.
- Cross-check conflicting signals before reporting: e.g. `karpenter=true` AND `cluster_autoscaler=true` → both autoscalers present, a real conflict worth surfacing.
- Detection rule of thumb: a feature is `true` when its detection command returns ≥1 matching pod, CRD, or resource. Be explicit in the summary about what evidence set the flag (e.g. "argocd: 5 pods in argocd ns").
- Don't fabricate counts. If an area was skipped (scope, permissions, timeout), record the count as `null`/`unknown` and note the gap — never default a skipped area to `0`.

---

<a id="metrics-and-alarms"></a>

# CloudWatch metrics & log thresholds (workload + node + EC2)

This human guide retains detailed sourcing and rationale for data-plane/workload signals. Runtime grading uses [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md) and complements [`../control-plane-health/thresholds.md`](../control-plane-health/thresholds.md). Load this document only for an explicit operator/background question.

Severity uses `Critical / High / Medium / Low / Info`; [`../runtime/report-contract.md`](../runtime/report-contract.md) maps customer-facing descriptive labels. Default lookback is 7 days; unobservable signals are **N/A** with the source reason, never PASS.

## Contents

- Container Insights — node metrics
- Container Insights — pod metrics
- EKS control-plane request metrics (`AWS/EKS`)
- EC2 node metrics (`AWS/EC2`)
- Control-plane log patterns (7-day)
- CloudTrail event analysis (7-day)
- Notes on sourcing
- ENA / VPC network-allowance metrics
- CoreDNS DNS-health metrics
- Karpenter controller metrics
- EBS volume performance metrics (`AWS/EBS`)
- NAT Gateway metrics (`AWS/NATGateway`)
- Extra Container Insights metrics
- Recommended CloudWatch alarms

## Container Insights — node metrics (namespace `ContainerInsights`)

| Metric | Normal | Warning | Critical | Finding |
|--------|--------|---------|----------|---------|
| `node_cpu_utilization` | <70% | >70% | >90% | Right-size or add capacity |
| `node_memory_utilization` | <80% | >80% | >95% | OOM risk — increase capacity / lower requests |
| `node_filesystem_utilization` | <70% | >70% | >85% | Disk exhaustion risk (image/log/ephemeral growth) |
| `cluster_failed_node_count` | 0 | >0 | >1 | Node failures detected |
| `cluster_node_count` | stable | — | — | Trend only — pair with autoscaler review |

## Container Insights — pod metrics (namespace `ContainerInsights`)

| Metric | Normal | Warning | Critical | Finding |
|--------|--------|---------|----------|---------|
| `pod_cpu_utilization` | 10–60% | <10% or >60% | >80% | Over- (waste) or under-provisioned (saturation) |
| `pod_memory_utilization` | 20–70% | <20% or >70% | >85% | Over- or under-provisioned vs requests |
| `pod_number_of_container_restarts` | <50 / 7d | >50 / 7d | >200 / 7d | Unstable pods — inspect CrashLoop / OOM |

Cross-check pod utilization against the in-cluster requests/limits coverage from the Performance pillar: low `pod_cpu_utilization` with high requests = right-sizing (cost) finding; high utilization with no limits = saturation (performance) finding.

## EKS control-plane request metrics (namespace `AWS/EKS`)

These are **default-vended** by EKS to CloudWatch on **K8s 1.28+** — they do **not** require Container Insights or any agent. Grade them whenever the cluster is 1.28+ even if Container Insights is off. Lookback 7 days.

| Metric | Statistic | Normal | Warning | Critical | Finding |
|--------|-----------|--------|---------|----------|---------|
| `apiserver_request_total_5XX` | Sum | <100 / 7d | >100 / 7d | sustained | API server 5xx — etcd timeouts, webhook failures, resource exhaustion |
| `apiserver_request_total_429` | Sum | <50 / 7d | >50 / 7d | sustained | APF throttling — clients exceeding API Priority & Fairness limits |
| `apiserver_storage_size_bytes` | Maximum | <6 GB | >6 GB (75% of 8 GB) | >7.2 GB (90%) | etcd nearing the 8 GB ceiling — writes rejected (NOSPACE) at the limit |
| `apiserver_admission_webhook_admission_duration_seconds` | Average | <1 s | >3 s | sustained | Admission webhook latency in the API request path (1 s mutating SLO) |
| `scheduler_pending_pods` | Maximum | 0 | >10 at peak | >10 sustained | Scheduling backlog — capacity/constraint/PVC issues |

> These five default-vended metrics are the lightweight baseline. The authoritative control-plane saturation grading (etcd growth-rate, APF 429s **by priority level**, per-URI LIST latency, KCM QPS, eviction stalls) lives in the **Control Plane Health** pillar and `control-plane-health/` and needs control-plane logging. Use these `AWS/EKS` metrics when only metrics (not logs) are available.

## EC2 node metrics (namespace `AWS/EC2`, per instance)

| Metric | Normal | Warning | Critical | Finding |
|--------|--------|---------|----------|---------|
| `CPUUtilization` | <70% | >80% | >95% | CPU saturation on the node |
| `StatusCheckFailed` | 0 | — | >0 | Hardware / system failure — instance needs replacement |

## Control-plane log patterns (7-day, control-plane logging enabled)

| Pattern | Severity if found | Action |
|---------|-------------------|--------|
| `ERROR` (>100 / 7d) | Medium | Investigate root cause / noisy component |
| `429` (throttling) | High | Reduce API call rate — identify the dominant client (see APF checks) |
| `OOMKilled` | High | Increase memory limits or right-size the workload |
| `FailedScheduling` | Medium | Check capacity / affinity / taints / topology constraints |
| `Evicted` | High | Node resource pressure — review requests and node sizing |

## CloudTrail event analysis (7-day, management events)

| Event pattern | Severity | Action |
|--------------|----------|--------|
| `AccessDenied` / `UnauthorizedOperation` errors | High | Investigate possible unauthorized access |
| `CreateAccessEntry` | Medium | Verify the grant was authorized — corroborate with AX2 access-entry check |
| `UpdateClusterConfig` / `UpdateNodegroupConfig` | Info | Audit trail of configuration changes |
| `DeleteCluster` | Info | Verify intentional |
| High write volume from a single principal | Medium | Unusual activity — confirm expected automation |

## Notes on sourcing

- Container Insights metrics require the CloudWatch Observability add-on (or the legacy CloudWatch agent + Fluent Bit). If absent, these rows are **N/A** and the gap itself is an **Observability** finding.
- EC2 metrics are always available for managed/self-managed nodes; Fargate has no EC2-node metrics (mark N/A for Fargate-only clusters).
- CloudTrail management events are on by default; data events are not — only grade what the trail actually captures.

## ENA / VPC network-allowance metrics (per node, `CWAgent` — conditional)

**Not auto-vended.** The ENA driver always tracks these on-node (`ethtool -S eth0 | grep allowance`), but they reach CloudWatch only with the CloudWatch Observability add-on (ethtool metrics enabled) or a standalone CW Agent with `ethtool.metrics_include`. Discover via `listMetrics metricName=linklocal_allowance_exceeded`. If absent, that itself is an **Observability gap** (Medium) — feeds Networking **N21** and Observability **O20**.

| Metric | Statistic | Normal | Finding if > 0 | Why |
|--------|-----------|--------|----------------|-----|
| `linklocal_allowance_exceeded` | Sum, Maximum | 0 | **High** if breached in 7d | Packets dropped at the **1024 PPS VPC DNS limit** — pods see `UnknownHostException` while CoreDNS reports healthy. Mitigate with NodeLocal DNSCache (N18). |
| `conntrack_allowance_exceeded` | Sum, Maximum | 0 | High | Connection-tracking table full — new connections (incl. DNS) can't establish. |
| `pps_allowance_exceeded` | Sum, Maximum | 0 | Medium | General bidirectional PPS cap exceeded — affects all traffic. |
| `bw_in/out_allowance_exceeded` | Sum | 0 | Low | Instance bandwidth cap hit — consider a larger instance / more ENIs. |

Severity: breach in **7d → High** (active drops), breach only in **30d → Medium** (intermittent — include timestamps), metric absent → Medium observability gap.

## CoreDNS DNS-health metrics (Prometheus — conditional)

Require the `amazon-cloudwatch-observability` add-on with Prometheus scraping (CoreDNS `:9153/metrics`) or an ADOT/Prometheus remote-write pipeline. Discover via `listMetrics metricName=coredns_dns_requests_total`. Basic Container Insights gives only generic pod CPU/mem/restarts — not these. Feeds Observability **O19** and Networking **N19/N21**.

| Metric | Statistic | Threshold | Why |
|--------|-----------|-----------|-----|
| `coredns_panics_total` | Sum | **>0 → Critical** | Any panic = CoreDNS pod crashed on internal error. Must always be 0. |
| `coredns_dns_responses_total` (rcode=SERVFAIL) | Sum | >100 / 5 min → High | Sustained upstream (Route 53 / external) DNS failures. |
| `coredns_dns_request_duration_seconds` p99 | Maximum | >5 s → High (or avg `_sum/_count` >1 s) | DNS tail latency — networking bottleneck or pod overload. |
| `coredns_dns_request_duration_seconds_count` | Sum | trend / baseline | Query volume — spikes = app loop or `ndots` misconfig. |
| `coredns_dns_responses_total` (rcode=NXDOMAIN) | Sum | baseline (10x spike = deleted service ref) | Expected from ndots search expansion. |

## Karpenter controller metrics (Prometheus — conditional)

Only when Karpenter is detected (nodes/instances tagged `karpenter.sh/nodepool`). Require Prometheus scraping of the Karpenter controller (`:8080/metrics`). Discover via `listMetrics metricName=karpenter_nodeclaims_created_total` (legacy: `karpenter_nodes_created`). Feeds Observability **O18**.

| Metric | Statistic | Threshold | Why |
|--------|-----------|-----------|-----|
| `karpenter_cloudprovider_errors_total` | Sum | >10 / 5 min → Medium | ICE (InsufficientInstanceCapacity), throttling, auth failures. |
| `karpenter_scheduler_unschedulable_pods_count` | Maximum | >5 sustained → Medium | Pods Karpenter cannot place. |
| `karpenter_scheduler_queue_depth` | Maximum | >5 sustained → Medium | Controller falling behind. |
| `karpenter_pods_startup_duration_seconds` | Maximum | >180 s → Medium | Slow pod scheduling-to-running (EC2 slowness / ICE retries). |
| `karpenter_nodeclaims_created_total` / `_terminated_total` | Sum | baseline / spike | Scale-up rate; mass terminations = Spot interruption storm or aggressive consolidation. |
| `karpenter_voluntary_disruption_decisions_total` | Sum | baseline | Disruption decision rate. |

## EBS volume performance metrics (namespace `AWS/EBS`, per volume)

For EBS-backed PVs. A volume out of burst credits or saturated on IOPS/throughput stalls stateful pods — REL-class impact. Feeds Performance **P13** (and data-plane Resilience).

| Metric | Statistic | Finding | Why |
|--------|-----------|---------|-----|
| `BurstBalance` (gp2/st1/sc1) | Minimum | <20% → High; hitting 0 sustained → Critical | Burst-credit exhaustion throttles the volume to baseline — latency cliff. Migrate gp2→gp3 (provisioned, no burst). |
| `VolumeReadOps` + `VolumeWriteOps` vs provisioned IOPS | Sum→IOPS | sustained ≥ provisioned → High | IOPS saturation; raise gp3 IOPS or split the volume. |
| `VolumeThroughputPercentage` / bytes vs provisioned | Average | sustained near 100% → High | Throughput saturation; raise gp3 throughput. |
| `VolumeQueueLength` | Average | persistently high → Medium | I/O backlog — under-provisioned volume. |

## NAT Gateway metrics (namespace `AWS/NATGateway`, per NAT)

| Metric | Statistic | Threshold | Why |
|--------|-----------|-----------|-----|
| `ErrorPortAllocation` | Sum | **>0 → High** | SNAT port exhaustion — new outbound connections fail. Add NAT gateways / spread load. |
| `PacketsDropCount` | Sum | >100 / 5 min → Medium | NAT dropping packets. |
| `BytesOutToDestination` | Sum | baseline / cost | High processing volume → add VPC endpoints / pull-through cache (cost A* + NM5). |

## Extra Container Insights metrics (when enabled)

| Metric | Statistic | Threshold | Why |
|--------|-----------|-----------|-----|
| `pod_cpu_utilization_over_pod_limit` | Average | >95% → Medium | Pod near its CPU limit (throttling). Raise the limit or right-size. |
| `pod_memory_utilization_over_pod_limit` | Average | >95% → High | Pod near its memory limit — OOMKill risk. |
| `node_status_condition_ready` | Minimum | <1 → High | Node not Ready (also Op25). |
| `pod_status_pending` | Maximum | >0 sustained → Medium | Pods stuck Pending — scheduling/capacity issue. |
| `apiserver_longrunning_requests` (ContainerInsights) | Average | >50 → Medium | High active long-running API requests (exclude watches) — control-plane pressure. |
| `apiserver_flowcontrol_rejected_requests_total` (ContainerInsights) | Sum | >10 / 5 min → High | APF rejections (same signal as control-plane-health APF; see O17). |

## Recommended CloudWatch alarms (IDR-onboarding deliverable)

When the review is part of IDR onboarding / a CWR, emit a **recommended-alarms table** alongside findings — each alarm with a concrete evaluation config the customer can create directly. Base set (always), plus conditional sets when the corresponding component/metric is detected.

**Base (no add-on needed where noted):**

| Alarm | Namespace | Threshold (period, datapoints) | Add-on? |
|-------|-----------|--------------------------------|---------|
| cluster_failed_node_count | ContainerInsights | Max > 0 (1 min, 1/1) | CW Observability |
| node_cpu_utilization | ContainerInsights | Avg > 80% (5 min, 3/5) | CW Observability |
| node_memory_utilization | ContainerInsights | Avg > 80% (5 min, 3/5) | CW Observability |
| node_filesystem_utilization | ContainerInsights | Avg > 80% (5 min, 3/5) | CW Observability |
| pod_cpu_utilization_over_pod_limit | ContainerInsights | Avg > 95% (5 min, 3/5) | CW Observability |
| pod_memory_utilization_over_pod_limit | ContainerInsights | Avg > 95% (5 min, 3/5) | CW Observability |
| pod_number_of_container_restarts | ContainerInsights | Sum > 5/hr (1 hr, 1/1) | CW Observability |
| node_status_condition_ready | ContainerInsights | Min < 1 (5 min, 2/3) | CW Observability (enhanced) |
| pod_status_pending | ContainerInsights | Max > 0 (5 min, 2/3) | CW Observability (enhanced) |
| apiserver_longrunning_requests | ContainerInsights | Avg > 50 (5 min, 3/5) | CW Observability (enhanced) |
| apiserver_flowcontrol_rejected_requests_total | ContainerInsights | Sum > 10 (5 min, 2/3) | CW Observability (enhanced) |
| apiserver_request_total_5XX | AWS/EKS | Sum > 10 (1 min, 1/1) | none (1.28+) |
| apiserver_storage_size_bytes | AWS/EKS | Max > 6.4 GB (5 min, 3/5) | none (1.28+) |
| ErrorPortAllocation | AWS/NATGateway | Sum > 0 (5 min, 1/1) | none |
| PacketsDropCount | AWS/NATGateway | Sum > 100 (5 min, 2/3) | none |

**Conditional — Karpenter** (when detected): `karpenter_cloudprovider_errors_total` Sum>10 (5min,2/3); `karpenter_scheduler_unschedulable_pods_count` Max>5 (5min,2/3); `karpenter_scheduler_queue_depth` Max>5 (5min,3/5); `karpenter_pods_startup_duration_seconds` Max>180s (5min,1/1); `karpenter_nodeclaims_terminated_total` Sum>15 (5min,1/1).

**Conditional — CoreDNS** (when DNS metrics present): `coredns_panics_total` Sum>0 (5min,1/1); `coredns_dns_responses_total` SERVFAIL Sum>100 (5min,2/3); `coredns_dns_request_duration_seconds` p99>5s (5min,2/3) or avg>1s.

**Conditional — ENA** (when ethtool metrics present): `linklocal_allowance_exceeded` Sum>0 (5min,1/1); `conntrack_allowance_exceeded` Sum>0 (5min,2/3); `pps_allowance_exceeded` Sum>0 (5min,2/3).

All alarms → SNS to the operations team; failed-node / node-not-ready / pod-pending → trigger incident response. Sources: [AWS Recommended Alarms — EKS](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html) · [EKS IDR Alarming Best Practices](https://repost.aws/articles/ARhnAXjQGMSr2l2_qb_J8uaA).