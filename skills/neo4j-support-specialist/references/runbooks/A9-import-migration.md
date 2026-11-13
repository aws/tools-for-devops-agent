# A9: Import and migration

**Problem it solves:** Bulk loads crawl or fail and dumps won't load. Evidence comes from the Job or task that ran the
load or dump, and from query.log for MERGE-heavy loads.

## A9.1 Slow MERGE-based loads

**Symptom:** load jobs that slow down as data grows; long `MERGE` statements in query.log with page hits growing with
store size.

**Cause:** `MERGE` without a uniqueness constraint or index on the merge key scans every node with the label, so each
row costs more than the last.

**Fix (operator):** Create constraints before loading (`CREATE CONSTRAINT ... REQUIRE n.id IS UNIQUE`), check with
`SHOW CONSTRAINTS` and `SHOW INDEXES`, batch rows with `CALL { ... } IN TRANSACTIONS`, and merge nodes before
relationships.

## A9.2 Offline bulk import

**Symptom:** an initial load of millions of rows through `LOAD CSV` or drivers takes hours.

**Fix (operator):** For initial loads use `neo4j-admin database import full` into a new or empty database (and
`neo4j-admin database import incremental`, Enterprise only, for supported incremental loads), then `CREATE DATABASE`.
On Community, which can't create databases, import into `neo4j` with the server stopped.

## A9.3 CSV parsing and escaping errors

**Symptom:** `LOAD CSV` or `neo4j-admin database import` errors about quotes, unexpected field counts or delimiters.
The errors are in the import Job or task output if the load runs there, otherwise in client logs.

**Cause:** Embedded quotes, delimiters inside fields, multi-line values or non-printable delimiters.

**Fix (operator):** Quote fields containing delimiters, double embedded quotes, set `FIELDTERMINATOR` (hex form such as
`'\u0009'` is allowed), and for `neo4j-admin database import` set `--delimiter`, `--array-delimiter`, `--quote` and
`--multiline-fields` to match the files.

## A9.4 Dump fails: "Active logical log detected"

**Signature:** `neo4j-admin database dump` (or a load or upload step that checks the store) fails with `Active logical
log detected, this might be a source of inconsistencies.` (text present on 2026.10). It's in the dump Job or task
output; a dump run by hand leaves nothing the agent can read.

**Cause:** The source database wasn't shut down cleanly, so its transaction logs still hold entries not checkpointed to
the store.

**Fix (operator):** Start and cleanly stop the database (`START DATABASE`, then `STOP DATABASE`) so recovery and a
checkpoint run, then dump. For a running database, take an online backup instead.

## A9.5 Dumps from old versions

**Symptom:** a dump or backup from an older major version won't load or start on 2026.x.

**Cause:** Stores from older versions must be migrated. Neo4j 2026.x migrates stores from 4.4 and 5.x with
`neo4j-admin database migrate`; anything older must first be upgraded to 4.4.

**Fix (operator):** `neo4j-admin database load` the dump, then `neo4j-admin database migrate <db>` (optionally
`--to-format=block`), then `CREATE DATABASE` or start it. For pre-4.4 stores, step through 4.4 first. Follow the
Upgrade and Migration Guide for the exact path.
