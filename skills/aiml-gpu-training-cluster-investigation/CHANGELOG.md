# Changelog

## 1.0.4

Eval coverage only. No change to the skill's instructions.

- Restored the three eval definitions whose subject matter the 1.0.1 and 1.0.2 fixes were
  built for: `control-plane-log-dead`, `capacity-block-expiry` and `xid-48-reboot-first`.
  They had been dropped when the set was rebuilt around resources that actually resolve,
  which left the three changes most tied to the review with nothing covering them. Each
  grades method rather than outcome, because their conditions cannot be manufactured on
  demand: a dead control-plane log, a live Capacity Block termination, and a genuine hardware
  double-bit ECC fault. The tool requires `expected_output` on every non-negative chat eval,
  so a trigger-only entry is not expressible; the `expected_output` states the procedure the
  skill has to demonstrate instead.
- Functional re-run as v5: 9 evals, 3 iterations, 48 runs, no execution failures. All three
  restored evals score above their no-skill baseline, which is what they exist to protect.

## 1.0.3

Changes driven by the functional eval, with the diagnosis corrected after a closer look at
the journals.

- The skill stopped the agent naming the resource it analysed. An FSx investigation quoted no
  file system ID at all, while the same run without the skill did name it, so the eval scored
  it as a regression. The log group and stream requirement added in 1.0.1 was too narrow, so
  rule R5a now covers every resource behind a claim: `fs-...` for storage, `i-...` for nodes,
  `cr-...` for capacity, the cluster by name. It applies to resources ruled out as well,
  because an exclusion is useless if the reader cannot tell what was excluded. Added to the
  Step 7 self-check and to report-format.md. Confirmed fixed: assertions went from 5/21 to
  13/21 against the no-skill run, and the regression flag cleared.
- Stream names must be written as the service writes them. Runs were sourcing a finding from
  the HyperPod health agent and then describing it as "the HMA log stream", which R5 already
  forbids but which no check caught. report-format.md and the Step 7 list now call for
  `SagemakerHealthMonitoringAgent/<instance-group>/<instance-id>` verbatim, and tell the agent
  to search its own draft for the paraphrase.
- Mode P is now tiered: the six FAIL-class checks P1 to P6 run first, the verdict is written,
  and P7 to P16 extend it afterwards, with anything unreached reported `Not checked`. Rule R1
  also asks for the gathering to be budgeted so the report always gets written.

  Worth recording why, because the first diagnosis was wrong. A Mode P run had made 67 tool
  calls without producing an answer, which looked like the 16 checks exhausting the agent.
  The journals say otherwise: context window utilization never passed 7.2% in any run, tool
  volume does not separate pass from fail (one coverage run passed at 77 calls while others
  failed at 73 and 80), and no-skill runs failed the same way at 21 calls. The real pattern is
  that a run fails exactly when its journal ends on a telemetry record with no final response
  recorded, which points at the eval reading the journal before the agent's last message
  lands rather than at anything in the skill. The tiering and the budget rule are still worth
  keeping on their own merits, but they are not a fix for that and are not claimed as one.

## 1.0.2

The Blackwell content added in 1.0.1 came from the NVIDIA catalog alone, so it was checked
against a real `p6-b300.48xlarge`: 8 x NVIDIA B300 SXM6 AC, driver 595.91.07, CUDA 13.2.
That turned up four wrong or vague field names and three readings that look like faults on
a perfectly healthy node.

- Rule 6 now quotes the `nvidia-smi -q -d ECC` fields by name rather than describing them:
  `SRAM Threshold Exceeded`, which sits under `Aggregate` and is the RMA gate;
  `SRAM Uncorrectable Parity` and `SRAM Uncorrectable SEC-DED`, which are two counters and
  not one; `DRAM Uncorrectable`; and the `Aggregate Uncorrectable SRAM Sources` breakdown
  across L2, SM, microcontroller, PCIE and other, which tells you which unit failed.
- Three signals were missing entirely. `Unrepairable Memory: Yes` is a REPLACE, and is the
  same situation Xid 157 reports from the driver side. `Channel Repair Pending` and
  `TPC Repair Pending` mean a repair is queued but not applied, so REBOOT. The
  `Bank Remap Availability Histogram` is a genuine early warning, because running out of
  remap capacity is what eventually shows up as a remap failure or an Xid 157.
- Xid 171 and 172 turn out to be available in practice. The current Deep Learning AMI ships
  595.91.07, comfortably past the R565 the catalog pairs them with.
- The NVLink error-counter names were wrong. `Replay Errors`, `Recovery Errors` and
  `CRC Errors` do not exist on 595.91.07. What the driver actually emits is
  `Malformed packet Errors`, `Buffer overrun Errors`, `Rx Errors`, `Rx remote Errors`,
  `Rx General Errors`, `Local link integrity Errors`, `Tx discards`,
  `Link recovery successful/failed/Total events`, `Effective Errors` and `Symbol Errors`.
- Three healthy readings that would each have produced a wrong finding are now called out.
  `FEC Errors - 0` counts corrected codewords and stood at 36,140,749,276 at boot.
  `Effective BER` and `Symbol BER` read `15e-255`, which is the floating-point floor and not
  a high error rate. `Raw Errors` and `Raw BER` were non-zero per lane on a healthy node, so
  neither is evidence on its own.
- Added the `Fabric` section fields, `State: Completed`, `Status: Success`, `CliqueId` and
  `GPU Fabric GUID`. These are a better fabric health check than reading Fabric Manager log
  lines.
- An InfiniBand device count is not an EFA check on Blackwell. A B300 with no EFA interface
  attached still showed `ibp198s0f0` and `ibp199s0f0`, both ConnectX bridges on `mlx5_core`
  firmware 28.47.2526, used for NVLink subnet management.
- The 1800 GB/s NVSwitch figure counts both directions while `nvidia-smi` reports one
  (`NV18` at 53.125 GB/s, so 956.25 GB/s per direction). Dividing one by the other makes a
  healthy fabric look half width.

## 1.0.1

Addresses the TFC SME review on PR #112. Each value below was checked against the NVIDIA
Xid catalog or the live SageMaker API rather than taken from the review as written, which
is how the four corrections noted here came up.

- Xid 48 now splits on which memory faulted. Added Xid 171 (`UNCORRECTABLE_DRAM_ERROR`)
  and 172 (`UNCORRECTABLE_SRAM_ERROR`) as qualifiers, plus routing rule 6: DRAM follows the
  reboot-and-retire path, SRAM checks the SRAM double-bit threshold flag and replaces if it
  is set, and an undetermined case is reported `UNVERIFIED` instead of defaulting to reboot.
  This was the one review item that could produce a wrong reboot-versus-replace verdict
- Added the NVLink 5 Xid family 144 to 150, Blackwell only, which is the hardware the skill
  targets for `p6-b200` and `p6-b300`. `WORKFLOW_NVLINK5_ERR` has no fixed verdict: it
  requires decoding `intrInfo` and `errorStatus`. Rule 10 therefore parses the readable
  message fields (sub component, fatal versus nonfatal, link) and marks the precise
  resolution `UNVERIFIED` rather than inventing a replace recommendation
- Added Xid 137 (`NVLINK_PRIV_ERR`) and rule 9: an illegal peer-to-peer access that presents
  as NVLink but is an application bug, immediate action IGNORE. Classified with 13 and 31
- Added Xid 11, 25, and 32 to the application class, and Xid 157 with the note that its
  immediate action is IGNORE while its investigatory action is CONTACT_SUPPORT
- Added `sagemaker.ListClusterEvents` and `DescribeClusterEvent` as an eighth timeline
  source, reached first when log delivery is broken. Gated on `NodeProvisioningMode` being
  `Continuous`, verified live: other clusters return
  `ValidationException: ListClusterEvents is only supported for cluster with
  NodeProvisioningMode set to Continuous`. The response carries no severity field, so the
  skill is told not to report one
- Added the `Capacity Reservation Instance Interruption Warning` event as per-instance proof
  of a Capacity Block termination, with `instance-termination-time` and
  `instance-lifecycle`, in place of inferring it from the reservation `EndDate`

## 1.0.0

- Initial version: GPU evidence coverage audit, node verdicts against an NVIDIA and AWS
  evidence bar, Proven/Hypothesis cause labels, NCCL/NVLink/EFA checks, instance-generic
  capability profile, frequent non-GPU edge cases, and pre-flight readiness checks P1 to P16
  for SageMaker HyperPod (Slurm and EKS), AWS ParallelCluster, and self-managed GPU clusters
