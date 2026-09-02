# FSx for Windows SLA — Operational Depth

The reasoning behind every threshold and finding. This is the "why" the analyzer can
draw on to explain findings; the enforced rules live in `references/finding-logic.md`.
All guidance here is grounded in AWS documentation (URLs at the end).

## The availability model

FSx for Windows publishes a **99.9% availability SLA**, but the SLA is only
meaningful when the file system is configured for it. Two deployment types offer
very different real-world availability:

- **Single-AZ** (`SINGLE_AZ_1`, `SINGLE_AZ_2`): one Windows file server + storage in
  a single AZ. Data is replicated within the AZ and AWS auto-replaces failed
  hardware, but there is **no standby and no automatic cross-AZ failover**. Expect
  ~30 minutes of downtime during failure-recovery events **and** during the weekly
  maintenance window. In rare multi-component or non-graceful failures, the file
  system can be **unrecoverable** except by restoring from a backup — which is why
  backups (dimension 5) matter most for Single-AZ.
- **Multi-AZ** (`MULTI_AZ_1`): an active + standby file server across two AZs using
  Windows Server Failover Clustering (WSFC), with **synchronous** replication
  between AZs. During planned maintenance or an active-server/AZ failure, FSx fails
  over to the standby automatically, so clients keep access.

**Why dimension 1 is a Warning, not Critical, for Single-AZ:** a Single-AZ file
system is a legitimate, supported choice for dev/test or cost-sensitive workloads —
it is not broken. It is a weaker availability posture, so it caps the rating at
Medium rather than declaring an outage. AWS Security Hub codifies the production
recommendation as control **FSx.5** ("should be Multi-AZ", Medium severity), backed
by AWS Config rule `fsx-windows-deployment-type-check`.

**Why the remediation is "create + migrate", never a toggle:** the deployment type
is fixed at creation. You cannot convert Single-AZ to Multi-AZ in place. Moving to
Multi-AZ means standing up a new file system and migrating data (AWS DataSync, or a
robocopy cutover), then repointing clients — usually via the file system's DNS
alias to minimize client reconfiguration.

## The Active Directory dependency (dimension 2)

FSx for Windows is domain-joined and depends on Active Directory for
authentication. When FSx cannot reach the domain controllers, the file system enters
the **`MISCONFIGURED`** lifecycle state — in which it is "either unavailable or at
risk to lose availability, and backups might not succeed." That is why a
`MISCONFIGURED` state is a **🔴 Critical** availability finding, not a warning.

`MISCONFIGURED` is almost always caused by a change in the customer's AD
environment. The three documented root causes:

1. **Network reachability** — security groups or network ACLs no longer allow the
   required ports to the DNS servers / domain controllers.
2. **Invalid service-account credentials** — the FSx service account password
   changed or expired.
3. **Insufficient service-account permissions** — the account lost the right to
   join the file system to (or manage it within) the target Organizational Unit.
   Related pitfall: **moving the OU objects FSx created** after creation will push
   the file system into `MISCONFIGURED`.

**Diagnosis path:** the public `AWSSupport-ValidateFSxWindowsADConfig` Systems
Manager automation runbook launches a temporary EC2 instance in the file system's
subnet(s) and runs AWS's FSx AD validation script, testing exactly these
reachability/credential/permission conditions. It is the recommended first step to
pinpoint the cause before updating the AD configuration. (This is a public AWS
Support runbook — safe to recommend.)

**AWS Managed AD vs self-managed:** when the file system uses AWS Managed Microsoft
AD, the associated directory has its own health `Stage` (`Active` is healthy;
`Impaired` / `Inoperable` / `RequestedFailed` indicate a directory problem that will
cascade to the file system). For self-managed AD there is no Directory Service
object to read, so the file system `Lifecycle` (`MISCONFIGURED`) is the primary
signal. The skill never connects to the customer's domain controllers directly.

## Throughput capacity sizing (dimension 3)

AWS's sizing guidance: **provision enough throughput to support your workload's read
throughput plus twice your workload's write throughput.** Writes are more expensive
on FSx for Windows because Multi-AZ replicates every write synchronously to the
standby, so the "2×" reflects the replication cost of writes.

So the required estimate is:

```
required_mbps ≈ avg_read_mbps + 2 × avg_write_mbps
```

computed from `DataReadBytes` and `DataWriteBytes` over the lookback window
(converted to average MBps). When provisioned throughput is at or below this
estimate, requests get throttled and clients experience latency, timeouts, and
disconnects — availability symptoms even though the file system is technically
"up". That is why undersized throughput is a ⚠️ Warning.

Throughput capacity is an **online, in-place** change (a brief failover occurs on
Multi-AZ during the update), so the remediation is low-friction: raise it. This is
the opposite of the deployment-type change.

**Metrics caveat:** the richer network/CPU throughput metrics are only published for
file systems with `ThroughputCapacity >= 32` MBps. Below that, the skill notes
limited metrics rather than treating their absence as a finding.

## Storage capacity headroom (dimension 4)

AWS recommends **maintaining at least 20% free storage capacity at all times** —
"using all of your storage capacity can negatively impact your performance and might
introduce data inconsistencies." So:

- `< 10%` free → 🔴 Critical (writes can fail; direct availability risk)
- `10–20%` free → ⚠️ Warning (below guidance)
- `≥ 20%` free → ✅ Pass

Use the **worst-case** free point (`Minimum(FreeStorageCapacity)`) in the window,
not the average, so a periodic spike toward full is not masked. Storage capacity
increases are online and in-place; AWS also provides a dynamic-scaling
CloudFormation template that auto-increases capacity when `FreeStorageCapacity`
drops below a threshold — a good remediation pointer.

## The cost-vs-SLA tradeoff (why dimensions 3 & 4 carry 💰 notes)

Utilization is two-sided. High utilization risks the availability problems above;
**very low utilization wastes money** on capacity you provisioned and pay for
continuously. Because the skill already measures utilization for the SLA checks,
reading it from the low end is nearly free:

- **Throughput over-provisioned** (provisioned ≫ read + 2× write, e.g. 4×+): a
  candidate to lower — throughput is adjustable online, so realizing the saving is
  easy.
- **Storage over-provisioned** (large sustained idle headroom, e.g. >70% free):
  harder to realize, because storage can only be **increased**, not decreased.
  Right-sizing means migrating to a smaller file system, so the note weighs the
  migration effort against the ongoing saving. If the workload is throughput-light
  and latency-tolerant and sits on SSD, HDD storage is materially cheaper and worth
  flagging.

**Design rule:** cost notes are advisory. They never lower the SLA Readiness rating,
because a right-sizing opportunity is not an availability defect. A file system can
be **High** on SLA and still carry a 💰 note — that is exactly the "safe but
wasteful" case the review is meant to surface.

## Backups, maintenance, alarms (dimensions 5–7)

- **Backups (5):** automatic daily backups are the recovery path from a Single-AZ
  unrecoverable failure and from accidental data loss. Retention of 0 means no daily
  recovery point. Match retention to your RPO (commonly 7–35 days) and schedule the
  daily backup outside peak hours.
- **Maintenance window (6):** on Single-AZ, the weekly maintenance window is a
  planned outage, so its placement matters — keep it off business-critical hours. On
  Multi-AZ, maintenance fails over to the standby, so the exposure is lower but a
  window should still be set explicitly rather than defaulted.
- **Alarms (7):** without CloudWatch alarms (at minimum on `FreeStorageCapacity`),
  the operator learns about low storage, throughput saturation, or a `MISCONFIGURED`
  state only after users are affected. EventBridge + Lambda can additionally notify
  on file-system health state changes. Observability is what turns the other six
  dimensions from "hope" into "know".

## Grounding sources

- Availability and durability: Single-AZ and Multi-AZ file systems —
  https://docs.aws.amazon.com/fsx/latest/WindowsGuide/high-availability-multiAZ.html
- Why is my FSx for Windows File Server in a Misconfigured state? —
  https://repost.aws/knowledge-center/fsx-windows-misconfigured-state
- Validate your Active Directory configuration for Amazon FSx
  (`AWSSupport-ValidateFSxWindowsADConfig`) —
  https://repost.aws/knowledge-center/fsx-validate-ad-configuration
- Managing storage capacity (20% free guidance + dynamic scaling) —
  https://docs.aws.amazon.com/fsx/latest/WindowsGuide/managing-storage-configuration.html
- Monitoring with Amazon CloudWatch (AWS/FSx metrics) —
  https://docs.aws.amazon.com/fsx/latest/WindowsGuide/monitoring-cloudwatch.html
- Security Hub control FSx.5 (Multi-AZ) —
  https://docs.aws.amazon.com/securityhub/latest/userguide/fsx-controls.html
