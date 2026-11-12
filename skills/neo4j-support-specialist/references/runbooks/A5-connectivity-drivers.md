# A5: Connectivity and drivers

**Problem it solves:** Applications can't connect, lose sessions, or overload one member. The cause usually shows in
configuration and network setup: advertised addresses, Service and NLB listeners and health, security groups, idle
timeouts, pod restarts. The error text itself is in client logs.

**What to read.** Bolt settings (`server.bolt.listen_address`, `server.bolt.advertised_address`,
`server.default_advertised_address`, `server.bolt.tls_level`, `dbms.routing.default_router`); EKS Services
(`type`, ports, `service.beta.kubernetes.io/aws-load-balancer-*` annotations) and the Helm `k8s-config` ConfigMap,
which sets advertised addresses; NLB listeners, target groups, target health and listener attributes; security groups
on nodes, tasks and the load balancer. Ports: 7687 Bolt, 7474 HTTP, 7473 HTTPS, 6362 backup, 6000 cluster and
discovery, 7000 Raft, 7688 server-side routing.

## A5.1 ServiceUnavailable or no routing servers

**Signature:** client `ServiceUnavailable`, `Unable to retrieve routing information`, `Could not perform discovery`,
`Connection refused` (driver wording varies).

**Cause:**

- `neo4j://` makes the driver fetch a routing table and then connect to the advertised addresses in it. If those are
  pod-internal DNS names, `localhost` or private IPs the client can't reach (typical for clients outside the cluster
  or behind one load balancer), every query fails after the first connection.
- Encryption mismatch: `+s`/`+ssc` scheme against `server.bolt.tls_level=DISABLED`, or plain scheme against
  `REQUIRED`.
- Nothing listening: server down, database offline, wrong port, target group unhealthy, security group closed.

**Check:**

1. Advertised addresses in the configuration vs where the clients run.
2. Scheme and TLS: client URI (if in logs or Lambda/ECS environment) vs `server.bolt.tls_level`.
3. Load balancer listener for 7687, target health, security group rules; pod readiness and restarts.

**Fix (operator):** Advertise addresses the clients can reach, or for clusters behind a single endpoint enable
server-side routing (`dbms.routing.default_router=SERVER`, port 7688 open between members). Use `bolt://` for a single
standalone server reached through a load balancer. Match the URI scheme to the TLS setting.

## A5.2 SessionExpired after a topology change

**Signature:** client `SessionExpired` / `SessionExpiredException` around a restart, reschedule or leader change.

**Cause:** The driver's routing table pointed at a member that went away; in-flight work on that connection fails.

**Check:** Events and `lastState` at the error times; leader changes in debug.log if shipped.

**Fix (operator):** Use driver managed transactions (`executeRead`/`executeWrite`), which retry on another member.
Reduce restarts (A1, A2). Occasional SessionExpired during planned restarts is expected.

## A5.3 Connections dropped by load balancers

**Symptom:** intermittent `connection reset`, `Connection to the database terminated`, or a failure on the first
query after an idle period.

**Cause:** An NLB drops TCP flows idle longer than its idle timeout (350 seconds by default for TCP listeners,
configurable as the `tcp.idle_timeout.seconds` listener attribute). Pooled driver connections idle longer than that
are dead when reused. Neo4j sends Bolt keep-alives only while a request runs
(`server.bolt.connection_keep_alive`, default 1m; the Helm chart sets 30s).

**Check:** `elbv2 describe-listener-attributes` for the 7687 listener; keep-alive settings; the driver's max connection
lifetime and liveness check if the application config is visible.

**Fix (operator):** Set the driver's max connection lifetime below the load balancer idle timeout and enable the
connection liveness check (Java: `withMaxConnectionLifetime`, `withConnectionLivenessCheckTimeout`), or raise the NLB
idle timeout.

## A5.4 Driver lifecycle in Lambda functions

**Symptom:** slow invocations, connection spikes on Neo4j matching Lambda concurrency. A driver created per invocation
shows only in function code or logs.

**Cause:** A driver created inside the handler opens a new pool, resolves routing and authenticates on every
invocation.

**Fix (operator):** Create the driver once outside the handler and reuse it across invocations; size the pool small,
since each execution environment serves one request at a time.

## A5.5 Reads not routed to secondaries

**Symptom:** one member (the writer) much busier than the others; reads slow under write load. query.log on each
member shows read queries landing on the writer.

**Cause:** Work submitted as write transactions (the default for auto-commit queries and `executeWrite`) always goes to
the writer. Only read transactions are routed to secondaries or other primaries.

**Fix (operator):** Use read transactions for reads: Python `session.execute_read`, JavaScript `session.executeRead`,
Java `session.executeRead`, Go `session.ExecuteRead`, .NET `session.ExecuteReadAsync`, Spring
`@Transactional(readOnly = true)`, or `routing_=RoutingControl.READ` with `driver.execute_query`.

## A5.6 Database name not set in the driver

**Symptom:** extra round trips per session; queries landing in an unexpected database. There's no server-side signal;
the setting lives in application code.

**Fix (operator):** Pass the database name in the session or query configuration so the driver skips home-database
resolution.

## A5.7 Browser WebSocket connection failure

**Signature:** Neo4j Browser shows `WebSocket connection failure. Due to security constraints in your web browser, the reason for the failure is not available to this Neo4j Driver.`

**Cause:** Browser loads over HTTP (7474) but then opens a Bolt WebSocket from the user's machine to the advertised Bolt
address. If 7687 isn't exposed, the advertised address is internal, or TLS settings differ between the two, it fails.

**Fix (operator):** Expose 7687 alongside 7474, advertise an address reachable from users, and use the same TLS setting
on both connectors.

## A5.8 Large results throttled

**Symptom:** large result sets stream slowly although the server isn't busy.

**Cause:** TCP flow control and Bolt fetch sizes pace the stream to the client's consumption rate.

**Fix (operator):** Consume results as they stream, tune the driver fetch size, and return only needed properties.

## A5.9 Network path validation

**Symptom:** timeouts between clients and members, or between members.

**Check:** Inbound rules on the Neo4j security group for 7687/7474 from client sources; between members for 6000, 7000
and 7688; 6362 only from backup sources; NACLs on the subnets; EKS NetworkPolicies can't be read and are listed as not
checked.

**Fix (operator):** Open the missing ports; on a cluster, `CALL dbms.cluster.checkConnectivity()` from a member checks
member-to-member ports; from a client host, test the port with `nc -vz <host> 7687`.

## A5.10 Unpinned driver version changed behavior

**Symptom:** errors start after an application deploy with no Neo4j change. query.log shows the driver name and
version on every line (for example `neo4j-cypher-shell/v2026.10.1`).

**Fix (operator):** Pin the driver version in the application build and upgrade deliberately.

## A5.11 Driver-side logging

**Symptom:** a client-side problem needs more detail than the application logs give.

**Fix (operator):** Enable driver debug logging for the affected service for a short period.

## A5.12 Bolt worker threads exhausted

**Signature:** container output
`ERROR Increase in thread starvation events detected (<n> events over a period of <ms> ms) - This may indicate an overload condition`.
A related 2026.x message, `Increase in network aborts detected (...) - This may indicate an issue with the network environment or an overload condition`,
comes from the same component.

**Cause:** More concurrent requests than Bolt worker threads (`server.bolt.thread_pool_max_size`, default 400), so new
requests wait. Usually long-running queries holding threads, a connection storm, or a pool size set too low.

**Check:** `server.bolt.thread_pool_max_size`; CPU and request rates at that time; slow queries in query.log
([A4.1](A4-query-transactions.md)); client pool sizes.

**Fix (operator):** Find and fix the long-running queries first; cap client pool sizes; raise the thread pool only if
CPU has headroom.
