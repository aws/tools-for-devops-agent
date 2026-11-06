# GPU Evidence Coverage Audit

<!-- Loaded by SKILL.md. Content validated live against HyperPod Slurm, HyperPod EKS, and ParallelCluster clusters. -->

## Step 3a: Find the kernel log source and prove it covers the nodes

Xids are only as visible as the customer's log shipping. Locate the source for the
orchestrator, then prove it is actually capturing kernel messages from the affected
nodes before you trust a zero.

| Orchestrator | Where Xids can appear in CloudWatch Logs |
|--------------|------------------------------------------|
| HyperPod (Slurm or EKS) | HMA detections in `/aws/sagemaker/Clusters/<ClusterName>/<ClusterId>`. The per-node detection stream appears only after the first detection, so it is absent on healthy nodes. HyperPod does not ship the full kernel log. Also check any customer-shipped kernel log group (below). |
| AWS ParallelCluster 3 | `/aws/parallelcluster/<cluster-name>-<timestamp>`, streams `<hostname>.<instance-id>.system-messages` (`/var/log/messages`, Amazon Linux and RHEL) or `<hostname>.<instance-id>.syslog` (`/var/log/syslog`, Ubuntu). Present only when the cluster's CloudWatch logging is on. |
| Self-managed EC2, EKS, or custom pipelines | Whatever group the customer's CloudWatch agent, Fluent Bit, or similar ships `/var/log/messages`, `/var/log/syslog`, the journal, or `dmesg` to. There is no fixed name. |

How to find customer-shipped groups:

1. `logs.DescribeLogGroups` with `logGroupNamePattern` (a case-sensitive **substring**
   match, so it finds `/aws/<anything>/<cluster-name>/kernel`), paginated with `nextToken`.
   Run it once for the cluster name, then once each for `kernel`, `messages`, `syslog`,
   `system`, `dmesg`, `journal`, and `gpu`. Do **not** rely on `logGroupNamePrefix` alone:
   customer pipelines rarely use the `/aws/parallelcluster` or `/aws/sagemaker` prefix.
   If the account has few log groups, list them all instead.
2. For each candidate, `logs.DescribeLogStreams` ordered by `LastEventTime`. Keep the
   group if stream names contain the affected **instance IDs** or their private DNS
   hostnames. ParallelCluster and most agents put one or the other in the stream name.
3. Evaluate **every** candidate source before deciding, not just the first one found. A
   node is `Measured` if any one source passes both coverage checks below.
4. If nothing matches, report kernel logs as `Not observable` and name where the operator
   should look. Do not assume there are none.

**Coverage proof, required before reporting "no Xids":** a healthy kernel is quiet, so
"no kernel lines in the window" does **not** mean the log isn't shipped, and "some
kernel lines" does **not** mean it is. Prove two things per affected instance and per
source.

**(b) first: find the stream that carries kernel messages from this node.** Run over
the node's lifetime (since launch), not only the window:

```
filter @logStream like /<instance-id>/ and @message like /kernel:/
| stats count(*) as kernelLines, max(@timestamp) as lastKernelLine by @logStream
```

(`kernel:` is the syslog-format marker in `/var/log/messages`, `/var/log/syslog`, and
syslog-format journal forwarding. If the source ships the journal as JSON, filter on
its kernel transport field instead.) The `@logStream` values returned are the only
streams that can prove kernel coverage. `NVRM` lines among them (for example the
driver load banner at boot) additionally prove the NVIDIA driver's output reaches
this source. No rows means this source does not carry kernel messages for the node.

**(a) then: prove that exact stream was continuously live through the impact window.**
Filter on the exact stream name from (b), never on the instance ID alone. On
ParallelCluster the instance ID matches every stream for the node (`slurmd`,
`cloud-init`, `computemgtd`, and others), which makes a dead kernel stream look live.
Bin the padded window (start minus 1 hour, end plus 1 hour) by hour:

```
filter @logStream = "<exact stream name from (b)>"
| stats count(*) as lines by bin(1h) as hour
| sort hour asc
```

Live means every hour in the padded window has `lines > 0`. A syslog stream on a
running host normally carries systemd and agent lines every hour, so an empty hour is
a delivery gap. First and last event times alone are **not** proof: a stream can have
events at both ends and nothing in between. List every empty hour in the report.

**Other GPU-communication signals.** In the same pass, record per node whether each of
these is observable, using `references/nccl-nvlink-efa.md`: NCCL transport lines, Fabric
Manager start lines (NVSwitch instances), `efa_*` or `node_amazonefa_*` counters, and GPU
activity (`GPUPowerUtilization` or `CWAgent`). Each goes in the coverage table as
`Observable`, `Not observable`, or `Not applicable`. A missing signal is a gap to report,
never a clean result.

**HyperPod is different.** HyperPod does not ship the node's system log. The
health-monitoring agent watches it on the node and writes only **detections**, and the
CloudWatch stream for a node is created only when the first detection is written. A
healthy GPU node therefore has **no** `SagemakerHealthMonitoringAgent/<group>/<instance-id>`
stream. Treat
that as `No HMA detections`, not `Not observable`, provided that:

- the node is a GPU or Trainium instance (HMA runs on these by default), and
- the cluster log group is receiving other streams, such as `ClusterMetrics/slurm` or
  `LifecycleConfig/...`, so log delivery from the cluster is working.

If the log group has no streams at all, report HMA status as `Not observable` and ask
the operator to confirm on the node that `sagemaker-health-monitoring-agent.service`
is running. Queries (a) and (b) above do not apply to HMA streams.

Interpret the results as follows:

| (a) live across window | (b) kernel lines ever | Xid status to report |
|------------------------|------------------------|----------------------|
| Yes | Yes | `Measured`: the `NVRM: Xid` count in the window is real, including 0 |
| Yes | No | `Not observable`: the pipeline ships other logs but not kernel messages |
| No (empty hours in the window) | Any | `Not observable` for the empty hours. List them |
| No stream for the instance | n/a | `Not observable` |

- Evaluate every source separately. One live source is enough for `Measured`, but
  report dead sources too, because the operator probably thinks they work.
- Identical counts from different nodes in the same query set usually mean identical
  boot output from the same AMI, not live logging. Check the hourly bins.
- Coverage is a point-in-time verdict. Late delivery can fill a gap later, and a
  stopped shipper can resume. State the query time in the report, and if a gap ends
  shortly before the query, say so rather than assuming the data is permanently lost.
- For `Not observable`, tell the operator to check the node directly with
  `dmesg -T | grep -i nvrm` or `journalctl -k | grep -i xid`, and to fix log shipping.
  Never report it as "no GPU errors".
- Check the Logs Insights `statistics` too. `recordsScanned = 0` on query (a) has two
  causes: the query is wrong (group, region, time range), or the source has no events
  in the window. Query (b) is the control. If (b) returns rows for the same group and
  instance, the query is right and the kernel stream is empty for the window
  (`Not observable`). If (b) is also empty, fix the query before concluding anything.

Other `NVRM:` lines that are not `NVRM: Xid` are driver diagnostics, not Xids. List
them in the timeline if they cluster around the failure, but do not classify them with
the Xid table or name them a root cause without corroborating evidence.
