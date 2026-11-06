# Log queries

How to query shipped logs with CloudWatch Logs Insights (`query_cloudwatch_logs`, or `use_aws` with `logs start-query`
and `logs get-query-results`). Container output on EKS through `use_kubectl` is in
[evidence-sources.md](evidence-sources.md). Keep result sets small: narrow the time window and `limit` first,
widen only if needed.

## Log groups

| Platform | Where container output goes |
| --- | --- |
| ECS | Task definition `logConfiguration.options.awslogs-group`; streams `<awslogs-stream-prefix>/<container>/<task-id>` |
| EKS with Container Insights | `/aws/containerinsights/<cluster>/application`; the Neo4j line is in the `log` field; filter on `` `kubernetes.namespace_name` `` and `` `kubernetes.pod_name` `` |
| EC2 | Whatever the CloudWatch agent configuration names; find candidates with `logs describe-log-groups` and a sample query. Package installs write `/var/log/neo4j/*.log`, and neo4j.log also goes to the journal |

On EKS, add this filter to the queries below:

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

Topic filters (add to either layout; use `log` instead of `@message` when nested):

Database state:

```text
filter @message like /remains in state|Unable to start database|DbmsReconciler|Panic detected|out of disk space|quarantine/
```

Recovery:

```text
filter @message like /Recovery in '|Recovery completed|Transaction logs are missing/
```

Checkpoints:

```text
filter @message like /checkpoint completed in/
```

GC pauses:

```text
filter @message like /Detected VM stop-the-world pause/
| parse @message /pauseTime=(?<pauseMs>\d+), gcTime=(?<gcMs>\d+), gcCount=(?<gcCount>\d+)/
| stats count(*) as pauses, max(pauseMs) as maxPauseMs by bin(10m)
```

Cluster:

```text
filter @message like /Raft|E_COUNT_EXCEEDED|handler for Raft ID|leader|binding|discovery/
```

Startup diagnostics dump (JVM and system memory, file limits, configuration, store sizes):

```text
filter @message like /DiagnosticsManager/
| sort @timestamp desc
| limit 40
```

## query.log, when shipped

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

Most expensive query texts (reuse the two `parse` lines):

```text
| stats count(*) as runs, max(ms) as maxMs, avg(ms) as avgMs, max(bytes) as maxBytes, sum(faults) as faults by query
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

Driver versions in use: `parse` as above, then `parse rest /bolt\t(?<driver>[^\t]+)\t/ | stats count(*) by driver`.

## security.log, when shipped

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
