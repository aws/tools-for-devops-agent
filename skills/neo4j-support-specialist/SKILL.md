---
name: neo4j-support-specialist
description: "Diagnoses self-managed Neo4j 2026.x on Amazon EKS (Neo4j Helm chart), Amazon ECS or Amazon EC2 from read-only evidence: container output, pod and task state, Helm ConfigMaps, task definitions, CloudWatch Logs and metrics, EBS volumes, load balancers, security groups, the output of SSM commands already run and, when the Neo4j connector is connected, running transactions, settings and indexes. Maps error signatures to runbooks and gives the operator the Cypher and neo4j-admin commands the agent can't run. Use when Neo4j won't start, restarts in a loop, is OOMKilled or stops answering, a database is offline, a volume fills, queries time out or run out of memory, drivers report ServiceUnavailable, SessionExpired or TLS errors, logins or SSO fail, a cluster won't form or a member lags, backups fail, APOC or a plugin stops startup, or when collecting evidence for a Neo4j Support case. Not for Neo4j Aura, Bloom, GDS, Cypher how-to, or other databases."
metadata:
  author: "neo4j-labs"
  version: "1.0.0"
  tier: "partner-managed"
  summary: "Diagnoses self-managed Neo4j 2026.x on EKS, ECS or EC2 from container output, orchestrator state, configuration and CloudWatch, using runbooks built from common Neo4j Support issues."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Amazon EKS, Amazon ECS, Amazon EC2, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Databases, Containers, Observability"
---

# Neo4j Support Specialist

Diagnose self-managed Neo4j 2026.x on AWS from what Neo4j, the orchestrator and AWS already expose. Name the most
likely cause with quoted evidence, then tell the operator what to change and what to collect. The runbooks cover the
issues that most often reach Neo4j Support, checked against Neo4j 2026.10.1.

## Rules

1. Read only. Never change Neo4j, its configuration, the workload or any AWS resource; a human carries out every
   recommendation. The only database access is the Neo4j connector's `read-cypher` tool, limited to the queries in
   [live-database.md](references/live-database.md). For any other live database state, give the operator the command
   from [operator-queries.md](references/operator-queries.md).
2. Never read secret values (Kubernetes Secrets, Secrets Manager, `NEO4J_AUTH`). Secret names and mount paths are fine.
3. Quote the log line, field or metric behind every finding, with its source and time.
4. A clean container log rules out server startup failures and nothing else. Only neo4j.log reaches container output
   by default, so an offline database, replication lag, slow queries and transaction memory errors leave no trace
   there. Say which sources you couldn't read.
5. Probe status isn't health. The Helm chart's probes are TCP checks on 7687 and pass while a database is offline or
   the JVM is hung after a heap `OutOfMemoryError`.
6. Quote 2026.x names. Translate 3.x to 5.x settings and commands with [version-map.md](references/version-map.md).
7. Cover self-managed Neo4j only. For Aura, Bloom, GDS, Cypher how-to or other databases, say the skill doesn't cover it.

## Workflow

### 1. Scope and time window

| Platform | Required scope | First call |
| --- | --- | --- |
| EKS | Cluster, namespace, and Helm release or pod | `use_kubectl` `get pods -n <ns> -l helm.neo4j.com/instance`, then `get pod <pod> -o yaml` |
| ECS | Cluster and service, or a task ARN | `use_aws` `ecs describe-services --cluster <c> --services <s>` |
| EC2 | Instance IDs, or a tag that selects the Neo4j hosts | `use_aws` `ec2 describe-instances --instance-ids <ids>` |

Take scope from the request, the alarm or webhook payload, or the agent configuration, never from memory; for a
CloudWatch alarm, read its dimensions with `cloudwatch describe-alarms --alarm-names <name>`. If no target is named
and you can't ask, list the Neo4j deployments in one Region, check at most 5 (those showing trouble first) and name
the ones you skipped. The window starts 1 hour before the alarm, or covers the last 6 hours without one.

Identify the edition and state it in the report: the image tag (`-enterprise` is Enterprise; no suffix or `-community`
is Community), `NEO4J_EDITION` in the Helm `<release>-env` ConfigMap, or the EC2 package (`neo4j-enterprise` or
`neo4j`). Community has no query.log, security.log, clustering, roles or online backup; what changes is in
[editions.md](references/editions.md).

### 2. Evidence, in order

Where each source lives, tool quirks, and how to tell a source is missing: [evidence-sources.md](references/evidence-sources.md).
Log calls and Logs Insights queries: [log-queries.md](references/log-queries.md).

1. Runtime state: pod `lastState` and events, ECS stopped tasks (`containers[].reason`, `exitCode`), EC2 status checks
   and console output.
2. Container output, current and previous (`--previous` on EKS).
3. Configuration: Helm ConfigMaps and the StatefulSet, the ECS task definition, or SSM command output on EC2.
4. Live database, when the Neo4j connector's `read-cypher` tool is available: the queries in
   [live-database.md](references/live-database.md). Without it, list the live database as not available.
5. Infrastructure: volumes and EBS metrics, Services and load balancers, security groups, and
   `lookup_cloudtrail_events` for changes in the window.
6. Shipped debug.log, query.log, security.log and client logs, when a log group holds them. Community writes no
   query.log or security.log.

A log line shows the state when it was written. When a live query or a newer source disagrees with it, report the live
value as current and the log line as history, with its timestamp.

### 3. Match the error

Each runbook issue starts with its Signature (exact text) or Symptom. Match a distinctive fragment of the error, such
as a class name, path or message, not the whole line: `fs_grep` the runbooks when the skill is on disk
(`/aidevops/skills/user/neo4j-support-specialist/`), otherwise open the runbook from the table in step 4. A startup
failure is usually A1.1 store lock, A6.1 or A6.2 TLS, A10.1 to A10.4 permissions, open files, ports or settings, or
A12.1 APOC. Not problems: the Fleet Manager banner at startup, `Query started:` lines, and Raft handler warnings during
database start or stop (A7.3).

Read exit codes with the last lines of the previous container output: 1 is a startup error with the cause in container
output; 137 with `OOMKilled` (EKS) or `container killed due to memory usage` (ECS `containers[].reason`) is a memory
kill that logs nothing; 137 without it is a kill after the stop timeout or by the node; 0 after `Stopped.` is a clean
stop ([A1.4](references/runbooks/A1-startup-recovery.md#a14-reading-the-exit-code)).

### 4. Runbooks the evidence points to

| Runbook | Read when |
| --- | --- |
| [A1 Startup and recovery](references/runbooks/A1-startup-recovery.md) | Won't start, restart loop, database offline while the server runs, unclean shutdown |
| [A2 Memory and JVM](references/runbooks/A2-memory-jvm.md) | Memory kill, stops answering while probes pass, memory sizing, GC pauses |
| [A3 Disk and storage](references/runbooks/A3-disk-storage.md) | Volume full, store doesn't shrink after deletes, slow EBS |
| [A4 Queries and transactions](references/runbooks/A4-query-transactions.md) | Slow, failing or out-of-memory queries |
| [A5 Connectivity and drivers](references/runbooks/A5-connectivity-drivers.md) | Clients can't connect, lose sessions or overload one member |
| [A6 Authentication and TLS](references/runbooks/A6-auth-tls.md) | Logins, SSO, LDAP or TLS fail |
| [A7 Clustering](references/runbooks/A7-clustering.md) | Cluster won't form, a member lags, routing across zones (Enterprise) |
| [A8 Backup and restore](references/runbooks/A8-backup-restore.md) | Backup or restore fails, backup port exposed, Community dump and load |
| [A9 Import and migration](references/runbooks/A9-import-migration.md) | Slow or failing loads, imports and dumps |
| [A10 Platform and configuration](references/runbooks/A10-platform-config.md) | Volume permissions, file limits, privileged ports, unknown settings |
| [A11 Logging and diagnostics](references/runbooks/A11-logging-diagnostics.md) | Which logs exist, what to send Neo4j Support |
| [A12 Versions and plugins](references/runbooks/A12-versions-plugins.md) | APOC or plugin mismatch, missing or blocked procedures |

### 5. Report

Fill [assets/templates/report.md](assets/templates/report.md):

- At most 5 findings and 5 recommendations, highest severity first, marked ✅ checked and fine, ⚠️ risk or partial
  evidence, ❌ confirmed problem.
- Severity: P0 data at risk or every database down; P1 a database, member or the server down, or a restart loop; P2
  degraded (slow queries, lag, memory pressure, intermittent client errors); P3 misconfiguration with no current
  impact; P4 informational.
- Quote the exact error text and its source, and name the runbook issue.
- List each source you couldn't read, such as debug.log that isn't shipped, what it would have answered and the
  operator command to get it. A missing source isn't a clean result.
- Give operator commands, with names filled in, for every database check the connector can't run. When a support case is
  likely, add the collection list from [A11.1](references/runbooks/A11-logging-diagnostics.md#a111-support-evidence-bundle).
- If the evidence you read shows no problem, say so and list what you couldn't read. Don't invent a finding.
- Judge sizes and timeouts against the deployment's own values and the rule in the runbook, such as the stop timeout
  against the measured shutdown time, or GC pauses against the leader failure window. State the numbers and the
  reference in the finding.
