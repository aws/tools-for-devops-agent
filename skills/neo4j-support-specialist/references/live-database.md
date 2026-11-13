# Live database checks

Use this file only when the Neo4j connector's `read-cypher` tool is available in the run. It reaches the `neo4j`
database through a Neo4j user that holds only the `devops_agent_diag` role: it can list transactions, settings,
indexes and constraints. The role has no read privilege on graph data, so it can't count or inspect nodes. Its
`DENY LOAD` only blocks `LOAD CSV` and similar loads.

The connector needs Enterprise. Community has no roles, so a connector user there has full rights: it can end other
users' transactions, read graph data and load URLs. On Community, still run only the queries below, and say in the
report that the connector's user isn't restricted.

## Rules

- Run only the queries below, unchanged. Never run `TERMINATE`, `MATCH` or any read of graph data, `LOAD CSV`, or a
  procedure. Some of these pass the tool's read-only check, and only the Neo4j role stops them.
- Don't call `get-schema`. Under this role it returns nothing.
- Quote the query and the rows behind each finding, like a log line.
- Query text in `SHOW TRANSACTIONS` can hold customer data. The query returns its first 200 characters; quote only
  what the finding needs.
- An empty result can mean the role lacks a privilege, not that nothing is there. Say so when logs suggest otherwise.
- If the tool isn't available, or a call fails, list "Live database (Neo4j connector)" under sources not available
  and continue with logs. A failure that mentions `DatabaseUnavailable` or "impossible to verify connectivity" means
  the `neo4j` database is stopped, failing or unreachable: go to
  [A1](runbooks/A1-startup-recovery.md). The tool can also be missing for the same reason: the server fails its
  start-up check while the database is down, and the run starts without the tool.
- For anything else, such as `SHOW DATABASES`, `SHOW SERVERS`, `dbms.components()`, JMX, connections, the routing
  table or the `system` database, give the operator the command from [operator-queries.md](operator-queries.md).

## Queries

### Long or memory-heavy transactions (A2, A4)

```cypher
SHOW TRANSACTIONS
YIELD database, transactionId, username, clientAddress, status, elapsedTime, currentQueryAllocatedBytes, currentQuery
WHERE currentQuery <> '' AND NOT currentQuery STARTS WITH 'SHOW TRANSACTIONS'
RETURN database, transactionId, username, clientAddress, status, elapsedTime, currentQueryAllocatedBytes,
       left(currentQuery, 200) AS query
ORDER BY elapsedTime DESC
LIMIT 20
```

Compare `currentQueryAllocatedBytes` with `dbms.memory.transaction.total.max` and the heap from the settings query.

### Settings changed since startup (A4, A5, A10)

```cypher
SHOW SETTINGS
YIELD name, value, startupValue, isExplicitlySet, isDynamic
WHERE isExplicitlySet AND isDynamic AND value <> startupValue
RETURN name, value, startupValue
LIMIT 100
```

A row here was changed at runtime with `dbms.setConfigValue`, so the task definition, ConfigMap or neo4j.conf no
longer shows the value in force. The change is lost on restart. Only dynamic settings can change at runtime; the
`isDynamic` filter drops static settings such as `server.directories.import`, whose value is the resolved path.

### Effective memory, timeout and connection settings (A2, A4, A5, A6, A10)

```cypher
SHOW SETTINGS
YIELD name, value, startupValue
WHERE name IN ['server.memory.heap.max_size', 'server.memory.pagecache.size', 'dbms.memory.transaction.total.max',
               'db.memory.transaction.total.max', 'db.memory.transaction.max', 'db.transaction.timeout',
               'db.lock.acquisition.timeout', 'server.bolt.thread_pool_max_size', 'server.bolt.tls_level',
               'server.config.strict_validation.enabled']
RETURN name, value, startupValue
LIMIT 100
```

### Indexes that aren't online (A3, A4)

```cypher
SHOW INDEXES
YIELD name, type, state, populationPercent, labelsOrTypes, properties, failureMessage
WHERE state <> 'ONLINE'
RETURN name, type, state, populationPercent, labelsOrTypes, properties, left(failureMessage, 300) AS failure
LIMIT 100
```

A `FAILED` index isn't used by queries and stays failed until it's dropped. Recreating the same index on the same data
fails again. The failure text names the cause. `22NBH` means one property value is too large for the index type.
On Neo4j 2026.10.1, a RANGE index fails on a string of about 8 KB and a TEXT index on a string above 32 KB, while a
FULLTEXT index accepts a 40 KB string. The fix depends on the lookup: a FULLTEXT index for word search, or an index on
a shorter property derived from the long one for exact or prefix matches. Give the operator the `DROP INDEX` and the
replacement as recommendations.

### Constraints (A4, A9)

```cypher
SHOW CONSTRAINTS
YIELD name, type, labelsOrTypes, properties
RETURN name, type, labelsOrTypes, properties
LIMIT 100
```

### APOC version (A12)

```cypher
RETURN apoc.version() AS apoc
LIMIT 1
```

Compare it with the server version from the image tag or package: APOC Core must be the matching release
(`2026.10.x` with `2026.10.x`), as in [A12.1](runbooks/A12-versions-plugins.md#a121-apoc-version-mismatch).
