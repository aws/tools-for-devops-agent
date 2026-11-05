---
name: elasticache-troubleshooting
description: Use this skill when an operator is investigating a problem with an Amazon
  ElastiCache cache, or with any Valkey, Redis OSS or Memcached cache on AWS, even if
  they only describe the symptom. Triggers include application timeouts while the cache
  dashboard looks healthy, latency talking to the cache, session or cache writes
  failing, high cache CPU or one hot shard, memory full, keys disappearing or a falling
  hit rate, connection errors or spikes, authentication failures, stale reads from
  replicas, a failover, serverless throttling, and error replies such as OOM, MOVED,
  CROSSSLOT, READONLY, NOAUTH or CLUSTERDOWN. Use it to find the root cause, rule out
  the lookalike cause, and give the operator a fix, or to apply an approved
  mitigation when the operator asks. Do not use it to create, size or
  migrate caches.
metadata:
  author: PopaCarlaDiana
  version: "1.0.0"
  summary: "Root-cause analysis for ElastiCache incidents from OpenTelemetry and CloudWatch metrics, events and logs, with approval-gated mitigation."
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA, INCIDENT_MITIGATION, CHAT"
  aws-devops-agent-skills.aws-services: "Amazon ElastiCache, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Databases, Observability"
---

# Amazon ElastiCache troubleshooting

Name the root cause of an ElastiCache incident from evidence, rule out the lookalike
cause that produces the same symptom, and give the operator a fix. When the operator
asks, apply one approved mitigation and verify it.

## Rules

- **Read-only while investigating.** Never run `modify-*`, `reboot-*`, `test-failover`,
  scaling, snapshot or delete operations during an investigation, and never create a
  resource metrics configuration (detailed OpenTelemetry metrics are billed). Present
  every change as a recommendation with its impact.
- **Changes only on request, one at a time.** Apply a change only when the operator asks
  you in chat to apply a mitigation and the change is a directed action they approve.
  Then follow Step 7. Never delete a resource, never change a production setting the
  operator did not name, and never batch several changes into one approval.
- **No data-plane access.** The cache endpoint is inside the customer's VPC. Do not
  try to connect. When only engine data can settle the question (for example, naming
  a hot key), recommend an operator-run command from
  [references/engine-followups.md](references/engine-followups.md) and say which
  result confirms the hypothesis.
- **Evidence over symptoms.** Every finding quotes the metric, the node or shard, the
  value and the time, compared with a baseline window of the same length before the
  onset.
- **Keep metric queries narrow.** PromQL and `GetMetricData` calls through the API are
  billed by CloudWatch (PromQL by samples scanned). Filter on the cache and the window,
  and aggregate.

## Workflow

Copy this checklist and complete every step in order.

- [ ] Step 1: Identify the deployment and choose the metrics path
- [ ] Step 2: Check events and changes at the onset
- [ ] Step 3: Separate the cause from its lookalikes
- [ ] Step 4: Check configuration and the slow log
- [ ] Step 5: Validate before reporting
- [ ] Step 6: Report
- [ ] Step 7: Apply an approved mitigation (only when the operator asks)

### Step 1: Identify the deployment and choose the metrics path

Run whichever applies (the operator may not say which kind of cache it is):

```
use_aws(service_name="elasticache", operation_name="describe_replication_groups",
        parameters={"ReplicationGroupId": "<id>"})
use_aws(service_name="elasticache", operation_name="describe_serverless_caches",
        parameters={"ServerlessCacheName": "<name>"})
use_aws(service_name="elasticache", operation_name="describe_cache_clusters",
        parameters={"CacheClusterId": "<id>", "ShowCacheNodeInfo": True})
```

Record: engine and version, serverless or node-based, `ClusterEnabled`, shards and
node roles per AZ, node type, `MultiAZ`/`AutomaticFailover`, parameter group name,
`LogDeliveryConfigurations`, and for serverless `CacheUsageLimits`.

- **Node-based Valkey:** load
  [references/otel-promql.md](references/otel-promql.md) now and run the OpenTelemetry
  queries yourself, whatever your role:
  1. Load the `exploring-metrics` skill and its `cloudwatch-promql` reference. Loading
     them makes the PromQL tools (`list_prometheus_metadata`, `get_prometheus_metrics`)
     available to you, including when you are a context-gathering or research
     sub-agent.
  2. Run the workflow in that reference (metadata check, triage batch over the
     incident and baseline windows).
  3. Only if the PromQL tools are still missing after step 1 and you can start a
     sub-agent, delegate a metrics task with the text "Load the exploring-metrics skill
     and its cloudwatch-promql reference, then query the ElastiCache for Valkey
     OpenTelemetry metrics with PromQL", the *Query rules*, *Triage batch* and
     *Interpretation* sections of the reference, the replication group ID, account,
     Region and both windows.

  Report OpenTelemetry metrics as unavailable only if `list_prometheus_metadata`
  returned no series or an error, or the PromQL tools were missing and you could not
  delegate. Quote which one as a gap.
- **Serverless (any engine), Redis OSS, Memcached, or gaps in the OpenTelemetry
  path:** load [references/classic-metrics.md](references/classic-metrics.md) for the
  classic `AWS/ElastiCache` queries.

### Step 2: Check events and changes at the onset

```
use_aws(service_name="elasticache", operation_name="describe_events",
        parameters={"SourceType": "replication-group", "SourceIdentifier": "<id>",
                    "StartTime": "<onset - 2h>", "EndTime": "<now>"})
```

Use `serverless-cache` or `cache-cluster` as the source type when that applies.
`DescribeEvents` returns up to 14 days of events, as message text. Look for messages
about a failover, a node replacement, a reboot, scaling, a snapshot or a parameter
change (their SNS names are `ElastiCache:FailoverComplete`,
`ElastiCache:CacheNodeReplaceStarted`/`Complete`, `ElastiCache:CacheNodesRebooted`,
`ElastiCache:ReplicationGroupScalingComplete`/`Failed`, `ElastiCache:SnapshotComplete`,
`ElastiCache:CacheClusterParametersChanged`) and, on serverless, the "Cache limit
approaching" notification for a slot near its 32 GiB limit. Also look up CloudTrail for
`ModifyReplicationGroup`, `ModifyCacheParameterGroup`, `ModifyServerlessCache`,
`TestFailover` and security group changes in the window. A change that lines up with
the onset is the leading hypothesis; confirm it with metrics.

### Step 3: Separate the cause from its lookalikes

Load [references/diagnosis-table.md](references/diagnosis-table.md) now; it is required
for every investigation. Anchor on the reported symptom and onset, then use the row for
that symptom. Rows cover: `OOM` write failures; evictions and hit-rate drops; latency on
every shard; periodic latency spikes; one hot shard; one shard's memory high or
climbing; big keys; command timeouts while the cluster looks healthy; retry bursts;
network limits; climbing connections; `maxclients`; connection churn; replication lag;
failovers; authentication errors and IAM token expiry; TLS mismatch; serverless
throttling.

When the operator quotes an engine error reply, or the error metrics show one, load
[references/error-strings.md](references/error-strings.md) to map it to its cause.

### Step 4: Check configuration and the slow log

- **Parameters** (node-based only):
  `use_aws(service_name="elasticache", operation_name="describe_cache_parameters",
  parameters={"CacheParameterGroupName": "<pg>", "Source": "user"})`. Check
  `maxmemory-policy`, `reserved-memory-percent`, `timeout`, `slowlog-log-slower-than`.
  Parameters missing from the `Source: user` result have their default value; a default
  group (`default.*`) uses `maxmemory-policy = volatile-lru`.
- **Slow log:** if `LogDeliveryConfigurations` sends `slow-log` to CloudWatch Logs, run
  a Logs Insights query on that log group over the window (JSON format):
  ```
  fields Command, `Duration (us)`, ClientAddress, CacheClusterId
  | parse Command /^(?<cmd>\S+)/
  | stats count(*) as n, max(`Duration (us)`) as max_us, avg(`Duration (us)`) as avg_us by cmd, CacheClusterId
  | sort max_us desc | limit 20
  ```
  Durations are in **microseconds**, and each one is time the engine's main thread
  spent on that command. Only commands slower than `slowlog-log-slower-than` (default
  10,000 µs) are logged. Delivered logs **replace the key and arguments** with
  `... (N more arguments)`, so name the command, the node and the client address, and
  recommend `SLOWLOG GET` to the operator for the key. Log delivery is not available
  for serverless caches.

### Step 5: Validate before reporting

Check your draft against each point. If one fails, go back to the step that produces
the missing evidence, then check again.

- [ ] Every metric value and timestamp is quoted from a tool result, not estimated.
- [ ] The onset is the first datapoint of the failure signal, and the baseline window
      contains no other incident.
- [ ] The cause's discriminating evidence from the diagnosis table is present.
- [ ] The lookalike's evidence was checked and is absent, not just unchecked.
- [ ] Every remediation is phrased as an operator-run action (Step 7 is the only
      exception, and only on request).

### Step 6: Report

Always give all five parts, even when the cause looks obvious.

1. **Root cause:** one sentence naming the mechanism, not the symptom.
2. **Evidence:** metric, node/shard, value and time, against the baseline.
3. **Ruled out:** the lookalike and the evidence that excludes it.
4. **Remediation:** an immediate mitigation and a durable fix, both for the operator
   to run.
5. **Gaps:** what could not be verified, with the command that would verify it.

### Step 7: Apply an approved mitigation (only when the operator asks)

Use this step only after a root cause is confirmed and the operator asks you to apply
the fix. Load [references/mitigation.md](references/mitigation.md) and use the row for
the confirmed cause. If the cause has no row there, or the row says operator-only,
give the manual steps instead.

1. **Pre-check:** run the row's read-only checks and quote the values. Stop and say why
   if a check fails.
2. **Propose exactly one operation:** the API operation, the target resource, the exact
   parameters, the expected effect, the risk and blast radius, how long it takes, and the
   rollback operation. Then request approval.
3. **After approval, apply it**, then wait for the row's verification signal over at
   least 5 one-minute datapoints after the change, and quote it against the values from
   the pre-check.
4. **Report:** applied or not, verified or not, and the rollback command. If the
   verification signal did not appear, say so and propose the rollback; do not try a
   second change on your own.

## Gotchas

- `EngineCPUUtilization` is the engine's single main thread. `CPUUtilization` is the
  whole host and stays low on nodes with 4 or more vCPUs while the engine is saturated.
  On nodes with 2 or fewer vCPUs (for example `t4g.small`), judge saturation with
  `CPUUtilization` against `90 / vCPU count` (AWS guidance: 45% on 2 vCPUs).
  `TrafficManagementActive = 1` means ElastiCache is managing traffic because more
  commands arrive than the engine can process; sustained, it indicates an underscaled
  node.
- `SuccessfulReadRequestLatency`/`SuccessfulWriteRequestLatency` support percentiles
  (`p99` through `ExtendedStatistics`). They measure the time the engine takes to
  respond, so the client's network round trip, TLS and its own processing are not in
  them. Never compare a client timeout with them alone. Pipelining with replies
  enabled inflates them.
- Units: request latency and slow log durations are microseconds; `ReplicationLag` is
  seconds; memory percentages are 0-100.
- Group-level aggregates hide skew. Always break down by node or shard.
- Burstable nodes (`cache.t3`, `cache.t4g`): `CPUCreditBalance` near 0 matters only when
  CPU is actually high. CPU credit metrics have 5-minute datapoints only. Never recommend a bigger node when CPU and latency are normal; a
  healthy cluster with client timeouts is a client-side cause.
- Serverless has no OpenTelemetry metrics and no parameter groups. Its
  `maxmemory-policy` is `volatile-lru`, so it evicts only keys that have a TTL; with
  none, writes at the limit fail with `OOM`. Its CloudWatch dimension is `clusterId`.
- In cluster mode, a replica redirects commands for its slots to the primary with
  `MOVED`, so writes sent to a replica return `MOVED`, not `READONLY`. A low, steady
  `MOVED` rate can come from clients refreshing their slot map; a high or rising rate
  is a client or topology problem.
- `CLUSTER SLOT-STATS` takes either `SLOTSRANGE <start> <end>` or `ORDERBY <stat>
  [LIMIT n]`, never both. Its statistics are `KEY-COUNT`, `CPU-USEC`,
  `NETWORK-BYTES-IN` and `NETWORK-BYTES-OUT`; there is no memory statistic. To name a
  key that uses a lot of memory, recommend `--memkeys`/`--bigkeys` on a replica.
- Cluster-aware clients connect to each node endpoint after discovery through the
  configuration endpoint. That is normal, not a misconfiguration.
- A high rate of `HELLO`/`CLIENT SETINFO`/`AUTH`/`PING` with no data commands is what
  many clients send on each *new* connection. Current connections stay flat because each connection
  lives only milliseconds. The churn rate is new connections per second.
- Mention an earlier episode outside the incident window only with facts you verified,
  and keep it separate from the root cause.
- A hit ratio over very few lookups is not meaningful (it jumps to 0% or 100%); quote
  the lookup rate with it.
- CloudWatch keeps 1-minute datapoints for 15 days and 5-minute datapoints for 63 days.
  For older incidents, use a 300-second period.
- `CurrConnections` includes 4 to 6 connections that ElastiCache uses for monitoring.
