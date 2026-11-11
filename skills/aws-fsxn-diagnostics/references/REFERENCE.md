# FSx for NetApp ONTAP — Failure-Mode Playbook and Reference

Control-plane, read-only diagnostic reference. Every threshold below is
evaluated from FSx API configuration and CloudWatch `AWS/FSx` metrics. No
data-plane access is assumed.

Companion files in this directory: `deployment-types.md` (per-type limits and
applicability), `cloudwatch-metrics.md` (metric catalog and per-type query
rules), `cloudtrail-audit.md` (change attribution), and `ontap-cli-pack.md`
(operator-run read-only CLI). Section numbers §1–§11 are unchanged from
earlier versions. The former §0, §12, and §13 now live in those files.

**Sources:** public AWS FSx for NetApp ONTAP documentation
(`docs.aws.amazon.com`), public NetApp ONTAP documentation, and public AWS
re:Post. Public doc wins any conflict. No internal content.

---

## Storage Tiers (Background)

Amazon FSx for NetApp ONTAP has two storage tiers:

- **Primary (SSD) tier** — provisioned, high-performance solid-state storage
  sized for the **active working set**. You pay for what you provision. When it
  fills, performance degrades and **writes can fail**.
- **Capacity pool tier** — fully elastic, cost-optimized storage for **cold /
  infrequently accessed** data. Grows automatically; you pay per GB used. Data
  moves between tiers via ONTAP data tiering (FabricPool) governed by a
  per-volume **tiering policy** and **cooling period**.

Correct sizing keeps hot data on SSD and cold data in the capacity pool.

---

## 1. SSD (Primary) Tier Capacity Exhaustion

**Evidence:** `StorageCapacityUtilization` CloudWatch metric; `StorageCapacity`
from `DescribeFileSystems`; per-tier capacity metrics. Read SSD fill **per
aggregate** (and per volume where relevant), not as a single file-system
average, so one full aggregate is not hidden — the per-aggregate and per-volume
metric categories are documented at
[Monitoring with CloudWatch](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html),
[Second-generation file system metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/so-file-system-metrics.html)
and [Volume metrics](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html).

The severity bands below are this skill's **operational** mapping for triage;
they are not AWS-published thresholds. The AWS-documented behavioral thresholds
are in the cascade that follows.

| Condition | Severity |
|-----------|----------|
| SSD utilization >= 95% or writes failing | CRITICAL |
| SSD utilization 85–95% (rising trend over 7d) | HIGH |
| SSD utilization 75–85% | MEDIUM |
| SSD utilization < 75% | INFO |

**Fix (control-plane):** increase primary SSD `StorageCapacity` (scale-up is
online); and/or enable/strengthen a volume **tiering policy** (`AUTO` or
`SNAPSHOT_ONLY`) so cold data moves to the capacity pool and frees SSD. A
decrease is also supported but moves data and can take a long time; monitor it
through `AdministrativeActions`
([Updating storage capacity and provisioned IOPS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/increase-storage-capacity.html)).
Review snapshot reserve and stale snapshots (`DescribeSnapshots`).

**AWS-documented SSD behavior** (from
[Managing storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html)):

- **Recommended ongoing maximum is 80%** SSD utilization (and, for
  second-generation file systems, 80% of any single aggregate). Sudden access-
  pattern changes can push utilization up quickly because the SSD tier also
  stages writes to, and caches random reads from, the capacity pool.
- **At 90%**, data read from the capacity pool is **no longer cached** on the
  SSD tier (SSD is preserved for new writes), so repeat cold reads keep paying
  capacity-pool latency.
- **At or above 98%**, **all tiering stops** — even for volumes with tiering
  policy `ALL`.
- **Don't apply this overhead by hand.** CloudWatch `StorageCapacity`
  (`StorageTier=SSD`, `DataType=All`) already reports capacity **net** of it —
  861.76 GiB on a 1,024 GiB file system. Read that metric; never multiply a
  utilization percentage by the provisioned capacity from `DescribeFileSystems`
  (a live run did and overstated free SSD by 105 GiB). The figures below explain
  *why* the two numbers differ — they are not a formula to compute with.
- Up to **16% of SSD is ONTAP overhead** (11% software + 5% aggregate snapshots;
  software portion drops to 6% above 30 TiB of SSD). **File metadata always
  lives on SSD** regardless of tiering policy. Sizing guide: reserve roughly
  **1 GiB of SSD for every 10 GiB** of data you intend to keep on the capacity
  pool.
- A backup can **fail** when the snapshot it needs would push the volume over
  **98%** SSD utilization, and both volume and file system must have enough SSD
  capacity
  ([Protecting your data with backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html),
  [Your backups fail due to insufficient volume capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/backups-failing.html)).

**Related diagnoses:**

- **MISCONFIGURED + full SSD aggregate.** A file system whose SSD aggregate is
  out of space can enter a **MISCONFIGURED** lifecycle state and refuse
  management actions, which commonly surfaces as "I can't delete my volume or
  SVM." Check `Lifecycle` and `FailureDetails` from `DescribeFileSystems`; the
  remediation is the SSD capacity increase, after which the file system returns
  to `AVAILABLE` and the refused action proceeds. See the public topics
  [File system in a MISCONFIGURED state](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-in-misconfigured-state.html),
  [SVM in a MISCONFIGURED state](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/misconfigured-svm.html),
  and [You can't delete an SVM or volume](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/cannot-delete-svm.html).
- **Tiering appears inactive.** Tiering only moves **cold** data per the volume's
  tiering policy and cooling period, and it pauses when the SSD tier is too full
  to tier (see the 98% behavior above). Confirm the policy/cooling period and the
  per-tier split before flagging; see
  [Volume data tiering](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-storage-capacity.html).
  (No specific aggregate-utilization percentage for when tiering begins is
  published by AWS — do not state one as a rule.)
- **Snapshot spill ("df says full, du disagrees")**: when snapshots outgrow the
  snapshot reserve they spill into the active file system. Evidence:
  CloudWatch `StorageUsed` per `VolumeId` with `StorageTier=All`,
  `DataType=Snapshot` (vs `DataType=User`), available on all deployment types
  (verified live), plus the `DescribeSnapshots` inventory (age, count) against
  volume size. Fix: raise
  snapshot reserve or enable volume autosize, shorten snapshot retention.

---

## 2. Throughput-Capacity Undersizing

Throughput capacity (MBps) provisions the **file server** (CPU + network + disk
throughput). Undersizing shows as saturation on multiple metrics simultaneously.

**Evidence:** `NetworkThroughputUtilization`, `FileServerDiskThroughputUtilization`,
`CPUUtilization` (AWS/FSx metric only — see §7 for EC2-level CPU false signal).

Metric definitions, dimensions per deployment type, units, and query rules
are in `references/cloudwatch-metrics.md`. Read it before interpreting any
metric below.

| Condition | Severity |
|-----------|----------|
| Two or more metrics sustained >= 90% | HIGH |
| Any one sustained 80–90% | MEDIUM |
| Brief spikes only | LOW |

**Burst-credit metrics (first-generation, throughput capacity < 512 MBps):**
`FileServerDiskThroughputBalance` and `FileServerDiskIopsBalance` report the %
of burst credits remaining. Per the first-generation metrics page they are
valid only below 512 MBps (verified live: `SINGLE_AZ_1` and `MULTI_AZ_1` at
128 MBps emit both). The second-generation metrics page does not list them, but
**gen2 emits them too**: verified live on `SINGLE_AZ_2` and `MULTI_AZ_2` at
384 MBps and on a 2-HA-pair `SINGLE_AZ_2` at 1,536 MBps per pair, both per
`FileSystemId` and per `FileServer`. Gen2 tiers of 384, 768, and 1,536 MBps
per HA pair burst disk throughput (to 3,125 MBps) and IOPS. 3,072 and 6,144 MBps
have no documented burst
([Performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)),
so no balance series is expected there (unverified). Where no balance series
exists, infer burst exhaustion from
`FileServerDiskThroughputUtilization` / `FileServerDiskIopsUtilization` per
`FileServer` on `Maximum` (sustained near 100% with rising client latency), and
state it as an inference. A missing balance series is a data gap, never
"healthy" or "zero".

| Condition | Severity |
|-----------|----------|
| Balance at/near 0 during business hours (throttled to baseline) with client latency rising | HIGH |
| Balance repeatedly draining toward 0 over the 7d window | MEDIUM |
| Balance dips but recovers, never near 0 | INFO (bursting as designed) |

A balance below 100% by itself is NOT throttling — it means the workload is
using burst above baseline. **Alarm on a low balance** (e.g. `Minimum` < 20%
for 15+ minutes), never on "< 100%", which fires on normal bursting. Where the
balance metrics exist, recommend this alarm whenever bursting is observed.

**Network burst exhaustion (no balance metric).** Network I/O also runs on a
credit mechanism (AWS performance guide: credits accrue below baseline and are
spent above it), with a published baseline and burst per throughput tier — but
AWS publishes **no network burst-balance metric**. Recognize it from the pattern:

- `NetworkThroughputUtilization` sustained well above 100% for a period, then
  dropping to and **holding at ~100%** (the baseline), while
- client throughput (`DataReadBytes`/`DataWriteBytes`) falls sharply at
  unchanged demand, and
- server-side latency (`Data*OperationTime` ÷ ops) does **not** rise — the delay
  is outside ONTAP, in the network path, so clients see it but the server does
  not, and
- the disk burst balances may read healthy or even refill (disk is no longer
  the limit).

Severity HIGH when clients are degraded. State it as an inference (no metric
confirms it) and say so in the report. Do not attribute it to the disk balance.

**Sizing the fix — use the BASELINE, not the burst.** Pick the smallest tier
whose **network baseline** covers the sustained requirement, where requirement =
read MB/s + **2 × write MB/s** (writes are replicated to the partner file server
and use twice the network). First-generation Single-AZ, us-east-1/us-east-2/
us-west-2/eu-west-1 network baseline per throughput tier: 128 → 188, 256 → 375,
512 → 750, 1,024 → 1,500, 2,048 → 3,125, 4,096 → 6,250 MB/s (other regions use
a lower row, e.g. 128 → 150, 256 → 300, 512 → 625). **This table is
first-generation only.** Second-generation network baseline **per HA pair**:
384 → 781, 768 → 1,563, 1,536 → 3,125, 3,072 → 6,250, 6,144 → 12,500 MB/s, with
disk throughput equal to the tier (burst to 3,125 MB/s up to 1,536). 384 and
768 are available only with one HA pair. Gen2 also has a **write ceiling below
the provisioned throughput**. All figures are from the performance table,
verified Oct 2026. Read the generation-, deployment-type-, and
region-specific row from the
[performance table](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html#impact-throughput-cap-performance)
before sizing. Never apply the gen1 numbers to a gen2 file system. The
read + 2 × write requirement formula applies to every type.
A throughput-capacity change switches out the file server, causing an
**automatic failover and failback** on **both Single-AZ and Multi-AZ** file
systems, typically a few minutes
([Managing throughput capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html)).
It is transparent to NFS and SMB clients because the endpoint IP is unchanged;
iSCSI and NVMe/TCP clients need client-side multipathing configured to fail over.
On **second-generation** file systems a change starts a **6-hour cooldown**
shared with SSD/IOPS scaling (the two cannot run at once); first-generation
instead queues/prioritizes concurrent requests rather than enforcing the 6-hour
wait. A pending change can also be delayed if it lands in the maintenance
window. Say so in the recommendation, and avoid scheduling it during a critical
run.

**Fix (control-plane):** increase throughput capacity to the next tier. This is
distinct from IOPS (see §3): throughput capacity governs MBps and file-server
CPU; provisioned SSD IOPS governs disk operations/sec.

---

## 3. SSD IOPS Bottleneck

**Evidence:** `DiskIopsUtilization`; provisioned SSD IOPS mode
(`AUTOMATIC` vs `USER_PROVISIONED`) from `DescribeFileSystems`.

**Read the two IOPS metrics together.** `DiskIopsUtilization` is measured against the
**provisioned** SSD IOPS; `FileServerDiskIopsUtilization` against the **file server's** own
ceiling (set by throughput capacity). High disk-side + low file-server-side → provision more
SSD IOPS; high file-server-side → raise throughput capacity. Provisioning SSD IOPS above the
file server's baseline (e.g. 6,000 at 128 MBps Gen1) runs the server on IOPS burst credits
(`FileServerDiskIopsBalance`).

| Condition | Severity |
|-----------|----------|
| `DiskIopsUtilization` sustained >= 95% | HIGH |
| 85–95% | MEDIUM |
| < 85% | INFO |

**Fix (control-plane):** raise provisioned SSD IOPS (`USER_PROVISIONED`) or
move from `AUTOMATIC` if the automatic value trails the workload. Confirm the
ceiling is IOPS and not throughput (§2) before recommending.

**Important:** High `DiskIopsUtilization` with low client
`DataReadOperations`/`DataWriteOperations` = background
operations (SnapMirror, dedup, WAFL scanner) — NOT a client-impacting issue.
Confirm client latency before escalating.

---

## 4. Data-Tiering (FabricPool) Misconfiguration

**Evidence:** per-volume tiering policy and cooling period (`DescribeVolumes`);
per-tier capacity split (CloudWatch).

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `SNAPSHOT_ONLY` | Default; moves cold snapshots only (min 2-day cooling) | Active datasets |
| `AUTO` | Moves cold user data + snapshots (default 31-day cooling; range 2–183 days) | General workloads |
| `ALL` | Moves all data immediately (Cloud Write Mode) | Large migrations |
| `NONE` | No tiering; all data stays on SSD | Latency-sensitive hot volumes |

**Common misconfigurations:**
- Policy `NONE` on a large archive/cold volume → SSD stays full unnecessarily. **MEDIUM/HIGH** depending on SSD pressure.
- Policy `ALL` on a hot volume → latency as active data reads from capacity pool. **MEDIUM**.
- Cooling period too long for the access pattern → cold data lingers on SSD. **LOW/MEDIUM**.

**Fix (control-plane):** set the tiering policy to match the access pattern and
tune the cooling period. Changing tiering policy is a control-plane operation
(`DescribeVolumes` shows current; modify via AWS Console or API).

---

## 5. SnapMirror Replication Failure / Lag

**Evidence (control-plane only, indicative):** capacity/throughput anomalies on
a destination file system, plus the user report. **Confirmation of SnapMirror
relationship state and lag is data-plane** (ONTAP REST/CLI).

| Condition | Severity |
|-----------|----------|
| Replication reported broken / RPO breached | CRITICAL |
| Lag growing over the 7d window | HIGH |
| Transient lag within RPO | LOW |

**Fix:** the actual resync/quiesce/resume is **data-plane** (ONTAP CLI/REST).
Report the signal, mark it as requiring data-plane confirmation, and reference
the extension below. Control-plane remediation is limited to ensuring
destination throughput/SSD headroom.

**Version-aware known issues** (check ONTAP version from `DescribeFileSystems`):

- **Slow transfers after upgrading to ONTAP 9.14.1 or later** — 9.14.1
  introduced a Background Replication Engine (BRE) throttle. Reduced SnapMirror
  throughput with no workload or network change after an upgrade is this, not a
  fault. Remediation is **data-plane**: `snapmirror modify -destination-path
  <svm:vol> -backoff-level medium` (or `none`), then `snapmirror abort` +
  `snapmirror resync`. FlexVol relationships only.
  NetApp KB: "Slower SnapMirror throughput after upgrading to ONTAP 9.14.1 or later"
- **Very slow transfers where the source is a FlexClone with tiered data**
  (CONTAP-676690) — ONTAP does not use speculative readahead reading snapshot
  data on clone volumes. Workaround: restore from backup to a standard volume
  and replicate that, or set `cloud-retrieval-policy promote` on both the clone
  and its parent (data-plane).
- **SVM disaster recovery (SVM-DR) is not supported** on FSx for NetApp ONTAP —
  only volume-level SnapMirror. Flag as unsupported rather than diagnosing.
- **Never delete SnapMirror-created snapshots on the source** — breaks the NCS
  (No Common Snapshot) chain. If `No common Snapshot copy found` error: delete
  relationship, create new destination volume, reinitialize.

---

## 6. Multi-Protocol (NFS / SMB) Access Issues

**Evidence:** `DescribeStorageVirtualMachines` (protocols enabled, AD join
state), volume `security style` from `DescribeVolumes`.

**Common issues:**
- SMB SVM not joined / AD join degraded → SMB clients fail. **HIGH**.
- Security style mismatch (NTFS style volume accessed over NFS) → permission errors. **MEDIUM**.
- Protocol not enabled on the SVM the client is using. **MEDIUM**.

**Required security group rules (inbound to FSx — client → file system):**

| Port | Protocol | Purpose |
|------|----------|---------|
| 2049 | TCP/UDP | NFS |
| 635 | TCP/UDP | mountd |
| 111 | TCP/UDP | portmapper (NFSv3) |
| 445 | TCP | SMB |

These are the only ports clients need **inbound to the FSx file system** to
mount/access shares. A missing one here is a client-reachability finding.

**Active Directory ports (389, 88, 464, 53, 636, 3268/3269) are NOT inbound
client→FSx rules.** They carry traffic from the **SVM to the domain
controllers** (LDAP, Kerberos, Kerberos password change, DNS, LDAPS, Global
Catalog) for the AD join and ongoing authentication. The reachability that
matters is **SVM → DC** (DC-side security groups / NACLs and the SVM's own
egress), not inbound on the FSx file system's security group. Do **not**
recommend adding 389/88/464/53 as *inbound* rules on the FSx SG to fix a client
access problem — that is the wrong direction and will not help. Flag an AD-port
gap only on the SVM→DC path, and only when AD/SMB is actually in use.

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 389 | TCP/UDP | SVM → DC | LDAP |
| 88 | TCP/UDP | SVM → DC | Kerberos |
| 464 | TCP/UDP | SVM → DC | Kerberos password change |
| 53 | TCP/UDP | SVM → DC | DNS |
| 636 | TCP | SVM → DC | LDAPS (if used) |
| 3268/3269 | TCP | SVM → DC | Global Catalog / GC over SSL (if used) |

**Endpoint routing depends on deployment type**
([Accessing your FSx for ONTAP data](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html),
[Network resources](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html#single-multi-az-resources)):

- **Single-AZ (`SINGLE_AZ_1`, `SINGLE_AZ_2`):** endpoints are ordinary IPs from
  the file system's subnet, inside the VPC CIDR. No floating IPs and no
  FSx-managed routes (`RouteTableIds` is empty and `EndpointIpAddressRange` is
  null, verified live). Clients in peered VPCs, over Direct Connect, or over VPN
  reach them like any other in-VPC address.
- **Multi-AZ (`MULTI_AZ_1`, `MULTI_AZ_2`):** NFS, SMB, and management endpoints
  are **floating IPs** from `OntapConfiguration.EndpointIpAddressRange`. A
  CloudFormation/API-created file system gets a **/24 inside `198.19.0.0/16`**
  (verified live: `198.19.222.0/24`, `198.19.39.0/24`). Console-created IPv4
  file systems use a range from the VPC's primary CIDR, and dual-stack uses
  `EndpointIpv6AddressRange`. FSx creates **one /32 route per floating IP**
  (`1 + number of SVMs`: management plus each SVM's NFS/SMB endpoint),
  targeting the **preferred subnet's ENI**, **only in the route tables listed
  in `OntapConfiguration.RouteTableIds`**, and tags those tables
  `AmazonFSx=ManagedByAmazonFSx` (all verified live). **iSCSI and intercluster
  (SnapMirror) endpoints are not floating.** They are in-VPC IPs, one per
  subnet.
  - A client whose subnet's route table is **not** in `RouteTableIds` cannot
    reach the endpoints, or loses access after a failover. This is a common
    Multi-AZ mount failure. Compare `RouteTableIds` with each client subnet's
    route table (`ec2:DescribeRouteTables`). Fix: add the route table to the
    file system (`update-file-system --ontap-configuration AddRouteTableIds=...`).
    Never hand-edit the FSx-managed routes.
  - VPC peering, Direct Connect, and VPN cannot route to floating IPs. Access
    from outside the VPC needs Transit Gateway, with the TGW attachment
    subnets' route tables associated with the file system. iSCSI / NVMe
    endpoints are not floating and are reachable without TGW.
  - Deleting or modifying an FSx-managed route (or the FSx ENIs) causes
    temporary or permanent loss of connectivity. A CloudTrail `DeleteRoute` /
    `ReplaceRoute` on an associated table is a strong root-cause signal (`cloudtrail-audit.md`).

### Clients outside the VPC or account

Run this before concluding where a client is (or isn't). The agent can see
only the accounts associated with its Agent Space.

| Client location | Visible to the agent? | SG rule on the FSx SG that admits it | Path checks |
|---|---|---|---|
| Same VPC, same account | Yes (`ec2:DescribeNetworkInterfaces`) | SG reference or CIDR | Local route; NACLs on both subnets |
| Shared VPC subnet (AWS RAM), client owned by another account | ENI visible to the VPC owner; instance details not visible | SG reference (`account/sg-id`) or CIDR | Same as same-VPC |
| Peered VPC, same Region (same or other account) | Peer side not visible across accounts | Peer SG reference (`account/sg-id`) or CIDR | Peering `active` (`DescribeVpcPeeringConnections`); routes **both ways** to each other's CIDR; NACLs both sides. **Multi-AZ:** peering can't reach floating IPs |
| Peered VPC, other Region | Peer side not visible | **CIDR only** (no cross-Region SG references) | Same as above |
| Transit Gateway | Remote VPC not visible across accounts | CIDR, or SG reference **only if SG referencing is enabled on the TGW and both VPC attachments**. Not across TGW peering, not in `use1-az3` | Attachment `available`; TGW route table has both CIDRs; the FSx subnets' AZs have an attachment subnet with routes; Multi-AZ: attachment subnets' route tables in `RouteTableIds` |
| Direct Connect / VPN / on-premises | No | **CIDR only** | VGW/TGW routes, on-prem routing, firewall. Multi-AZ needs TGW |

Rules:
- "No instance in this account carries the referenced SG" **is not** "no
  client exists". Ask where the client is.
- If **every** inbound rule on the FSx SG is an SG reference, any client on a
  CIDR-only path (DX, VPN, on-prem, cross-Region, PrivateLink) is silently
  dropped, which shows up as a hang, not "refused". Flag it against the
  client's actual path.
- Client-side resources in another account (routes, NACLs, SGs, flow logs)
  are a **data gap**. List the exact checks for that account's owner.
- Sources: [VPC peering SG references](https://docs.aws.amazon.com/vpc/latest/peering/vpc-peering-security-groups.html),
  [TGW SG referencing](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-vpc-attachments.html).

### Intermittent access (non-deterministic failures)

When mounts or I/O fail **sometimes** (works, then hangs, then works):
1. **Get failure timestamps** from the user (UTC) and line them up with:
   - FSx failover triggers: throughput changes, maintenance window, file-server
     replacement (§8; CloudTrail `UpdateFileSystem`; AWS Health);
   - burst exhaustion (§2): balance near 0, or network pinned at baseline;
   - SG/NACL/route changes in CloudTrail at those times (`cloudtrail-audit.md`).
2. **Flow logs over time:** for the FSx ENIs and the client ENI, query
   ACCEPT/REJECT on 111/635/2049 (and 445 for SMB) around each failure. REJECTs
   only at failure times point to a rule change or asymmetric path. All ACCEPT
   while the client hangs points away from SG/NACL (client, NFS lock reclaim
   after failover, or data plane).
3. **NACL return traffic:** NACLs are stateless, so ephemeral ports
   (1024–65535) must be allowed in both directions. Missing return rules can
   fail some connections and not others, depending on the client's source port.
4. **Multi-AZ:** check whether failures follow failovers (floating IP moves to
   the standby ENI) and whether every client route table is in
   `RouteTableIds`.
5. **If flow logs are off:** state that the cause **can't be determined** from
   the control plane, record the gap, and recommend enabling flow logs on the
   FSx ENIs and the client ENI (a customer write, not done by this skill), then
   reproducing. Don't guess a root cause.

### NFS Mount-Failure First-Touch Intake

**Split the list first.** Items 1–4 and the client half of item 5 are
operator-only — no API returns them. Everything in item 5 marked *(you look
this up)* you fetch yourself with AWS calls before replying (SKILL.md Step 1
item 1) and report in the same reply as the questions: fs-id, Region, SVM, LIF
IPs, the FSx security group and its rules, the client subnet/SG when the
instance is in this account, and the route tables. **The fs-id and Region are
never questions for the operator** — `DescribeFileSystems` with no filter
lists every file system in the account; filter to `FileSystemType = ONTAP` and
name the match. A reply that asks for the fs-id, or that asks anything without
also giving AWS-side findings, is a defect.

Collect ALL of the following in one pass **before** any packet analysis:

1. **Client environment**: OS and kernel (`uname -r`), NFS client package
   (`rpm -q nfs-utils` / `dpkg -l | grep nfs-common`), the exact mount command
   with its full option string, output of the verbose attempt (`mount -vvv ...`),
   and `dmesg | tail -50` captured within a minute of the failure.
2. **Reachability to the SVM NFS endpoint (LIF)**:
   `nc -zv <lif> 111 2049 635 4045 4046` and `rpcinfo -p <lif>` (portmapper
   must answer before NFSv3 can mount).
3. **Isolation probes — run BEFORE requesting packet captures**:
   - Try NFSv4.1: `mount -t nfs -o vers=4.1,sec=sys ...`. If v4.1 mounts where
     v3 fails, the fault is the portmapper/NFSv3-TCP path — customer is
     unblocked immediately.
   - Try NFSv3 over UDP: `-o vers=3,proto=udp,mountproto=udp`. If UDP works
     and TCP does not, focus on the TCP RPC reply path. UDP may be disabled on
     the SVM's NFS server, so a UDP failure on its own proves nothing. Confirm
     with `vserver nfs show` (`ontap-cli-pack.md`) before drawing a conclusion.
4. **Blast radius**: does the same client mount a different FSx file system?
   Does a different client in the same subnet fail? All SVMs/volumes or one?
   Both LIFs (Multi-AZ)? When did it last work and what changed?
5. **Network topology**: *(you look this up)* fs-id, region, SVM, target LIF
   IP, the FSx security group and its rules, and the relevant route-table
   entries; *ask only* for the client VPC/subnet/security groups when the
   client is outside this account, and for the path type (same VPC / peering /
   TGW / DX / VPN).
6. **Packet capture, only after 1–5, dual-sided**: client-side
   `tcpdump -i any -nn -s 0 -w client.pcap host <lif>`; FSx side cannot run
   native ONTAP packet traces — use **VPC Traffic Mirroring** on the file
   system's ENIs instead.

**Identity-mapping failure signatures:**
- `nobody:nobody` ownership under NFSv4 → ID-domain mismatch between client's
  `idmapd.conf` and SVM's `v4-id-domain` (data-plane confirmation).
- Permission denied under both v3 and v4 for non-root user on NTFS security-style
  volume → missing UNIX-to-Windows name mapping (data-plane confirmation; but
  security-style evidence from `DescribeVolumes` is control-plane).

### SMB / Active Directory Diagnostic

**Phase 1 (control-plane):**
1. Check the FSx security group allows inbound **TCP 445** (SMB) from the
   clients. The AD ports (389, 88, 464, 53, 636, 3268/3269) are **SVM → DC**,
   not inbound client→FSx rules — verify them on the SVM→DC path (DC-side
   SG/NACL and SVM egress), not as inbound rules on the FSx SG. See the two
   tables above.
2. Check SVM `ActiveDirectoryConfiguration` via `DescribeStorageVirtualMachines`
3. Check SVM lifecycle state
4. SVM MISCONFIGURED after a join attempt: read ONTAP's join error from
   CloudTrail `UpdateStorageVirtualMachine`
   `responseElements.storageVirtualMachine.ontapErrorMessage` before going to
   Phase 2 (procedure: `review-checks.md` item 6, "Directory healthy but the
   join failed")
**Phase 2 (data-plane — ONTAP CLI):** run by the operator, not the skill, as
the SMB row of the `ontap-cli-pack.md` read-only command pack. Core commands:
- `vserver cifs show` — CIFS service status
- `vserver cifs check` — CIFS server / DC connectivity status
- `vserver cifs domain discovered-servers show` — DCs found and their status
- `vserver services name-service dns check` — DNS resolution
- `vserver cifs share show` — share ACLs

**AD join requirements:**
- 7 service account delegations required (Reset Password, Read/Write Account Restrictions, Validated Write to DNS Host Name, Validated Write to Service Principal Name, Create/Delete Computer Objects)
- Port 464 (Kerberos password change) required — commonly missed
- SMB Workgroup mode available as fallback (no AD required) but loses Kerberos auth

**Directory state (AWS Managed Microsoft AD only).** If the SVM joins an AWS
Managed AD, check the directory itself before concluding the fault is on the
FSx side: `aws ds describe-directories --directory-ids <d-xxxx>` and read
`Stage` plus `StageReason`. A directory in `Failed`, `Impaired`, or
`RequiresUpdate` explains an SVM that cannot join or that drops out of the
domain, and the remediation is on the directory, not the file system. Needs
`ds:DescribeDirectories` (and `ds:DescribeDomainControllers` to confirm both
DCs are healthy).

**SVM `Lifecycle` is not an AD health signal.** An SVM can stay `CREATED` after
the directory behind it is gone (verified live: the AWS Managed AD was deleted
and the SVM still reported `CREATED` a week later, with nothing owning its
`DnsIps`). Confirm the directory exists: `ds:DescribeDirectories` returns it,
and the configured `DnsIps` belong to live ENIs
(`ec2:DescribeNetworkInterfaces --filters Name=addresses.private-ip-address,Values=<dns-ip>`).
If not, check CloudTrail `ds.amazonaws.com` `DeleteDirectory` for who removed
it and when (`cloudtrail-audit.md`). The SMB path is then broken regardless of what FSx reports.
Confirm with `vserver cifs check` (`ontap-cli-pack.md`) if the operator can run it. Rate
severity by whether SMB carries live traffic (review-checks.md, analysis rule 8).

**Do not use the field name to decide whether AD is managed or self-managed.**
`DescribeStorageVirtualMachines` returns the join config under
`ActiveDirectoryConfiguration.SelfManagedActiveDirectoryConfiguration` **even
when the SVM is joined to an AWS Managed Microsoft AD** — unlike FSx for Windows
File Server, ONTAP SVMs always join in the "self-managed" shape (domain name,
OU, user name, DNS IPs). Verified on a live AWS Managed AD join. Concluding
"self-managed, so no directory to check" from that field is wrong and will skip
the check above. To tell them apart, compare the SVM's `DnsIps` against
`DnsIpAddrs` from `ds:DescribeDirectories` — if they match, it is an AWS Managed
AD and the directory is in scope. If there is no directory in the account whose
IPs match, treat it as genuinely self-managed and go to DNS and connectivity
instead.

**VPC Flow Logs — confirming SG or NACL blocking.** Security-group inspection
proves what the rules *say*; flow logs prove what traffic actually *did*. When
the SG looks correct but the mount or domain join still fails, query flow logs
on the FSx ENI for REJECT entries on the AD ports:

```
fields @timestamp, srcAddr, dstAddr, srcPort, dstPort, protocol, action
| filter dstAddr = "<fsx-svm-ip>" or srcAddr = "<fsx-svm-ip>"
| filter dstPort in [445, 389, 88, 464, 636, 53] or srcPort in [445, 389, 88, 464, 636, 53]
| filter action = "REJECT"
| sort @timestamp desc
| limit 50
```

REJECT on 88, 389, 445 or 464 confirms SG or NACL blocking rather than an
ONTAP-side problem. For NFS, substitute ports 111, 2049, 635, 4045 and 4046.
Reading existing flow logs needs `ec2:DescribeFlowLogs` plus
`logs:StartQuery`/`logs:GetQueryResults`. **Enabling** flow logs is a write and
therefore a recommendation to the customer, never an action this skill takes.

---

## 7. False-Signal Suppression Rules (Do NOT Flag These)

Signals that look like findings but are expected behavior. Suppressing them is
as important as raising real findings.

- **EC2-level CPU on the file servers reads ~99–100% at all times.** ONTAP does
  not release vCPUs when idle. Never use instance-level CPU as evidence of
  saturation; only the `AWS/FSx` `CPUUtilization` metric is meaningful.
- **Throughput scaling stuck `IN_PROGRESS` (AdministrativeActions).** During a
  throughput-capacity scale, the preferred (serving) file server scales first
  and immediately serves traffic at the NEW throughput. If the standby node
  then hits an insufficient-capacity condition, the administrative action stays
  `IN_PROGRESS` — but the customer already has the requested throughput, is
  metered at the old (lower) rate until completion, and the action resolves
  automatically. Report as INFO with that explanation, not as a fault. Exception:
  if the pending action **blocks another required operation**, that is a real
  finding (HIGH).
- **Insufficient-capacity errors (ICE) on scaling operations** — the remedy is
  to retry the operation until it succeeds; there is no configuration fix.
- **A daily automatic backup was skipped** — if the file system's maintenance
  window overlaps its backup window, maintenance (patching) takes priority and
  can consume the whole window. Evidence: compare `WeeklyMaintenanceStartTime`
  and `DailyAutomaticBackupStartTime` from `DescribeFileSystems`. Finding is the
  **WINDOW OVERLAP** (MEDIUM, fix: separate the windows), not the missed backup.
  For ONTAP read `OntapConfiguration.WeeklyMaintenanceStartTime` (the top-level
  field is null). Its format is `d:HH:MM` (d = 1 Monday … 7 Sunday); the daily
  backup start is `HH:MM` every day. They overlap whenever the maintenance
  `HH:MM` falls within roughly an hour of the backup `HH:MM` — e.g. `1:05:00`
  (Monday 05:00) vs `05:00` IS an overlap every Monday. Compute this explicitly;
  do not eyeball the two strings.
- **Tiering that has not moved data yet** — tiering moves only data that is
  cold per the volume's policy and cooling period, and pauses when SSD is too
  full (§1, §4). Confirm policy, cooling period, and per-tier split before
  flagging. AWS publishes no aggregate-utilization percentage at which tiering
  begins, so do not state one. Tiering relieves the aggregate only; it never
  reduces a FlexVol's logical used space, so do not recommend it as the fix for
  a full volume.
- **Closed ports for a protocol the incident does not involve** — e.g. AD/LDAP
  (389, 88, 464, 53) or SMB (445) closed on an NFS-only file system/incident.
  If those ports were never part of the baseline and that protocol is not in use,
  record at most an INFO observation, not a finding.
- **Do not attribute pre-existing state to a recent change.** Before stating that
  a change "removed" or "dropped" a rule/setting, confirm it existed before (prior
  config, CloudTrail `Revoke*`/`Modify*` event, or the user's baseline). If you
  cannot confirm it was ever present, say "not present" — never "removed by".

---

## 8. Lifecycle and Stuck-Operation Diagnosis

**Evidence:** `AdministrativeActions` from `DescribeFileSystems` /
`DescribeVolumes`, CloudTrail management events, resource `Lifecycle` states.

- **Failed SSD storage-decrease (STORAGE_OPTIMIZATION FAILED):** leaves a
  FAILED admin action that blocks **ALL** subsequent CloudFormation stack updates
  (including throughput-only changes). Check `AdministrativeActions` for a stuck
  `STORAGE_OPTIMIZATION` action. SSD **decrease is supported on
  second-generation file systems only** (`SINGLE_AZ_2`, `MULTI_AZ_2`); each
  decrease must be at least 9% of current SSD capacity, must not push
  utilization above 80%, and is subject to the 6-hour cooldown
  ([Decreasing SSD storage capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-capacity-and-IOPS.html)).
  First-generation SSD can only be increased. Resolution for a failed decrease:
  increase SSD back to the original or a higher value.
- **File system stuck in DELETING**: first check CloudTrail for the
  `DeleteFileSystem` event. Billing stops at the API call. A large amount of
  data in the capacity pool legitimately extends deletion time.
- **SVM stuck deleting / cannot delete**: if the SVM is AD-joined, the common
  cause is the CIFS server — disable dynamic DNS updates and delete the CIFS
  configuration first (data-plane: `vserver services name-service dns
  dynamic-update modify -is-enabled false`, then `vserver cifs delete`), then
  retry. An error of the shape "Attempt to move IP ... failed because AWS
  prevents IP moves outside of the ENI's subnet" is a service-side fault —
  direct the user to AWS Support.
- **Patching/upgrade failures**: check SSD free space first (a nearly-full SSD
  tier blocks maintenance), then whether the maintenance window elapsed before
  completion.
- **Failover / failback** ([Failover process](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html#Failover)):
  automatic on **all** deployment types and typically completes in < 60
  seconds. Multi-AZ fails back automatically, usually in < 60 seconds. On
  multi-pair `SINGLE_AZ_2`, each HA pair fails over independently, so expect
  one pair's volumes to be affected, not the whole file system. Triggers:
  file-server failure, throughput change, planned maintenance, and AZ outage
  (Multi-AZ only). Transparent to NFS/SMB because the endpoint IP is unchanged.
  iSCSI / NVMe/TCP depend on client multipathing. Implement NFS retry logic in
  applications to handle the brief disconnection.

---

## 9. Baseline Checks (No Clear Symptom)

Use when there is a concern about a file system but no clear symptom yet, and
as the baseline sweep under any diagnosis whose symptom fits no other section.
These checks look for **conditions that cause or precede incidents**; they are
not a best-practices posture audit. Run each check and report PASS / finding
with the severity tables above:

1. **SSD utilization posture** against the skill's severity bands (MEDIUM
   75–85%, HIGH 85–95%, CRITICAL ≥ 95%) and AWS's behavioral thresholds (80%
   recommended maximum, 90% capacity-pool read caching stops, 98% tiering
   stops) (§1). Per aggregate on gen2.
2. **Throughput and IOPS headroom** — 7-day p95 of §2/§3 metrics against
   provisioned values.
3. **Tiering policy vs observed access** — per-volume policy/cooling period vs
   per-tier capacity split (§4).
4. **Backup posture** — automatic daily backups enabled, retention matches
   stated RPO, backup window does NOT overlap the maintenance window (§7),
   recent backups actually present **per volume** (`DescribeBackups` filtered
   by `volume-id`; a recent backup of one volume does not cover the others).
   Before calling a backup "missing", confirm the volume can be backed up:
   only online **read-write** volumes (`OntapConfiguration.OntapVolumeType =
   RW`) are backed up, so DP / SnapMirror-destination, LS, and FlexCache
   volumes have no backups by design. `AutomaticBackupRetentionDays = 0`
   disables automatic backups and **deletes existing automatic backups**. If
   it changed recently, check CloudTrail `UpdateFileSystem` (`cloudtrail-audit.md`) and treat it
   as data-loss risk. Deleting a volume deletes its automatic backups unless a
   final backup was taken
   ([Protecting your data with backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html)).
5. **Snapshot hygiene** — stale snapshots, count growth, reserve pressure (§1).
6. **Resilience shape** — deployment type vs the workload's stated
   availability requirement and performance envelope (`deployment-types.md`). Single-AZ survives
   a file-server failure, not an AZ outage. Apply the `deployment-types.md` "deployment type
   itself is the finding" table. For Multi-AZ: every client subnet's route table is in
   `RouteTableIds`, and off-VPC clients come through Transit Gateway (§6). For
   multi-pair `SINGLE_AZ_2`: per-HA-pair balance of capacity and load (§1, §3).
7. **Protocol/AD posture** — SVM protocol enablement and AD join state vs what
   clients actually use (§6).
8. **Version currency** — ONTAP version and pending `AdministrativeActions`;
   note the 9.14.1 SnapMirror behavior change (§5) when an upgrade is planned.

---

### Volume snapshot policies (ONTAP-native, separate from AWS Backup)

Sources: [Working with snapshots](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html)
and [Volume properties](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html).

`DescribeVolumes` returns `OntapConfiguration.SnapshotPolicy` per volume. The
built-in policies:

| Policy | Schedule kept | Notes |
|---|---|---|
| `default` | hourly (6), daily (2, Mon–Sat), weekly (2, Sun) | FSx default for new volumes |
| `default-1weekly` | hourly (6), daily (2), weekly (**1**) | Same cadence, less weekly retention |
| `none` | **nothing** | No ONTAP snapshots at all |
| custom | operator-defined | Created via ONTAP CLI/REST only; exact schedules are data-plane — confirm with `volume snapshot policy show` |

**Why this matters in a diagnosis.** ONTAP snapshots and AWS Backup are
independent recovery mechanisms. A volume set to `none` has **no** file-level
recovery points of its own, so the only restore path is the daily automatic
backup — and with `AutomaticBackupRetentionDays: 1` that is a single
point-in-time per volume. Report that combination as a finding, not as two
separate observations. Always state the policy actually in effect per volume
rather than describing the defaults: a live run recommended "hourly" in the
abstract on a file system whose main NFS volume was already set to `none`.

Snapshot space is visible without the CLI: CloudWatch `StorageUsed` with
`DataType=Snapshot` versus `DataType=User` per `VolumeId`. A volume on policy
`none` can still hold large snapshot data from automatic backups — observed
live at 172.8 GiB of snapshots against 115.8 GiB of user data — so "policy is
`none`" does **not** imply "no snapshot space consumed".

## 10. Escalation-Readiness Packet

When findings require AWS Support (or NetApp via AWS Support), end the report
with a pre-filled escalation packet — these are the fields support teams require
before accepting an FSxN escalation:

- AWS Region; file system id; SVM id(s)/name(s); volume id(s)/name(s);
  backup id(s) where relevant.
- Issue category (one of: Performance/Slowness, SnapMirror/Replication, NFS,
  SMB/CIFS, Tiering/FabricPool, Networking/Connectivity, Patching/Upgrade,
  Mounting, Volume/SVM deletion stuck, Capacity/Scaling, SnapCenter, Other).
- Issue start/end time in **UTC**; ongoing or resolved.
- One-paragraph description with business/technical impact.
- Exact error messages observed (console, API, client-side).
- Investigation performed and what was ruled out (this skill's findings table
  satisfies this).
- Logs/metrics reviewed (CloudWatch metrics + window, CloudTrail events).
- Reproduction steps, if known.
- For SnapMirror issues: where the peer/origin lives and the relationship
  `source path -> destination path`.
- For SnapCenter issues: SnapCenter version, plug-ins involved, whether
  SnapGathers logs have been collected (§11).
- **ONTAP CLI evidence:** either the operator-provided output already
  analyzed (with its timestamp) or, if it couldn't be collected, the open
  question and the `ontap-cli-pack.md` read-only command pack so Support can request it
  directly.

---

## 11. SnapCenter Triage (Adjacent Tooling)

SnapCenter is NetApp's standalone backup-management product; it is not part of
the FSx service. AWS owns only the AWS-side path (networking, security groups,
NACLs, FSx availability). Four known issues are quick to recognize:

- **Scheduled backups stop after upgrading to SnapCenter 6.0+, manual backups
  fine.** Signature: "RabbitMQ Connection Failure" alerts; `SnapManagerWeb.log`
  "RabbitMQ broker is unreachable". Cause: upgrade's RabbitMQ installer fails
  to recreate users/permissions. Fix requires NetApp support.
- **Scheduled jobs stop after an IIS recycle or Windows Server restart**
  (SnapCenter 6.1.x/6.2 on WS2019/2022): the IIS **Application Initialization**
  feature is missing — install it via Server Manager, reboot, confirm.
- **SnapCenter Plug-in for Oracle cannot discover FSx storage** ("credentials
  for the storage system <SVM> is not configured"): remove individual SVMs from
  the Storage Connection tab and register the **cluster** instead, then refresh
  resources.
- **Telerik Reporting CVE-2024-7840** (bundled viewer files): upgrade to a
  SnapCenter build shipping Telerik Reporting 2024 Q3 (18.2.24.924) or later.

---

## Data-Plane MCP Extension (Documented, NOT Built Here)

Deep volume-level state, SnapMirror relationship health and lag, NFS
export-policy rules, and CIFS/SMB share ACLs are only available through the
**ONTAP REST API** or **ONTAP CLI** to the file system — the **data plane**.
This skill stops at control-plane diagnosis and flags where data-plane
confirmation is required.

A separate MCP server connecting to the ONTAP management endpoint would be
required to extend into data-plane RCA. This is Phase 2 scope.

**Data-plane boundary triggers — recognize and route, do not diagnose here.**
When the symptom matches one of these, the root cause lives in the data plane
(ONTAP CLI/REST). Name it, capture the control-plane signals you can, mark it as
requiring data-plane confirmation, and follow the procedure in `ontap-cli-pack.md`: hand the operator the matching `ontap-cli-pack.md` command pack, then
route to the account's normal AWS Support path if the paste does not resolve
the question. The skill never runs ONTAP commands or performs the ONTAP-side
remediation itself.

- **FlexCache** — the affected volume is a FlexCache cache or origin (read
  latency, cache misses after a dataset change, or hung I/O after a takeover/
  giveback). Latency may belong to the origin, not the file system on the case.
  Control-plane signal: `FileServerCacheHitRatio` and capacity-pool read metrics
  (§2). Confirmation and fix are data-plane.
- **Hot / imbalanced aggregate** — writes stay slow after SSD capacity and
  throughput were already increased, because load is concentrated on one or two
  aggregates while the file-system average looks healthy. Control-plane signal:
  read `StorageCapacityUtilization` and the IOPS-utilization metrics **per
  aggregate** on `Maximum`, not as a file-system average (§1, §3). The rebalance
  is data-plane.
- **Node panic / failover / LIF not returning home** — back-end node events. The
  client-visible part (transient I/O errors, NFS lock-reclaim failures around a
  failover) is covered publicly at
  [Troubleshooting I/O errors and NFS lock reclaim failures](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/nfs-failover-issues.html);
  node internals are escalation-only.
- **NFS identity / access** — `nobody:nobody` ownership, "permission denied" for
  non-root users on an NTFS security-style volume, stale handles after a file-id
  change, or export-policy auth rejections. Security-style evidence from
  `DescribeVolumes` is control-plane; the name-mapping / export-policy fix is
  data-plane.

---

## Reference Links

- FSx for NetApp ONTAP User Guide: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html
- Managing storage capacity: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-storage-capacity.html
- Managing throughput capacity: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html
- Provisioned SSD IOPS: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provisioned-ssd-iops.html
- Data tiering / FabricPool: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html
- CloudWatch metrics for FSx ONTAP: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/monitoring-cloudwatch.html
- File system metrics (metric + dimension definitions): https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-metrics.html
- Second-generation (per-aggregate) file system metrics: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/so-file-system-metrics.html
- Volume metrics (per-volume): https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/volume-metrics.html
- Updating storage capacity and provisioned IOPS: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/increase-storage-capacity.html
- Troubleshooting (MISCONFIGURED, can't delete, SSD decrease, backups): https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/troubleshooting.html
- File system in a MISCONFIGURED state: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-system-in-misconfigured-state.html
- You can't delete an SVM or volume: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/cannot-delete-svm.html
- Backups fail due to insufficient volume capacity: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/backups-failing.html
- I/O errors and NFS lock reclaim failures: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/nfs-failover-issues.html
- Performance (ceilings, read + 2×write sizing): https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html
- Insufficient-capacity errors on scaling: https://repost.aws/knowledge-center/fsx-ontap-fix-insufficient-capacity-errors
- Maintenance windows and daily backup windows: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/maintenance-windows.html
- Working with backups: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html
- FSx ONTAP network troubleshooting: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/network-issues.html
- Troubleshoot NFS mount errors: https://repost.aws/knowledge-center/fsx-ontap-mount-errors-on-linux
- Cross-VPC access via Transit Gateway: https://repost.aws/knowledge-center/fsx-ontap-cross-vpc-access
- NetApp NFS best practices (TR-4067): https://www.netapp.com/media/10720-tr-4067.pdf
- NetApp KB - SnapMirror throughput after ONTAP 9.14.1: https://kb.netapp.com/on-prem/ontap/Perf/Perf-KBs/Slower_SnapMirror_throughput_after_upgrading_to_ONTAP_9.14.1_or_later
- NetApp KB - NFSv4.x mounts show owner as nobody: https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/NFSv4.x_mounts_show_file_and_group_owner_as_nobody
- NetApp KB - SnapCenter data requirements: https://kb.netapp.com/Cloud/Amazon_FSX/What_data_is_required_to_troubleshoot_SnapCenter_issue_associated_with_Amazon_FSx_for_NetApp_ONTAP
