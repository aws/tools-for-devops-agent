# Amazon ElastiCache troubleshooting

This skill helps AWS DevOps Agent name the root cause of an Amazon ElastiCache
incident from read-only telemetry: latency spikes, high engine CPU, one hot shard,
memory pressure and `OOM` write failures, evictions, connection timeouts and churn,
replication lag, failovers, serverless throttling, and engine error replies. When the
operator asks, it can also apply one approved mitigation through DevOps Agent directed
actions and verify it.

## ⚠️ Important Notice

This skill is sample code, not intended for production use without additional
review and testing. Users should validate in a non-production environment first.
Investigations are read-only: every change is a recommendation. The skill applies a
change only when the operator asks in chat, directed actions are enabled, and the
operator approves that single action.

## Purpose

Several ElastiCache failure modes look identical from the application. Keys that
"disappear" can be evictions, TTL expiry or a cold cache. Latency on one shard can be a
hot key or an undersized node. Telling them apart needs ElastiCache-specific
knowledge: which metric separates the causes, which units and limits apply, and
which engine data is redacted from delivered logs. This skill gives the agent that
knowledge as reference files: the queries to collect the evidence and the ElastiCache
facts needed to read it.

## Key Capabilities

- Identifies the deployment (node-based or serverless, engine, cluster mode) and picks
  the metrics path
- Queries the native ElastiCache for Valkey OpenTelemetry metrics with PromQL:
  per-shard load and skew, per-command calls and latency, error replies by type,
  memory, connections and network allowance
- Uses classic `AWS/ElastiCache` CloudWatch metrics for serverless caches, Redis OSS and
  Memcached, and for the metrics OpenTelemetry has no equivalent for
- Correlates ElastiCache events, CloudTrail changes, parameter groups and delivered
  slow logs with the onset
- Rules out the lookalike cause with evidence before naming the root cause
- Recommends operator-run engine commands (for example `CLUSTER SLOT-STATS`,
  `SLOWLOG GET`) when only engine data can name a key or client
- On request, applies one approval-gated mitigation (for example
  `maxmemory-policy = allkeys-lru` for `OOM` on a cache whose data can be regenerated), with a pre-check,
  verification and rollback

## Prerequisites

- An Agent Space with access to the account and Region of the cache.
- Read-only permissions, all included in the AWS managed policy
  `AIDevOpsAgentAccessPolicy`: `elasticache:Describe*`, `cloudwatch:GetMetricData`,
  `cloudwatch:ListMetrics`, `logs:StartQuery`, `logs:GetQueryResults`,
  `logs:FilterLogEvents`, `cloudtrail:LookupEvents`. In that policy,
  `cloudwatch:ListMetrics` is covered by `cloudwatch:List*`.
- The OpenTelemetry queries use CloudWatch PromQL (the `list_prometheus_metadata` and
  `get_prometheus_metrics` tools). CloudWatch documents that PromQL queries need
  `cloudwatch:GetMetricData` and `cloudwatch:ListMetrics`
  ([IAM permissions for PromQL](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-PromQL.html#CloudWatch-PromQL-IAM)),
  both of which the managed policy above allows.
- Optional but recommended: slow log delivery to CloudWatch Logs for node-based
  clusters.
- OpenTelemetry metrics are emitted automatically for node-based Valkey replication
  groups. No configuration is needed for the vended metrics the skill uses. Queries
  through the CloudWatch API are charged by samples scanned.

### Optional: applying mitigations

To let the agent apply a mitigation after approval
([directed actions](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-working-with-directed-actions.html)):

1. Create an actions role that trusts `aidevops.amazonaws.com` with `sts:AssumeRole`,
   `sts:SetSourceIdentity` and `sts:TagSession`, with `aws:SourceAccount` and
   `aws:SourceArn` conditions for your Agent Spaces. Allow only the actions the skill
   can propose: `elasticache:ModifyCacheParameterGroup`,
   `elasticache:ModifyReplicationGroupShardConfiguration`,
   `elasticache:IncreaseReplicaCount` and `elasticache:ModifyServerlessCache`, scoped to
   your caches and parameter groups (or a tag condition).

   The agent never removes capacity, and rollbacks that remove capacity are operator-run.
   The role leaves out `elasticache:DecreaseReplicaCount`. Two of the actions above can
   also lower capacity (`ModifyReplicationGroupShardConfiguration` with a lower shard
   count, `ModifyServerlessCache` with a lower limit), and IAM cannot tell the two
   directions apart, so for those the rule is enforced by the skill and by the
   operator's approval of each action, not by the role.
2. Register it as the actions role on the Agent Space's AWS account (Capabilities).
3. Turn on **Enable agent actions** (Configuration).

Every change still needs the operator's approval in chat. Changes cannot run inside an
autonomous investigation, and the agent refuses delete operations.

## Usage

The skill loads for investigations and chat about ElastiCache. Example prompts:

- "Since about 14:15 UTC our application reports connection timeouts to ElastiCache
  cluster my-cache in us-east-1, and the cluster CPU went up. Find the root cause."
- "Writes to our product catalog cache started failing around 10:00 UTC. What's wrong?"
- "We see periodic latency spikes on ElastiCache cluster my-cache. Find the root cause."
- In chat, after an investigation: "The data in this cache can be regenerated, so it is
  safe to evict. Apply the mitigation."

## Limitations

- Scope is Amazon ElastiCache (node-based and serverless). Self-managed Valkey, Redis OSS
  or Memcached on EC2 is not covered: its telemetry and operations are not defined by
  ElastiCache.
- ElastiCache for Redis OSS has no OpenTelemetry metrics, and older versions lack some
  metrics and commands. The skill checks the engine version first. Memcached is covered
  with classic metrics only.
- The agent cannot connect to the cache (it runs outside the customer VPC), so it
  cannot name a hot or big key by itself. It recommends the engine command for the
  operator to run.
- Delivered slow logs redact key names and arguments.
- OpenTelemetry metrics are not emitted for serverless caches, Redis OSS, Memcached or
  replication groups on Outposts.
- Mitigations are limited to the ElastiCache API operations in
  `references/propose-mitigation.md`. Data commands (`LTRIM`, `DEL`, `EXPIRE`), client changes
  and application fixes stay with the operator.

## Files

| File | Content |
|---|---|
| `SKILL.md` | Scope, rules, workflow checklist, validation step, output format |
| `references/discover-deployment.md` | Which kind of cache it is, metrics path, features by engine version |
| `references/check-events-and-changes.md` | ElastiCache events and CloudTrail lookups |
| `references/read-parameters.md` | Reading parameters, and the parameters this skill names |
| `references/query-logs.md` | Slow log and engine log, and the Logs Insights queries |
| `references/query-otel-metrics.md` | OpenTelemetry PromQL rules, triage batch and interpretation |
| `references/query-classic-metrics.md` | Classic CloudWatch metrics by question |
| `references/error-replies.md` | Engine error replies, how to confirm, how to fix |
| `references/recommend-engine-command.md` | Operator-run engine commands for keys, slots and clients |
| `references/propose-mitigation.md` | Approval-gated mitigations: operation, pre-check, verification, rollback |
