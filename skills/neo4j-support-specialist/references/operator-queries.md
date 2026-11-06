# Operator commands

Commands the report hands to a human. The agent can't run any of them. Copy the ones a finding needs, fill in names,
and say what the output will confirm. Mark commands that change state (`START DATABASE`, `STOP DATABASE`, restore) as
changes the operator decides on.

## Getting a shell

| Platform | Command |
| --- | --- |
| EKS | `kubectl exec -it -n <ns> <pod> -c neo4j -- cypher-shell -u <admin-user>` (prompts for the password) |
| ECS | `aws ecs execute-command --cluster <cluster> --task <task-id> --container neo4j --interactive --command "cypher-shell -u <admin-user>"` (needs ECS Exec enabled on the service) |
| EC2 | Session Manager or SSH, then `cypher-shell -u <admin-user>` |

Use `-d system` for DBMS-level commands when the user database is down: `SHOW DATABASES`, `SHOW SERVERS` and the
`dbms.*` procedures below work from `system`.

## Cypher: state

```cypher
// Database status, role, store format, transaction ids and replication lag per member
SHOW DATABASES YIELD name, address, role, writer, requestedStatus, currentStatus, statusMessage,
  lastCommittedTxn, replicationLag, store;

// Servers in a cluster
SHOW SERVERS YIELD name, address, state, health, hosting;

// Cluster health for specific databases (clusters only; fails on a standalone server)
CALL dbms.cluster.statusCheck(['neo4j']);

// Ports between this member and the others (clusters only)
CALL dbms.cluster.checkConnectivity();

// Version and edition
CALL dbms.components();
```

## Cypher: workload

```cypher
// Longest-running transactions and their memory
SHOW TRANSACTIONS YIELD database, transactionId, username, clientAddress, status, elapsedTime, cpuTime, waitTime,
  currentQueryAllocatedBytes, estimatedUsedHeapMemory, activeLockCount, pageFaults, currentQuery
ORDER BY elapsedTime DESC LIMIT 20;

// Memory pools (heap and native) per pool and database
CALL dbms.listPools();

// JVM heap and GC from JMX
CALL dbms.queryJmx('java.lang:type=Memory') YIELD attributes RETURN attributes.HeapMemoryUsage;
CALL dbms.queryJmx('java.lang:type=GarbageCollector,*') YIELD name, attributes
RETURN name, attributes.CollectionCount, attributes.CollectionTime;

// Connections
CALL dbms.listConnections();
```

## Cypher: schema and plans

```cypher
SHOW INDEXES YIELD id, name, type, state, populationPercent, labelsOrTypes, properties, readCount, lastRead;
SHOW CONSTRAINTS;

// Plan without running
EXPLAIN <query>;
// Plan with row counts and db hits (runs the query)
PROFILE <query>;
```

From a file with parameters: `cypher-shell -u <user> -f query.cypher -P '{id: 42}'`.

## Cypher: configuration

```cypher
SHOW SETTINGS YIELD name, value
WHERE name STARTS WITH 'server.memory' OR name STARTS WITH 'dbms.memory' OR name STARTS WITH 'db.memory'
   OR name STARTS WITH 'server.bolt' OR name STARTS WITH 'dbms.ssl' OR name STARTS WITH 'dbms.cluster'
RETURN name, value;
```

An empty result can mean the user lacks the `SHOW SETTING` privilege, not that nothing matched.

## Cypher: changes (operator's decision)

```cypher
STOP DATABASE <db>;
START DATABASE <db>;
CALL dbms.setDefaultDatabase('<db>');   // run against system
```

## neo4j-admin

Run inside the Neo4j container or host as the neo4j user (uid 7474).

| Purpose | Command |
| --- | --- |
| Support bundle | `neo4j-admin server report --to-path=/tmp/report` (`--list` shows what it collects) |
| Memory sizing | `neo4j-admin server memory-recommendation --memory=<container limit> --docker` |
| Validate configuration before a restart | `neo4j-admin server validate-config` |
| Store information | `neo4j-admin database info <db>` |
| Consistency check (database stopped, or on a backup) | `neo4j-admin database check <db> --report-path=/tmp/cc` |
| Copy / compact | `neo4j-admin database copy <source> <target>` (database stopped) |
| Backup | `HEAP_SIZE=2g neo4j-admin database backup --from=<host>:6362 --to-path=<dir> --pagecache=2g <db>` |
| Restore | `neo4j-admin database restore --from-path=<backup> --overwrite-destination=true <db>` (database stopped) |
| Migrate an older store | `neo4j-admin database migrate <db>` |

## Copying files out

| Platform | Command |
| --- | --- |
| EKS logs | `kubectl cp -c neo4j <ns>/<pod>:/logs ./neo4j-logs-<pod>` |
| EKS report | `kubectl exec -n <ns> <pod> -c neo4j -- neo4j-admin server report --to-path=/tmp/report`, then `kubectl cp -c neo4j <ns>/<pod>:/tmp/report ./report-<pod>` |
| ECS | ECS Exec to run the report, then copy it to S3 from inside the task (`aws s3 cp`, if the task role allows) |
| EC2 | Run the evidence command below, or copy `/var/log/neo4j/` |

## EC2: read-only evidence command (SSM Run Command)

The operator runs this with their own credentials; the agent reads the result on its next run with
`ssm list-command-invocations --instance-id <id> --details` or `ssm get-command-invocation`. It only reads. Paths are
for the deb/rpm package; adjust for tarball installs.

`neo4j-evidence.json`:

```json
{
  "commands": [
    "echo '== version'; neo4j --version 2>/dev/null",
    "echo '== service'; systemctl status neo4j --no-pager 2>/dev/null | head -20",
    "echo '== limits'; pid=$(pgrep -f EntryPoint | head -1); [ -n \"$pid\" ] && grep -E 'open files|processes' /proc/$pid/limits",
    "echo '== memory'; free -m",
    "echo '== disk'; df -h /var/lib/neo4j /var/log/neo4j 2>/dev/null",
    "echo '== config'; grep -v -E '^[[:space:]]*(#|$)' /etc/neo4j/neo4j.conf | grep -v -i -E 'password|secret|token|credential|private_key'",
    "echo '== neo4j.log'; journalctl -u neo4j --since '-6h' --no-pager 2>/dev/null | tail -150",
    "echo '== debug.log errors'; grep -E '\"level\":\"(ERROR|WARN)\"| (ERROR|WARN) ' /var/log/neo4j/debug.log 2>/dev/null | tail -80",
    "echo '== kernel OOM'; dmesg -T 2>/dev/null | grep -i -E 'out of memory|oom-kill' | tail -20"
  ]
}
```

```bash
aws ssm send-command \
  --document-name AWS-RunShellScript \
  --targets Key=InstanceIds,Values=i-0123456789abcdef0 \
  --parameters file://neo4j-evidence.json \
  --comment neo4j-support-evidence \
  --cloud-watch-output-config CloudWatchOutputEnabled=true,CloudWatchLogGroupName=/neo4j/ssm-evidence
```

Inline output stops at 24,000 characters; the CloudWatch output keeps the rest, in the log group named above.
