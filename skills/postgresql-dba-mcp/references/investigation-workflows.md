# Targeted PostgreSQL investigation workflows

These workflows supplement the safety and report-routing guidance in `SKILL.md`.
Keep investigations read-only and treat findings as evidence requiring workload
context and owner review. AWS DevOps Agent registers this file as the reference
artifact titled `postgresql-dba-mcp: investigation-workflows`.

When a user asks for current targeted evidence after a health report, run the
relevant predefined diagnostic again. Do not answer solely from bounded rows or
columns in an earlier report. If a repeated complete check is deduplicated, explain
that a new chat is required for an independent snapshot.

## Vacuum, dead tuples, physical bloat, and transaction ID age

1. Run query 7.1 for vacuum recency and dead tuples.
2. Run query 7.3 for transaction ID age.
3. Run query 5.2 for dead-tuple ratio. It is not physical bloat or reclaimable space.
4. Run query 5.5 when physical bloat is requested. It returns one grouped row per
   user table using a statistical physical-layout heuristic, excludes system schemas,
   and separately estimates table and aggregate index waste. It remains a heuristic,
   not measured reclaimable space.
5. Run query 3.2 to identify long transactions that may prevent cleanup.
6. Gather table size, write rate, autovacuum logs/settings, oldest transaction, and
   storage trend before proposing remediation. `ANALYZE` updates planner statistics
   and is not a read-only follow-up.

## Index review

1. Run query 8.1 for indexes with no recorded scans.
2. Run query 8.2 for potential duplicate candidates. Require all candidate names and
   definitions; compare access method, uniqueness/constraint semantics, key versus
   INCLUDE columns, operator classes, collations, ordering, expressions, predicates,
   validity, dependencies, and workload use.
3. Run query 8.3 for table scan ratios.
4. Review statistics reset time, seasonal/batch workloads, query plans, write overhead,
   storage, and ownership. Zero scans or similar columns are not drop instructions.
5. If a change is separately approved, assess concurrent-DDL limitations, replication,
   lock behavior, storage, validation, and rollback before execution.

## Statement performance and plan-only EXPLAIN

1. Use category 6 when `pg_stat_statements` is enabled and access is approved. Query
   6.1 ranks cumulative `total_exec_time`; this is elapsed execution duration, not CPU
   utilization. Query 6.2 ranks mean execution duration.
2. Run query 6.9 and state the `pg_stat_statements` reset timestamp. Rankings cover
   only the current statistics window. The corrected ranking queries exclude the
   current diagnostic role to reduce self-observation; application traffic is omitted
   if that role is reused.
3. Use the fingerprint and server-produced `normalized_query_preview` together. A
   preview is bounded and redacted, not complete SQL and not a source of bind values.
   Fingerprints are not reversible. Full normalized SQL requires an explicit approved
   lookup outside the current MCP surface.
4. Call `explain_query` only with one approved complete `SELECT`; never pass a truncated
   preview. State that plan-only `EXPLAIN` was executed and the underlying `SELECT` was
   not executed.
5. Follow the guardrails returned by the MCP:
   - costs and rows are estimates, not observed runtime facts;
   - a stable-expression range boundary is not automatically non-sargable;
   - nested loops are not inherently unscalable;
   - a sequential scan can be appropriate for a small or nonselective relation;
   - do not generalize one node's row estimate to other nodes;
   - indexes and rewrites are proposals requiring representative workload validation;
   - `ANALYZE` is not read-only because it updates statistics.
6. PostgreSQL planning may evaluate trusted `IMMUTABLE` or `STABLE` expressions. Keep
   least-privilege object/EXECUTE access and do not broaden privileges for convenience.

## Replication visibility

1. Run queries 4.1 and 4.2 for PostgreSQL replication and slot state.
2. Review relevant engine-specific CloudWatch metrics separately.
3. Confirm RDS PostgreSQL versus Aurora before interpreting lag; architectures differ.
4. Replication-slot inventory is cluster-wide catalog evidence and can include another
   database. Never drop a slot from this evidence alone; confirm subscriber ownership,
   retained WAL, recovery requirements, and data-loss impact.

## Connections and lock waits

1. Run query 3.1 for connection-state totals and query 3.4 for user/database distribution.
2. Run query 3.2 for long-running activity.
3. Run query 3.3 for waiting and blocking relationships.
4. Capture owner, transaction state, age, lock graph, and business impact before
   proposing cancellation or termination. Idle-in-transaction is not automatically
   safe to terminate.

## On-screen readiness evidence

Use this workflow for every pre-upgrade request. Readiness output is delivered on
screen only as the MCP's validated Markdown result; there is no downloadable-file
or HTML delivery, and a request phrased as "downloadable" or "HTML" is served the
same on-screen way with a plain statement that no downloadable file is produced.

1. Require an explicit target major version. Call `check_upgrade_readiness` with
   `report_format="markdown"`.
2. Report the exact `ValidUpgradeTarget` engine versions returned for the requested
   major and exact-target instance-class orderability. API failure or an absent major
   remains unavailable/fail evidence; never infer support from the general engine catalog.
3. Run category 10 queries 10.1 through 10.12. Query 10.7 is visible-view inventory,
   not proof of catalog dependency. Query 10.10 contains only user-created ICU
   collations and is manual-review evidence, not an automatic blocker.
4. For Aurora, use cluster availability/member metadata and cluster `VolumeBytesUsed`.
   Do not derive storage headroom from DB-instance `AllocatedStorage`, `FreeStorageSpace`,
   or `MultiAZ`. For standalone RDS PostgreSQL, instance storage evidence may apply.
5. Distinguish database-local evidence from cluster-wide catalog evidence. Mark
   unconnected database-local checks `Not collected`.
6. Review extensions against exact target support, run authoritative RDS/Aurora
   pre-upgrade checks, and test the exact path on a clone.
7. Document rollback, downtime, replication, parameter-group, extension, and driver
   plans before approval. Absence of a reported failure is not upgrade approval.
