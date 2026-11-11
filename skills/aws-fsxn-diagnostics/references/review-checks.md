# Required Review Checks — Procedures, Severity and Analysis Rules

**Sources:** public AWS FSx for NetApp ONTAP documentation (`docs.aws.amazon.com`) and live validation. Read-only, control-plane.

Load this file on every run that touches a specific file system (SKILL.md
Step 3). It holds the detailed procedure behind each required check, the
severity definitions, and the analysis rules. Every check ends as a finding,
a PASS, or a data gap.

## Severity definitions

| Severity | Meaning | First-response SLA |
|----------|---------|-------------------|
| CRITICAL | Active or imminent outage / data-loss risk (SSD at/near 100%, writes failing, replication broken) | 1 hour |
| HIGH | Serious degradation likely to become outage soon (SSD >85%, sustained throughput/IOPS saturation, growing SnapMirror lag) | 4 hours |
| MEDIUM | Degradation or misconfiguration affecting performance/cost but not imminent | 1 business day |
| LOW | Minor deviation from best practice; optimization opportunity | 3 business days |
| INFO | Observation / no action required | Best effort |

- Assign a severity to **every** finding in **every** reply format — prose
  replies as well as the report artifact. If you state a finding, its severity
  goes with it, at the **start** of the finding ("**LOW** — backup retention is
  1 day"): a section heading such as "Lower priority" or "Confirm before the
  run" does not count. Keep the labels when a sub-agent's findings are
  rewritten into the final reply.
- Grade on **present** impact. A finding whose impact is not currently being
  exercised is graded on present impact and called *latent* — e.g. a broken AD
  on a file system with no active SMB clients is MEDIUM and latent, not HIGH.
- Assign each finding's severity **independently**. Do not downgrade a signal
  because another finding is more severe.
- Severity is never raised to justify including the escalation packet.
- A narrow question (one metric, one capacity figure) still ends with one
  labelled line for any CRITICAL or HIGH condition already in the collected
  data — a MISCONFIGURED or FAILED file system or SVM, or a failed
  `AdministrativeActions` entry — marked as outside the question.

## Item 6 — NFS/SMB connectivity and the client path

Security-group rules, route table, SVM endpoint, and NFS first-touch intake
([REFERENCE.md §6](REFERENCE.md)).

**Identify the failing client before naming a root cause.** If the user hasn't
given the client's IP, subnet, or security group, every SG or route finding is
a **leading hypothesis**, not "found it" or "high confidence" — even when the
evidence is strong. In CHAT, present the hypothesis **and** in the same reply
ask for the client's private IP / subnet / attached SGs, the exact mount
command, `mount -vvv` output, and the portmapper/NFS/mountd reachability and
NFSv4.1 isolation probes from §6. Confirm the cause only once the client is
identified.

**Locate the client and its path before ruling anything out**
([REFERENCE.md §6 "Clients outside the VPC or account"](REFERENCE.md)):

- **Not finding the client in this account is not evidence that no client
  exists.** Clients in another account, a shared VPC (RAM), a peered VPC, or
  on-premises are invisible here. Ask where the client is, and record its side
  as a data gap.
- **SG rules that reference other security groups** match only same-VPC
  clients, same-Region peered VPCs (`account/sg-id` reference), and TGW
  clients **only when SG referencing is enabled on both the TGW and both VPC
  attachments** (never across TGW peering, not in `use1-az3`). DX, VPN,
  on-premises, cross-Region peering, and PrivateLink clients need a **CIDR
  rule**. An FSx SG whose rules are *all* SG references silently drops those
  clients, so flag it against the client's path.
- **Check both sides of the path:** routes to the FSx subnet from the client
  side and back, NACLs (including return traffic on ephemeral ports
  1024–65535), the peering connection / TGW attachment state, and TGW route
  tables. Client-side resources in another account are a data gap.
- **Intermittent / non-deterministic failures:** follow §6 "Intermittent
  access". Correlate failure times with failover, maintenance, throughput
  changes, and burst exhaustion. Use flow-log ACCEPT/REJECT over time. If flow
  logs are off, say the cause can't be determined from the control plane and
  recommend enabling them on the FSx ENIs and the client ENI, then reproducing.
- Where an SG looks correct but access still fails, query existing VPC flow
  logs for REJECT on the relevant ports (§6).
- Port and networking prerequisites per protocol:
  [File system access control with Amazon VPC](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limit-access-fsx-creating-security-groups.html).

## Item 6 — AD existence (mandatory whenever an SVM has `ActiveDirectoryConfiguration`, or is MISCONFIGURED with an AD-join failure message)

A failed join leaves `ActiveDirectoryConfiguration` **empty**, so the check
still applies: take the intended `DnsIps` / domain from the SVM's
`CreateStorageVirtualMachine` or latest `UpdateStorageVirtualMachine`
CloudTrail event (`requestParameters.activeDirectoryConfiguration`; the
password is omitted) and run (a)–(c) on them.

Take the SVM's `DnsIps` and check:

- (a) does a `ds:DescribeDirectories` directory list them in `DnsIpAddrs`, and
  what is its `Stage`?
- (b) does a live ENI own each IP (`ec2:DescribeNetworkInterfaces` filtered on
  `addresses.private-ip-address`)?
- (c) if neither matches: are the `DnsIps` inside the file system's VPC CIDR
  (`ec2:DescribeVpcs`)?
  - **Inside the VPC, and no ENI owns them → the domain controllers were
    deleted** (an IP in your own VPC with no ENI can't be a live DC). State it
    as a finding, not "may be unreachable".
  - **Outside the VPC** (on-premises, peered, or another VPC) → the AD is
    outside AWS visibility. Record a data gap and ask the operator to verify
    DC reachability.

**Attribution.** Look up CloudTrail `DeleteDirectory` and use the event
**after the SVM's `CreationTime`**; events before it are environment build or
teardown. If the DnsIps are in the VPC and such an event exists, **report it
as the most likely cause**, naming the caller (`userIdentity.arn`), time, and
`directoryId`. The DnsIp ↔ `directoryId` link can't be proven after deletion,
so state that once as a caveat; it doesn't downgrade the finding.

**Don't dismiss it:**

- not as "an AWS Managed AD, unrelated to this self-managed AD" — AWS Managed
  AD is joined through `SelfManagedActiveDirectoryConfiguration` too, so the
  field name tells you nothing;
- not as "cleanup" or "test harness" — who ran it doesn't change what it broke;
- SVM `Lifecycle=CREATED` is **not** evidence of AD health. A
  `Failed`/`Impaired` directory, not FSx, is the fault.

**Directory healthy but the join failed** (directory `Active`, SVM
MISCONFIGURED with "unable to create a storage virtual machine within the
specified Active Directory", no `Smb` endpoint): the cause is inside the join
(service-account rights, OU, DNS, ports on the SVM's iSCSI LIFs → DCs).

**Read ONTAP's own join error from CloudTrail first.** Look up the latest
`UpdateStorageVirtualMachine` event for the SVM (item 11) and read
`responseElements.storageVirtualMachine.ontapErrorMessage`. After a join
attempt it carries ONTAP's step-by-step result (which DC and port it reached,
and the failing step, e.g. LDAP bind `RESULT_ERROR_LDAPSERVER_INVALID_CREDENTIALS`).
Quote the failing step verbatim and base the cause on it. The field is not
populated on `CreateStorageVirtualMachine` (lifecycle is still `PENDING` in
that response). Only when no event carries the field is the exact error
ONTAP-only: then give the SMB/AD-join rows of
[ontap-cli-pack.md](ontap-cli-pack.md). Either way, don't assert a cause
neither source shows. Give the operator these options **in this order**:

1. Fix the prerequisite, then **retry the join on the same SVM**
   ([Joining SVMs to AD](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/join-svm-to-ad.html)).
   Volumes and NFS stay untouched. An SVM that never joined needs the **full**
   configuration, not only the corrected field: a username/password-only
   update applies to an SVM that is already joined.
   ```bash
   aws fsx update-storage-virtual-machine \
     --storage-virtual-machine-id <svm-id> \
     --active-directory-configuration 'SelfManagedActiveDirectoryConfiguration={DomainName=<domain>,OrganizationalUnitDistinguishedName="<ou>",FileSystemAdministratorsGroup=<group>,UserName=<service-account>,Password=<password>,DnsIps=[<dc-ip-1>,<dc-ip-2>]},NetBiosName=<netbios-name>'
   ```
   Copy this template exactly: keep the double quotes around the OU (a DN
   contains commas; unquoted, the CLI rejects the command), keep `DnsIps`
   in `[ ]`, and keep `NetBiosName` inside the `--active-directory-configuration`
   value — there is no `--netbios-name` flag.
   Fill the values from the SVM's last Create/Update `requestParameters`
   (CloudTrail omits the password) and tell the operator to supply the
   password from their secret store rather than typing it on the command line.
   Put this filled command in the reply itself, headed operator-run — never
   "I have the command ready if you want it".
2. If NFS on this SVM must not be disturbed while AD is worked on, create a
   **second SVM** for SMB.
3. Delete and recreate the SVM only as a last resort, and state first that its
   volumes must be deleted before the SVM can be, and what backups exist.

**Severity:** **HIGH if SMB is in use** (SMB client traffic observed, or the
user reports SMB clients); **MEDIUM if SMB is only configured** (an SMB/NTFS
volume exists, port 445 is open, but no client traffic is observed). An SMB
volume or open port by itself is "configured", not "in use". Zero
`Data*Operations` in the window → MEDIUM. State which one applied, and that it
rises to HIGH as soon as SMB clients exist.

## Item 7 — Lifecycle and stuck operations

`AdministrativeActions`, DELETING states, failed SSD shrink blocking
CloudFormation, patching failures. Also check for a **MISCONFIGURED**
`Lifecycle` with `FailureDetails`: a full SSD aggregate can put the file system
(or SVM) into MISCONFIGURED and make it refuse actions, surfacing as "can't
delete my volume/SVM"; the fix is an SSD capacity increase
([REFERENCE.md §1](REFERENCE.md), [§8](REFERENCE.md)).

## Item 8 — Backup vs maintenance window, computed

- `WeeklyMaintenanceStartTime` is `d:HH:MM`: **day, hour, minute**, with
  1 = Monday … 7 = Sunday. Parse field by field: `1:05:00` → day `1` (Monday),
  hour `05`, minute `00` → **Monday 05:00**, not 05:05.
- `DailyAutomaticBackupStartTime` is `HH:MM`, daily.
- Times of day within 60 minutes of each other = **overlap** on that weekday
  (`1:05:00` vs `05:00` → 0 minutes apart → overlaps every Monday) →
  **MEDIUM**; fix: separate the windows.
- Show the parsed values and the arithmetic in the evidence.
- Recent backups must be present **per RW volume** (only online
  `OntapVolumeType=RW` volumes are backed up).

## Item 9 — Retention and snapshot policy

- `AutomaticBackupRetentionDays=0` (backups off, existing automatic backups
  deleted) → **HIGH**.
- `1` day → **LOW**; state it against the RPO.
- An RW volume with `SnapshotPolicy=none` → **LOW**.
- Before anyone suggests deleting a backup or snapshot, state what recovery it
  removes, from these two values, in a paragraph before the first delete
  command.
- **Backup cost facts** (for "delete backups to save money"); never claim a
  backup is free or that deleting it saves nothing:
  - All FSx backups are **incremental**; deleting one removes only the data
    unique to it, so the saving is that unique changed data, not the
    backup's full size.
  - `AUTOMATIC` backups expire on their own after
    `AutomaticBackupRetentionDays`; `USER_INITIATED` and `AWS_BACKUP`
    backups are kept until someone deletes them, so they are the usual cost
    lever.
  - `AWS_BACKUP` backups can't be deleted through the FSx console, CLI or
    API — the operator deletes them in AWS Backup.
  - For a cost question, also list the account's `USER_INITIATED` and
    `AWS_BACKUP` backups in the Region whose volume or file system no longer
    exists (`describe-backups` with no filter; the source is gone from
    `describe-volumes`). They outlive their source and never expire, so they
    are often the real cost. Label them as outside the file system asked
    about, and state the recovery impact: the only copy of that data.
  - Source: [Protecting your data with volume backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html).
- Backup failure causes and checks:
  [Troubleshooting FSx for ONTAP backups](https://repost.aws/knowledge-center/fsx-ontap-troubleshoot-backups).

## Item 10 — Alarms

`cloudwatch:DescribeAlarms`, filtered to the fs-id. No alarm on SSD
`StorageCapacityUtilization` (and burst balance where it exists) → **LOW**
observability gap. Recommend the alarm; never offer to create it.

## Item 11 — Change history (CloudTrail)

Window: the Step 2 window (30 days when there is no incident). Cover FSx, EC2
security-group, `ds`, KMS, and AWS Backup events
([cloudtrail-audit.md](cloudtrail-audit.md)).

- **Query the file system's own Region.** CloudTrail is regional: a lookup in
  another Region returns zero events, and that zero proves nothing.
- **Never use `AttributeKey=ResourceName` with an fs-, svm-, or fsvol- ID.**
  FSx events have an empty `Resources[]`, so that lookup always returns zero.
  Look up each mutating `EventName` (`UpdateFileSystem`, `UpdateVolume`,
  `UpdateStorageVirtualMachine`, `Delete*`) and filter with
  `contains(CloudTrailEvent, '<fs-id>')`. Add the `Create*` events
  (`CreateStorageVirtualMachine`, `CreateVolume`, `CreateFileSystem`) whenever
  a resource may have been broken **since creation** (MISCONFIGURED with no
  later Update): it has no Update/Delete history, and the Create call's
  `requestParameters` is the evidence. `ResourceName` does work for EC2 IDs
  (sg-, rtb-, acl-).
- **Never use `AttributeKey=EventSource,AttributeValue=fsx.amazonaws.com`.** It
  returns every `Describe*`/`List*` call (including your own), 50 per page, so
  real changes fall off the first page.
- **Budget:** one call per `EventName` you need, `--start-time` at the window
  edge, first page only unless it is full *and* still inside the window. Don't
  re-query the same `EventName` by another resource, and don't widen the
  window hunting for a change: "no matching events in the window" is a finding.
- **Report every mutating event found** in a *Change history* table (time,
  event, caller, what changed, from `requestParameters`), including events by
  test or automation roles.
- **Link each change to the finding it explains** — e.g. an `UpdateFileSystem`
  that set `weeklyMaintenanceStartTime` is the origin of the window overlap.
  Never write "no config changes" if any mutating event is in the window.
- **A "who changed this" audit also covers dependency events** —
  `DeleteDirectory`, `ds:` changes, and security-group `Authorize*`/`Revoke*`.
  Include them, or state plainly that only `fsx:` calls were in scope.
- Report a setting as "removed" only with a matching change event; otherwise
  describe the current state only.

## Environment context

Read the file system's `Tags` (e.g. `Environment`, `Project`,
`aws:cloudformation:stack-name`) and state the inference explicitly ("tags
`Project=…` suggest a test environment"). Context may lower the severity of
**resilience and posture** findings (Single-AZ, no replica, short retention),
and the report must say so. It never lowers CRITICAL or HIGH operational
findings (data loss, broken access, capacity exhaustion). When tags are
absent, assume production.

## Analysis rules

1. **Check for active known issues first** — a service event may explain the symptom.
2. **CloudWatch shows what; ONTAP CLI shows why.** For the "why", request
   operator-run, read-only CLI output ([ontap-cli-pack.md](ontap-cli-pack.md)). Never run it yourself.
3. **High `DiskIopsUtilization` with low client `DataReadOperations` /
   `DataWriteOperations` = background I/O** (SnapMirror, dedup, WAFL scanner),
   not client-impacting; confirm client latency before escalating.
   **`Data*OperationTime` is in SECONDS**: average latency =
   Sum(`Data*OperationTime`) / Sum(`Data*Operations`) over the same period.
4. **Check product gaps before recommending features** — some requests are open
   feature requests (Entra ID SMB auth, EFA support, S3 Access Points in GovCloud).
5. **SSD decrease is second-generation only** (`SINGLE_AZ_2` / `MULTI_AZ_2`;
   ≥ 9% per step, must not exceed 80% utilization, 6-hour cooldown).
   First-generation SSD can only be increased. A failed decrease leaves a stuck
   `STORAGE_OPTIMIZATION` AdministrativeAction that blocks all subsequent
   CloudFormation updates.
6. **A drop in client ops to zero is ambiguous** — the client may have stopped,
   unmounted, or lost connectivity, or writes may be failing (ENOSPC). Don't
   assert refused writes or corruption without client error text, an
   `ENOSPC`/`EIO` report, or ONTAP evidence; state the ambiguity as a data gap.
7. **Distinguish volume-level from aggregate (SSD-tier) capacity.** A full
   FlexVol on a lightly used aggregate is fixed by growing the volume
   (`UpdateVolume`), not by `UpdateFileSystem StorageCapacity` or tiering.
   Per-volume used space is `StorageUsed` per `VolumeId`.
8. **Connectivity severity is keyed to fallback.** Loss of a single protocol
   path is CRITICAL only when there is data-loss risk or **no** working
   alternative path (e.g. port 2049 closed = all NFS down). If a working
   protocol/version remains: **HIGH** only when the lost path carries live
   client traffic now; **MEDIUM** when it is legacy, optional, or not in use
   (e.g. port 111/NFSv3 closed but all clients mount NFSv4.1 on 2049). When in
   doubt, prefer MEDIUM and state the assumption.
9. **Utilization metrics are percentages of BASELINE, not of a hard cap**, so
   they legitimately exceed 100% while bursting. Treat >100% as "bursting
   above baseline", never as a data error. Throughput collapse at constant
   demand with `NetworkThroughputUtilization` pinned at ~100% = network
   throttled to baseline after bursting ([REFERENCE.md §2](REFERENCE.md)). The
   gen1 baseline table in §2 must not be used for gen2.
10. **"What is our ceiling / how close are we" gets BOTH numbers** and says
    which binds: the **throughput-capacity** limit (`ThroughputCapacity` /
    `ThroughputCapacityPerHAPair`) **and** the **network baseline** for that
    tier, generation and Region from the §2 table, citing the
    [Performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
    page. Size any fix with read + 2×write.
11. **SSD thresholds** (80% recommended maximum, 90% stops capacity-pool read
    caching, 98% stops tiering) and the severity bands are in
    [REFERENCE.md §1](REFERENCE.md).
