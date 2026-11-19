# A12: Versions, APOC and plugins

**Problem it solves:** Plugin and version mismatches stop startup or hide procedures. A mismatched APOC jar stops the
server with the cause in container output; the image tag and plugin list are in the pod or task spec.

**What to read.** Image tag (`neo4j:2026.10.1-enterprise`, or `neo4j:2026.10.1` for Community), `NEO4J_PLUGINS`
(for example `["apoc"]`, which makes the image fetch the matching APOC Core), jars mounted into
`/var/lib/neo4j/plugins`, Helm `apoc_config` and `apoc_credentials` values, `dbms.security.procedures.unrestricted` and
`dbms.security.procedures.allowlist`.

## A12.1 APOC version mismatch

**Signature:** container output `Caused by: org.neo4j.kernel.lifecycle.LifecycleException: Component
'apoc.ApocConfig@...' failed to initialize` with a `NoSuchMethodError` cause, exit 1 (for example APOC 5.26.0 on Neo4j
2026.10.1).

**Cause:** APOC Core versions match Neo4j versions exactly; a jar built for another version calls methods that don't
exist. Typical after upgrading the image while a mounted or baked-in APOC jar stayed behind.

**Fix (operator):** Use the APOC Core release matching the Neo4j version (`2026.10.x` with `2026.10.x`), or let the image
install it with `NEO4J_PLUGINS='["apoc"]'`; remove old jars from the plugins volume.

## A12.2 Procedures missing after an upgrade

**Signature:** client `There is no procedure with the name apoc...` for procedures that used to work. Wording not
confirmed on 2026.x; match on `There is no procedure with the name`.

**Cause:** Since Neo4j 5, APOC is split into APOC Core (supported by Neo4j, shipped in the image's `labs` folder) and APOC
Extended (community-maintained, separate jar). Procedures such as `apoc.load.jdbc` and the TTL feature are in Extended.

**Fix (operator):** Check which package holds the procedure; install the matching APOC Extended jar if it's needed and
accepted, or replace the call with a Core or Cypher equivalent.

## A12.3 Procedure blocked by the sandbox

**Signature:** client `... is unavailable because it is sandboxed and has dependencies outside of the sandbox`
(2026.10 wording; older: `procedure is not available due to having restricted access rights, check configuration`).

**Cause:** Procedures that use internal APIs must be listed in `dbms.security.procedures.unrestricted`.

**Fix (operator):** Add the procedure or namespace (for example `apoc.*`) to `dbms.security.procedures.unrestricted`,
keeping the list as narrow as practical, and restart.
