# Pre-flight Readiness (Mode P)

<!-- Loaded by SKILL.md. Content validated live against HyperPod Slurm, HyperPod EKS, and ParallelCluster clusters. -->

## Mode P: Pre-flight readiness for a long run

Run Steps 1, 2, and 3a first. Use the planned run length and checkpoint interval if the
user gave them. If not, do not stop to ask: run every check, report the latest safe start
time for common run lengths (24, 48, and 72 hours) against the capacity end, and mark the
run-length-dependent verdict `Needs input`. Score each check `PASS`, `RISK`, `FAIL`, or `UNVERIFIED`, with the evidence.

| # | Check | How | FAIL or RISK when |
|---|-------|-----|-------------------|
| P1 | Reserved capacity outlasts the run | EC2 Capacity Block: `ec2.DescribeCapacityReservations` `EndDate`. HyperPod on a training plan: `sagemaker.DescribeTrainingPlan` for the group's `TrainingPlanArn` (`Status`, `DurationHours`, and end time where returned). Instances in a Capacity Block begin terminating 30 minutes before the end (60 for UltraServers) | Run start plus run length is later than end minus the termination lead time. RISK if the last checkpoint would land inside the lead time |
| P2 | Extension is possible | `ec2.DescribeCapacityBlockExtensionOfferings` with the reservation ID and the extra hours needed (read-only; nothing is purchased) | FAIL for P1 and no offering returned. Report offerings found, without quoting prices to the customer unverified |
| P3 | A failed node can be replaced | Training plan: `AvailableSpareInstanceCount` and `UnhealthyInstanceCount`. Capacity Block: `AvailableInstanceCount`. Otherwise Service Quotas for the instance type, compared with current use | RISK when no spare exists. A listed quota is **not** proof of replacement capacity (live testing saw Service Quotas report 1 while HyperPod enforced 0), so quota-only evidence is `UNVERIFIED` |
| P4 | Automatic recovery is on | HyperPod: `DescribeCluster` `NodeRecovery`. Slurm jobs need `srun --auto-resume=1` (ask) | FAIL when `NodeRecovery = None` |
| P5 | New nodes are tested before taking work | HyperPod instance group `OnStartDeepHealthChecks` | RISK when empty on GPU groups |
| P6 | GPU faults will be visible | Step 3a coverage for every compute node | FAIL when any node is `Not observable` |
| P7 | EFA can pass traffic at full width | `ec2.DescribeSecurityGroups` on the cluster ENIs: a self-referencing all-traffic rule inbound and outbound. EFA interfaces attached per node vs `MaximumEfaInterfaces` (capability profile). EFA-capable types only | FAIL when the rule is missing; RISK when fewer EFA interfaces are attached than the type supports |
| P8 | Storage has headroom | `fsx.DescribeFileSystems` deployment type and capacity; Step 5 saturation metrics over the last similar run | RISK when any saturation metric reached the Step 5 threshold during a previous run |
| P9 | Reserved GPUs are being used | Step 5 idle reserved hours over the last 24 to 72 hours | RISK when most reserved GPU hours were idle. Report the hours. HyperPod: `Not observable` in CloudWatch (use the observability add-on) |
| P10 | Capacity end is alarmed | `events.ListRules`, looking for a rule on the `Capacity Block Expiration Warning` event | RISK when no rule exists |
| P11 | Software stack meets the instance minimums | Minimums for the instance type from `references/nccl-nvlink-efa.md` section 5. Driver version from the kernel boot line `NVRM: loading NVIDIA UNIX Open Kernel Module ... <version>` in the shipped kernel log | FAIL below the minimum; `UNVERIFIED` when unreadable |
| P12 | NCCL uses EFA and NVLink on the last run | NCCL lines from the last job (Branch D layer 1); Fabric Manager start lines on NVSwitch instances | FAIL on `via NET/Socket/` or Fabric Manager failure; `UNVERIFIED` when no NCCL lines are shipped, with the collection command |
| P13 | Cluster management is healthy | `cloudwatch.DescribeAlarms` with `StateValue=ALARM`, filtered to alarms whose name or dimensions reference the cluster, head node, or its instances (ParallelCluster creates head-node alarms such as `ClustermgtdHeartbeat`) | RISK for any alarm in ALARM; say how long it has been in that state |
| P14 | Network headroom for one replacement | `cluster-edge-cases.md` section 1: `DescribeSubnets` `AvailableIpAddressCount` against IPs per node, and the `L-DF5E4CA3` network interface quota | RISK when free IPs or interfaces cannot cover one replacement node |
| P15 | EFA security group outbound rule | Outbound rules of the cluster security groups (HyperPod EFA clusters) | RISK when outbound is `0.0.0.0/0` instead of the self-referencing rule (documented to cause EFA health check failures) |
| P16 | Compute nodes can bootstrap | ParallelCluster: compute subnet route table and multi-interface EFA nodes (`cluster-edge-cases.md` section 4); recent `Found the following bootstrap failure nodes` or protected-mode lines | FAIL for EFA nodes in a public subnet without NAT; RISK on recent bootstrap failures |

Lead the report with the checks that FAIL, then RISK. Each gets one concrete operator
action. Do not run any of them.
