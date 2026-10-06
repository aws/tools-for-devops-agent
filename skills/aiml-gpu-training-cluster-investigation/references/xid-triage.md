# NVIDIA Xid Triage Reference

Source: [NVIDIA Xid catalog](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html).
Descriptions and action buckets below are taken from that catalog. The "Class" column
is this skill's grouping of NVIDIA's action buckets for root-cause routing. Always
prefer the catalog if it has been updated.

Xids appear in the kernel log as `NVRM: Xid (PCI:<bus-id>): <code>, ...`. On HyperPod
they are surfaced in the `SagemakerHealthMonitoringAgent` log stream inside the HMA
detection message. On ParallelCluster they appear in the `system-messages` or `syslog`
stream of `/aws/parallelcluster/<cluster>-<timestamp>`. On self-managed fleets they
appear only in whatever log group the customer ships the system log to. See SKILL.md
Step 3a for discovery and the coverage check.

An absent Xid is only meaningful when kernel logging for that node is proven live.
`Not observable` and `0 Xids` are different findings.

## Commonly seen codes

NVIDIA catalog values (description, immediate action) as checked. Where an AWS page gives
a different first step, the AWS step is listed because it is specific to EC2.

| Xid | NVIDIA description | NVIDIA immediate action | Verdict for this skill |
|-----|--------------------|-------------------------|------------------------|
| 11 | Invalid or corrupted push buffer stream | RESTART_APP (investigatory: CHECK_APP/CUDA) | Application: LEAVE ALONE (unless paired with a hardware Xid) |
| 13 | Graphics Engine Exception | RESTART_APP | Application: LEAVE ALONE (unless paired with a hardware Xid) |
| 25 | Invalid or illegal push buffer stream | RESTART_APP (investigatory: CHECK_APP/CUDA) | Application: LEAVE ALONE (unless paired with a hardware Xid) |
| 31 | GPU memory page fault | RESTART_APP | Application: LEAVE ALONE (unless paired with a hardware Xid) |
| 32 | Invalid or corrupted push buffer stream | RESTART_APP (investigatory: CHECK_APP/CUDA) | Application: LEAVE ALONE (unless paired with a hardware Xid) |
| 43 | GPU stopped processing | IGNORE | Sympathetic: follow the Xid that preceded it |
| 45 | Preemptive cleanup, due to previous errors | WORKFLOW_XID_45 | Sympathetic: follow the other Xid |
| 46 | GPU stopped processing | RESET_GPU | REBOOT; REPLACE if it recurs |
| 48 | Double Bit ECC Error | WORKFLOW_XID_48 (solo: RESET_GPU; with 63 or 64: DRAIN_AND_RESET) | Depends on which memory faulted, see rule 6. Framebuffer/DRAM: REBOOT (AWS: a reboot retires the page or activates remapped rows); REPLACE if 64 or a remap failure follows, or it recurs. SRAM with the threshold flag set: REPLACE |
| 62 | Internal micro-controller halt | RESET_GPU | REBOOT; REPLACE if it recurs |
| 63 | GPU memory remapping event | IGNORE | MONITOR alone. After a 48, a remap is pending: REBOOT to activate it |
| 64 | GPU memory remapping failure | RESET_GPU | REPLACE (AWS: remap failure needs stop/start to move to healthy hardware) |
| 74 | NVLINK Error | WORKFLOW_NVLINK_ERR | REBOOT; REPLACE if it recurs |
| 79 | GPU has fallen off the bus | RESTART_BM | REBOOT first (AWS); stop/start (REPLACE) if it persists |
| 92 | High single-bit ECC error rate | IGNORE | MONITOR; watch for 48/64 |
| 94 | Contained memory error | RESTART_APP | LEAVE ALONE (contained); MONITOR |
| 95 | Uncontained memory error | RESET_GPU | REBOOT; REPLACE if it recurs |
| 109 | Context Switch Timeout Error | RESET_GPU | REBOOT; REPLACE if it recurs |
| 110 | Security Fault Error | RESET_GPU | REBOOT; investigate software |
| 119 | GSP RPC Timeout | RESET_GPU | Driver configuration: AWS says these occur with GSP activated and the fix is to deactivate GSP. A reboot alone does not stop recurrence. Verdict LEAVE ALONE with the GSP action |
| 120 | GSP Error | RESET_GPU | Same as 119 |
| 136 | Link Training Failed | RESET_GPU | REBOOT; REPLACE if it recurs |
| 137 | NVLink Privilege Error | IGNORE (investigatory: XID_137_FLOW) | Application, not hardware: LEAVE ALONE. An illegal NVLink peer-to-peer access reported by the remote MMU, usually an application bug. Presents as NVLink but is not an NVLink fault. See rule 9 |
| 140 | ECC Unrecovered Error | RESET_GPU | REBOOT; REPLACE if it recurs |
| 143 | GPU Initialization Error | RESET_GPU | REBOOT; REPLACE if it recurs |
| 144 | NVLINK: SAW Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 145 | NVLINK: RLW Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 146 | NVLINK: TLW Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 147 | NVLINK: TREX Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 148 | NVLINK: NVLPW_CTRL Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 149 | NVLINK: NETIR Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 150 | NVLINK: MSE Error | WORKFLOW_NVLINK5_ERR | NVLink 5 (Blackwell only), see rule 10 |
| 151 | Key rotation Error | RESTART_VM | REBOOT |
| 154 | GPU Recovery Action Changed | XID_154 (informational, about another Xid) | Use its value, see rule 7 |
| 155 | NVLINK: SW Defined Error | RESET_GPU (investigatory: INVESTIGATE_SW_USER) | Software-defined link event: REBOOT only if links stay down; not a hardware verdict on its own |
| 156 | Resource Retirement Event | RESET_GPU (investigatory: IGNORE) | MONITOR |
| 157 | Resource Retirement Failure | IGNORE (investigatory: CONTACT_SUPPORT) | The GPU could not retire the resource, and the catalog notes no repair is possible for lack of resources. On EC2 the support path is to move off the hardware: REPLACE (stop/start). Note the immediate action is IGNORE, so 157 alone with a healthy job is not an outage, but it does mean the GPU has exhausted its retirement capacity |
| 158 | GPU Fatal Timeout | RESET_GPU | REBOOT; REPLACE if it recurs |
| 171 | Uncorrectable DRAM Error | (none listed, qualifier on Xid 48) | Not a standalone verdict. It tells you the Xid 48 double-bit error was in DRAM (framebuffer): follow the framebuffer path, REBOOT. See rule 6 |
| 172 | Uncorrectable SRAM Error | (none listed, qualifier on Xid 48) | Not a standalone verdict. It tells you the Xid 48 double-bit error was in SRAM: check the SRAM DBE threshold flag, and REPLACE if it is set. See rule 6 |

Note on conflicting sources: the Amazon ECS GPU auto repair page lists 155 as "GPU NVLink
flit CRC error" and 156 as "GPU NVLink lane error". The NVIDIA catalog describes them as
above. Follow NVIDIA, and say the sources differ if the verdict depends on it.

Other GPU memory signals that are not Xids ([AWS Xid troubleshooting](https://repost.aws/knowledge-center/ec2-linux-troubleshoot-xid-errors)):

| Signal | Where | Verdict |
|--------|-------|---------|
| `WARNING: infoROM is corrupted at gpu` | Kernel log (does not match `NVRM: Xid`) | REBOOT; stop/start (REPLACE) if it persists |
| `Remapped Rows ... Pending: Yes` | `nvidia-smi -q` on the node | REBOOT (GPU reset required) |
| `Remapping Failure Occurred: Yes` | `nvidia-smi -q` on the node | REPLACE (stop/start) |
| `Pending Page Blacklist: Yes` (older GPUs) | `nvidia-smi -q` on the node | REBOOT |
| `SRAM Threshold Exceeded: Yes` | `nvidia-smi -q -d ECC`, under `Aggregate` | REPLACE. The NVIDIA RMA gate for an SRAM double-bit error, see rule 6 |
| `Unrepairable Memory: Yes` | `nvidia-smi -q -d ECC` | REPLACE. No repair path remains; the same condition Xid 157 reports |
| `Channel Repair Pending: Yes` or `TPC Repair Pending: Yes` | `nvidia-smi -q -d ECC` | REBOOT. A repair is staged but not yet applied |
| `Bank Remap Availability Histogram` shifting from `Max` toward `Low` / `None` | `nvidia-smi -q -d ROW_REMAPPER` | MONITOR, and a pre-failure signal worth reporting. It measures remaining remap capacity per bank (a healthy B300 reads `Max: 5760 bank(s)` with zeros elsewhere). Exhausted capacity is what later surfaces as a remap failure or Xid 157, so a degrading histogram is the early warning |
| Fewer GPUs than the instance type has | Distinct `GpuId` (`AWS/EC2`) or `index` (`CWAgent`) dimension values from `ListMetrics`, compared with `DescribeInstanceTypes` GPU count; on the node, `nvidia-smi --list-gpus` | REPLACE (AWS: stop and start). Missing metrics are Not observable, never a low count |

## Routing rules

1. **Order matters.** Sort Xids by time per node. The first non-sympathetic Xid is the
   candidate cause; later 43/45 entries are usually consequences.
2. **Hardware class on one node, job failed after:** branch A. Recommend replacing that
   node (not reboot) if the same hardware-class Xid recurs after a reboot.
3. **Application class on many nodes at once, no hardware class anywhere:** branch F.
   Suspect code, input data, or framework version.
4. **119/120 on multiple nodes after an AMI or driver change:** branch E. Correlate with
   `UpdateClusterSoftware` or `CurrentImageId` changes.
5. **63 alone** is not a root cause. Do not report it as one.
6. **Xid 48 is two different verdicts. Decide which memory faulted before recommending
   anything.** The NVIDIA Xid 48 flow splits on whether the double-bit error was in the
   framebuffer (DRAM) or in SRAM: "If the ECC error is reported for SRAM (excludes
   'framebuffer'), check for SRAM DBE thresholds" and "follow RMA flow if exceeded".
   Route it:

   | Evidence | Verdict |
   |----------|---------|
   | Xid 171 (`UNCORRECTABLE_DRAM_ERROR`) present, or the 48 message names the framebuffer | DRAM: follow the Xid 63/64 guidance. REBOOT to retire the page or activate the remapped row; REPLACE if 64 or a remap failure follows |
   | Xid 172 (`UNCORRECTABLE_SRAM_ERROR`) present, or the 48 message names an SRAM unit | SRAM: the reboot-retires-a-page logic does not apply. Check the SRAM DBE threshold flag. If set, the NVIDIA flow is RMA, which on EC2 means REPLACE (stop/start) |
   | Neither 171/172 present and the 48 message does not say | `UNVERIFIED` which memory faulted. Report the 48, say the DRAM/SRAM split could not be determined from the log, and name the one check that resolves it (below). Do not default to REBOOT as if it were DRAM |

   None of these counters are reachable through an AWS API. They live on the node, so ask
   the operator for them and hold the verdict at `Hypothesis (to validate)` until you have
   them. The field names below come from `nvidia-smi -q -d ECC` on a live
   `p6-b300.48xlarge` running driver 595.91.07 with CUDA 13.2. Quote them as they appear:

   ```
   ECC Errors
       Volatile / Aggregate
           SRAM Correctable
           SRAM Uncorrectable Parity        <- SRAM, two separate counters
           SRAM Uncorrectable SEC-DED       <-
           DRAM Correctable
           DRAM Uncorrectable               <- DRAM
           SRAM Threshold Exceeded : No     <- the RMA gate, Aggregate only
       Aggregate Uncorrectable SRAM Sources
           SRAM L2 / SRAM SM / SRAM Microcontroller / SRAM PCIE / SRAM Other
       Channel Repair Pending  : No
       TPC Repair Pending      : No
       Unrepairable Memory     : No
   ```

   A few notes on reading that output.

   `SRAM Threshold Exceeded` is the field the RMA flow actually keys on. It only appears
   under `Aggregate`, so do not go looking for it under `Volatile`. If it says `Yes`, the
   verdict is REPLACE.

   There are two SRAM uncorrectable counters, `Parity` and `SEC-DED`. Report whichever one
   is non-zero and call it by name. Adding them together loses the distinction.

   `Aggregate Uncorrectable SRAM Sources` breaks the count down by unit: L2, SM,
   microcontroller, PCIE, other. Without the vendor decode table this is as close as you
   get to knowing which part failed, so quote the non-zero one.

   Two fields settle a verdict on their own. `Unrepairable Memory: Yes` means the GPU has
   run out of repair options, which is REPLACE; Xid 157 describes the same situation from
   the driver's side. `Channel Repair Pending: Yes` or `TPC Repair Pending: Yes` means a
   repair is queued but not yet applied, which is REBOOT, the same logic as a pending row
   remap.

   Where BMC access exists, NSM Msg Type `0x3`, Cmd Code `0x7D`, bit 0 carries the same
   information as `SRAM Threshold Exceeded` out of band.

   One caveat on driver versions. Xid 171 and 172 only appear on newer drivers; the catalog
   pairs them with CUDA 12.7 and R565. On anything older, not seeing them tells you nothing
   about DRAM. The current Deep Learning AMI ships 595.91.07, so a reasonably up-to-date
   fleet will have them.
7. **Xid 154 overrides the table.** Its message states the required action, for example
   `Xid 154 GPU recovery action changed from 0x0 (None) to 0x2 (Node Reboot Required)`.
   Values: `None`, `Drain P2P`, `Drain and Reset`, `GPU Reset Required`, `Node Reboot Required`.
   `GPU Reset Required` or `Node Reboot Required` means REBOOT for the node it names.
8. **Unknown code:** report the raw code and message, mark the classification
   `UNVERIFIED`, and link the NVIDIA catalog. Do not guess.
9. **An Xid with NVLink in the name is not automatically an NVLink fault.** Xid 137
   (`NVLINK_PRIV_ERR`) is an illegal peer-to-peer access that the remote MMU reports, and
   the catalog's immediate action for it is IGNORE, with an application-debug flow for
   investigation. It belongs with 13 and 31, not with 74 or the 144 to 150 family. Calling
   137 a hardware error is the same mistake as calling an Xid 31 one.
10. **Xid 144 to 150 have no single verdict. Do not make one up.** These are Blackwell
    only; the catalog marks them NO for A100 and H100 and YES for B100 and GB200, which
    covers the `p6-b200` and `p6-b300` this skill is aimed at. All seven route to
    `WORKFLOW_NVLINK5_ERR`, and that bucket says `<intrInfo>` and `<errorStatus>`
    "must be decoded and evaluated" against the catalog's "XID 144-150 Decode" table
    before you get a resolution. That table is not reproduced here, so work with what the
    message itself gives you.

    Quote the Xid line as it appears. The fields come in a fixed order: Xid number, sub
    component, fatal or nonfatal, crosscontain, injected, link, then `intrInfo`,
    `errorStatus` and `errorDebugData` in parentheses. Of those, the sub component, the
    fatal flag and the link number are readable without the decode table, so report all
    three.

    For the verdict, `fatal` on a link that stays down is a REBOOT candidate, and becomes
    REPLACE if it comes back on the same link after that reboot. A `nonfatal` on its own
    is MONITOR. Either way, mark the precise resolution `UNVERIFIED` because the register
    decode is missing, and link the catalog so the operator can finish the job. A bare
    "NVLink error, replace the node" is never an acceptable output for these codes.

    Before you call it hardware at all, check Fabric Manager and the `nvidia-smi nvlink`
    state in `references/nccl-nvlink-efa.md`. Several of the counters there read non-zero
    on healthy nodes, so that section matters.

## HyperPod node conditions

Observed on a live HyperPod Slurm cluster: an application out-of-bounds GPU write
produced `Xid 31`, HMA logged `reason: XidUserAppError` and a DCGM policy violation
(`ErrNum: 31`) within about 1 second, and the node stayed `Running` with no reboot or
replacement.

HMA messages include a node condition such as `NvidiaErrorReboot` or
`NvidiaErrorTerminate`, and EventBridge node health events can carry
`HealthStatusReason`, `RepairAction`, and `Recommendation`. Quote these verbatim in the
report. They describe the action HyperPod took or recommends.
