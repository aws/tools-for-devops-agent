# Frequent Cluster Edge Cases

Frequent causes of GPU cluster incidents that are not GPU faults. Each has a read-only
detection path and a fixed conclusion. Log strings are quoted from the linked pages.

## 1. Subnet IP and network interface exhaustion

Large GPU instances consume many IP addresses, and a subnet's CIDR cannot be changed later.
HyperPod documents that each P5 instance creates **32 IP addresses on Slurm** (one per
network card) and **81 on EKS** (50 from the primary card plus one from each of the other 31).
HyperPod cannot request the ENI quota increase itself.

Detect:
- `ec2.DescribeSubnets` `AvailableIpAddressCount` for every subnet in `VpcConfig` and each
  group's `OverrideVpcConfig` (HyperPod), or the cluster's compute subnets.
- IPs per node: HyperPod P5 per the figures above; EC2 nodes: count of `NetworkInterfaces`
  plus their secondary private IPs from `DescribeInstances`.
- `servicequotas.GetServiceQuota` for Amazon VPC `L-DF5E4CA3` (Network interfaces per
  Region) versus network interfaces in use.

Conclude: in an incident, `CurrentCount < TargetCount` with free IPs below one node's need
is a network capacity cause (Branch B), not hardware. In pre-flight, RISK when free IPs
cannot cover one replacement node.

Source: [HyperPod prerequisites](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-prerequisites.html).

## 2. EFA security group outbound rule

HyperPod documents: allow all traffic to and from the security group itself, and "avoid
using `0.0.0.0/0` for outbound rules, as this may cause EFA health check failures". Flag an
outbound `0.0.0.0/0` rule on an EFA HyperPod cluster as RISK, and link it to any EFA deep
health check failure. Source: same page.

## 3. ParallelCluster nodes that never arrive (scaling, bootstrap, protected mode)

Streams in `/aws/parallelcluster/<cluster>-<timestamp>` on the head node:
`<host>.<instance-id>.clustermgtd`, `.slurm_resume`, `.slurmctld`; on compute nodes
`.cloud-init-output`.

| String | Meaning | Conclusion |
|--------|---------|------------|
| `InsufficientInstanceCapacity` in `clustermgtd` or `slurm_resume` | EC2 had no capacity for the launch | Branch B (capacity) |
| `Found the following bootstrap failure nodes` | Nodes launched but failed to join | Configuration or lifecycle failure; node verdict LEAVE ALONE; read the node's `cloud-init-output` |
| `Node bootstrap error` | Reason for a bootstrap failure | Same |
| `Partitions bootstrap failure count` ... `cluster will be set into protected mode if protected failure count reach threshold` | Repeated bootstrap failures | After the threshold, the cluster enters protected mode and stops launching into the failing queue. Report the queue |

Sources: [Slurm cluster protected mode](https://docs.aws.amazon.com/parallelcluster/latest/ug/slurm-protected-mode-v3.html),
[Node bootstrap error](https://docs.aws.amazon.com/parallelcluster/latest/ug/compute-node-initialization-bootstrap-error-v3.html).

## 4. EFA nodes in a public subnet (ParallelCluster)

From ParallelCluster 3.15.0, EFA-enabled nodes launch with more than one network interface,
and "Amazon EC2 does not auto-assign a public IP address to an instance launched with more
than one network interface". Such nodes "fail to bootstrap if they rely on an auto-assigned
public IP for internet access (a public subnet with no NAT gateway)".

Detect: compute subnet route table has `0.0.0.0/0` to an `igw-` and no NAT; nodes have more
than one network interface and no `PublicIpAddress`. Conclude: proven precondition FAIL,
node verdict LEAVE ALONE. Source: [ParallelCluster EFA](https://docs.aws.amazon.com/parallelcluster/latest/ug/efa-v3.html).

## 5. Capacity Block not yet active

`DescribeCapacityReservations` `State = scheduled` with `StartDate` in the future: nodes
cannot launch into it yet. Expected behavior, not a fault. State the start time.

## 6. FSx for Lustre maintenance window

`fsx.DescribeFileSystems` `WeeklyMaintenanceStartTime` (day and UTC time). During patching
"your file system will be temporarily unavailable", operations retry, and "the in-memory
cache will be erased during maintenance, leading to higher latencies". A stall that starts
inside the window, followed by higher latency, is FSx maintenance: `Proven` if client I/O
drops exactly in the window, otherwise `Hypothesis`.
Source: [FSx for Lustre maintenance windows](https://docs.aws.amazon.com/fsx/latest/LustreGuide/maintenance-windows.html).

## 7. HyperPod-specific visibility

- HyperPod "currently doesn't support the exportation of system metrics to Amazon
  CloudWatch", and its instances do not appear in the customer account's EC2 APIs. GPU
  activity for HyperPod nodes is therefore `Not observable` in CloudWatch; point to the
  HyperPod observability add-on (Amazon Managed Service for Prometheus). Source:
  [HyperPod FAQ](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-faq-slurm.html).
- Deep health check results are written to `DeepHealthCheckResults/<id>` streams in the
  cluster log group, for example `Encountered FaultyInstance. Replace the Instance. ...
  ERROR:Bandwidth has less than threshold: Expected minimum threshold :80,NCCL Test output Bw: 30`.
  A failure there is hardware-grounded evidence for REPLACE.
- HyperPod EKS node labels (read with the EKS API when available):
  `sagemaker.amazonaws.com/node-health-status` = `Schedulable`, `Unschedulable` (deep
  health checks running), `UnschedulablePendingReplacement`, or `UnschedulablePendingReboot`.
  A node can be `Running` in the SageMaker API while tainted unschedulable. With
  `NodeRecovery = None`, a pending label stays until an operator acts.
  Source: [HyperPod EKS resilience labels](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-eks-resiliency-node-labels.html).

## 8. Straggler GPU (clock, temperature, power, PCIe)

With `CWAgent` NVIDIA metrics per `index`: `nvidia_smi_clocks_current_sm`,
`nvidia_smi_temperature_gpu`, `nvidia_smi_power_draw`, `nvidia_smi_pcie_link_width_current`,
`nvidia_smi_pcie_link_gen_current`. One GPU clearly below its peers on the same node during
the same job is a straggler candidate: MONITOR, then REBOOT if it persists. Label it
`Hypothesis` unless it lines up with the slowdown; outlier thresholds are heuristics.
AWS recommends persistently setting maximum clocks
([Optimize GPU settings](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/optimize_gpu.html)).
