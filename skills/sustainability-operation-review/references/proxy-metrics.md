# Resource Intensity Proxy Metrics — Derivation Reference

How to compute the KPIs in Step 4 and Step 6 of the skill.

## Why Proxy Metrics At All

Reported carbon emissions move for many reasons at once: methodology revisions, grid mix
variation, AWS energy procurement, data center efficiency changes, and shifts in the
customer's allocation share driven by other customers' usage — alongside the customer's own
changes. They are therefore a poor *feedback signal* for architecture work, because the signal
and the noise arrive together: a customer can do everything right and see the number go the
wrong way, with no way to tell from the figure alone which cause dominated.

Resource intensity metrics have none of those confounders. They measure what the customer
provisions and how hard they work it, so they respond immediately and unambiguously to
architecture change — which makes them the right primary metric for an engineering team.

This is about signal quality, not about the size of the customer's influence. Provisioning
decisions do move the reported figure, and embodied hardware carbon in particular scales with
provisioned capacity; the KPIs exist to isolate that effect, not to substitute for a small one.

## Why Not Just Use Cost

Cost is a decent first-order proxy and often correlates. But it breaks in specific,
predictable ways:

| Divergence | Mechanism |
|-----------|-----------|
| Volume discounts, Savings Plans, Reserved Instances, EDP | Spend falls; resource consumption is unchanged. Committed-but-idle capacity has no marginal cost signal at all. |
| Free inbound data transfer | Inbound egress-to-AWS is free. The network and device resources consumed are real. Cost tooling sees nothing. |
| Regional price vs grid intensity | These are set by unrelated mechanisms. A cheaper Region can have a dirtier grid, and vice versa. |
| Growth | Cost-per-transaction can improve through scale while absolute resource consumption grows. Both facts are true; only one is visible in a unit-cost chart. |
| Storage class pricing vs footprint | Price ratios between classes do not match resource-footprint ratios. |

The counter-point worth stating honestly: in most workloads, most of the time, cost and
resource intensity move together. The value of measuring intensity is not that cost is
usually wrong — it's that intensity is *always* attributable, and it catches the cases
above that cost structurally cannot see.

## The Core Formula

```
intensity = resource_quantity / business_output_units
```

Both terms over the same window (default 30 days), at the same period granularity.

An intensity KPI without a credible denominator is not a KPI. If no business output
metric exists, report absolute resource footprint and raise SUS06-BP01 as the top
finding — do not fabricate a denominator.

---

## Compute: vCPU-Hours

Never count instances. An instance count treats a `t3.nano` and an `m7i.48xlarge` as
equal. Count vCPU × hours.

### EC2 / Auto Scaling

```
provisioned_vCPU_hours = Σ over instances (vCPUs(instance_type) × running_hours)
utilized_vCPU_hours    = Σ over instances (vCPUs(instance_type) × running_hours × avg_CPUUtilization)
```

- `vCPUs(instance_type)` from `ec2.DescribeInstanceTypes` → `VCpuInfo.DefaultVCpus`.
  Do **not** infer vCPU count from the instance name size suffix — the mapping is not
  uniform across families.
- `running_hours` from instance state transitions, or `CPUUtilization` datapoint count ×
  period ÷ 3600 (a datapoint exists only while running).
- For ASGs, sum across members over time rather than using the current desired count.

### ECS / Fargate

```
task_vCPU        = task_definition.cpu / 1024
provisioned      = Σ (task_vCPU × task_running_hours)
utilized         = Σ (CpuUtilized / 1024 × task_running_hours)     # Container Insights
```

Without Container Insights, `utilized` is unavailable — say so rather than assuming
provisioned = utilized.

### EKS

```
node_provisioned = Σ over nodegroups (vCPUs(instance_type) × node_count × hours)
pod_requested    = Σ over pods (requests.cpu × pod_hours)
utilized         = Σ over pods (actual cpu usage × pod_hours)       # Container Insights / metrics-server
```

EKS has **two** gaps worth reporting separately:
- **Scheduling gap** = node_provisioned − pod_requested (nodes bigger than what's scheduled)
- **Request gap** = pod_requested − utilized (requests set higher than real usage)

The second is usually larger and is invisible without pod-level metrics.

### Lambda

```
vCPU_equivalent = memory_MB / 1769        # 1769 MB ≈ 1 full vCPU
vCPU_hours      = Σ (Duration_ms / 1000 / 3600 × vCPU_equivalent)
```

Lambda has no idle time, so provisioned ≈ utilized. The efficiency question for Lambda
is whether memory is oversized relative to `Duration` — over-allocated memory means
over-allocated CPU. Provisioned Concurrency, by contrast, **does** have idle time and
should be counted as provisioned-but-unused when invocations don't fill it.

### RDS / Aurora

```
vCPU_hours = vCPUs(instance_class) × hours × (Multi_AZ ? 2 : 1)
```

For Aurora Serverless v2: `avg(ServerlessDatabaseCapacity) × 2 × hours`
(1 ACU ≈ 2 GiB memory with proportional CPU).

Count reader instances individually. `CPUUtilization` gives the utilized fraction.

---

## Storage: Weighted GB-Months

```
weighted_GB_months = Σ over resources (GB × months_provisioned × class_weight)
```

### Weights

| Class | Weight |
|-------|--------|
| EBS (gp2, gp3, io1, io2, st1, sc1), instance store | 1.0 |
| EFS Standard, FSx | 1.0 |
| S3 Standard | 0.8 |
| S3 Standard-IA, One Zone-IA | 0.5 |
| S3 Glacier Instant Retrieval | 0.3 |
| S3 Glacier Flexible Retrieval, Deep Archive | 0.1 |
| EBS snapshots (incremental, compressed) | 0.5 |

**These weights are directional, not a carbon model.** They encode one idea: archive
tiers sit on denser, lower-power media at lower duty cycle than always-provisioned block
storage, so a KPI that treats them as equivalent will hide the value of lifecycle
policies. Always state in the report that they are heuristic. If a customer needs
defensible per-class figures, that requires AWS-published data that does not currently
exist at this granularity.

### Sources

- **EBS** — `ec2.DescribeVolumes` → `Size`. Provisioned size, not used size. In-volume
  utilization needs the CloudWatch agent (`disk_used_percent`); if absent, note the
  limitation rather than assuming volumes are full.
- **S3** — CloudWatch `AWS/S3` `BucketSizeBytes` with the **`StorageType` dimension**
  (`StandardStorage`, `StandardIAStorage`, `OneZoneIAStorage`, `GlacierInstantRetrievalStorage`,
  `GlacierStorage`, `DeepArchiveStorage`, `IntelligentTieringFAStorage`, …). Without the
  dimension you get a single total and cannot apply weights. Daily metric, so use
  `Period: 86400`.
- **RDS** — `AllocatedStorage`; Aurora storage is cluster-shared and reported via
  `VolumeBytesUsed`.
- **Snapshots** — `ec2.DescribeSnapshots`; sizes are the source volume size, and actual
  consumption is incremental. Apply the 0.5 weight and note the approximation.
- **EFS/FSx** — `describe_file_systems` → `SizeInBytes`.

---

## Network: Weighted GB Transferred

```
weighted_GB = Σ over paths (GB_transferred × distance_weight)
```

| Path | Weight | Rationale |
|------|--------|-----------|
| Within AZ | 0.25 | Shortest path, least network hardware |
| Cross-AZ | 0.5 | Inter-DC within a Region |
| Cross-Region | 1.0 | Long-haul backbone |
| Internet egress | 1.0 | Backbone + edge |

### Sources

- **EC2** — `NetworkIn` / `NetworkOut` (bytes, Sum). These don't distinguish AZ from
  Region; use topology relationships to attribute.
- **ELB** — `ProcessedBytes`; ALB `RequestCount` per target AZ for cross-AZ inference.
- **NAT Gateway** — `BytesOutToDestination`, `BytesInFromDestination`. Traffic here to
  AWS services with a gateway VPC endpoint is pure waste (SUS04-BP07).
- **CloudFront** — `BytesDownloaded` (egress), cache hit ratio to derive origin fetches.
- **S3 replication** — `ReplicationLatency`, `BytesPendingReplication`; CRR volume from
  `BytesDownloaded` on the source with the replication filter.
- **Transit Gateway** — `BytesIn` / `BytesOut` per attachment.
- **VPC Flow Logs** — the most accurate source for AZ-level attribution when available.
  If not enabled, state that AZ-level splits are inferred from topology.

Inbound internet traffic is free of charge but not free of resource consumption. Include
it in the KPI and note that it carries no cost signal.

---

## Business Output Denominators

In descending order of usefulness:

| Denominator | Source | Notes |
|-------------|--------|-------|
| Business transactions | Customer-supplied custom CloudWatch metric | Best. Ask for it. |
| Orders / bookings / records processed | Application metric | Directly meaningful to the business |
| Requests | ALB `RequestCount`, API GW `Count`, CloudFront `Requests` | Good for request-response; blind to work-per-request |
| Invocations | Lambda `Invocations`, SQS `NumberOfMessagesDeleted` | Event count |
| Active users | Customer metric | Good for user-facing platforms |
| Jobs completed | Batch `SucceededJobs`, Step Functions `ExecutionsSucceeded` | Right choice for batch |
| Records / events | Kinesis `IncomingRecords`, MSK `MessagesInPerSec` | Right choice for streaming |
| Data processed | S3 `BytesDownloaded`, Glue DPU-hours | Volume, weakest proxy for value |

Scale so the KPI reads naturally — "vCPU-hours per 1M requests" rather than a number
with six leading zeros.

---

## Reporting Intensity KPIs

Report each as:

| KPI | Current | 30d Prior | Change | Direction |
|-----|---------|-----------|--------|-----------|
| vCPU-hours per 1M requests | 42.1 | 51.3 | −17.9% | ✅ improving |
| Utilization gap | 38% | 41% | −3pp | ✅ improving |
| Weighted GB-months per 1M requests | 8.4 | 8.1 | +3.7% | ⚠️ worsening |

Rules:
- Always show the direction, and always define which direction is good.
- Distinguish percentage change from percentage-point change for KPIs that are
  themselves percentages.
- A 30-day window can be distorted by a deployment, incident, or seasonal peak. Note any
  known event in the window rather than reporting the delta as a clean trend.
- Report absolute footprint alongside intensity. Intensity improving while absolute
  consumption grows is a real and common situation, and reporting only intensity hides it.

## What These Metrics Cannot Do

State these limits in the report:

1. They are **not** carbon figures and must not be converted into MTCO2e.
2. The storage and network weights are heuristics, not published AWS coefficients.
3. Cross-workload comparison is invalid unless both use the same denominator definition.
4. They don't capture embodied hardware carbon, which is allocated by AWS and not
   influenceable except by consuming fewer resource-hours.
5. Memory, GPU memory, and in-volume storage utilization are invisible without the
   CloudWatch agent. Absent that, the utilization gap is CPU-only and understates the
   real gap.

---

## KPI Set, Emissions Sanity Check, and Cost–Carbon Divergence (Step 6)

For each KPI relevant to the detected workload shape:

```
intensity = resource_quantity / business_output_units
```

Report each KPI with: current value, value 30 days prior, % change, and direction.

Standard KPI set:

| KPI | Formula | Improvement lever |
|-----|---------|-------------------|
| Compute intensity | provisioned vCPU-hours ÷ business output | SUS03-BP02, SUS05-BP01 |
| Utilization gap | (provisioned − utilized) vCPU-hours ÷ provisioned | SUS02-BP01, SUS03-BP02 |
| Storage intensity | weighted GB-months ÷ business output | SUS04-BP03, SUS04-BP05 |
| Network intensity | weighted GB transferred ÷ business output | SUS04-BP07, SUS02-BP04 |
| Graviton share | Graviton vCPU-hours ÷ total vCPU-hours, overall and per service | SUS05-BP02 |
| Graviton-eligible x86 share | x86 vCPU-hours with a Graviton option (`references/graviton-migration.md`) ÷ total vCPU-hours | SUS05-BP02 |
| Current-generation share | current-generation vCPU-hours (either architecture) ÷ total vCPU-hours | SUS05-BP02 |
| Managed service ratio | managed-service resources ÷ total resources | SUS05-BP03 |
| Idle resource count | resources with < 5% utilization over 30 days | SUS02-BP03, SUS03-BP02 |

For AI/ML workloads, add the inference, training, and token KPIs from
`references/ai-ml-workloads.md` as a separate table. Never convert tokens, inferences, or
training runs into MTCO2e.

**Sanity-check emissions against topology before reporting both.** The check is relative:
AWS publishes no emissions factor per vCPU-hour, so never judge a figure against an absolute
grams-per-vCPU-hour value. Run three tests:

1. **Zero against a fleet.** Every scope, LBM included, is at or below the reporting threshold
   in months where the topology shows a sizeable provisioned fleet (thousands of vCPU-hours a
   month or more). Scope 2 MBM alone can legitimately be near zero; LBM and Scope 3 should not be.
2. **Shares that don't line up.** When emissions are grouped by account or Region, compare each
   group's share of emissions with its share of provisioned vCPU-hours. A group holding most of
   the provisioned capacity but a negligible share of emissions, or the reverse, fails the test.
3. **Broader coverage.** Emissions for accounts or Regions the topology does not cover are
   normal: the emissions cover a broader scope. Say so; this test never fails.

A failed test 1 or 2 means the two datasets do not describe the same system — most often the
emissions cover a whole payer account or a different account while the topology covers one
workload, or the file is sample data.

When a test fails, do **not** reconcile them, average them, or pick the one
that looks more credible. Report the KPIs as the assessment, report the emissions figure with
its source and scope stated, and add an explicit finding that the two inputs cover different
scopes and the emissions figure cannot be read as this workload's footprint. Emissions
covering a broader scope than the topology is normal and expected — say that plainly rather
than treating it as an error in either input.

### 6.1 Cost vs Carbon Divergence Check

Explicitly test whether cost is tracking resource intensity. Where they diverge, the
divergence is a finding, because it means cost tooling will not surface the issue.

Cost data comes from `ce:GetCostAndUsage` over the same window as the KPIs. Whether the role
already has it depends on which managed policy it carries — `AIDevOpsAgentAccessPolicy` grants
it via `ce:Get*`, `AIOpsAssistantPolicy` does not. On `AccessDeniedException`, skip this
sub-step, state that the divergence check requires `ce:GetCostAndUsage`, and continue. Never
infer divergence from resource data alone.

Known divergence patterns to check for:

| Pattern | Test | Why cost is blind |
|---------|------|-------------------|
| Volume discounts / commitments | Cost per unit falling while vCPU-hours per unit flat or rising | Discount reduces spend, not resource consumption |
| Free inbound transfer | High inbound GB with no corresponding cost line | Inbound is free; the resource use is real |
| Cheap-but-carbon-intense Region | Region with low $/hour but high grid intensity | Price and grid intensity are unrelated |
| Growth masking regression | Absolute resource use rising while cost-per-unit improves | Efficiency per unit improved; absolute footprint grew |
| Reserved / committed idle capacity | Paid-for capacity running at low utilization | Already paid, so no cost signal to optimize |

If you find no divergence, say so plainly. In many workloads cost and carbon do track
each other, and claiming a divergence that isn't there undermines the whole report.
