# ElastiCache Troubleshooting Skill — Test Results (with vs without the skill)

Companion to *ElastiCache Troubleshooting Skill — Test Scenarios (Phase 1)*.

## How to read this doc

For every scenario we injected a real fault on a test cluster and ran the **same**
DevOps Agent investigation in two Agent Spaces in the same account: one with the
`elasticache-troubleshooting` skill and one without. Nothing else differed. Each section
shows the scenario, the scores of all runs, **one full response per agent**, and an
analysis of what the skill changed and why it did or did not make a difference.

**Scoring** (per run, 0-2 on each criterion, maximum 8):

| Criterion | 2 | 1 | 0 |
|---|---|---|---|
| Root cause | Names the injected mechanism | Partial, or restates the symptom | Wrong |
| Lookalike ruled out | Explicitly, with evidence | Mentioned without evidence | No |
| Evidence | Metric + node/shard + value + time | Vague | None |
| Remediation | Correct and presented as operator-run | Generic or partly wrong | Wrong or unsafe |

**Test cluster:** ElastiCache for Valkey 8.1, cluster mode enabled, 2 shards × 1 replica,
`cache.m7g.large`, TLS, slow log delivered to CloudWatch Logs, us-east-1. Load is generated
from an EC2 instance in the same VPC.

Account IDs, ARNs, resource IDs and IAM names in the quoted responses are replaced with
placeholders.

## Summary

Testing covered S1, S3, S4 and S5 (11 rounds, 40 investigations). S2, S6, S7, S8 and the
negative checks were not run; they remain in `evals/evals.json` only as the two negative
cases.


| Scenario | Without skill (avg /8) | With skill (avg /8) | Root cause correct (without → with) | Did the skill make a difference? |
|---|---|---|---|---|
| S1 OOM under noeviction — attempt 1 | 7.0 (2 runs) | 6.5 (2 runs) | 2/2 → 2/2 | **No.** Test design gave the cause away; see analysis. Re-run planned |
| S1 OOM under noeviction — attempt 2 (policy set 11 h earlier) | 6.3 | 7.7 | 3/3 → 3/3 | **Yes, modestly:** directly observed `OOM` rate and error types, and the right fix; see analysis |
| S2 Evictions | — | — | — | Not run (testing stopped) |
| S3 Hot key | 6.0 | 7.7 | 2/3 → 3/3 | **Partly:** both find the hot shard; the skill adds the fix and excludes other causes; see analysis |
| S4 Expensive commands — attempt 1 | 5.0 | 7.7 | 2/3 → 3/3 | **Yes:** consistency and discriminating evidence; see analysis |
| S4 Expensive commands — attempt 2 (OTel fix, 1 with-skill run) | 5.0 (from attempt 1) | 8 (1 run) | 2/3 → 1/1 | **Yes**, and the OpenTelemetry path now runs; single run, see caveats |
| S5 Connection churn — attempt 1 | 6.3 | 5.7 | 3/3 → 1/3 | **No, worse:** a previous scenario's traffic in the lookback window misled 2 of 3 with-skill runs; see analysis |
| S5 Connection churn — attempt 2 (symptom-anchoring fix, same incident) | 6.3 (from attempt 1) | 6.7 | 3/3 → 1/3 (+2 partial) | **Mixed:** better, still tied to the earlier traffic stop in 2 runs; clean re-run planned |
| S5 Connection churn — attempt 3 (clean history) | 5.3 | 6.3 | 2/3 → 2/3 | **Yes, modestly:** evidence stays on cache telemetry, `maxclients` checked, fix given; one with-skill run misread the handshake commands |
| S6 Replication lag | — | — | — | Not run (testing stopped) |
| S7 READONLY after failover | — | — | — | Not run (testing stopped) |
| S8 Serverless throttling | — | — | — | Not run (testing stopped) |
| N1/N2 Must not trigger | — | — | — | Not run (testing stopped) |

---

## S1 — OOM under `noeviction` (attempt 1)

### Scenario

- **Fault injected:** `maxmemory-policy` set to `noeviction` on the cluster's parameter group,
  then the load generator wrote 10 KB keys with no TTL until memory was full and kept
  writing. From 10:08:51 UTC every write was rejected with `OOM` (~18.7k rejected writes/s).
- **Prompt (both spaces):** *Session writes failing* — "Since about 10:08 UTC today our
  application cannot write session data to ElastiCache cluster ec-test-cme in us-east-1.
  Find the root cause."
- **Expected root cause:** memory at maxmemory under `noeviction`, so writes are rejected with
  `OOM`. Evidence: memory ~100%, `OOM` error replies, evictions = 0, the policy value. Fix:
  because no key has a TTL, an eviction policy such as `allkeys-lru`, deleting keys, or more
  capacity (`volatile-lru` would free nothing).
- **Lookalike to rule out:** an eviction policy that is working (evictions > 0, no `OOM`).

### Scores

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Notes |
|---|---|---|---|---|---|---|
| With skill, run 1 | 2 | 2 | 2 | 1 | 7 | Recommended `volatile-lru` (cannot work, no key has a TTL); offered to apply the change itself. Chat-style output |
| With skill, run 2 | 2 | 1 | 2 | 1 | 6 | Observed `OOM` errors directly; evictions = 0 not stated; no remediation section |
| Without skill, run 1 | 2 | 2 | 1 | 1 | 6 | Factual errors in the memory timeline; recommended `volatile-lru`; offered to apply. Chat-style output |
| Without skill, run 2 | 2 | 2 | 2 | 2 | 8 | Identified the client instance; `OOM` inferred, not observed |
| **Average** | | | | | **With 6.5 / Without 7.0** | |

Run 3 was not executed: the analysis below showed the test design had to change first.

### Response — with the skill (run 2)

> # Investigation summary
>
> ## Impact
>
> ### Session writes rejected with OOM
>
> Starting ~10:12 UTC on 2026-11-03, writes to ec-test-cme (arn:aws:elasticache:us-east-1:123456789012:replicationgroup:ec-test-cme) are rejected with `OOM` at ~18.6k errors/s, and no other error types appear. Successful SET calls dropped from ~4.8k/s to ~0 by 10:14, and the key count has been flat since.
>
> ## Root causes
>
> ### noeviction policy + session keys with no TTL
>
> About 414k session keys (~12.4 KB each) were written to each shard primary between 10:07 and 10:09 UTC, none with a TTL (CurrVolatileItems = 0). At 10:09:00, parameter group ec-test-cme was changed to maxmemory-policy=noeviction (applied immediately). With nothing allowed to evict or expire, memory stays full, so reverting to volatile-lru would also not free anything.
>
> **Observations:**
>
> - **maxmemory-policy changed to noeviction at 10:09 UTC:** ElastiCache event 2026-11-03 10:09:00 UTC on parameter group ec-test-cme: 'Updated parameter maxmemory-policy to noeviction'. describe_cache_parameters confirms the user-set value is noeviction (ChangeType immediate, so it is already live; nodes in-sync). With noeviction, once memory is full the engine rejects writes with OOM instead of evicting keys. The only other user-set parameter is cluster-enabled=yes. Other events in 08:00–10:40 are only cluster creation (09:42–09:45) and slow-log delivery being enabled (09:46).
> - **~414k keys per primary, none with TTL:** CurrItems on both primaries went from 0 to ~414k between 10:07 and 10:09 UTC (0001-001: 413,930; 0002-001: 413,929), then stayed flat. CurrVolatileItems is 0 on both, so no key has a TTL. With maxmemory-policy=noeviction (set at 10:09), nothing can be evicted or expire, so writes will fail with OOM once memory is full.
>
> ## Key findings
>
> ### Memory at 100% of maxmemory on all 4 nodes
>
> Between 10:09 and 10:10 UTC, memory used on every node jumped from ~20.7 MB (0.40%) to the 5,140,907,060-byte limit (100%), and the limit itself did not change. Under noeviction, the engine rejects every write once memory is full.
>
> ## Investigation gaps
>
> - **CloudTrail lookups not permitted:** CloudTrail operations aren't allowed for this agent, so it's unknown who made the 10:09 maxmemory-policy change or what the policy was before.
> - **Application-side logs unavailable:** No application logs were available, so the write failures are confirmed only from the engine's OOM error counts.
>
> *(Observations repeated verbatim under several headings in the original output are shown once.)*

### Response — without the skill (run 2)

> # Investigation summary
>
> ## Impact
>
> ### Memory at 100% on both shards, writes halted
>
> DatabaseMemoryUsagePercentage on ec-test-cme-0001-001 and ec-test-cme-0002-001 jumped from about 0.4% to 100% between 10:08 and 10:09 UTC and has stayed there through 10:35. SetTypeCmds dropped from about 175K–307K/min to 0 after 10:09. Evictions were 0 throughout. EngineCPUUtilization rose from 0.5% to about 21% and is holding there.
>
> ## Root causes
>
> ### No-TTL session keys combined with the noeviction policy
>
> At 10:08–10:09 UTC, client ec-test-loadgen (i-0123456789abcdef0) wrote about 413,930 keys per shard (about 12.4 KB each, about 5.14 GB per shard), none with a TTL (CurrVolatileItems=0). At 10:09:00, parameter group ec-test-cme set maxmemory-policy=noeviction (the default.valkey8.cluster.on default is volatile-lru). With memory full, the engine refuses all writes. Restoring volatile-lru alone would not free memory because no key has a TTL. An allkeys-* policy, deleting keys, or adding capacity is needed.
>
> **Observations:**
>
> - **414K keys per shard, none with TTL; client still sending about 5.9 GB/min:** CurrItems on 0001-001 and 0002-001 rose from 0 to about 413.9K per shard at 10:08–10:09 and has been flat since. CurrVolatileItems is 0, so no key has a TTL. BytesUsedForCache on 0001-001 went from 20.7 MB to 5.14 GB. NetworkBytesIn on 0001-001 stays at about 5.87–5.90 GB/min from 10:10 to 10:35 (about 0.6 MB/min before) while SetTypeCmds is 0. The client is still sending large payloads that are not being stored, which is consistent with OOM rejections. Replica 0001-002 also sits at about 99.99% memory. GetTypeCmds returned no data.
> - **maxmemory-policy changed to noeviction:** An ElastiCache event at 2026-11-03 10:09:00 UTC shows parameter group `ec-test-cme` updated `maxmemory-policy` to `noeviction`. That was about 23 minutes after the replication group was created (09:45:40) and slow-log delivery was enabled (09:46:31). With noeviction, write commands fail with OOM errors once memory reaches maxmemory. The nodes also logged that cache.m7g.large does not support persistence (appendonly).
> - **Write burst at 10:08–10:09 filled memory, no evictions:** SetTypeCmds was 175,029 + 307,303 at 10:08 and 238,900 + 106,625 at 10:09 across the two primaries (about 830K total), then 0. CurrConnections rose from 5/4 to 13/12 at 10:08. Memory reached 100% within the same 2 minutes while Evictions stayed at 0, which is consistent with maxmemory-policy=noeviction (confirmed via describe_cache_parameters, Source=user). Engine CPU stays at about 21% with no successful writes, which may point to clients retrying rejected commands.
> - **Sole client: EC2 ec-test-loadgen:** Security group &lt;cache-sg&gt; (ec-test-cache, &lt;vpc&gt;) allows TCP 6379 only from &lt;client-sg&gt;. The only instance in that group is i-0123456789abcdef0 `ec-test-loadgen` (&lt;private IP&gt;, running, launched 2026-11-03 09:41:32 UTC), so it is the likely source of the write burst.
>
> ## Key findings
>
> ### Memory filled under noeviction — writes rejected with OOM
>
> The ec-test-loadgen client wrote about 414K keys per shard with no TTL (about 5.1 GB per primary) at 10:08–10:09 UTC, filling both primaries and replicas to maxmemory. With maxmemory-policy=noeviction (set at 10:09:00), Valkey cannot evict and rejects further writes. SETs are at 0 while NetworkBytesIn stays at about 5.9 GB/min, so the client keeps sending rejected writes. OOM errors have not yet been observed directly.
>
> ## Investigation gaps
>
> - **CloudTrail not available:** The cloudtrail lookup_events API is not allowed. The workaround of reading raw CloudTrail objects failed with AccessDenied: role &lt;agent-role&gt; has no s3:GetObject on bucket &lt;cloudtrail-bucket&gt;. Who changed maxmemory-policy to noeviction (10:09 UTC) cannot be attributed.
> - **No code repository connected:** No code repository or deployment pipeline is associated, so the code that writes session keys without a TTL could not be inspected.
>
> *(Observations repeated verbatim under several headings in the original output are shown once.)*

### Differences

| Aspect | Without the skill | With the skill | Who did better |
|---|---|---|---|
| Root cause | `noeviction` + keys with no TTL | `noeviction` + keys with no TTL | Same |
| Evidence that writes fail with `OOM` | **Inferred**: "OOM errors have not yet been observed directly"; deduced from `SetTypeCmds` = 0 while `NetworkBytesIn` stayed high | **Observed**: "rejected with `OOM` at ~18.6k errors/s, and no other error types appear", from the Valkey OpenTelemetry error metric | **Skill** |
| Lookalike (evictions) ruled out | "Evictions were 0 throughout" | Not stated explicitly | Without |
| Remediation | "An allkeys-* policy, deleting keys, or adding capacity is needed" | Notes `volatile-lru` would not help, but gives no fix | **Without** |
| Extra context | Identified the client instance from the security group | None | Without |
| Onset time | 10:08 (correct) | ~10:12 (late; the first `OOM` was 10:08:51) | Without |
| Factual errors (run 1 of each) | Run 1 reversed the memory timeline | None | Skill |

### Why the skill did not make a difference here

1. **The fault gave the cause away.** The `noeviction` change was applied 15 seconds
   before the fault started, and ElastiCache records it as an event. Both agents found the
   event right at the onset and connected it to the failures. Most of the reasoning came
   from that event, not from the metrics. Real customers usually set the policy long before
   their data grows into it, and that is the case where telemetry knowledge is needed.
2. **The base model already knows the mechanism.** "`noeviction` + full memory = `OOM`"
   is general Valkey knowledge. The skill can only add value with ElastiCache-specific
   signals (here, the OTel `valkey.errors` metric that shows the `OOM` replies), and that
   advantage was real but small.
3. **The skill missed two things the baseline got right.** It did not cover the case where
   no key has a TTL, so a `volatile-*` policy frees nothing. Its output also did not force
   a remediation and an explicit lookalike check.

### What we changed

- **Skill:** the `OOM` row now covers "nothing evictable" (`noeviction`, or `volatile-*`
  with no TTL keys), requires quoting evictions = 0 and checking `CurrVolatileItems`, and
  gives the correct fix for each case. The output must always include all five parts, and
  the onset is the first failure datapoint. The skill must not offer to apply changes.
- **Test design:** every policy change now happens at least 3 hours before its scenario, so
  no change event sits at the onset, and all runs use Investigation mode (run 1 of both
  spaces came back as chat-style answers).
- **S1 attempt 2** will re-run this scenario with the updated skill, with `noeviction`
  set more than 3 hours before the fault.

---

## S4 — Expensive commands (`KEYS` and a large `HGETALL`)

Skill revision: after the S1 changes.

### Scenario

- **Fault injected:** 1M small keys and one 200,000-field hash loaded. Background traffic of
  about 11,000 `GET`s per second. Every 30 seconds the client ran `KEYS nomatch:*` (a full
  keyspace scan on every primary) and `HGETALL` on the big hash. From 11:02:52 UTC each call
  blocked the engine for ~17–19 ms, about 1,000 times a normal `GET`.
- **Prompt (both spaces):** *Intermittent cache latency spikes* — "Since about 11:02 UTC today
  we see periodic latency spikes on ElastiCache cluster ec-test-cme in us-east-1. Find the
  root cause."
- **Expected root cause:** O(N) commands (`KEYS`, `HGETALL` on a big hash) blocking the
  single-threaded engine. Evidence: their latency far above every other command, matching
  slow log entries every ~30 s. Fix: `SCAN`/`HSCAN`, bounded reads; the key name needs
  `SLOWLOG GET` because delivered slow logs redact keys.
- **Lookalike to rule out:** engine saturation (all commands slow together, high engine CPU).

### Scores

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Notes |
|---|---|---|---|---|---|---|
| With skill, run 1 | 2 | 2 | 2 | 2 | 8 | Compared per-family latency (`KeyBasedCmdsLatency` vs `GetTypeCmdsLatency`) to exclude saturation |
| With skill, run 2 | 2 | 2 | 1 | 2 | 7 | Slow-log evidence only; side note misstates the earlier policy (`volatile-lru` instead of `noeviction`) |
| With skill, run 3 | 2 | 2 | 2 | 2 | 8 | Same comparison as run 1; flags the slow-log redaction and recommends `SLOWLOG GET` |
| Without skill, run 1 | 2 | 1 | 2 | 2 | 7 | Found the slow log; did not test the saturation lookalike; relied on test-environment clues |
| Without skill, run 2 | 0 | 0 | 1 | 0 | 1 | **Missed the cause.** Did not read the slow log; attributed the spikes to 5-minute `NetworkBytesIn` bumps |
| Without skill, run 3 | 2 | 1 | 2 | 2 | 7 | Found the slow log; incorrectly stated that latency metrics were flat |
| **Average** | | | | | **With 7.7 / Without 5.0** | |

The responses below are **run 3 from each space**: both reached the right answer, so the
comparison shows what the skill adds *beyond* the correct conclusion. The baseline's
failed run is quoted in the analysis.

### Response — with the skill (run 3)

> ## Root cause: a client polling with `KEYS` and `HGETALL` every ~30 seconds
>
> **Cluster:** `ec-test-cme`, Valkey 8.1.0, cluster-mode enabled, 2 shards, each `cache.m7g.large`. Created fresh at 09:45:40 UTC today.
>
> **What's happening:** A client at `<client IP>` is hitting both shard primaries directly every ~30–31 seconds, running:
> - **`KEYS`** — a full keyspace scan (O(N), blocks the single-threaded engine)
> - **`HGETALL`** — a large hash read (also O(N))
>
> Valkey's command engine is single-threaded per node, so each of these calls blocks that node's main thread for ~17.5–19 ms. Since it fires on both primaries in lock-step every 30s, you see a periodic spike on the whole cluster — matching exactly what you reported.
>
> **Evidence:**
> - Slow log shows **174 entries** in the 10:00–11:32 window — 100% of them are `KEYS` or `HGETALL`, no other command appears at all.
> - First occurrence: **11:02:52 UTC** (10s after your reported onset), then every 30–31s continuously through at least 11:19:43.
> - `KeyBasedCmdsLatency` sits at a sustained ~17,400–17,900 µs from 11:03 onward, while `GetTypeCmdsLatency` (~1.2 µs) and `SetTypeCmdsLatency` (<1 µs) stay negligible — one command family is the outlier, classic signature of an expensive O(N) command, not general engine saturation.
> - Engine CPU on both primaries: only ~7.6% (replicas ~0.43%) — nowhere near saturation.
> - Evictions = 0, ErrorCount = 0, replication lag ≈ 0 — ruling out eviction, errors, and replication as causes.
>
> **Ruled out:** hot shard (both primaries identical load), engine saturation, memory pressure/eviction, replication lag/failover, and any recent parameter-group or replication-group config change.
>
> **Separate note:** there was an earlier, unrelated OOM episode from 10:08–10:53 UTC (memory hit 100% under `maxmemory-policy=noeviction`, causing write failures). That resolved before 11:02 and isn't connected to the spikes you're asking about — but worth revisiting that policy given this cluster already hit it once today.
>
> **Fix:**
> - Find and stop/throttle whatever's running at `<client IP>` — it's issuing `KEYS`/`HGETALL` every 30s against both primaries.
> - Replace `KEYS <pattern>` with `SCAN` (non-blocking, cursor-based).
> - If `HGETALL` is reading a large hash, switch to `HSCAN` or split the hash into smaller keys.
> - If this is a health-check or metrics script, point it at `INFO`/CloudWatch instead of scanning the keyspace directly.
>
> One gap: CloudWatch slow logs redact the actual key/pattern arguments, so I can't give you the literal `KEYS` pattern or hash name from here — pulling `SLOWLOG GET` directly from the primaries, or checking the client code at `<client IP>`, would nail that down.

### Response — without the skill (run 3)

> Found it — and the two angles corroborate each other nicely.
>
> **Root cause: periodic blocking `KEYS` scans from a client, not an infrastructure issue**
>
> ec-test-cme is a brand-new test cluster (Valkey 8.1, cluster mode enabled, 2 shards × primary+replica, created 09:38 UTC today). Nothing changed on the cluster itself — no scaling, parameter group edits, failovers, reboots, or snapshot activity in CloudTrail. The maintenance and snapshot windows aren't in play either (backups are disabled, maintenance window is Wednesday-only).
>
> What's actually happening, pulled straight from the slow-log (`/ec-test/slow-log`):
>
> - Starting at **11:02:52 UTC**, a client at **&lt;client IP&gt;** opened persistent connections directly to both shard primaries and began issuing **`KEYS` + `HGETALL`** on an almost exact **~31-second cadence** — still running as of this check.
> - Each `KEYS` call takes ~17–19ms. Valkey processes commands single-threaded per shard, and `KEYS` is an O(N) full-keyspace scan over the ~500K keys on each shard — so every ~31 seconds, that shard's event loop stalls for ~18ms and queues up every other request behind it. That's your periodic spike.
> - This also explains two secondary symptoms: the CPU floor jumping from ~0.45% to a sustained ~7–7.6% at 11:02 (repeated full scans are CPU-expensive), and the step up in connection count on both primaries (the scanning client's persistent sockets).
> - Ruled out: evictions are 0, swap is 0, replication lag is negligible — it's not a memory or replica-health problem. The per-minute CloudWatch latency metrics look flat because the spikes are sub-minute and get averaged away; only the slow-log exposes them.
>
> **Likely source:** At **11:02:18 UTC** — seconds before the pattern started — someone logged into a purpose-built load-generator EC2 instance (`ec-test-loadgen`, i-0123456789abcdef0) via EC2 Instance Connect. That instance was launched 09:41 UTC specifically for this test and was network-permitted to reach the cache cluster on port 6379. The timing lines up almost exactly with the spike onset, and no other session or change in the window is a candidate. It's very likely &lt;client IP&gt; is that instance's private IP and a manual benchmark/test script using `KEYS` was kicked off at login.
>
> **Fix:** Replace `KEYS` with cursor-based `SCAN` (and avoid `HGETALL` on large hashes) in whatever script is running on `ec-test-loadgen`, or point it at a read replica instead of the primaries if it's a recurring job.
>
> Want me to pull CPU/network metrics on `ec-test-loadgen` to confirm the traffic pattern lines up, or check if an SSM session (with logging) captured the actual command that was run?

### Differences

| Aspect | Without the skill | With the skill | Who did better |
|---|---|---|---|
| Found the cause | **2 of 3 runs.** Run 2 never read the slow log and blamed periodic `NetworkBytesIn` bumps: "a cron-like loop or topology/health-check poll cycling through shards" | **3 of 3 runs** | **Skill** |
| Ruling out engine saturation | Not tested. Run 3 claims "the per-minute CloudWatch latency metrics look flat … only the slow-log exposes them", which is wrong | Runs 1 and 3 compare per-family latency: `KeyBasedCmdsLatency` ~17,400 µs vs `GetTypeCmdsLatency` ~1.2 µs, "one command family is the outlier … not general engine saturation" | **Skill** |
| Where the evidence comes from | Test-environment clues: an EC2 Instance Connect login seconds before onset, the `ec-test-loadgen` tag, "test cluster" naming | Telemetry only: slow log, per-family latency, engine CPU per node | **Skill** (a real customer incident has none of those clues) |
| Key name / next step | Not addressed | Runs 2 and 3 note that delivered slow logs redact keys and recommend `SLOWLOG GET` | **Skill** |
| Remediation | `SCAN` instead of `KEYS`, avoid `HGETALL` | `SCAN`/`HSCAN`, split the hash, use `INFO`/CloudWatch for health checks | Similar |
| Factual errors | Run 3: latency metrics "look flat" | Run 2: earlier policy misstated; "bypassing the config endpoint" (cluster clients always connect to node endpoints) | Both had one |

### Why the skill made a difference here

1. **It made the right check routine.** The skill's symptom table sends periodic latency
   spikes to "expensive commands" and tells the agent to read the slow log and compare
   per-command latency. All three with-skill runs did both. Without it, the agent found the
   slow log in 2 of 3 runs. In the third it reasoned from aggregate network metrics and
   reached a wrong, plausible-sounding answer.
2. **It supplied the evidence that excludes the lookalike.** Comparing one command family's
   latency with the others is what separates "one expensive command" from "the engine is
   overloaded". The baseline never made that comparison, and one run asserted that the
   metrics showing it were flat.
3. **It knows an ElastiCache-specific limit.** Delivered slow logs redact key names. The
   skill turned that into a concrete gap and a next step (`SLOWLOG GET`) instead of
   leaving it unexplained.

### Caveats

- **Test-environment leakage.** The baseline leaned on clues a customer incident would not
  have (an SSH login seconds before the onset, resource names containing "test" and
  "loadgen"). This probably *flatters* the baseline. For the next scenarios the load
  generator stays logged in from before the fault, and its Name tag is changed to a neutral
  application name.
- **OTel path not exercised.** The trace confirms the skill loaded and the agent read both
  metric references, but it did not delegate the PromQL queries. It then stated, wrongly,
  that "OpenTelemetry/PromQL metrics … are not queryable from this environment". (In S1 the
  same path worked: only the OTel error metric gives the per-type breakdown it reported.)
  Classic per-family latency was enough here, but the skill's delegation instruction was too
  easy to skip.
- **Distractor.** Both agents noticed the earlier S1 episode on the same cluster. Each
  scenario now starts only after the previous one has been cleaned up for at least 15 minutes.

### What we changed

- **Skill:** OpenTelemetry delegation is now a required step, and the agent may only call
  OTel "unavailable" after the sub-agent's metadata call fails. Gotcha added: a
  cluster-aware client connects to node endpoints after discovery, so that is not a
  misconfiguration. Prior episodes outside the incident window
  may be mentioned only with verified facts.
- **Test design:** neutral Name tag on the load generator, and log in well before starting
  each fault.

---

## S4 — Expensive commands, attempt 2 (after the OpenTelemetry fix)

### Why a second attempt

The attempt 1 traces showed that the skill loaded but never ran the OpenTelemetry (PromQL)
queries. The skill is read by a **context-gathering sub-agent**, and an interim wording told
that agent the PromQL tools "belong to the metrics sub-agent, not to you", so it fell back
to classic metrics and reported OTel as "not queryable". The skill now tells whichever agent
reads it to load the `exploring-metrics` skill itself, which makes the PromQL tools
available, and to report OTel as unavailable only if the metadata call fails.

### What was run

- **One with-skill investigation**, to check the fix. Same title and description as
  attempt 1 (onset 11:02 UTC).
- **Retrospective:** the fault had been stopped at 11:52 UTC, so the agent investigated the
  same incident window after the fact, from stored metrics and logs.
- **Baseline:** not re-run; the comparison uses the attempt 1 baseline runs (same incident
  window, investigated while the fault was live).

**Trace:** the agent loaded `exploring-metrics`, read the skill's OTel reference and the
`cloudwatch-promql` reference, and `list_prometheus_metadata` returned `ec-test-cme` among
the groups emitting OpenTelemetry metrics. The OTel path is now reached.

### Score

| Run | Root cause | Lookalike | Evidence | Remediation | Total |
|---|---|---|---|---|---|
| With skill (after fix) | 2 | 2 | 2 | 2 | **8** |

### Response — with the skill (after the fix)

> ## Root cause: a client is hammering the cluster with `KEYS` and `HGETALL` scans every ~30 seconds
>
> **What's happening**
> Starting at **11:02:52 UTC** — matching your reported onset almost to the second — a single client at `<client IP>` (two long-lived connections) began polling cluster `ec-test-cme` roughly every 30 seconds with:
> - Full-keyspace `KEYS` scans against **both shards**
> - A full-hash `HGETALL` against a large hash on **shard 2**
>
> These are O(N) commands that block Valkey's single-threaded engine for **~17–19 ms each time** — that's the periodic spike you're seeing. It stopped as cleanly as it started: last occurrence was **11:52:54 UTC**, and traffic has been flat/zero since.
>
> **Why I'm confident it's this and not something else**
> - Slow log shows 297 matching entries, exactly ~30s apart, all from the same two connections
> - `KEYS`/`HGETALL` latency (~18ms) is ~15,000–20,000x higher than normal `GET`/`SET` (~1µs) — classic expensive-command signature, not general load
> - Engine CPU peaked at only ~7.6% (nowhere near saturation)
> - Both shards behaved identically — rules out hot-key/shard skew
> - Memory, evictions, replication health, and connection counts were all normal
> - No ElastiCache API changes or failover events around the onset — this was a data-plane client action, not an infra change
>
> **What's ruled out:** engine saturation, hot shard/key skew, memory pressure/evictions, OOM errors, connection exhaustion, replication lag/failover, and serverless throttling (this is node-based Valkey, not serverless anyway).
>
> **Fix**
> - Find whatever is running at `<client IP>` and stop/fix it — replace `KEYS *` with cursor-based `SCAN`, and swap `HGETALL` on the large hash for `HSCAN` or targeted `HGET`/`HRANDFIELD`
> - If it's a health-check or monitoring job, dial back its frequency or move it off the hot path
> - Consider an ACL rule denying `KEYS` for that client role, and a CloudWatch alarm on slow-log volume so this pages you next time
>
> **One gap worth noting:** activity has been zero since 11:52:54 UTC. If you're still seeing spikes right now, that's not reflected in what I found — worth confirming whether this already resolved on its own or is still ongoing.

### Differences from attempt 1

| Aspect | Baseline (attempt 1) | With skill, attempt 1 | With skill, attempt 2 |
|---|---|---|---|
| Found the cause | 2 of 3 | 3 of 3 | 1 of 1 |
| Excludes engine saturation with a latency comparison | No | Yes (per-family classic metrics) | Yes: "~15,000–20,000x higher than normal `GET`/`SET`" |
| Error replies checked | No | No | Yes: "OOM errors" ruled out, which requires the per-type error metric |
| OpenTelemetry metrics | n/a | Not used; reported as "not queryable" | Metadata call succeeded; OTel path used |
| Evidence source | Partly test-environment clues (SSH login, resource names) | Telemetry | Telemetry only |
| Remediation | `SCAN` instead of `KEYS` | `SCAN`/`HSCAN`, split the hash | Same, plus an ACL denying `KEYS` and an alarm on slow-log volume |
| Incident still ongoing? | n/a | n/a | States the end time (11:52:54) and flags it as a gap to confirm |

### Why it matters

The fix turned the OpenTelemetry path back on, and the answer gets slightly broader
(error types are checked, so `OOM` is explicitly excluded) and keeps the elements that made
attempt 1 better than the baseline: the latency comparison that excludes saturation, and
evidence that comes only from telemetry. It also handled a **retrospective** investigation
well: it found where the incident ended and said so, instead of reporting it as ongoing.

### Caveats

- **One run**, so this checks the fix, not consistency. Consistency comes from attempt 1
  (3 of 3).
- **Different conditions from the baseline:** the baseline investigated the live incident,
  this run investigated it afterwards. Both used the same incident window.
- The trace confirms the PromQL metadata call; the individual `get_prometheus_metrics`
  queries were not inspected. The "OOM errors ruled out" finding indicates the error-type
  query ran.
- `KEYS *` in the fix is the agent's guess: the real pattern was `KEYS nomatch:*`, which
  the redacted slow log cannot show. The answer does not recommend `SLOWLOG GET` for the key
  name this time.

---

## S3 — Hot key on one shard

Skill revision: after the S4 OpenTelemetry fix.

### Scenario

- **Fault injected:** 8 processes reading one key (`hot:{1}`, slot 9842, owned by shard
  `0002`) in pipelines, plus ~5,700 background `GET`s per second spread over the whole
  keyspace. Started 13:19:58 UTC. In PromQL one primary's main-thread CPU was far above
  the other's.
- **Prompt (both spaces):** *Cache latency and CPU high* — "Since about 13:19 UTC p99 latency
  on ElastiCache cluster ec-test-cme in us-east-1 increased and CPU looks high. Find the
  root cause."
- **Expected root cause:** key-distribution skew (a hot key) on one shard. Evidence: one
  primary's throughput and engine CPU far above the other's; per-command latency normal.
  Fix: client-side caching or splitting the key; scaling up does not fix skew. Next step:
  an operator command to name the key (`CLUSTER SLOT-STATS` on Valkey 8).
- **Lookalike to rule out:** an undersized node (all shards loaded alike).

### Scores

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Notes |
|---|---|---|---|---|---|---|
| With skill, run 1 | 2 | 2 | 2 | 2 | 8 | Fix: key-schema redesign, "adding shards won't fix pure skew". Recommends `--hotkeys` (needs an LFU policy) and `MONITOR` on the primary |
| With skill, run 2 | 2 | 2 | 2 | 1 | 7 | No fix proposed; states ElastiCache exposes only average latency (percentiles are available) |
| With skill, run 3 | 2 | 2 | 2 | 2 | 8 | Fix: client-side TTL cache, split the key, "scaling the node vertically won't fix"; error types checked |
| Without skill, run 1 | 2 | 2 | 2 | 1 | 7 | Hot-shard pattern found; no fix, only "check the load generator's key-hashing config" |
| Without skill, run 2 | 2 | 2 | 2 | 1 | 7 | Also noticed network egress at 68% of the allowance; hedges between hot key and mis-routing client; no fix |
| Without skill, run 3 | 1 | 1 | 2 | 0 | 4 | Concluded "manual load/benchmark traffic … not a production incident" from an SSH login at 13:19:16; no fix |
| **Average** | | | | | **With 7.7 / Without 6.0** | |

Responses below: **with-skill run 3** and **without-skill run 1**, a typical good run from each
side.

### Response — with the skill (run 3)

> ## Root cause: hot shard from a GET traffic skew
>
> Since 13:19 UTC, `ec-test-cme`'s latency and CPU rise trace back to a key-distribution skew hitting one shard, not an engine-wide or resource problem.
>
> **What happened:**
> - Traffic ramped from 0 to steady-state between 13:19:00–13:25:00 UTC.
> - Shard `ec-test-cme-0002` (primary `ec-test-cme-0002-001`) absorbed **~151,500 cmd/s**, while sibling shard `ec-test-cme-0001` only carried **~2,850 cmd/s** — a **~53x** imbalance.
> - CPU on the hot primary sat at **~27%** vs **~4.25%** on the quiet primary — replicas stayed idle (~0.43%) the whole time, meaning clients are routing all reads to primaries.
> - The dominant command is plain `GET` at sub-microsecond average latency — so it's not an expensive command, it's sheer volume queuing on one node's single engine thread.
>
> **Ruled out:** memory pressure (flat ~2.3–2.5%), evictions (0), OOM/MOVED/CROSSSLOT/CLUSTERDOWN errors (0), connection storms (stable 17–18 clients), replication lag/failover (link healthy throughout), and any parameter-group/config change or ElastiCache/CloudTrail event near 13:19 — the CloudTrail and events history is clean for that window.
>
> **Fix:**
> - *Now*: find the hot key(s) hammering shard `0002` — a quick `CLUSTER COUNTKEYSINSLOT` / `--bigkeys` or a brief `MONITOR` sample against `ec-test-cme-0002-001` will name it. If it's one hot key, front it with a short client-side TTL cache.
> - *Durably*: if the access pattern is just skewed, redesign the key/hash-tag scheme to spread load across slots, or split the hot key. Scaling the node vertically won't fix a distribution problem.
>
> One gap worth flagging: I couldn't get a true p99 directly from the metrics store (it only exposes averages, not a histogram) — running `LATENCY HISTORY`/`SLOWLOG GET` on `ec-test-cme-0002-001` would give you the percentile detail if you need it for a postmortem.

### Response — without the skill (run 1)

> Found it. Here's what happened to `ec-test-cme`:
>
> **Root cause: a sudden, heavily skewed read-traffic surge (likely a benchmark/load-test client) hit the cluster at 13:19–13:20 UTC — not an AWS infrastructure issue.**
>
> **The cluster:** 2-shard, cluster-mode-enabled Valkey replication group on `cache.m7g.large` nodes, created just ~3.5 hours before the incident (09:38 UTC) — looks like a test cluster.
>
> **What changed at 13:20 UTC**, after being completely idle (zero commands, ~0.45% CPU, 4-5 connections) since at least 12:00:
> - **Shard 2 primary** (`ec-test-cme-0002-001`): CPU jumped **0.45% → 27.3%** (~60x), GETs went from 0 → **~9.1M/min**, network out hit **~4.8 GB/min**
> - **Shard 1 primary** (`ec-test-cme-0001-001`): CPU jumped 0.45% → 4.25%, GETs → ~171K/min — much smaller effect
> - Both primaries picked up 13 new persistent connections simultaneously — consistent with one cluster-aware client opening connections to every shard at once
> - Replicas on both shards stayed completely idle — this rules out a failover
> - Writes stayed at ~0, item count was flat at ~500K keys, cache hit rate 100% — this is pure read load against a pre-loaded dataset, not a data load job
>
> **Why shard 2 took the brunt:** both shards are identical hardware, so the ~60x CPU disparity points to non-uniform key distribution in the traffic — the generator is disproportionately hitting keys that hash into shard 2's slot range (8192–16383). Classic hot-shard pattern in a cluster-mode deployment.
>
> **Ruled out:** I checked CloudTrail for the cluster and found nothing — no parameter group changes, scaling, reboots, or failovers. No CloudWatch alarms are even configured on this resource. Memory/eviction metrics stayed flat throughout, so it's not memory pressure either.
>
> A couple of things worth checking next if you want to dig further:
> - VPC Flow Logs on the shard-2 primary's ENI to identify the source IP/service generating this traffic (ElastiCache data-plane commands don't show in CloudTrail)
> - The load generator's key-hashing/distribution config, since the 60x shard skew suggests it isn't spreading keys evenly across slots

### Differences

| Aspect | Without the skill | With the skill | Who did better |
|---|---|---|---|
| Hot shard identified | 3 of 3 runs see the skew; run 3 then concludes "test traffic, not a production incident" | 3 of 3, every run names key-distribution skew | **Skill** (consistency of the conclusion) |
| Fix | None in any run: "check the load generator's key-hashing config", flow logs, slow log | Runs 1 and 3: client-side TTL cache, split the key, redesign hash tags; "scaling the node vertically won't fix a distribution problem" | **Skill** |
| Other causes excluded | Memory, failover, config changes | Also expensive commands (per-command `GET` latency sub-µs) and engine error types (`OOM`/`MOVED`/`CROSSSLOT`/`CLUSTERDOWN` = 0) from the OpenTelemetry metrics | **Skill** |
| Extra insight | Run 2: network egress at 68% of the node's baseline allowance | Not mentioned | Without |
| How to name the hot key | Not addressed | Addressed, but with weak tools: `MONITOR` on a primary, `--hotkeys` (needs an LFU policy), `--bigkeys` (finds big keys, not hot ones). None used `CLUSTER SLOT-STATS`, the right tool on Valkey 8.1 | Skill, with errors |
| Factual errors | — | Runs 2 and 3: "only exposes averages" (the classic latency metrics support percentile statistics) | Without |
| Test-environment clues | Run 3 built its conclusion on an EC2 Instance Connect login 40 s before the onset | Not used | **Skill** |

### Why the skill made a partial difference

1. **The diagnosis itself is easy for both.** A 53x throughput gap between two shards is
   visible in standard per-node metrics, and the base model knows what a hot shard is.
2. **The skill adds the operational half.** It turns "one shard is hot" into "this is skew,
   scaling up will not fix it, cache or split the key". The baseline never proposed a fix.
   It also excludes the other candidate causes with ElastiCache-specific evidence
   (per-command latency, error types) instead of leaving them open.
3. **The skill's operator commands were the weak point.** The right commands are in
   `references/engine-followups.md`, but the agent did not read that file and improvised,
   recommending `MONITOR` on a primary, which the reference forbids.

### Caveats

- **Test-environment leakage again:** the load generator session was reconnected just
  before the fault, and one baseline run used that login as its main evidence.
- The prompt mentions p99 latency, but the injected fault mainly raised CPU and throughput;
  neither side could show a p99 change, and two with-skill runs wrongly said percentiles are
  unavailable.

### What we changed

- **Skill:** the hot-shard row now carries the key-naming commands inline: `CLUSTER
  SLOT-STATS ORDERBY CPU-USEC` on Valkey 8+, `--hotkeys`/`OBJECT FREQ` only under LFU, never
  `MONITOR` on a primary. It also carries the fix (client-side cache, split the key). New
  gotcha: the classic latency metrics support percentile statistics (`p99` via
  `ExtendedStatistics`).
- **Test design:** keep the load-generator session open across scenarios; if it must be
  reopened, wait 15 minutes before starting a fault.

---

## S5 — Connection churn (attempt 1)

Skill revision: after the S3 changes.

### Scenario

- **Fault injected:** 32 threads each opening a new TLS connection to shard `0001`'s primary,
  sending one `PING` and closing, about 360 new connections per second. Started about
  14:15 UTC.
- **Important condition:** the S3 hot-key load on shard `0002` had run until about 14:03 UTC,
  so the hour before the onset contained a large, unrelated traffic pattern that then
  stopped.
- **Prompt (both spaces):** *Cache connection timeouts* — "Since about 14:15 UTC our application
  reports connection timeouts to ElastiCache cluster ec-test-cme in us-east-1, and the
  cluster CPU went up. Find the root cause."
- **Expected root cause:** no connection pooling (a new TLS connection per request). Evidence:
  new connections per second very high while current connections stay flat; no rejected
  connections. Fix: reuse connections through a pool.
- **Lookalike to rule out:** `maxclients` reached (connections near the limit, rejections > 0).

### Scores

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Notes |
|---|---|---|---|---|---|---|
| With skill, run 1 | 1 | 2 | 1 | 0 | 4 | Attributed the timeouts to a "cluster-wide traffic stop" (the end of S3) and the old hot-shard skew; churn only noted as a side effect; no pooling fix |
| With skill, run 2 | 2 | 2 | 2 | 2 | 8 | ~360 new connections/s that send only `CLIENT SETINFO`/`PING`/`AUTH`; 0 rejections vs the 65,000 limit; pooling fix; S3 burst correctly called unrelated |
| With skill, run 3 | 1 | 2 | 1 | 1 | 5 | Main cause "shard 2 connectivity cut off, never recovered" is wrong; churn identified on shard 1; pooling only as step 3 |
| Without skill, run 1 | 2 | 1 | 2 | 2 | 7 | New connection per request + TLS handshake cost; rejections not checked |
| Without skill, run 2 | 2 | 1 | 2 | 1 | 6 | Correct, but leaned on SSH sessions and the load generator's CPU; no explicit fix |
| Without skill, run 3 | 2 | 1 | 1 | 2 | 6 | Correct, suggests a connection pool; wrongly says shard 2 shows the same pattern |
| **Average** | | | | | **With 5.7 / Without 6.3** | |

Responses below are the **median run of each side**: with-skill run 3 and without-skill run 3.

### Response — with the skill (run 3)

> ## Root cause: client connectivity to shard 2 cut off around 14:02–14:07 UTC, never recovered
>
> **What happened to `ec-test-cme`:**
>
> - Both shards' command traffic dropped to **zero around 14:02–14:07 UTC** — earlier than the 14:15 UTC you reported, which lines up with typical alert/timeout-threshold lag.
> - **Shard 1** (primary `ec-test-cme-0001-001`, us-east-1a) came back at **14:17 UTC**, but its clients reconnected in a churn storm — ~360 new connections/sec instead of resuming pooled connections. That's what drove its CPU from a ~4% baseline up to **~37-38%**. This is the "CPU went up" symptom you saw.
> - **Shard 2** (primary `ec-test-cme-0002-001`, us-east-1d) **never came back** through 14:49 UTC. This matters a lot because shard 2 normally carries ~98% of the cluster's traffic (a **53x hot-shard skew** vs shard 1 at baseline) — so it's almost certainly the main source of your app's timeouts.
> - Despite the outage, neither shard's replication link ever flagged unhealthy and no failover triggered — the engine's own health checks considered both primaries fine the whole time, which is why ElastiCache didn't fail shard 2 over automatically.
>
> **Ruled out:** memory pressure/evictions (flat ~2.3% of max), expensive O(N) commands (workload is GET-dominated), `maxclients` exhaustion (zero rejections, well under the 65,000 limit), true engine CPU saturation (shard 2's primary was actually near-idle, 0.44%, during its outage), and any customer-made config/security-group change (CloudTrail shows nothing relevant in the window).
>
> **Recommended next steps:**
> 1. Check the app's network path/DNS to the shard-2 node endpoint specifically (not just the cluster configuration endpoint) — a cluster-aware client with a stale cached topology would keep timing out even after the control plane reports healthy.
> 2. Run `CLUSTER SLOT-STATS ORDERBY CPU-USEC LIMIT 10` against shard 2 to pin down the specific hot key/slot behind the 53x skew.
> 3. Have the application use persistent/pooled connections rather than per-request connects — that's what's driving the CPU spike on the recovered shard.
> 4. Check the AWS Health Dashboard for `us-east-1` / AZ `use1-az6` around 14:00-14:20 UTC — I couldn't rule out an underlying AZ-level network event from read-only ElastiCache/CloudTrail APIs alone.

### Response — without the skill (run 3)

> ## Root cause: client-side connection leak, not an AWS-side change
>
> **`ec-test-cme`** is a brand-new cluster (Valkey 8.1.0, cluster-mode enabled, 2 shards, `cache.m7g.large`, TLS required, created 09:38 UTC today — only ~4.5h old when this started).
>
> **What's happening:**
> - No AWS-side trigger at all — no failover/reboot events, no mutating CloudTrail calls (no parameter group edits, scaling, or reboots) in the hours before the incident.
> - Evictions = 0, memory flat, swap = 0, replication lag ≈ 0 → rules out hot keys, eviction storms, and memory pressure.
> - The CPU increase is isolated to the **primary nodes only** — replicas stayed flat at ~1.5–2% the whole time. That points at the write/connection path, not a general resource problem.
> - On shard 0001's primary, `NewConnections` jumped from a flat **0/min baseline to ~21,000/min (~350/sec) instantaneously at 14:16 UTC** and has stayed there continuously since — CPU jumped from ~5% to a steady ~21–22% (EngineCPU ~36–38%) at the same moment.
> - Shard 0002's primary shows the identical pattern starting slightly earlier, ~14:01–14:02 UTC.
> - Meanwhile `CacheHitRate` data stops reporting after 14:02 — connections are climbing but there's no proportional GET/SET activity, meaning these connections aren't being reused for real work.
>
> **Why this causes timeouts:** the cluster requires TLS in transit, so every new connection costs a full TCP+TLS handshake. Sustaining ~350+ new connections/sec per primary is CPU-expensive just from handshake crypto. As the primaries' CPU/accept capacity gets eaten by this churn, new connection attempts and commands start timing out — matching exactly what you're seeing.
>
> **Likely culprit:** a client application pointed at this new cluster that's creating a fresh connection per request instead of reusing a pool (e.g., default `redis-py`/`Jedis` client without `ConnectionPool` configured) — classic connection-leak pattern, and it lines up with the cluster being brand new today.
>
> **Next steps to confirm:**
> 1. Check the ElastiCache slow log (`/ec-test/slow-log`, already enabled) around 14:00–14:20 UTC to see if actual commands are slow or it's purely connection-setup cost.
> 2. Identify the calling service via its security group (&lt;cache-sg&gt;) or VPC Flow Logs to find who's opening ~350 conns/sec.
> 3. If `ec-test-cme` is a scenario/test cluster, confirm with the owning team whether this is an intentional connection-storm test rather than a real leak.

### Differences

| Aspect | Without the skill | With the skill | Who did better |
|---|---|---|---|
| Root cause | 3 of 3: new connection per request, TLS handshake cost | 1 of 3. Runs 1 and 3 made the end of the previous scenario's traffic the main cause ("cluster-wide traffic stop", "shard 2 never came back") | **Without** |
| Best single answer | Run 1 (7/8) | Run 2 (8/8): "~360 new connections/sec, each doing nothing but handshake commands (`CLIENT SETINFO`, `PING`, `AUTH`) — zero actual `GET`/`SET`" | Skill |
| `maxclients` lookalike | Not checked in any run | All 3 runs: "zero rejections, well under the 65,000 limit" | **Skill** |
| Fix | Connection pool (runs 1, 3) | Pooling in runs 2 and 3; run 1 proposes none for this incident | Without |
| Factual errors | Run 3: says shard 2 has "the identical pattern" | Runs 1 and 3: treat a client that stopped as an outage | Both |
| Test-environment clues | Run 2 leaned on SSH sessions and the load generator's CPU | Not used | Skill |

### Why the skill made it worse here

1. **It sent the agent to the loudest anomaly instead of the reported symptom.** The skill's
   investigation order starts with per-shard skew, and the hour before the onset held the
   S3 hot-shard load and its abrupt end. Two runs built their answer around that and treated
   the reported symptom (connection timeouts, CPU up) as secondary.
2. **Its baseline window was not clean.** The skill compares the incident with "a window of
   the same length before the onset", which here contained a different incident. It gave
   no rule for that case.
3. **The skill's real advantage still showed.** When it stayed on the symptom (run 2), it
   produced the strongest evidence of any run: the OpenTelemetry per-command breakdown
   showing only handshake commands, plus an explicit `maxclients` check that no baseline
   run made.

This is a real weakness, not only a test artifact. Production clusters often have unrelated
noise just before an incident.

### What we changed

- **Skill:** new rule to anchor on the reported symptom and onset. A change that *ended*
  before the onset (traffic stopping, a load going away) is not the cause of symptoms that
  start after it, and traffic that stops on all nodes with no errors and no events means the
  clients stopped, not an outage. If the window before the onset contains a different
  anomaly, the agent must say so and pick an earlier steady-state baseline. Connection
  symptoms now go straight to the connection checks before the skew checks.
- **Test design:** the gap between scenarios is now at least 60 minutes, so the agent's
  lookback window is quiet. A follow-up with-skill run on the same incident (same noisy
  history) checks the fix under the same conditions as this baseline.

---

## S5 — Connection churn, attempt 2 (same incident, after the symptom-anchoring fix)

Three with-skill investigations of the **same incident window** (onset 14:15 UTC, same noisy
history) after adding the "anchor on the reported symptom" rule. Baseline: attempt 1.

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Change vs attempt 1 |
|---|---|---|---|---|---|---|
| With skill, run 1 | 1 | 2 | 2 | 2 | 7 | Was 4. Names churn and TLS handshake cost as the CPU driver, recommends pooling, calls the hot-shard skew "unrelated". Still treats the 14:03 traffic stop as the start of this incident |
| With skill, run 2 | 2 | 2 | 2 | 2 | 8 | Same as attempt 1's best run: only `PING`/`CLIENT SETINFO`, zero data commands, 0 rejections, pooling fix; S3 burst "not connected to this issue" |
| With skill, run 3 | 1 | 2 | 1 | 1 | 5 | Unchanged: "Shard-0002 … never reconnected … almost certainly the source of the timeouts"; no pooling fix |
| **Average** | | | | | **6.7** (attempt 1: 5.7; baseline 6.3) | |

**What the fix changed.** All three runs now state that the problem is client-side and not a
cache failure, so the rule "traffic that stops everywhere with no errors means the clients
stopped" took effect. Two runs still link the traffic stop 12 minutes before the reported
onset to the incident. In a real incident that link is not unreasonable, so further tuning
against this particular history would risk overfitting the skill to a test artifact.

**Next:** a clean re-run (attempt 3), with at least 60 quiet minutes before the onset, for
both spaces. That measures the skill on the scenario itself rather than on its sensitivity
to the previous scenario.

---

## S1 — OOM under `noeviction`, attempt 2 (policy set 11 hours earlier)

Skill revision: current (OpenTelemetry loading, symptom anchoring, hot-shard fix, OOM row
covering "nothing evictable").

### What changed from attempt 1

- `maxmemory-policy=noeviction` had been in place since 10:07 UTC, so no parameter-change
  event sits at the onset.
- The data was wiped, then the same writer (10 KB keys, no TTL, 8 workers) filled the
  cluster. Memory reached 100% and every write was rejected from about 21:16 UTC
  (~18,000 rejected writes per second).
- **Prompt (both spaces):** *Session writes failing* — "Since about <onset> UTC today our
  application cannot write session data to ElastiCache cluster ec-test-cme in us-east-1.
  Find the root cause." The agents refer to a reported onset of about 21:30 UTC, roughly
  14 minutes after the real one; both spaces received the same text.
- **Expected root cause, lookalike, and fix:** as in attempt 1.

### Scores

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Notes |
|---|---|---|---|---|---|---|
| With skill, run 1 | 2 | 2 | 2 | 2 | 8 | Explains `allkeys-lru` is right because no key has a TTL; "the `noeviction` policy was already in place; the write burst just exposed it". Used classic `ErrorCount`; states OTel was "not available in this pass" |
| With skill, run 2 | 2 | 2 | 2 | 1 | 7 | Direct `OOM` rate (~18,000/s, 135M cumulative), evictions = 0. Offers to apply the change itself; mentions an SSH login as the likely trigger and other test-named clusters |
| With skill, run 3 | 2 | 2 | 2 | 2 | 8 | `SET` rate 26,092/s, memory 100% at 21:18, `OOM` ~18,400/s, "only `OOM` errors are present" (no routing or cluster errors). Slip: says `noeviction` was "not something changed today" |
| Without skill, run 1 | 2 | 2 | 2 | 1 | 7 | Right mechanism and evictions = 0; fix is only "switching `maxmemory-policy` off `noeviction`"; `OOM` inferred ("OOM-style error") |
| Without skill, run 2 | 2 | 2 | 2 | 1 | 7 | Right mechanism; conditional fix (`allkeys-lru`, or `volatile-lru` if keys have TTLs); offers to apply the change; `OOM` inferred |
| Without skill, run 3 | 2 | 1 | 1 | 1 | 5 | Builds a wrong story ("session payloads suddenly getting much larger") on an item count that fell after the test data was wiped; never cites evictions = 0; "fastest unblock" is `volatile-lru`, which frees nothing |
| **Average** | | | | | **With 7.7 / Without 6.3** | |

Responses below: **with-skill run 3** and **without-skill run 2**.

### Response — with the skill (run 3)

> ## Root Cause: Out-of-memory (`OOM`) write rejections due to `noeviction` policy
>
> **Cluster**: `ec-test-cme` (Valkey 8.1.0, cluster-mode-enabled, 2 shards, Multi-AZ) in us-east-1
>
> **What happened:**
> 1. **21:17 UTC** — `SET` command rate spiked from ~0/s to **26,092 calls/s** (a burst of session writes) across both shards
> 2. **21:18 UTC** — Memory usage hit **100% of maxmemory** on *every node* (both shards, primaries and replicas) — up from a steady ~2.25% baseline
> 3. The cluster's parameter group (`ec-test-cme`) has **`maxmemory-policy = noeviction`** — so instead of evicting old keys to make room, Valkey started **rejecting all writes with OOM errors**
> 4. **`OOM` errors** ramped from 0 to ~18,300–18,500/s by 21:20Z and have stayed elevated through now (22:48Z) — this is the ongoing failure you're seeing. Eviction count stayed at **zero the entire time**, confirming nothing is being freed.
>
> **Ruled out:**
> - No failover, maintenance, or node replacement events
> - No config/API changes around the incident window (CloudTrail shows zero mutating calls on the cluster) — the `noeviction` policy is pre-existing, not something changed today
> - No hot shard — both shards show symmetric memory/CPU behavior
> - No slow queries — the slow log is empty, so this isn't a performance issue
> - No connection limit or routing (`MOVED`/`CROSSSLOT`) errors — only `OOM` errors are present
>
> **Fix:**
> - **Immediate**: free up memory so writes can succeed again — either manually clear/expire stale session keys, or switch `maxmemory-policy` to `volatile-lru` (if session keys have TTLs) or `allkeys-lru` (if not). This is an immediate, no-reboot parameter change.
> - **Durable**: set an eviction policy appropriate for session data going forward, ensure TTLs are enforced on session keys, and consider scaling the cluster if the working set genuinely exceeds the current ~5.14 GB/node capacity. Worth alarming on memory usage >90% and OOM error count going forward.
>
> One gap: I couldn't see what triggered the 21:17Z write burst itself (traffic spike, bulk session-warming job, or a redundant-write bug) since the slow log is empty and key names are redacted — correlating your application logs around 21:15–21:17Z would help pin that down.

### Response — without the skill (run 2)

> ## Root cause found: memory exhaustion + `noeviction` policy
>
> Your writes are being rejected by the engine because **`ec-test-cme` hit 100% memory usage and its parameter group is set to `noeviction`** — once a Redis/Valkey-compatible cache is full under that policy, it rejects all writes instead of evicting old keys to make room. Reads still work, which matches what you're likely seeing.
>
> **The timeline:**
> - **~21:15 UTC** — `DatabaseMemoryUsagePercentage` jumped from ~2.3% to **100%** in a single 5-minute window, and `BytesUsedForCache` spiked from ~116 MB to **~5.14 GB** almost instantly. `NetworkBytesOut` jumped ~90x at the same time.
> - **Evictions stayed at 0** the entire time — this is the smoking gun. If eviction were configured, memory pressure would just drop old keys and writes would keep succeeding. Instead, nothing got evicted, so once memory was full, writes started failing.
> - **~21:30 UTC** — matches your reported start of write failures, roughly 15 minutes after the memory spike (likely the lag before full saturation / your alerting caught it).
>
> **What's ruled out:**
> - No CloudTrail-recorded config changes — no security group, parameter group, subnet, VPC, or ElastiCache modification happened in this window.
> - No failover, node replacement, or ElastiCache service events.
> - Security groups are correctly scoped (cache SG only allows the app's SG on 6379) and unchanged — not a network issue.
> - No pending modifications; cluster is `available` and parameters are in-sync.
> - TLS/encryption settings (transit encryption required) are unchanged from cluster creation — not the trigger, since writes worked fine before 21:30.
>
> So the proximate cause looks application-side: something caused a sudden burst of ~5GB of writes to this cache in under 5 minutes — most likely missing TTLs on session keys, a bulk write, or a runaway write loop — and the `noeviction` policy turned that into a hard write-rejection once memory filled up.
>
> One more data point worth noting: there was a pattern of repeated manual console logins and SSH sessions into `checkout-api-1` (the app instance) around 20:55–22:25 UTC by a user. Any change made directly on that box (app config, local settings) wouldn't show up in CloudTrail, so it's worth asking that person what they were doing.
>
> **To actually fix the write failures right now**, you'd want to either change the `maxmemory-policy` to something like `allkeys-lru` (or `volatile-lru` if your session keys have TTLs), or scale up the cluster for headroom. I can make that parameter group change if you'd like — just confirm you want me to proceed and I'll request approval for it.

### Differences

| Aspect | Without the skill | With the skill | Who did better |
|---|---|---|---|
| Root cause | 3 of 3: `noeviction` + full memory. Run 3 adds a wrong trigger story (larger payloads) | 3 of 3, with the correct trigger (a write burst against an already-set policy) | Skill, slightly |
| Evidence that writes fail with `OOM` | Inferred in every run ("OOM-style", "almost certainly") | Observed in runs 2 and 3: ~18,000–18,400 `OOM` replies per second | **Skill** |
| Other errors excluded | Not examined | Run 3: "only `OOM` errors are present" (no `MOVED`/`CROSSSLOT`) | **Skill** |
| Evictions = 0 stated | Runs 1 and 2; **not** run 3 | All three | Skill |
| Fix | Run 1: no policy named. Run 2: conditional and correct. Run 3: `volatile-lru` "with TTLs" as the fastest unblock, which frees nothing | Run 1 names `allkeys-lru` and explains why `volatile-*` cannot work; run 3 conditional | **Skill** |
| Offers to apply the change | Runs 1, 2, 3 | Run 2 | Both (agent default?) |
| Test-environment clues | Run 2 and 3 point at the SSH sessions | Run 2 uses the SSH session as the likely trigger | Both |
| Factual slips | Run 3 (payload story) | Run 3 ("not changed today") | Without, more serious |

### Why the skill made a difference this time

1. **Without a change event at the onset, the metrics decide.** Attempt 1 was a tie because both
   sides read the same parameter-change event. Here the only way to see the failure itself is
   in the telemetry, and the skill's OpenTelemetry error-type query gives it: a direct,
   per-second `OOM` count, and a check that nothing else is failing.
2. **It encodes the TTL subtlety.** The earlier failure was recommending `volatile-lru` when no
   key has a TTL. Run 1 now states exactly that. The baseline's weakest run repeats the
   mistake.
3. **It keeps the answer anchored.** The baseline's run 3 builds an explanation from the wrong
   evidence; the skill's rules to quote evictions and the policy value kept all three
   with-skill runs on the mechanism.

### Caveats

- **OpenTelemetry was skipped in run 1**, despite the rule that forbids calling it
  unavailable. Whether the PromQL tools were missing or never loaded has to be read from that
  trace.
- **The offer to apply a change** appears in both spaces, including after the skill says not
  to. It looks like a default of the agent's closing message rather than something the
  skill controls; it is an open question for the DevOps Agent team.
- **Test-environment clues remain:** repeated EC2 Instance Connect logins and other test-named
  replication groups in the account were picked up by 3 of 6 runs, though not as the main
  evidence.
- The prompt used an onset about 14 minutes after the real one, in both spaces.

---

## S5 — Connection churn, attempt 3 (clean history)

Skill revision: after S1 attempt 2 (symptom anchoring, OpenTelemetry loading).

### What changed from attempts 1 and 2

- The cluster had been idle overnight, so the hour before the onset held no other scenario.
- Same fault: about 350 new TLS connections per second to shard `0001`'s primary, each sending
  the client handshake and one `PING`, then closing. Started about 09:19 UTC.
- Same prompt, with the new onset.
- **New test-environment clue:** the load-generator instance was started at 08:38 UTC (it had
  been stopped overnight), which CloudTrail records as `StartInstances`.

### Scores

| Run | Root cause | Lookalike | Evidence | Remediation | Total | Notes |
|---|---|---|---|---|---|---|
| With skill, run 1 | 2 | 2 | 1 | 2 | 7 | Churn on one node, `CLIENT SETINFO` at 669/s, 0 rejections vs the 65,000 limit, pooling fix. States the new-connection rate as 27–35/s (it was ~350/s) |
| With skill, run 2 | 2 | 2 | 2 | 2 | 8 | 335 new connections/s, `PING` and `CLIENT SETINFO` in lockstep with zero data commands, connected clients flat, 0 rejections, pooling fix |
| With skill, run 3 | 1 | 1 | 1 | 1 | 4 | Reads the handshake commands as coming from *existing* connections, says "no new connections opened", and lists connection churn as ruled out |
| Without skill, run 1 | 2 | 1 | 2 | 0 | 5 | `NewConnections` 11k–20k/min plus TLS handshake cost; `maxclients` not checked; no fix; leans on the instance start and the test-named clusters in the account |
| Without skill, run 2 | 2 | 1 | 2 | 1 | 6 | Churn; built around the instance start and the client host's CPU; fix only as "check pool size" |
| Without skill, run 3 | 1 | 1 | 2 | 1 | 5 | Churn mechanism, but attributed to a retry storm after "the app restart" (the instance start); no fix |
| **Average** | | | | | **With 6.3 / Without 5.3** | |

Responses below are the **median run of each side**: with-skill run 1 and without-skill run 2.

### Response — with the skill (run 1)

> ## Root cause found
>
> The timeouts and CPU spike trace to a **connection-churn storm hitting a single node** — `ec-test-cme-0001-001`, the primary of shard `ec-test-cme-0001`. The other three nodes (shard `ec-test-cme-0002` and the shard-1 replica) are completely unaffected.
>
> **What happened, starting ~09:19–09:21 UTC:**
> - New-connection rate on that one node jumped from a steady 4–5/s to **27–35/s**, with connected clients tracking almost 1:1 — meaning connections are being opened and dropped roughly every second (churn, not sustained use).
> - The command surge is almost entirely **`CLIENT SETINFO`** (the handshake command clients send on every new connection), peaking at 669 calls/s — not `GET`/`SET`/other data commands, which stayed flat at 0 the whole time.
> - Main-thread CPU on that node rose from ~0.44% baseline to a **peak of 34.4%**, still ~32% as of 09:41 UTC — so this is still ongoing.
> - This is pure connection-setup/TLS-handshake overhead, not application read/write load, a hot key, memory pressure, or a cluster-wide issue.
>
> **Ruled out:** maxclients limit (35 connections vs. a 65,000 limit, 0 rejected), whole-cluster saturation, data-driven hot key, memory/eviction pressure, failover or config change (no ElastiCache events or CloudTrail activity), and snapshot I/O (automatic backups are disabled despite the snapshot window overlapping).
>
> **Likely driver:** a client (or client library) connecting without pooling — since this replication group requires TLS, every un-pooled connection pays a full TLS handshake, and that cost is landing entirely on one node's connection-handshake path.
>
> **Suggested next steps:**
> - Run `CLIENT LIST` against `ec-test-cme-0001-001`, or check VPC Flow Logs for its ENI, to identify the source IP/application causing the churn.
> - Have that client reconnect through the cluster configuration endpoint with connection pooling/keep-alive enabled — this should drop the handshake overhead immediately.
> - This is still active as of the last check (09:41 UTC) — worth confirming current state before considering it resolved.

### Response — without the skill (run 2)

> ## Root cause: connection churn from `checkout-api-1`, concentrated on one cache node
>
> Here's the timeline:
>
> | Time (UTC) | Event |
> |---|---|
> | 08:38 | Operator (&lt;user&gt;) started EC2 instance `checkout-api-1` (i-0123456789abcdef0, `c7i.xlarge`) — it had been stopped |
> | 08:38–09:19 | Everything quiet on both the instance and the cache cluster |
> | **09:19–09:20** | `checkout-api-1` CPU jumps 0.3% → ~90%, NetworkOut jumps from ~13KB to ~160MB per 5 min |
> | **09:19–09:20** | ElastiCache node **`ec-test-cme-0001-001`** (only that one node): `NewConnections` jumps from 0/min to **17,000–20,000/min**, sustained through 09:47 |
> | 09:20 onward | That same node's CPU climbs to 18–20%, and **EngineCPUUtilization** (the Redis engine thread) climbs even higher, to 30–35% |
>
> **What's driving it:** The signature is connection churn, not load — `NewConnections` is enormous while `CurrConnections` stays tiny (27–36). Connections are being opened and immediately torn down rather than pooled/reused. Since this cluster enforces TLS, every new connection pays a handshake cost, which is why the engine CPU rose even more than overall node CPU on this `cache.m7g.large` (2 vCPU) node.
>
> Importantly, only one node (`0001-001`, the primary of shard 1) is affected — the replica and the other shard's two nodes show no change at all. That rules out general traffic growth and points to something hitting that single node directly rather than going through the cluster configuration endpoint.
>
> **Ruled out:**
> - Memory pressure/evictions — zero evictions, flat freeable memory
> - Config/scaling changes or failover — CloudTrail shows no `ModifyReplicationGroup`/`ModifyCacheCluster`/parameter changes, only read-only Describe calls
> - Other infra changes — no security-group, IAM, or pipeline changes in the window
>
> **Most likely explanation:** after `checkout-api-1` was restarted at 08:38, some process on it (connection-per-request pattern, a reconnect/retry loop, or a warm-up/load script — the `ec-test` naming hints this may be a test resource) started hammering the single node's endpoint with short-lived, unpooled TLS connections starting at 09:19, saturating that node's engine thread and causing timeouts for other legitimate clients competing for capacity.
>
> **To confirm definitively, I'd check:**
> 1. The actual process on `checkout-api-1` and its Redis/Valkey client config — pool size and whether it targets the node endpoint vs. the cluster config endpoint (&lt;configuration endpoint&gt;)
> 2. Whether a code deploy landed on checkout-api around 08:30–09:20 that changed connection handling
> 3. VPC Flow Logs between checkout-api-1 and the cache node to confirm the connection source/count directly

### Differences

| Aspect | Without the skill | With the skill | Who did better |
|---|---|---|---|
| Root cause | Churn in all 3 runs; run 3 frames it as a retry storm after a restart | Churn in runs 1 and 2; run 3 reads it backwards ("no new connections opened") | Tie |
| Where the explanation comes from | All 3 runs build it on the instance start at 08:38 and test-named resources in the account | Cache telemetry only: per-command handshake calls, new connections, CPU per node | **Skill** |
| `maxclients` lookalike | Not checked in any run | Checked in all 3 ("35 connections vs. a 65,000 limit, 0 rejected") | **Skill** |
| Fix | None stated in runs 1 and 3; "check pool size" in run 2 | Connection pooling / keep-alive in runs 1 and 2 | **Skill** |
| What the connections send | Not examined | `CLIENT SETINFO`/`PING` with zero data commands (runs 1–3, from OpenTelemetry per-command metrics) | **Skill** |
| Factual errors | Run 3 attributes the churn to the instance start 40 minutes earlier | Run 1 states the wrong new-connection rate; run 3 rules out churn | Without, slightly |

### Why the skill made a modest difference

1. **It kept the diagnosis on the cache.** Every baseline run built its story around a
   CloudTrail event that only exists in this test setup (an instance start 40 minutes before
   the onset). In a real incident that clue would not exist, and the baseline's evidence would
   be thinner. The with-skill runs did not use it.
2. **It closes the investigation.** The skill requires the lookalike check and a remediation,
   and the with-skill runs have both. The baseline described the symptom accurately but left
   the operator without a fix.
3. **It adds evidence the baseline does not reach.** The OpenTelemetry per-command metrics
   show that the extra traffic is only connection handshakes. That is the strongest proof
   of churn, and no baseline run had it.
4. **Its gap: reading that evidence.** One run took the handshake commands as traffic on
   existing connections, and another took the current-connections count for the rate of new
   connections. The skill did not explain that short-lived connections leave the
   current-connections count flat.

### What we changed

- **Skill:** the churn row and a new gotcha explain that a high rate of `HELLO`/`CLIENT
  SETINFO`/`AUTH`/`PING` with no data commands is what each new connection sends; that
  current connections stay flat because each connection lives only milliseconds; and that
  the churn rate is `NewConnections` per second (OTel: `rate(valkey.connections.received)`),
  not the current-connections count.

### Caveats

- **Test-environment leakage:** the instance start at 08:38 is an artifact of stopping the
  load generator overnight. It probably shaped every baseline run.
- **Overall for S5:** across three attempts the skill went from worse (attempt 1, noisy
  history) to modestly better (attempt 3). The best single answer in every attempt came from
  the skill.
