# Log queries

How to query shipped logs with CloudWatch Logs Insights (`query_cloudwatch_logs`, or `use_aws` with `logs start-query`
and `logs get-query-results`). Container output on EKS through `use_kubectl` is in
[evidence-sources.md](evidence-sources.md). Run every query over the time window from SKILL.md Step 1, set as the
query's start and end time, never as an open range. Every query ends in `limit`. Start narrow and widen only if
needed.

## Log groups

| Platform | Where container output goes |
| --- | --- |
| ECS | Task definition `logConfiguration.options.awslogs-group`; streams `<awslogs-stream-prefix>/<container>/<task-id>` |
| EKS with Container Insights | `/aws/containerinsights/<cluster>/application`; the Neo4j line is in the `log` field; filter on `` `kubernetes.namespace_name` `` and `` `kubernetes.pod_name` `` |
| EC2 | Whatever the CloudWatch agent configuration names; find candidates with `logs describe-log-groups` and a sample query. Package installs write `/var/log/neo4j/*.log`, and neo4j.log also goes to the journal |

On EKS, add this filter right after the `fields` line of each query below:

```text
filter `kubernetes.namespace_name` = "<ns>" and `kubernetes.pod_name` like /<release>-/
```

On ECS, narrow to one task with `filter @logStream like /<task-id>/`.

## Container output (neo4j.log and stderr)

Text lines: `<yyyy-MM-dd HH:mm:ss.SSS+0000> <LEVEL> <message>`.

Problems:

```text
fields @timestamp, @logStream, @message
| filter @message like /ERROR|WARN|Exception|OutOfMemoryError|Panic detected|Unrecognized setting|Lock file has been locked|Base directory|Too many open files|not accessible for user|failed to initialize|thread starvation|network aborts/
| sort @timestamp desc
| limit 100
```

Start and stop history:

```text
fields @timestamp, @logStream, @message
| filter @message like /Starting\.\.\.|Started\.|Stopping\.\.\.|Stopped\.|shutdown initiated/
| sort @timestamp asc
| limit 200
```

A `Stopping...` with no later `Stopped.` in the same stream means the stop was cut short ([A1.3](runbooks/A1-startup-recovery.md#a13-unclean-or-slow-shutdown)).

## debug.log, when shipped

**JSON layout** (Docker image default): one object per line with `time`, `level`, `category`, `message`, and
`databaseName` for database-scoped entries. When the line is the whole event, Logs Insights discovers the fields:

```text
fields @timestamp, level, category, databaseName, message
| filter level in ["ERROR", "WARN"]
| sort @timestamp desc
| limit 100
```

When the JSON is nested in a Fluent Bit `log` field, match on the text instead:

```text
fields @timestamp, log
| filter log like /"level":"(ERROR|WARN)"/
| sort @timestamp desc
| limit 100
```

**Text layout** (Helm chart default): `<time> <LEVEL> [<category>] <message>`:

```text
fields @timestamp, @message
| parse @message /^(?<ts>\S+ \S+) (?<lvl>[A-Z]+)\s+\[(?<cat>[^\]]+)\] (?<msg>.*)$/
| filter lvl in ["ERROR", "WARN"]
| sort @timestamp desc
| limit 100
```

Topic queries, written for the text layout. Use `log` instead of `@message` when the line is nested in a Fluent Bit
`log` field.

Database state (the second line adds Community's wording):

```text
fields @timestamp, @logStream, @message
| filter @message like /remains in state|Unable to start database|DbmsReconciler|Panic detected|out of disk space|quarantine/ or @message like /Failed to start DatabaseId|recovery not possible|Database panic|Could not append transaction|No space left on device/
| sort @timestamp desc
| limit 100
```

Recovery:

```text
fields @timestamp, @logStream, @message
| filter @message like /Recovery in '|Recovery completed|Transaction logs are missing/
| sort @timestamp desc
| limit 50
```

Checkpoints:

```text
fields @timestamp, @logStream, @message
| filter @message like /checkpoint completed in/
| sort @timestamp desc
| limit 50
```

GC pauses, worst 10-minute windows first:

```text
fields @timestamp, @message
| filter @message like /Detected VM stop-the-world pause/
| parse @message /pauseTime=(?<pauseMs>\d+), gcTime=(?<gcMs>\d+), gcCount=(?<gcCount>\d+)/
| stats count(*) as pauses, max(pauseMs) as maxPauseMs by bin(10m)
| sort maxPauseMs desc
| limit 20
```

Cluster:

```text
fields @timestamp, @logStream, @message
| filter @message like /Raft|E_COUNT_EXCEEDED|handler for Raft ID|leader|binding|discovery/
| sort @timestamp desc
| limit 100
```

Startup diagnostics dump (JVM and system memory, file limits, configuration, store sizes):

```text
fields @timestamp, @logStream, @message
| filter @message like /DiagnosticsManager/
| sort @timestamp desc
| limit 40
```

## query.log, when shipped

Enterprise only: Community leaves query.log empty.

Completion lines on 2026.x (`<TAB>` is a tab character):

```text
<time> INFO  id:<n> - transaction id:<n> - <ms> ms: (planning: <ms>, waiting: <ms>) - <bytes> B - <hits> page hits, <faults> page faults - bolt-session<TAB>bolt<TAB><driver/version><TAB><TAB>client/<ip>:<port><TAB>server/<ip>:<port>><TAB><db> - <user> - <query> - {<params>} - runtime=<runtime> - {<annotations>}
```

Failed queries use `ERROR` and append the error text after a final `-`. `Query started:` lines (VERBOSE logging) repeat the
prefix with `Query started:` and are excluded by the parse below.

Slowest queries:

```text
fields @timestamp, @message
| parse @message /(?<lvl>INFO|WARN|ERROR)\s+id:(?<qid>\d+) - transaction id:(?<tx>\d+) - (?<ms>\d+) ms: \(planning: (?<planMs>\d+), waiting: (?<waitMs>\d+)\) - (?<bytes>\d+) B - (?<hits>\d+) page hits, (?<faults>\d+) page faults - (?<rest>.*)/
| filter ispresent(ms)
| parse rest /client\/(?<client>[^\t ]+).*>\t(?<db>\S+) - (?<user>\S+) - (?<query>.*?) - \{/
| sort ms desc
| limit 25
```

Most expensive query texts: the slowest-queries query through its second `parse` line, then:

```text
| stats count(*) as runs, max(ms) as maxMs, avg(ms) as avgMs, max(bytes) as maxBytes, sum(faults) as totalFaults by query
| sort maxMs desc
| limit 20
```

Failed queries:

```text
fields @timestamp, @message
| filter @message like /ERROR\s+id:/
| sort @timestamp desc
| limit 50
```

Driver versions in use: the slowest-queries query through its second `parse` line, then:

```text
| parse rest /bolt\t(?<driver>[^\t]+)\t/
| stats count(*) as sessions by driver
| sort sessions desc
| limit 20
```

## security.log, when shipped

Enterprise only: Community leaves security.log empty.

```text
fields @timestamp, @message
| filter @message like /42NFF|failed to log in|unauthorized|logged in/
| sort @timestamp desc
| limit 100
```

In the JSON layout, `source` holds `client/<ip>:<port>` and `authenticatedUser` the user.

## Client application logs

```text
fields @timestamp, @logStream, @message
| filter @message like /ServiceUnavailable|SessionExpired|TransientError|ClientException|DatabaseError|SSLHandshakeException|certification path|no longer available|routing information|51N72/
| sort @timestamp desc
| limit 100
```
