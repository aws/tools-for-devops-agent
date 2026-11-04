---
name: elasticache-troubleshooting
description: Use this skill when an operator is investigating a problem with an Amazon
  ElastiCache cache, or with any Valkey, Redis OSS or Memcached cache on AWS, even if
  they only describe the symptom. Triggers include application timeouts or latency
  talking to the cache, session or cache writes failing, high cache CPU or one hot
  shard, memory full, keys disappearing or a falling hit rate, connection errors or
  spikes, stale reads from replicas, a failover, serverless throttling, and error
  replies such as OOM, MOVED, CROSSSLOT, READONLY, NOAUTH or CLUSTERDOWN. Use it to find
  the root cause, rule out the lookalike cause, and give the operator a fix. Do not use
  it to create, size or migrate caches.
metadata:
  author: PopaCarlaDiana
  version: "1.0.0"
  summary: "Root-cause analysis for ElastiCache incidents from OpenTelemetry and CloudWatch metrics, events and logs."
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.aws-services: "Amazon ElastiCache, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Databases, Observability"
---

# Amazon ElastiCache troubleshooting

Name the root cause of an ElastiCache incident from evidence, rule out the lookalike
cause that produces the same symptom, and give the operator a fix.

## Rules

- **Read-only.** Never run `modify-*`, `reboot-*`, `test-failover`, scaling, snapshot
  or delete operations, and never create a resource metrics configuration (it is
  billed). Present every change as a recommendation for the operator to run, with
  its impact. Do not offer to apply it yourself.
- **No data-plane access.** The cache endpoint is inside the customer's VPC. Do not
  try to connect. When only engine data can settle the question (for example, naming
  a hot key), recommend an operator-run command from
  [references/engine-followups.md](references/engine-followups.md) and say which
  result confirms the hypothesis.
- **Evidence over symptoms.** Every finding quotes the metric, the node or shard, the
  value and the time, compared with a baseline window of the same length before the
  onset.

## Workflow

Copy this checklist and complete every step in order.

- [ ] Step 1: Identify the deployment and choose the metrics path
- [ ] Step 2: Check events and changes at the onset
- [ ] Step 3: Separate the cause from its lookalikes
- [ ] Step 4: Check configuration and the slow log
- [ ] Step 5: Validate before reporting
- [ ] Step 6: Report

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

Use `serverless-cache` or `cache-cluster` as the source type when that applies (events
are kept 14 days). Look for `FailoverComplete`, `CacheNodeReplaceStarted`/`Complete`,
`CacheClusterScalingComplete`/`Failed`, `SnapshotComplete` and, on serverless,
`Cache Limit Approaching`. Also look up CloudTrail for `ModifyReplicationGroup`,
`ModifyCacheParameterGroup`, `ModifyServerlessCache`, `TestFailover` and security group
changes in the window. A change that lines up with the onset is the leading hypothesis;
confirm it with metrics.

### Step 3: Separate the cause from its lookalikes

Load [references/diagnosis-table.md](references/diagnosis-table.md) now; it is required
for every investigation. Anchor on the reported symptom and onset, then use the row for
that symptom. Rows cover: `OOM` write failures; evictions and hit-rate drops; latency on
every shard; periodic latency spikes; one hot shard; one shard's memory high; big keys;
latency with low engine CPU; `maxclients`; connection churn; replication lag; failovers;
serverless throttling.

When the operator quotes an engine error reply, or the error metrics show one, load
[references/error-strings.md](references/error-strings.md) to map it to its cause.

### Step 4: Check configuration and the slow log

- **Parameters** (node-based only):
  `use_aws(service_name="elasticache", operation_name="describe_cache_parameters",
  parameters={"CacheParameterGroupName": "<pg>", "Source": "user"})`. Check
  `maxmemory-policy`, `reserved-memory-percent`, `timeout`, `slowlog-log-slower-than`.
  A default group (`default.*`) uses `volatile-lru`.
- **Slow log:** if `LogDeliveryConfigurations` sends `slow-log` to CloudWatch Logs, run
  a Logs Insights query on that log group over the window (JSON format):
  ```
  fields Command, `Duration (us)`, ClientAddress, CacheClusterId
  | parse Command /^(?<cmd>\S+)/
  | stats count(*) as n, max(`Duration (us)`) as max_us, avg(`Duration (us)`) as avg_us by cmd, CacheClusterId
  | sort max_us desc | limit 20
  ```
  Durations are in **microseconds** (above 100,000 means the engine thread was
  blocked). Delivered logs **redact key names**, so name the command, the node and the
  client address, and recommend `SLOWLOG GET` to the operator for the key.

### Step 5: Validate before reporting

Check your draft against each point. If one fails, go back to the step that produces
the missing evidence, then check again.

- [ ] Every metric value and timestamp is quoted from a tool result, not estimated.
- [ ] The onset is the first datapoint of the failure signal, and the baseline window
      contains no other incident.
- [ ] The cause's discriminating evidence from the diagnosis table is present.
- [ ] The lookalike's evidence was checked and is absent, not just unchecked.
- [ ] Every remediation is phrased as an operator-run action.

### Step 6: Report

Always give all five parts, even when the cause looks obvious.

1. **Root cause:** one sentence naming the mechanism, not the symptom.
2. **Evidence:** metric, node/shard, value and time, against the baseline.
3. **Ruled out:** the lookalike and the evidence that excludes it.
4. **Remediation:** an immediate mitigation and a durable fix, both for the operator
   to run.
5. **Gaps:** what could not be verified, with the command that would verify it.

## Gotchas

- `EngineCPUUtilization` is the engine's single main thread. `CPUUtilization` is the
  whole host and stays low on nodes with 4 or more vCPUs while the engine is saturated.
  On nodes with 2 or fewer vCPUs (for example `t4g.small`), judge saturation with
  `CPUUtilization` against `90 / vCPU count`. `TrafficManagementActive = 1` means the
  node is underscaled.
- `SuccessfulReadRequestLatency`/`SuccessfulWriteRequestLatency` support percentiles:
  request `p99` through `ExtendedStatistics`.
- Units: request latency and slow log durations are microseconds; `ReplicationLag` is
  seconds; memory percentages are 0-100.
- Group-level aggregates hide skew. Always break down by node or shard.
- Serverless has no OpenTelemetry metrics and no parameter groups, and evicts only keys
  that have a TTL.
- In cluster mode, a low steady `MOVED` rate is normal. Writes sent to a replica return
  `MOVED`, not `READONLY`.
- Cluster-aware clients connect to each node endpoint after discovery through the
  configuration endpoint. That is normal, not a misconfiguration.
- A high rate of `HELLO`/`CLIENT SETINFO`/`AUTH`/`PING` with no data commands is what
  each *new* connection sends. Current connections stay flat because each connection
  lives only milliseconds. The churn rate is new connections per second.
- Mention an earlier episode outside the incident window only with facts you verified,
  and keep it separate from the root cause.
- Hit ratios are noise below about 10 lookups per second.
- One-minute datapoints are kept 15 days. For older incidents, use a 300-second period.
