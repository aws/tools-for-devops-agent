---
name: aws-elasticache-devops
description: Use this skill when an application that uses an Amazon ElastiCache cache
  (node-based or serverless; Valkey, Redis OSS or Memcached) sees connection errors or
  timeouts, command errors or timeouts (error replies such as OOM, MOVED, CROSSSLOT,
  READONLY, NOAUTH or CLUSTERDOWN), slower responses, write failures, a drop in cache
  hits, authentication failures, replicas that return older data than the primary, or a
  failover; or when an alarm fires on an ElastiCache metric such as engine CPU, memory,
  evictions, connections, latency, replication lag or throttled commands. It finds the
  root cause, separates it from the other causes of the same symptom, and gives the
  operator a fix, or applies an approved mitigation when the operator asks. Use it even
  if only the symptom is described. Do not use it to create, size or migrate caches, or
  for self-managed Valkey or Redis (for example on EC2).
metadata:
  author: PopaCarlaDiana, nanyan0312
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

## Scope

- **Amazon ElastiCache only**, node-based and serverless. Self-managed Valkey, Redis OSS
  or Memcached (for example on EC2) is out of scope: its metrics, logs and operations
  are not defined by ElastiCache.
- **Valkey is the primary target.** ElastiCache for Redis OSS is covered with classic
  metrics only: it has no OpenTelemetry metrics, and older versions lack some metrics
  and commands. Check the engine version before recommending a feature
  ([discover-deployment.md](references/discover-deployment.md)).
- **Memcached** is covered with classic metrics only.

## Rules

- **Read-only while investigating.** Never run `modify-*`, `reboot-*`, `test-failover`,
  scaling, snapshot or delete operations during an investigation, and never create a
  resource metrics configuration (detailed OpenTelemetry metrics are billed). Present
  every change as a recommendation with its impact.
- **Changes only on request, one at a time.** Apply a change only when the operator asks
  you in chat to apply a mitigation and the change is a directed action they approve.
  Then follow Step 6. Never delete a resource, never change a production setting the
  operator did not name, and never batch several changes into one approval.
- **No data-plane access.** The cache endpoint is inside the customer's VPC. Do not
  try to connect. When only engine data can settle the question (for example, naming
  a hot key), recommend an operator-run command from
  [references/recommend-engine-command.md](references/recommend-engine-command.md) and
  say which result confirms the hypothesis.
- **Evidence over symptoms.** Every finding quotes the metric, the node or shard, the
  value and the time, compared with a baseline window of the same length before the
  onset. Break every metric down by node or shard: group-level aggregates hide skew.
- **Keep metric queries narrow.** PromQL and `GetMetricData` calls through the API are
  billed by CloudWatch (PromQL by samples scanned). Filter on the cache and the window,
  and aggregate.
- **G1: use the classic metric where OpenTelemetry has no equivalent.** That is
  `CurrItems`, `CurrVolatileItems`, latency percentiles, `ReplicationLag`,
  `CPUUtilization`, CPU credits, IAM expirations and `NetworkBaselineUsage*`. For
  node-based Valkey, query both paths.
- **G2: never recommend a fix that loses data without the condition that the data is
  safe to lose.** This covers `allkeys-*` eviction policies, deletes and flushes: state
  the condition and what is lost.
- **G3: recommend only data-plane commands that do not hurt the node.** Use the form and
  the never-recommend list in
  [references/recommend-engine-command.md](references/recommend-engine-command.md).
- **G4: never recommend a capacity change** (a larger node, more shards or replicas,
  higher serverless limits) for a hot key, an unbounded collection or a client-side
  cause.

## Workflow

Copy this checklist and complete every step in order.

- [ ] Step 1: Identify the deployment
- [ ] Step 2: Collect the evidence once
- [ ] Step 3: Judge every cause
- [ ] Step 4: Validate before reporting
- [ ] Step 5: Report
- [ ] Step 6: Apply an approved mitigation (only when the operator asks)

### Step 1: Identify the deployment

Follow [references/discover-deployment.md](references/discover-deployment.md): which
kind of cache it is, which metrics path applies, which features its engine version
supports. For an alarm, the alarm's metric and dimensions name the cache. The onset is
the first datapoint of the failure signal; the baseline is a window of the same length
before it.

### Step 2: Collect the evidence once

Collect all of it before judging any cause, so that configuration and logs count as
evidence next to the metrics:

- Metrics: OpenTelemetry ([references/query-otel-metrics.md](references/query-otel-metrics.md))
  and classic ([references/query-classic-metrics.md](references/query-classic-metrics.md)).
  For node-based Valkey, run the OpenTelemetry queries yourself, whatever your role: the
  OTel file says how to get the PromQL tools.
- Events and changes at the onset:
  [references/check-events-and-changes.md](references/check-events-and-changes.md).
- Parameters: [references/read-parameters.md](references/read-parameters.md).
- Slow log and engine log: [references/query-logs.md](references/query-logs.md).

### Step 3: Judge every cause

Anchor on the reported symptom and onset, even if another anomaly looks bigger. A change that *ended* before the onset (traffic stopping, a
load going away) does not cause symptoms that start after it. Traffic that stops on every
node with no errors and no events means the clients stopped, not that the cache failed.
If the window just before the onset contains a different anomaly, say so, report it
separately, and choose an earlier steady-state window as the baseline. Mention an earlier
episode outside the incident window only with facts you verified, and keep it separate
from the root cause.

Mark each cause **confirmed** (all its evidence is present), **ruled out**
(its deciding evidence is absent) or **unknown** (evidence missing; name the gap). The
cause is confirmed only when its evidence is present **and** the lookalike's evidence is
absent. More than one cause can be confirmed: report one primary cause and the
contributing ones, with the evidence for each. When comparing nodes or shards,
quote the values for each one; do not call a node an outlier without the numbers.

When the operator quotes an engine error reply, or the error metrics show one, load
[references/error-replies.md](references/error-replies.md) to map it to its cause.

### Step 4: Validate before reporting

Check your draft against each point. If one fails, go back to the step that produces
the missing evidence, then check again.

- [ ] Every metric value and timestamp is quoted from a tool result, not estimated.
- [ ] The onset is the first datapoint of the failure signal, and the baseline window
      contains no other incident.
- [ ] The cause's discriminating evidence is present.
- [ ] The lookalike's evidence was checked and is absent, not just unchecked.
- [ ] Every remediation is phrased as an operator-run action (Step 6 is the only
      exception, and only on request).

### Step 5: Report

Always give all five parts, even when the cause looks obvious.

1. **Root cause:** one sentence naming the mechanism, not the symptom.
2. **Evidence:** metric, node/shard, value and time, against the baseline.
3. **Ruled out:** the lookalike and the evidence that excludes it.
4. **Remediation:** an immediate mitigation and a durable fix, both for the operator
   to run.
5. **Gaps:** what could not be verified, with the command that would verify it.

### Step 6: Apply an approved mitigation (only when the operator asks)

Use this step only after a root cause is confirmed and the operator asks you to apply
the fix. Load [references/propose-mitigation.md](references/propose-mitigation.md) and use
the row for the confirmed cause. If the cause has no row there, or the row says
operator-only, give the manual steps instead.

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
   second change on your own. A rollback that removes capacity (scale-in, removing a
   shard or a replica) is operator-run: give the command, do not apply it.
