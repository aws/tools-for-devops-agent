# A4: Query performance, transactions and runtime errors

**Problem it solves:** Queries time out, run out of memory or fail. These errors go to the client and to query.log,
not to container output, so this runbook depends on query.log or client logs being readable. Without them the report
says so and gives the operator the checks. Community writes no query.log, so there these errors are only in client
logs.

**query.log in 2026.10.** `db.logs.query.enabled` defaults to `VERBOSE` with threshold `0s`, so every query writes a
`Query started:` line and a completion line. A completion line reads
`INFO  id:<n> - transaction id:<n> - <ms> ms: (planning: <ms>, waiting: <ms>) - <bytes> B - <n> page hits, <n> page faults - <session> <driver> client/<ip>:<port> ... <db> - <user> - <query> - {<params>} - runtime=<runtime> - {<annotations>}`;
failed queries are logged at `ERROR` with the error text appended. Parameter logging
(`db.logs.query.parameter_logging_enabled`) is on by default. Parse patterns are in [log-queries.md](../log-queries.md).

## A4.1 Query shapes that explode

**Symptom:** long durations, high allocated bytes and page hits for specific queries; client timeouts. Shapes: several
`OPTIONAL MATCH` clauses in a row, disconnected patterns (cartesian products), counting relationships by expanding
them instead of using the degree.

**Cause:** Each `OPTIONAL MATCH` or disconnected pattern multiplies rows; intermediate results grow until the query
times out or hits a memory limit.

**Check:** Top queries by duration and by allocated bytes in query.log; repeated query text from one application;
whether the slowest queries share a shape.

**Fix (operator):** `PROFILE` the query ([operator-queries.md](../operator-queries.md)); collapse rows with `WITH ... collect()`
between optional parts or use `COUNT {}` / `EXISTS {}` subqueries; connect patterns; count degrees with `COUNT { (n)-[:TYPE]->() }`, which the
planner answers from the stored degree instead of expanding every relationship.

## A4.2 Large updates or deletes in one transaction

**Signature:** client error `51N72` mentioning `memory pool out of memory` and
`dbms.memory.transaction.total.max`; the same text on a query.log `ERROR` line. Nothing in container output. Without a
limit, the same pattern ends in a heap `OutOfMemoryError` ([A2.2](A2-memory-jvm.md)).

**Cause:** One transaction holds all changes in heap until commit. `dbms.memory.transaction.total.max` (default 70% of
the maximum heap) caps all transactions together; `db.memory.transaction.max` caps one transaction (unlimited by
default). Bulk `DELETE`, `SET` or `REMOVE` over millions of entities in one statement hits the limit or times out.

**Check:** Failed statements and their allocated bytes; the transaction memory settings; whether the failing workload
is a batch or migration job.

**Fix (operator):** Batch with `CALL { ... } IN TRANSACTIONS OF <n> ROWS` (or `apoc.periodic.iterate` from APOC Core),
choosing the batch size from allocated bytes per row. Set `db.memory.transaction.max` so one runaway transaction fails
instead of starving others. Batching gives up atomicity: a failure leaves earlier batches committed.

## A4.3 Read/delete conflict

**Signature:** client `ReadAndDeleteTransactionConflictException`.

**Cause:** A read observed an entity that a concurrent transaction deleted before the read finished.

**Fix (operator):** Retry the read (driver managed transactions retry transient errors), and avoid long reads running
alongside bulk deletes of the same data.

## A4.4 Schema changed during a transaction

**Signature:** transient error `Database constraints changed since the start of this transaction`
(`ConstraintsChanged`). Older versions: `Database constraints have changed (txId=...) after this transaction (txId=...) started, which is not yet supported`.

**Cause:** A constraint or index was created or dropped while the transaction ran.

**Fix (operator):** Retry; run schema changes outside busy periods. Driver managed transactions (`executeRead` /
`executeWrite`) retry it automatically.

## A4.5 Capturing execution plans

**Symptom:** a slow query has been identified and needs a plan.

**Fix (operator):** Run the query prefixed with `PROFILE` (executes) or `EXPLAIN` (doesn't) through cypher-shell, using
the parameters from query.log. To inspect a running query's memory and locks, use `SHOW TRANSACTIONS` while it runs.
Commands are in [operator-queries.md](../operator-queries.md).

## A4.6 MERGE on a null property

**Signature:** `Cannot merge the following node because of null property value for ...` (2026.10 wording; older:
`Cannot merge node using null property value for`). In client logs or on a query.log `ERROR` line.

**Cause:** Input rows lack the property `MERGE` matches on.

**Fix (operator):** Filter rows with a null key before `MERGE` (`WHERE row.id IS NOT NULL`) or supply a default with
`coalesce()`.

## A4.7 CREATE with a missing end node

**Signature:** `Failed to create relationship ..., node ... is missing`. In client logs or on a query.log `ERROR`
line.

**Cause:** The `MATCH` for one end of the relationship returned no node, so `CREATE` has nothing to connect. Since
Neo4j 5 this fails by default; `dbms.cypher.lenient_create_relationship=true` restores the old behavior of silently
skipping the row.

**Fix (operator):** Fix the input or the `MATCH`; use the lenient setting only as a temporary compatibility measure.

## A4.8 Slotted runtime internal error

**Signature:** `The target slotted execution context cannot hold the data to copy` (the message still exists in the
slotted and pipelined runtimes on 2026.10). In client logs or on a query.log `ERROR` line.

**Cause:** A runtime bug triggered by a specific query plan.

**Fix (operator):** Run the query with another runtime (`CYPHER runtime=interpreted` or `runtime=slotted` prefix) as a
workaround, check the release notes of newer 2026.x versions, and send the query and plan to Neo4j Support.
