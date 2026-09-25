# NCCL Transport, NVLink / NVSwitch, and EFA Signals

Where each GPU-communication signal can be seen, what a good and a bad value look like,
and what to do when it is not visible. Log strings are quoted from the sources linked in
each section. Do not paraphrase them into search patterns that match more than they say.

## 1. Which transport NCCL actually used

NCCL writes its transport choices only when `NCCL_DEBUG=INFO` (or higher) is set, and only
to the job's stdout or to `NCCL_DEBUG_FILE`. These reach CloudWatch only if the customer
ships job output. Search every log source found in SKILL.md Step 3a for `NCCL INFO` and
`NCCL WARN` first. **If there are no NCCL lines at all, NCCL transport is `Not observable`.**
Never infer "NCCL used EFA" from the instance type or the EFA security group.

| Log line | Meaning | Verdict |
|----------|---------|---------|
| `NET/OFI Selected Provider is efa` and `Using network AWS Libfabric` | Inter-node traffic goes over EFA through the AWS OFI NCCL plugin | Good |
| `Using network IB` | NCCL chose an InfiniBand-verbs network | Unexpected on EC2 EFA instances; report it |
| Channel lines `... via NET/Socket/<n>` | Inter-node traffic over TCP sockets | **Bad** on EFA instances: silent fallback. The AWS blog on P3dn measured about a three-fold bus-bandwidth gain for EFA over TCP |
| Channel lines `... via P2P/CUMEM` | Intra-node GPU to GPU by direct peer access (NVLink on NVSwitch nodes) | Good |
| `NVLS Creating Multicast group ...` | NVLink SHARP in use for collectives | Good on NVSwitch systems that support it |
| Channel lines `... via SHM/direct/direct` | Intra-node traffic through host shared memory | On an NVSwitch node, peer access is not being used; report as degraded |

Sources: [NCCL logging](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/troubleshooting/logging.html),
[Training LLMs on SageMaker: best practices](https://aws.amazon.com/blogs/machine-learning/training-large-language-models-on-amazon-sagemaker-best-practices/),
[Optimizing deep learning on P3dn with EFA](https://aws.amazon.com/blogs/compute/optimizing-deep-learning-on-p3-and-p3dn-with-efa/).

When NCCL is not observable, give the operator this to collect on one affected job:
`NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=INIT,NET,P2P,SHM,NVLS NCCL_DEBUG_FILE=/fsx/nccl_%h_%p.log`
(subsystem names from the NCCL logging page), then search the files for the lines above.

## 2. NVLink and NVSwitch fabric

The CloudWatch agent's NVIDIA plugin does **not** collect any NVLink counter (its full
metric list is utilization, temperature, power, memory, PCIe link, encoder, and clocks).
NVLink health reaches AWS only through the system log:

| Signal | Where | Meaning |
|--------|-------|---------|
| `NVRM: Xid ...: 74` | Kernel log, HyperPod HMA | NVLink error (NVIDIA catalog: immediate action per NVLink workflow, investigatory action contact support). Hardware class |
| `NVRM: Xid ...: 71`, `NVLink: fatal error detected on link <n>` | Kernel log, HyperPod HMA (`reason: XidHardwareFailure`) | Fatal NVLink error; example in the HyperPod HMA documentation. Hardware class |
| `NVRM: Xid ...: 155` / `156` | Kernel log | GPU NVLink flit CRC error / lane error (listed by Amazon ECS GPU auto repair). Hardware class |
| Other `NVRM:` lines that mention NVLink without `Xid` | Kernel log | Driver diagnostics. List them in the timeline with node and hour. **Do not classify** them or call them a cause without corroboration |
| Fabric Manager start: `Started "Nvidia Fabric Manager"` | System log (`/var/log/messages` or journal) | Fabric Manager service started. Applies to NVSwitch instance types (section 4) |
| `CX Bridge device ... is usable for NVLink subnet management` | System log | P6-B200 and P6-B300 only: AWS documents that on these types Fabric Manager configures NVFabric through ConnectX bridge devices, so this line shows the bridge was found |
| Fabric Manager absent, failed, or restarting on an NVSwitch instance | System log | NVLink between GPUs may not be up. Hardware or driver-stack problem: node verdict `REBOOT`, then `REPLACE` if it recurs. AWS documents Fabric Manager as required on P6-B200 and P6-B300; on other NVSwitch types, report a failure as a strong signal but label the NVLink impact `Hypothesis (to validate)` with `nvidia-smi topo -m` as the check |
| `nvidia-fabricmanager.service: ... PIDFile= references a path below legacy directory /var/run/` | System log | systemd path warning. **Benign.** Exclude it before counting Fabric Manager "errors" |

Sources: [NVIDIA Xid catalog](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html),
[HyperPod health monitoring](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-eks-resiliency-health-monitoring-agent.html),
[ECS GPU auto repair Xid list](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/managed-instances-gpu-auto-repair.html),
[EC2 public NVIDIA drivers, P6-B200 and P6-B300 considerations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/public-nvidia-driver.html),
[CloudWatch agent NVIDIA metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-NVIDIA-GPU.html).

On-node confirmation for the operator (not available through AWS APIs): NVLink status and
error counters from `nvidia-smi nvlink` and DCGM, and `systemctl status nvidia-fabricmanager`.

## 3. EFA error counters

| Source | Metric names |
|--------|--------------|
| CloudWatch agent `efa` section (namespace `CWAgent`) | `efa_retrans_pkts`, `efa_retrans_timeout_events`, `efa_impaired_remote_conn_events`, `efa_unresponsive_remote_events`, `efa_rx_dropped`, `efa_rdma_read_wr_err`, `efa_rdma_write_wr_err` |
| HyperPod observability EFA exporter | `node_amazonefa_*` (for example `node_amazonefa_rx_drops`, `node_amazonefa_rdma_read_wr_err`) |
| On the node | `rdma -p statistic show`, or `/sys/class/infiniband/<device>/ports/<port>/hw_counters/` |

Read them as signals, not thresholds: a rise in retransmit timeouts, impaired or
unresponsive remote events, or work-request errors on the affected nodes, starting at or
before the hang, supports Branch D. A rise that starts after the hang is an effect.
Sources: [CloudWatch agent EFA metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-EFA.html),
[Monitor an EFA](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa-working-monitor.html).

## 4. Which instance types have an NVSwitch fabric

`DescribeInstanceTypes` does not report NVSwitch or NVLink. Use the "GPU Peer to Peer"
column of the [EC2 accelerated computing instance page](https://aws.amazon.com/ec2/instance-types/accelerated-computing/),
summarised here as checked:

| Instance types | GPU peer to peer | Treat as |
|----------------|------------------|----------|
| p4d.24xlarge, p4de.24xlarge | 600 GB/s NVSwitch | NVSwitch |
| p5.48xlarge, p5e.48xlarge, p5en.48xlarge | 900 GB/s NVSwitch | NVSwitch |
| p6-b200.48xlarge, p6-b300.48xlarge, P6e-GB200 UltraServers | 1800 GB/s NVSwitch | NVSwitch (P6e: NVLink domain spans the UltraServer) |
| p5.4xlarge and other single-GPU sizes | N/A | No intra-node GPU communication |
| Multi-GPU g7 and g7e sizes | Yes via PCIe | PCIe peer to peer, no NVSwitch |
| Multi-GPU g4dn, g5, g6, g6e sizes | Not listed | `NVSwitch presence unverified`; do not expect Fabric Manager; the operator checks `nvidia-smi topo -m` |

For a type not in this table, re-check the instance page. Never infer NVSwitch from the
GPU model name.

## 5. Software stack minimums

AWS publishes minimums for these types ([DLAMI P6 software requirements](https://docs.aws.amazon.com/dlami/latest/devguide/p6-support-dlami.html)):

| Component | P6-B200 | P6-B300 | P6e-GB200 |
|-----------|---------|---------|-----------|
| NVIDIA driver | R570 | R580 | R570 |
| NVLink 5 support | R570 | R580 | n/a in table |
| CUDA toolkit | 12.8 | 13.0 | 12.8 |
| Linux kernel | 6.1 | 6.1 | 6.12 |
| EFA installer | 1.41.0 | 1.44.0 | 1.42.0 |
| AWS OFI NCCL plugin | 1.15.0 | 1.17.1 | 1.15.0 |

For other GPU types no minimum table was found. Compare with the stack of a current DLAMI
that lists the type in `supported_ec2_instances` (DLAMI release notes) and report the
result as a comparison, not a pass or fail.

How to read versions without logging in:

| Component | Where |
|-----------|-------|
| NVIDIA driver | Kernel boot line `NVRM: loading NVIDIA UNIX Open Kernel Module for x86_64 <version>` in the shipped kernel log |
| Linux kernel | Kernel boot lines, if shipped |
| AWS OFI NCCL plugin | NCCL INFO lines at init, if shipped |
| CUDA toolkit, EFA installer | Not in AWS APIs; ask |

A version that cannot be read is `UNVERIFIED`, not a pass.
