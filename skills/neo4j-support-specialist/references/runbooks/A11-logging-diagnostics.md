# A11: Logging, monitoring and diagnostics

**Problem it solves:** Which evidence exists, how to read it, and what to ask for when it's missing. With default
logging only neo4j.log reaches container output; debug.log, query.log and security.log stay in files under `/logs`
unless the deployment already ships them. The report names the missing sources and gives the operator the commands to
collect them.

**Log files in 2026.10.**

| File | Default destination | Format | Holds |
| --- | --- | --- | --- |
| neo4j.log | Container output (Docker image and Helm chart); the journal for systemd installs | Text | Start, stop, startup failures, panics, warnings |
| debug.log | `/logs/debug.log` | JSON on the Docker image (`time`, `level`, `category`, `message`, `databaseName`); text `<time> <LEVEL> [<category>] <message>` on the Helm chart | Database state, recovery, checkpoints, cluster, GC pauses, startup diagnostics dump |
| query.log | `/logs/query.log` | Text | Every query (`VERBOSE` by default) with duration, memory, page hits and faults, client, user |
| security.log | `/logs/security.log` | Text; JSON if configured | Logins, failures, admin commands |
| http.log | `/logs/http.log` | Text | HTTP API requests |
| gc.log | Off (`server.logs.gc.enabled=false`) | JVM | GC detail when enabled |

The JVM writes `OutOfMemoryError` and other uncaught errors to stderr, which is also container output. Package installs
on EC2 write the files to `/var/log/neo4j/`.

## A11.1 Support evidence bundle

**Symptom:** a support case is likely, or the operator asks what to send.

**What to include in the report:**

1. What the agent read: platform, Neo4j version (image tag or package version), topology, time window, the findings and
   quoted evidence.
2. What the operator should collect from each affected server:
   - `neo4j-admin server report --to-path=<dir>` (collects logs, configuration, metrics and system information into one
     archive; `--list` shows what it would collect), run inside the pod, task or host;
   - otherwise `/logs` (debug.log, neo4j.log, query.log, security.log), the effective configuration
     (`SHOW SETTINGS` or the ConfigMaps / task definition), `SHOW DATABASES`, `SHOW SERVERS`, and for a cluster the same
     from every member;
   - consistency check report if corruption is suspected ([A1.6](A1-startup-recovery.md)).
3. How to copy files out of a container: [operator-queries.md](../operator-queries.md).

## A11.2 Finding logs under systemd

**Symptom:** Neo4j installed from the deb or rpm package on EC2; neo4j.log seems missing. The agent sees these logs
only if the journal or `/var/log/neo4j/` is shipped to CloudWatch Logs, or an SSM command already collected them.

**Cause:** Under systemd, the service's stdout (neo4j.log content) goes to the journal; the other files stay in
`/var/log/neo4j/`.

**Fix (operator):** `journalctl -u neo4j --since "<time>"`; ship the journal and `/var/log/neo4j/*.log` with the
CloudWatch agent.

## A11.3 Shipping logs off the host

**Symptom:** the investigation needed debug.log, query.log or security.log and they weren't readable.

**Fix (operator):** Ship the log files to CloudWatch Logs: on EKS, a Fluent Bit or CloudWatch agent configuration that
tails `/logs/*.log` on the logs volume, or Console appenders for the extra loggers in `server-logs.xml` (Helm value
`logging.serverLogsXml`) so they join container output; on ECS, a FireLens sidecar or a log-shipping container reading
the logs volume; on EC2, the CloudWatch agent tailing `/var/log/neo4j/*.log`. These are deployment changes for the
operator to plan; the agent works with whatever is shipped.

## A11.4 Controlling log volume

**Symptom:** query.log or debug.log volume too high to keep or ship.

**Fix (operator):** query.log logs every query by default; raise `db.logs.query.threshold`, or set
`db.logs.query.enabled=INFO` to log only completed queries above the threshold. Use Log4j2 filters in
`server-logs.xml` to drop specific noisy entries.

## A11.5 Top expensive queries from query.log

**Symptom:** a question about the slowest, most memory-hungry or most frequent queries.

**Check:** Logs Insights queries in [log-queries.md](../log-queries.md): top by duration, by allocated bytes, by page
faults, and most frequent query text, excluding `Query started:` lines.

## A11.6 Logging query parameters

**Symptom:** query.log lines need parameter values to reproduce a query.

**Fix (operator):** Parameter logging (`db.logs.query.parameter_logging_enabled`) is on by default in 2026.10; check it
wasn't turned off, and mind `db.logs.query.obfuscate_literals` and `db.logs.query.max_parameter_length`. Parameters can
contain personal data; treat query.log accordingly.

## A11.7 Reading debug.log

**Symptom:** debug.log is available and needs triage.

**Check:** Filter `ERROR` and `WARN` first, then by category: `DbmsReconciler` (database state), `Recovery`,
`CheckPointerImpl`, `VmPauseMonitorComponent`, `RaftMessageDispatcher`, `BatchingMessageHandler`, `ErrorAccountant`.
The startup diagnostics dump (`DiagnosticsManager` entries after each start) holds JVM and OS memory, file-descriptor
limits, the effective non-default configuration, and per-database store file sizes. Queries in
[log-queries.md](../log-queries.md).

## A11.8 sysinfo via Cypher

**Symptom:** a request for the Browser `:sysinfo` data (store sizes, page cache, transactions).

**Fix (operator):** `SHOW DATABASES YIELD *` for status, store format and transaction ids; `CALL dbms.listPools()` for
memory pools; `SHOW TRANSACTIONS` for running work; store sizes from the debug.log startup dump or the filesystem. See
[operator-queries.md](../operator-queries.md).
