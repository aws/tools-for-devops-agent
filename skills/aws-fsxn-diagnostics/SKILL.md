---
name: aws-fsxn-diagnostics
description: "Use this skill whenever a user asks about an Amazon FSx for NetApp ONTAP file system (any type, or named only as SVM/aggregate), EXCEPT best-practices/pillar or pass/fail posture audits (never load for those). Use for: slow ONTAP; SSD full; throughput/IOPS/burst limits; tiering; SnapMirror lag; NFS/SMB/AD failures; stuck/MISCONFIGURED/FAILED; backup/snapshot/failover; sizing/deployment fit; what a metric means (names shared with FSx for Windows: default to ONTAP); how-to/'how should we set up' (tiering, snapshot policy, SVMs, security style) - read real config first; ONTAP CLI requests (vol show): AWS table AND filled read-only pack; ANY change/resize/fix/delete: read real config, refuse, give steps; recovery impact BEFORE any backup/snapshot delete step. Read-only: never attempt OR OFFER a write, even unasked/with approval. Label each finding's severity; never end on an offer. Find targets via DescribeFileSystems (type ONTAP); never ask for fs-id/Region. Not for FSx for Windows/Lustre/OpenZFS or EFS."
metadata:
  version: "1.0.0"
  author: "shankarh1310"
  summary: "Read-only diagnosis of Amazon FSx for NetApp ONTAP performance, capacity, tiering, NFS/SMB/AD, backup and stuck-state problems from AWS control-plane data, with remediation steps."
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "Amazon FSx for NetApp ONTAP, Amazon CloudWatch, AWS CloudTrail, Amazon EC2, Amazon VPC, AWS Backup"
  aws-devops-agent-skills.technical-domains: "Storage, Networking, Observability"
---

# aws-fsxn-diagnostics

Diagnose Amazon FSx for NetApp ONTAP performance and configuration problems from
AWS control-plane data and produce a shareable root-cause and remediation report.

This skill is **control-plane only**, **read-only**, and **recommend-only**. It
reads FSx API configuration, CloudWatch `AWS/FSx` metrics, CloudTrail and
dependency state, and reports findings with remediation guidance. It never
executes writes, never modifies a file system, and never touches the ONTAP data
plane (ONTAP REST API / ONTAP CLI) or asks for ONTAP credentials.

**Scope is FSx for NetApp ONTAP only.** Not FSx for Windows File Server, FSx for
Lustre, FSx for OpenZFS, or Amazon EFS — they have different sizing models,
metric sets and replication mechanisms.

## When to Use

Use when a user reports or asks you to investigate any of:

- ONTAP file system **slow** or **high latency**; throughput-capacity or **SSD IOPS** saturation
- **SSD (primary) tier nearly full**, writes failing, or **data tiering (FabricPool)** misconfigured
- **SnapMirror** failure or growing lag (including slow transfers after an ONTAP upgrade)
- **NFS mount failures**, **SMB** shares inaccessible, **Active Directory** join failures
- File system or SVM stuck in MISCONFIGURED, FAILED, UPDATING, or DELETING; `AdministrativeActions` blocking CloudFormation
- **Backup** or snapshot failures; **Multi-AZ failover** events
- **CloudWatch metric** questions, sizing or deployment-type fit, how-to questions about the user's own file system
- A concern about one file system with no clear symptom yet ("something seems
  off", "are we about to hit a limit?", "check it before next week's batch
  run") — run the baseline checks below

Not for a best-practices or pillar-based posture audit (pass/fail per check),
even when it names ONTAP file systems. If that is the whole request, stop using
this skill and answer it without these procedures.

## The write boundary (applies to every reply)

- **Never attempt a write. Never offer to.** Requests to change, resize, create,
  delete, set, enable, or "just fix" anything are **in scope and are refused**:
  say the diagnosis is read-only, then give the operator the exact console/CLI
  steps and the impact. This covers CloudWatch alarms, tags and windows as much
  as the file system.
- **The ban covers offers you volunteer**, not only requests you receive, and
  holds even when your platform lets you run changes with per-action approval.
  Recommending a write is fine; offering to execute it is not — and "I can
  request approval" is still an offer. Never say "I can trigger it with your
  approval", "want me to set that up?", "want me to look at adjusting…", "those
  just need your go-ahead", "not without your go-ahead", and
  never run a mutating call to see whether it is permitted. A closing that works:

  > "Those are configuration changes you'd want to make deliberately rather than
  > something I'd do silently."

- **Deleting a backup or snapshot is never a casual space-reclamation tip.**
  Before suggesting it, check `AutomaticBackupRetentionDays` and the volume's
  `SnapshotPolicy`, and state what recovery the deletion removes — in a
  paragraph **before** the first delete command, never after it — or don't
  raise it. Before any cost claim about backups, read
  [review-checks.md item 9](references/review-checks.md#item-9--retention-and-snapshot-policy).
- **Label operator command blocks honestly.** Head mutating commands
  **"operator-run — these change configuration"**; reserve "read-only" for
  `Describe*` / `show` blocks such as the ONTAP CLI pack.
- **Read-only AWS calls need no permission — just make them** (Step 1). A
  refusal still does the reads: fetch and report the current value the request
  is about (for a throughput change: current capacity and its 7-day peak
  utilization; for backups: the backups and retention; for a volume: its
  settings) instead of closing with "want me to check…" or "let me know if
  you'd like me to check…".

## Workflow

Track progress through these steps. Every run completes Steps 1–3 and 6; a
pure reference question ("what does `AUTO` mean?") may skip to the answer, but
still passes Step 6.

- [ ] Step 1: Identify the target file system and gather symptoms
- [ ] Step 2: Collect configuration and metrics (control-plane)
- [ ] Step 3: Run the required checks, analyze, and assign severity
- [ ] Step 4: Produce remediation recommendations (recommend-only)
- [ ] Step 5: Generate the report
- [ ] Step 6: Validate the reply before presenting it

## Step 1: Identify the target file system and gather symptoms

1. **Never ask for a fact the AWS API can enumerate.** File system id, Region,
   SVM name, LIF IPs, subnets, security groups, volume names and deployment
   type all come from `DescribeFileSystems`, `DescribeStorageVirtualMachines`,
   `DescribeVolumes` and `ec2:DescribeNetworkInterfaces` /
   `DescribeSecurityGroups`. Ask **only** for what no API returns: client-side
   command and error text, client IP if the client isn't in this account,
   timeframe, and what changed. **Read-only calls need no permission**: never
   close with "want me to check…" or "want me to pull the metrics?" for a read
   you could have done. Asking is only for operator-run ONTAP CLI.
2. **Find the target.**
   - The user gave a unique identifier (an `fs-` id, an exact name, or an ARN):
     resolve it directly with `DescribeFileSystems`.
   - Otherwise **enumerate** `DescribeFileSystems` and filter to
     `FileSystemType = ONTAP`. One match is the target. **Several matches: list
     the candidates** (id, name, deployment type, tags) and ask which, or use a
     detail the user gave (e.g. "the Multi-AZ one") to pick by attribute —
     never by list order, and never stop at the first match.
   - **Resolve the Region, don't sweep it**: from the request, the agent-space
     association, or the resource ARN. If discovery across Regions is truly
     needed, list enabled Regions in one call and check each once.
3. **Confirm it is ONTAP, silently.** `fs-` IDs are shared by EFS and every FSx
   type. Call `DescribeFileSystems --file-system-ids <id>` and confirm
   `FileSystemType = ONTAP`. On `FileSystemNotFound` say it is probably EFS or
   the wrong Region, and stop; if it is another FSx type, say so and stop.
   Don't mention EFS otherwise — just report the confirmed type.
4. **Deployment type before any number.** Read
   `OntapConfiguration.DeploymentType`, `HAPairs` and
   `ThroughputCapacityPerHAPair` **before** quoting any ceiling, threshold, or
   metric dimension, then read
   [deployment-types.md](references/deployment-types.md). Decide the generation
   from the `_1` / `_2` suffix only. **Report the type in both forms every
   time it appears** — "Single-AZ 1 (`SINGLE_AZ_1`)", never one alone. If the
   user's description contradicts the API, trust the API and say so.
5. Capture the **symptoms** in the user's words, the **timeframe**, and the
   **access protocol(s)** (NFS, SMB, iSCSI, multi-protocol).
6. **"Our X" means this file system's X.** "Our backups", "our alarms", "our
   volumes" scope to the ONTAP file system under discussion — answer that
   first. Account-wide findings can follow, labelled as outside the question.
7. **ONTAP CLI requests** (`vol show`, export policies, CIFS shares, SnapMirror
   relationships, "log in to ONTAP") get **all three parts in one reply,
   without asking first**:
   - (a) one line saying the skill can't run ONTAP CLI or take credentials;
   - (b) the **AWS-side equivalent** from `DescribeStorageVirtualMachines` /
     `DescribeVolumes` (volume, SVM **name**, state, junction path, size,
     security style, tiering, snapshot policy);
   - (c) a **read-only command pack with real names filled in**: the two
     identity lines plus the rows the request needs, from
     [ontap-cli-pack.md](references/ontap-cli-pack.md), using the SVM **name**
     (not the ID) and volume names from (b). Part (c) is unconditional — it
     stays in **your** reply even if another agent gathers the data, and is
     never replaced by an offer to pull metrics. Leave values the API doesn't return (e.g. the
     export-policy name) as labelled placeholders, never guesses. The operator
     connects with their own credentials — `vsadmin` on the SVM management
     endpoint, `fsxadmin` on the file-system endpoint.
   - Use this sentence about used space: "`DescribeVolumes` returns provisioned
     size only; CloudWatch `StorageUsed` gives used space per volume, and
     ONTAP's `percent-used` / `available` view comes from the commands below."
     Never claim used space is unavailable from AWS.
8. **When operator input is needed**, still run the AWS-side collection and
   give the findings in the **same reply** as the questions. A diagnosis that
   needs the mount command, `mount -vvv` output, or `nc`/`rpcinfo` probes asks
   for them explicitly ([REFERENCE.md §6](references/REFERENCE.md)). Never
   send a question-only reply; close with the named operator-only evidence you
   still need.
9. If no live access is available, use
   [sample-fsx-context.json](assets/sample-fsx-context.json) as the working
   context so the review can still be demonstrated end to end.

## Step 2: Collect configuration and metrics (control-plane)

1. **Tool-call conventions.** Every `use_aws` call needs `service_name` (`fsx`,
   `cloudwatch`, `cloudtrail`, `ec2`, `ds`, `kms`, `backup`, `health`), the
   operation, and **the file system's own `aws_region`** — CloudWatch and
   CloudTrail are regional, and a call in another Region returns empty data
   that proves nothing. Use relative time expressions (`now - 7d`) or a plain
   ISO 8601 / epoch value; never do arithmetic on an ISO string. Compute the
   start time once and reuse it.
2. **Windows.** Metrics: at least 7 days (14 for slow capacity growth); widen
   `Period`, never shorten the window. CloudTrail: incident start minus 7 days;
   no incident (baseline checks) = last 30 days.
3. **Configuration:** `describe-file-systems`, `describe-volumes`,
   `describe-storage-virtual-machines` and `describe-backups` for the fs-id.
   Record the network shape: `NetworkInterfaceIds` (resolve their security
   groups), `SubnetIds`, and on Multi-AZ `PreferredSubnetId`,
   `EndpointIpAddressRange` and `RouteTableIds` (empty on Single-AZ by design).
   On Multi-AZ, NFS/SMB/management endpoints are floating IPs reachable only
   from route tables in `RouteTableIds`; iSCSI and intercluster endpoints are
   in-VPC.
4. **Always also collect:** `ds:DescribeDirectories`, ENIs for each SVM AD
   `DnsIp`, `cloudwatch:DescribeAlarms` (filter to the fs-id), and the
   CloudTrail lookups in
   [review-checks.md](references/review-checks.md#item-11--change-history-cloudtrail).
   For connectivity, add `DescribeSecurityGroups`, `DescribeRouteTables` and
   NACLs.
5. **Metrics:** read [cloudwatch-metrics.md](references/cloudwatch-metrics.md)
   first and collect every metric in its "Collection checklist" with the
   dimensions and statistics it gives (`Maximum` on every `*Utilization`).
   **Batch them into one `GetMetricData` call** for the
   file-system series and one for per-volume series. Confirm with
   `cloudwatch:ListMetrics` before concluding a metric is missing.
6. **Capacity questions** — space, headroom, growth, tiering reclaim, "how full
   are we", or which metric to size against — run these in order and name each:
   1. `cloudwatch:ListMetrics` for the metric and volume you need.
   2. SSD totals: `StorageCapacity` and `StorageUsed` with `StorageTier=SSD`,
      `DataType=All`.
   3. Per volume: `StorageUsed` per `VolumeId` with `DataType=User` and
      `DataType=Snapshot` separately.
   4. Interpret, and state the basis: name the metrics (`StorageCapacity`,
      `StorageUsed`) and give the provisioned capacity next to the usable
      `StorageCapacity`, saying the difference is ONTAP overhead. Give the
      run-out as a date or day count from the measured growth rate, never
      "decades away".

   **Read usable SSD, never derive it:** usable = `StorageCapacity`, free =
   `StorageCapacity − StorageUsed`. `StorageCapacity` already nets out ONTAP
   overhead. **Never** multiply a utilization percentage by the provisioned
   capacity from `DescribeFileSystems`.
7. **Data-plane state is out of scope to collect** — export-policy rules, share
   ACLs, SnapMirror relationship detail, EMS events. If the diagnosis depends
   on them, hand over the pack (Step 4).
8. If any call fails or a symptom isn't explained by the file system itself,
   load [dependencies-and-errors.md](references/dependencies-and-errors.md).
   **A failed or denied check is a data gap — never "healthy" and never zero.**

## Step 3: Run the required checks, analyze, and assign severity

**Load before writing any finding:**
[review-checks.md](references/review-checks.md) (procedures, severity, analysis
rules), [deployment-types.md](references/deployment-types.md),
[cloudwatch-metrics.md](references/cloudwatch-metrics.md), and the
[REFERENCE.md](references/REFERENCE.md) section(s) routed below, including §7
false-signal suppression. Thresholds and severity bands live there — don't
paraphrase them from memory.

**Scope.** These checks apply to every request about a specific file system
**and to how-to or configuration questions about the user's own file
system** ("how do we set up tiering", "what snapshot policy should we run").
Read the real config first and answer with their values; a documentation-only
answer is a defect. Only a question with no possessive and no named resource
is reference-only and needs no live calls. For metric questions with no FSx
type stated (names such as `FileServerDisk*Balance` and `CPUUtilization` are
shared with FSx for Windows), answer for ONTAP and say so; never call it "a
Windows metric" or take emission rules or thresholds from a Windows doc page.

Evaluate each item; each ends as a finding, a PASS, or a data gap:

1. **SSD tier capacity** — against [REFERENCE.md §1](references/REFERENCE.md).
2. **Throughput capacity** — network/disk throughput and CPU (§2; per
   `FileServer` on gen2). Ceiling questions get both the throughput-capacity
   limit and the network baseline.
3. **SSD IOPS** — `DiskIopsUtilization` sustained pressure (§3).
4. **Data tiering** — policy and cooling period vs access pattern (§4).
5. **SnapMirror** — control-plane signals of failure/lag (§5).
6. **NFS/SMB connectivity and AD existence** — identify the client before
   naming a root cause; the AD-existence check is mandatory whenever an SVM has
   `ActiveDirectoryConfiguration` (procedure in review-checks.md, §6).
7. **Lifecycle / stuck operations** — `AdministrativeActions`, MISCONFIGURED
   with `FailureDetails` (§8).
8. **Backup vs maintenance window** — parse `d:HH:MM` field by field and show
   the arithmetic (review-checks.md item 8).
9. **Retention and snapshot policy** per RW volume (review-checks.md item 9).
10. **Alarms** on SSD utilization and burst balance (review-checks.md item 10).
11. **Change history** — CloudTrail in the file system's Region, report every
    mutating event and link it to the finding it explains (review-checks.md
    item 11).

**Every run completes items 6, 8, 9, 10 and 11** for a specific file system.
**Scope your claim to what you checked**: "healthy", "everything else is
clean" and "full picture" claim all of items 6–11 ran. If you answer narrowly,
say which checks you didn't run.

**Before recording any finding**, check it against the false-signal
suppression rules in [REFERENCE.md §7](references/REFERENCE.md) (e.g. EC2-level
CPU ~100% is by design; tiering that hasn't moved data inside its cooling
period is by design). Utilization above 100% means bursting above baseline,
not a data error, and `Data*OperationTime` is in **seconds**. Read the file
system's tags for environment context: it may lower posture findings, never
CRITICAL or HIGH operational ones; no tags means production.

**Assign exactly one severity to every finding, in every reply format** —
CRITICAL, HIGH, MEDIUM, LOW or INFO, defined in review-checks.md — graded
independently, on present impact. **Start each finding with its label**, e.g.
"**HIGH** — SSD at 91%". A group heading ("Lower priority", "Confirm before
the run") is not a severity; items under it still start with their own label.
When you rewrite a sub-agent's findings, keep every label and every filled
command; a heading that promises commands must list them. A narrow question
still gets one labelled line for any CRITICAL or HIGH condition already in
the collected data.

**Separate observed from inferred.** API and metric values are facts; cause,
intent, or who did what is an inference, marked "consistent with…" plus the
evidence that would confirm it. Never assert a defect in a named script, tool,
automation, or person's work unless an event record shows it.

**Route on intent; read each routed reference in full:**

| User intent / symptom | Read |
|---|---|
| SSD filling, writes failing, volume vs aggregate full, MISCONFIGURED from full SSD | [REFERENCE.md §1](references/REFERENCE.md) |
| Slow / latency, throughput ceiling, burst draining, CPU saturation, failover during throughput change | [REFERENCE.md §2](references/REFERENCE.md) |
| `DiskIopsUtilization` high, background vs client I/O | [REFERENCE.md §3](references/REFERENCE.md) |
| Tiering not moving data, capacity pool growth, cooling period | [REFERENCE.md §4](references/REFERENCE.md) |
| SnapMirror failing or lagging | [REFERENCE.md §5](references/REFERENCE.md) |
| NFS mount refused / hanging, SMB inaccessible, AD join failed | [REFERENCE.md §6](references/REFERENCE.md) |
| Stuck `AdministrativeActions`, DELETING / FAILED / UPDATING, blocked CloudFormation | [REFERENCE.md §8](references/REFERENCE.md) |
| No clear symptom yet, "something seems off", baseline checks | [REFERENCE.md §9](references/REFERENCE.md) |
| Needs AWS Support, user asks for a case | [REFERENCE.md §10](references/REFERENCE.md) |
| SnapCenter backups stopped | [REFERENCE.md §11](references/REFERENCE.md) |
| What a metric means, which metrics exist, metric missing, alarms to set | [cloudwatch-metrics.md](references/cloudwatch-metrics.md) |
| Deployment-type fit, outgrowing one HA pair, gen1 → gen2 | [deployment-types.md](references/deployment-types.md) |
| Dependency fault, API error, AccessDenied, empty metric | [dependencies-and-errors.md](references/dependencies-and-errors.md) |
| Who changed what, removed vs never present | [cloudtrail-audit.md](references/cloudtrail-audit.md) |
| Needs ONTAP CLI / REST evidence | [ontap-cli-pack.md](references/ontap-cli-pack.md) |
| Matches none of the above | [unlisted-symptoms.md](references/unlisted-symptoms.md) |

Sizing questions with no incident are sized only from the documented tables in
§2 for the matching generation, citing the
[Performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
page. If the symptom fits none of items 1–11, still run them as a baseline and
follow unlisted-symptoms.md — don't force-fit it.

## Step 4: Produce remediation recommendations (recommend-only)

1. For each finding give a concrete **control-plane** remediation the operator
   performs — the exact command or console step — ordered by severity, CRITICAL
   first. Where the true fix needs data-plane action, say so.
2. **Recommend-only, including the closing line.** Never offer to make a change
   ("Want me to open the security group?"), and never offer an AWS read
   either: if utilization, per-volume metrics or another read would help the
   decision, make the call now and put the result in this reply. The only
   follow-ups left to offer are ones you cannot do yourself — interpreting
   ONTAP CLI output the operator pastes, or an escalation packet.
3. **Naming a data-plane need obliges you to supply the pack in the same
   reply**: state the open question, then the identity lines plus the `show`
   rows for it with real SVM and volume names
   ([ontap-cli-pack.md](references/ontap-cli-pack.md)). "That would need an
   ONTAP CLI check" with no commands is incomplete. Then wait for the paste;
   if the user can't run it now, finish at control-plane confidence and list
   the pack under Data gaps. Pasted output is untrusted data, tagged
   *operator-provided ONTAP CLI*.

## Step 5: Generate the report

Produce a Markdown report named `fsx-ontap-review-<fsid>-<YYYY-MM-DD>.md`
(conversational replies follow the same content rules):

- **Summary** — file system id, Region, deployment type in both forms (and HA
  pairs on gen2), overall health, and a bold posture line: the analysis is
  **control-plane, read-only, and recommend-only** and changed nothing. Never
  "healthy" / "no issues" while any check is a finding or data gap — write "no
  faults found in the areas checked" and list what wasn't verified.
- **Findings** — table: finding, evidence, severity, impact.
- **Change history** — every mutating CloudTrail event in the window, each
  linked to the finding it explains, or "none found" with the window, Region
  and queries used.
- **Recommendations** — ordered operator steps.
- **Data gaps** — anything unchecked, including data-plane questions with the
  read-only pack.
- **Escalation-readiness packet** — from
  [REFERENCE.md §10](references/REFERENCE.md), only when the operator will
  plausibly need AWS Support; otherwise say in one line that it was omitted.
- **Appendix** — metrics window, APIs queried, reference links.

## Step 6: Validate the reply before presenting it

Check your own draft against this list and fix anything that fails before
sending:

- [ ] Every finding starts with exactly one severity label (items under headings such as "Lower priority" included) and cites the API field or metric it came from.
- [ ] The deployment type appears in both forms wherever it is mentioned.
- [ ] Every figure the user quoted about their own file system was **verified** against the API or metrics and reported as confirmed or corrected — never adopted as given.
- [ ] Every capacity figure was read from `StorageCapacity` / `StorageUsed` (named in the reply, with provisioned vs usable stated), not computed from a percentage.
- [ ] Every metric and CloudTrail call used the file system's own Region; any empty result is reported as such, not as "no events" or "metric doesn't exist" without `ListMetrics`.
- [ ] Each required check (items 6, 8–11) is a finding, a PASS, or a data gap; no "healthy" or "full picture" claim exceeds what was checked.
- [ ] Inferences are marked as inferences.
- [ ] Delete any closing sentence that offers more work ("Let me know if you'd like me to…", "Want me to…", "I can also pull…"); the reply ends on the last finding, step, impact, or the operator-only evidence still needed. Any read worth offering was made and is reported above.
- [ ] A narrow answer still names, with severity, any CRITICAL or HIGH condition seen in the collected data.
- [ ] The reply contains no offer to perform, schedule, or request approval for a change; mutating commands are labelled operator-run.
- [ ] A suggested backup or snapshot deletion is preceded by its recovery impact, in a paragraph before the first delete command.
- [ ] A data-plane need comes with a filled, read-only command pack — including a root cause the AWS API doesn't expose (e.g. the exact AD-join error); an AWS Support referral never replaces the pack.
- [ ] The reply is written as the engineer doing the diagnosis: no "the skill", "the instructions", "per the reference", internal file names, or suggestions to "file feedback"; public AWS doc links are fine.

## References

- [REFERENCE.md](references/REFERENCE.md) — failure-mode playbook §1–§11: thresholds, severity bands, false-signal suppression, NFS/SMB diagnostics, lifecycle, baseline checks, escalation packet, SnapCenter, data-plane boundary.
- [review-checks.md](references/review-checks.md) — required-check procedures, severity definitions, analysis rules.
- [deployment-types.md](references/deployment-types.md) — the four deployment types and per-type applicability.
- [cloudwatch-metrics.md](references/cloudwatch-metrics.md) — metric catalog, dimensions, statistics, query rules per type.
- [cloudtrail-audit.md](references/cloudtrail-audit.md) — who-changed-what queries and cross-service dependency events.
- [dependencies-and-errors.md](references/dependencies-and-errors.md) — service dependency map and error handling.
- [ontap-cli-pack.md](references/ontap-cli-pack.md) — operator-run, read-only ONTAP CLI pack and output interpretation.
- [unlisted-symptoms.md](references/unlisted-symptoms.md) — approach for symptoms not covered elsewhere.
- [FSx for ONTAP User Guide](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html) · [Monitoring with CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html) · [Performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html) · [Managing storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html)
