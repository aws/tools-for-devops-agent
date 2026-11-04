# Amazon ElastiCache troubleshooting

This skill helps AWS DevOps Agent name the root cause of an Amazon ElastiCache
incident from read-only telemetry: latency spikes, high engine CPU, one hot shard,
memory pressure and `OOM` write failures, evictions, connection timeouts and churn,
replication lag, failovers, serverless throttling, and engine error replies.

## ⚠️ Important Notice

This skill is sample code, not intended for production use without additional
review and testing. Users should validate in a non-production environment first.
It is read-only: every change it proposes (parameter, scaling, client configuration)
is a recommendation for the operator to review and run.

## Purpose

Several ElastiCache failure modes look identical from the application. Keys that
"disappear" can be evictions, TTL expiry or a cold cache. Latency on one shard can be a
hot key or an undersized node. Telling them apart needs ElastiCache-specific
knowledge: which metric separates the causes, which units and limits apply, and
which engine data is redacted from delivered logs. This skill gives the agent that
knowledge as a symptom → cause → evidence → lookalike table, plus the queries to
collect the evidence.

## Key Capabilities

- Identifies the deployment (node-based or serverless, engine, cluster mode) and picks
  the metrics path
- Queries the native ElastiCache for Valkey OpenTelemetry metrics with PromQL:
  per-shard load and skew, per-command calls and latency, error replies by type,
  memory, connections and network allowance
- Falls back to classic `AWS/ElastiCache` CloudWatch metrics for serverless caches,
  Redis OSS and Memcached
- Correlates ElastiCache events, CloudTrail changes, parameter groups and delivered
  slow logs with the onset
- Rules out the lookalike cause with evidence before naming the root cause
- Recommends operator-run engine commands (for example `CLUSTER SLOT-STATS`,
  `SLOWLOG GET`) when only engine data can name a key or client

## Prerequisites

- An Agent Space with access to the account and Region of the cache.
- Read-only permissions, covered by the default AWS DevOps Agent policy:
  `elasticache:Describe*`, `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`,
  `logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`,
  `cloudtrail:LookupEvents`.
- Optional but recommended: slow log delivery to CloudWatch Logs for node-based
  clusters.
- OpenTelemetry metrics are emitted automatically for node-based Valkey replication
  groups. No configuration is needed for the vended metrics the skill uses.

## Usage

The skill loads for investigations and chat about ElastiCache. Example prompts:

- "Since about 14:15 UTC our application reports connection timeouts to ElastiCache
  cluster my-cache in us-east-1, and the cluster CPU went up. Find the root cause."
- "Writes to our session cache started failing around 10:00 UTC. What's wrong?"
- "We see periodic latency spikes on ElastiCache cluster my-cache. Find the root cause."

## Limitations

- The agent cannot connect to the cache (it runs outside the customer VPC), so it
  cannot name a hot or big key by itself. It recommends the engine command for the
  operator to run.
- Delivered slow logs redact key names and arguments.
- OpenTelemetry metrics are not emitted for serverless caches, Redis OSS, Memcached or
  Outposts.

## Files

| File | Content |
|---|---|
| `SKILL.md` | Workflow, symptom-to-cause table, output format, gotchas |
| `references/otel-promql.md` | OpenTelemetry PromQL rules, triage batch and interpretation |
| `references/classic-metrics.md` | Classic CloudWatch metrics by question |
| `references/error-strings.md` | Engine error replies, how to confirm, how to fix |
| `references/engine-followups.md` | Operator-run engine commands for keys, slots and clients |
