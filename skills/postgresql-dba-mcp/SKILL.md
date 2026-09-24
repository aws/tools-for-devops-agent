---
name: postgresql-dba-mcp
description: "Provides read-only diagnostic guidance for Amazon RDS for PostgreSQL and Aurora PostgreSQL through the postgresql-dba-mcp server's 10 tools and 55 predefined queries. Use for health checks, on-screen customer-shareable reports, shared_buffers and memory sizing, parameter tuning, vacuum and transaction ID analysis, index review, SQL plans, query fingerprints, replication, connections, and lock investigation. Health-check requests call MCP report_format=markdown and the complete validated report is presented on screen in the AWS DevOps Agent Output panel."
metadata:
  version: "1.18"
  author: "viveksingh112"
  aws-devops-agent-skills.technical-domains: rds,aurora,postgresql,database,performance,memory,shared_buffers,cache-sizing,parameter-tuning,vacuum,indexes,replication
---

# PostgreSQL DBA MCP diagnostic guidance

This skill interprets evidence returned by the PostgreSQL DBA MCP server. It is
not packaged by `template.yaml`; install or register it separately only through
an approved AWS DevOps Agent skill workflow.

## Safety and evidence rules

1. Keep investigations read-only. Do not execute remediation through these tools.
2. Do not present thresholds, control-plane heuristics, or a single metric as a
   diagnosis. Correlate database results, CloudWatch history, configuration,
   workload context, and recent changes.
3. Never recommend a production change without impact analysis, rollback,
   backups where applicable, an approved change window, and owner confirmation.
4. Do not recommend terminating sessions, dropping replication slots, dropping
   indexes, or changing parameter groups solely from one diagnostic result.
5. Prefer `pg_cancel_backend` over termination only after the application owner
   confirms the target and impact. Never interrupt autovacuum casually.
6. `VACUUM FULL` and non-concurrent index creation can take strong locks. Treat
   them as potentially disruptive and recommend safer evaluated alternatives,
   such as ordinary vacuum or `pg_repack`, only after compatibility review.
7. Treat RDS and Aurora as different platforms. Verify engine documentation and
   current parameter behavior before recommending configuration changes.
8. For upgrades, test on a restored snapshot or clone and use authoritative RDS
   pre-upgrade checks. MCP results are supporting evidence, not approval.
9. Do not expose secret values, usernames, endpoint details, full query text, or
   customer data beyond the approved audience. Statement-bearing activity and
   performance results may include only server-produced normalized query preview
   fields: maximum 240-character DML previews with comments, literals, and bind
   references replaced. Treat a withheld or unavailable preview literally, never
   reconstruct redacted values, and never request runtime bind values.
10. For Aurora, use DB cluster metadata for availability-zone/member evidence,
    storage encryption, deletion protection, backup retention, preferred backup
    window, storage type, and cluster parameter-group attachment. Never interpret
    DB instance `MultiAZ=False` as an Aurora availability failure or
    `DBInstance.AllocatedStorage` as current Aurora storage usage. If cluster
    metadata is unavailable, report `Not collected`; do not fall back to similarly
    named instance fields.
11. `pg_stat_statements.total_exec_time` is cumulative statement execution duration
    over the statistics window, not CPU utilization or measured processor time.
    Use query 6.9 for `stats_reset` evidence. Statement rankings exclude the current
    diagnostic role to reduce self-observation; if that role is reused by an
    application, its traffic is also omitted.
12. Describe execution precisely. After diagnostics, state: read-only diagnostic SQL
    and metadata calls were executed; no database or infrastructure change was made,
    and displayed remediation commands were not executed. For plan inspection, state:
    plan-only `EXPLAIN` was executed and the underlying `SELECT` was not executed.

### Current MCP report contract (MCP 1.14)

These requirements match the deployed 1.14 report and delivery behavior:

- The server exposes 55 predefined queries.
- Every health report represents all 26 canonical sections in order.
- A section with collected evidence renders raw evidence followed by at most one natural-language `Automated DBA Assessment`; internal priority and routine no-change values are not customer-visible.
- A collected zero-row section remains present as `No rows returned` and MUST NOT render an assessment. Error or unavailable evidence MAY retain a concise evidence-gap assessment.
- A separate `Evidence-Based Insight` paragraph MUST NOT appear because it duplicates the structured assessment.
- On-screen structured health output uses schema 1.2.
- Health section 11 is `Potential Duplicate Index Candidates`.
- Health section 23 is `Top 10 Statements by Total Execution Time`.
- Query 5.5 returns one table-level heuristic physical-bloat row per user table;
  it excludes system schemas and is not measured reclaimable space.
- Pre-upgrade checks use queries 10.1 through 10.12. Query 10.10 inventories only
  user-created ICU collations for manual review.
- Upgrade conclusions must surface exact `ValidUpgradeTarget` engine versions and
  exact-target instance-class orderability. Unknown or failed discovery remains
  unavailable, never assumed supported.
- Aurora upgrade storage evidence uses cluster `VolumeBytesUsed`; instance
  `FreeStorageSpace` and `AllocatedStorage` percentages are not applicable.
- Empty successful upgrade checks must not duplicate `No rows returned` tables.
- Database-local checks cover only explicitly connected databases; cluster-wide
  catalog evidence, including replication-slot inventory, must be labeled as such.
- `ANALYZE` is not read-only because it updates planner statistics.

## Required arguments

Health-check requests MUST use complete on-screen Markdown (`report_format="markdown"`)
and MUST pass the allowlisted `instance_id`. The five-query path MUST use explicit
`report_format="quick"`. There is no downloadable-file or HTML delivery; the complete
report is presented on screen in the AWS DevOps Agent Output panel.

Data-plane tools require an allowlisted endpoint and database:

```text
execute_health_query(
  category="<category>",
  query_id="<query-id>",
  instance_endpoint="<allowlisted-endpoint>",
  database="<allowlisted-database>"
)

run_full_health_check(
  instance_endpoint="<allowlisted-endpoint>",
  database="<allowlisted-database>",
  report_format="markdown",
  instance_id="<allowlisted-instance-id>",
  report_name="<approved-report-name>"
)

run_full_health_check(
  instance_endpoint="<allowlisted-endpoint>",
  database="<allowlisted-database>",
  report_format="quick"
)

run_full_health_check(
  instance_endpoint="<allowlisted-endpoint>",
  database="<allowlisted-database>",
  report_format="markdown",
  instance_id="<allowlisted-instance-id>",
  report_name="<approved-report-name>"
)

explain_query(
  query="<single-select-statement>",
  instance_endpoint="<allowlisted-endpoint>",
  database="<allowlisted-database>"
)
```

Control-plane tools use allowlisted RDS DB instance identifiers:

```text
get_instance_config(instance_id="<allowlisted-instance-id>")
get_instance_metrics(instance_id="<allowlisted-instance-id>", period_minutes=60)
get_log_files(instance_id="<allowlisted-instance-id>")
check_upgrade_readiness(instance_id="<allowlisted-instance-id>", target_major_version=17)
check_upgrade_readiness(
  instance_id="<allowlisted-instance-id>",
  target_major_version=17,
  report_format="markdown",
  instance_endpoint="<allowlisted-endpoint>",
  database="<allowlisted-database>",
  report_name="<approved-report-name>"
)
get_parameter_group(instance_id="<allowlisted-instance-id>", filter_modified=True)
get_parameter_group(instance_id="<allowlisted-instance-id>", filter_modified=False)
```

The server uses its configured secret automatically. Do not put credentials in
prompts and do not request a different secret ARN.

## Report-mode workflow

Reports are delivered **on screen only**. There is no downloadable file, HTML
artifact, S3 object, or URL, and the MCP never writes to S3 or returns a URL. A
request phrased as "downloadable", "HTML", "a file", or "a report link" is served
the same way as any report request: produce the complete on-screen report and
state plainly that it is provided on screen with no downloadable file.

### Report-mode routing

1. For a health-check request, call `run_full_health_check` with
   `report_format="markdown"`, the allowlisted instance ID, writer endpoint,
   database, and optional report label. The MCP validates and returns all 26
   canonical sections as one complete tool result. Present that complete result;
   MUST NOT gather diagnostics independently, invent values, summarize, drop
   sections or rows, or reconstruct a substitute report.
2. AWS DevOps Agent displays the complete Markdown in the tool's expandable
   **Output** panel and may add managed commentary or a summary in the primary
   chat. Treat the marker-bounded Output result as the authoritative report; do
   not claim that a custom skill controls the managed final-response format.
3. Use `report_format="quick"` only when the user explicitly asks for a quick,
   five-query, limited, or targeted health check. A short natural request is not
   quick intent.
4. For a generic health check, call `list_rds_instances()` when scope must be
   discovered. When exactly one matching allowlisted writer is unambiguous, use
   its allowlisted instance ID and writer endpoint, and use the requested or
   explicitly confirmed allowlisted database. If no allowlisted database is
   known, ask one concise database question; MUST NOT fall back to `postgres` or
   another database by convention. Let the MCP derive the Aurora cluster or RDS
   instance label unless the user supplied a custom report name. If multiple
   targets remain plausible, ask one concise target question. If no instance is
   allowlisted for diagnostics at all, state that no instance is available for
   diagnostics and stop.
5. For a pre-upgrade or upgrade-readiness request, use the Markdown readiness
   workflow (`check_upgrade_readiness` with `report_format="markdown"` and the
   explicit target major version). Ask one concise question only when the target
   major version or target instance is genuinely ambiguous.

Markdown mode validates every required section/check and footer inside the MCP
server before returning the complete report content, which is presented on screen
in the Output panel.

The visible **Key PostgreSQL Parameters** section MUST contain only these
reference-toolkit names, in this order: `max_connections`, `shared_buffers`,
`checkpoint_timeout`, `max_wal_size`, `default_statistics_target`, `work_mem`,
`maintenance_work_mem`, `random_page_cost`, `rds.logical_replication`,
`wal_keep_segments`, and `hot_standby_feedback`. A setting unavailable on the
selected engine/version MUST be labeled unavailable rather than replaced with
an unrelated parameter.

## Workflow 1: complete on-screen health check and explicit quick mode

Use this workflow for every generic or unqualified health-check request.

1. Discover and verify the allowlisted target when needed, then call
   `run_full_health_check` with `report_format="markdown"`, the matching
   `instance_id`, writer endpoint, database, and report label.
2. The MCP validates all 26 sections before returning the tool result. In AWS
   DevOps Agent, direct users to the expandable **Output** panel for the complete
   marker-bounded report. The managed primary chat may add a summary; that does
   not replace or invalidate the complete Output result.
3. If the user explicitly asks for a quick or five-query check, call
   `run_full_health_check` with `report_format="quick"` instead.
4. For a fresh rerun, invoke `run_full_health_check` again. If the managed chat
   deduplicates the request against prior context instead of calling the tool,
   tell the user to start a new chat for an independent snapshot.
5. For targeted follow-up, run the relevant predefined diagnostic again rather
   than answering from the three rows or six columns visible in an earlier
   bounded health-report section.
6. Keep observations separate from hypotheses and recommendations. Never execute
   a displayed remediation command.

A cache ratio, CPU percentage, or connection count is workload-dependent. Review
its trend and business impact instead of applying a universal threshold.

## Workflow 2: vacuum, dead tuples, and transaction ID age

For vacuum, dead-tuple, transaction-ID, index, SQL-plan, replication, connection,
lock, or pre-upgrade investigations, retrieve and follow the applicable procedure
from the reference artifact titled
`postgresql-dba-mcp: investigation-workflows` (source file
`references/investigation-workflows.md`). The safety, evidence, query-preview,
report-routing, and approval rules in this main file continue to apply.

## Workflow 3: configuration review

1. Call `get_instance_config` and identify RDS versus Aurora.
2. Call `get_parameter_group` with `filter_modified=True` to identify
   `AWS Source=user` values in the DB **instance** parameter group. `Source=system`
   formulas are not user overrides and are excluded from this view. This tool
   does not inspect an Aurora DB cluster parameter group.
3. `get_parameter_group(filter_modified=False)` shows all current values in the
   DB instance parameter group, including system formulas, but it does not
   recover an overwritten engine default or authorize sizing from those formulas. For Aurora, inspect the cluster parameter group and exact
   engine default separately through authorized AWS read-only APIs or current
   engine-family/version documentation. If that evidence is unavailable, report
   the cluster override and exact default as unknown and stop before prescribing
   a parameter reset, target value, or reboot.
4. Run query 2.1 for effective live settings. Keep PostgreSQL
   `pg_settings.source` separate from the AWS parameter `Source` field.
5. Correlate with CloudWatch and database workload evidence.
6. Verify recommendations against documentation for the exact engine family and
   version. Parameter defaults and semantics can change.

Memory settings are cumulative across sessions and operations. Do not calculate
risk from `work_mem * max_connections` alone; account for concurrency and plan
operators.

### `shared_buffers` deterministic workflow

This procedure is mandatory for every `shared_buffers`, shared buffers,
buffer-pool sizing, cache-sizing, PostgreSQL/Aurora memory-sizing, parameter-
tuning, or “how much memory” question. The output gates below are requirements,
not suggestions.

1. Call `list_rds_instances()` with no argument, then call
   `get_instance_config` for the selected allowlisted instance. Classify the
   platform only from the returned engine.
2. Start an evidence ledger with these exact fields. Copy tool gate values
   verbatim; do not fill gaps by inference:

```text
PLATFORM_GATE: <aurora-postgresql|postgres|UNKNOWN>
WRITER_ID: <allowlisted ID|UNKNOWN>
WRITER_ENDPOINT: <allowlisted endpoint|UNKNOWN>
LIVE_SETTING_PROVENANCE: POSTGRESQL_ONLY
CLUSTER_PROVENANCE_GATE: <tool value|UNKNOWN>
ENGINE_DEFAULT_GATE: <tool value|UNKNOWN>
CACHE_FIT_GATE: <tool value|OBSERVATION_ONLY>
MEMORY_SIZING_GATE: <tool value|INSUFFICIENT_EVIDENCE>
INDIRECT_MEMORY_DERIVATION_GATE: PROHIBITED
SHARED_BUFFERS_RECOMMENDED_POLICY: <USE_VERIFIED_AURORA_ENGINE_DEFAULT|VERIFY_ENGINE_DEFAULT_AND_WORKLOAD>
SHARED_BUFFERS_FINAL_GATE: <PASS|FAIL|NOT_APPLICABLE>
RECOMMENDED_SHARED_BUFFERS: <verified value|UNKNOWN>
```

   The final user-facing answer MUST reproduce every ledger field above as an
   individual line with the exact field name and value. A Markdown table MAY
   additionally present the same evidence, but table labels, section headings,
   or prose paraphrases do not replace these exact lines. The answer MUST NOT
   omit `SHARED_BUFFERS_RECOMMENDED_POLICY`. For Aurora, while provenance or
   default gates remain unresolved, the answer MUST contain both exact lines:

```text
SHARED_BUFFERS_RECOMMENDED_POLICY: USE_VERIFIED_AURORA_ENGINE_DEFAULT
RECOMMENDED_SHARED_BUFFERS: UNKNOWN
```

3. Query 2.1 reports effective live PostgreSQL settings. Its
   `pg_settings_source` and `pg_settings_context` fields are not AWS parameter-
   group provenance. Never use them to name an AWS parameter group or claim an
   AWS override.
4. When `CLUSTER_PROVENANCE_GATE` or `ENGINE_DEFAULT_GATE` is `UNKNOWN`, or
   `MEMORY_SIZING_GATE` is `INSUFFICIENT_EVIDENCE`, set
   `RECOMMENDED_SHARED_BUFFERS: UNKNOWN`. Do not supply a formula, percentage,
   page count, byte/GiB target, named override, reset action, or reboot action.
   Advertised instance RAM cannot close these gates.
   `INDIRECT_MEMORY_DERIVATION_GATE: PROHIBITED` means you MUST NOT back-solve
   `DBInstanceClassMemory`, an engine default, or a `shared_buffers` target from
   `effective_cache_size`, another live setting, a sibling formula, or arithmetic
   relationships between settings. You MUST NOT call those values a hint,
   suggestion, signal, indication, consistency check, likely formula,
   formula-derived default, likely source, or evidence of any `shared_buffers`
   value. Query 2.1 may return sibling live settings, but omit their numeric
   values from the user-facing `shared_buffers` analysis unless they establish a
   separate documented fact; never convert them to pages, bytes, MiB, or GiB for
   this analysis. This prohibition applies to observations, interpretation,
   conclusions, and next steps because suggestive wording is still an indirect
   inference even when followed by a disclaimer.
   For Aurora, set `SHARED_BUFFERS_RECOMMENDED_POLICY` to
   `USE_VERIFIED_AURORA_ENGINE_DEFAULT`. A perfect `BufferCacheHitRatio` does not
   weaken or change this policy. After separate authorized evidence verifies the
   exact cluster provenance and exact engine default, recommend using or
   restoring that verified default unless an approved workload-specific reason
   supports a custom value. Do not describe the default as a fixed percentage
   unless exact engine-version and instance-family evidence proves that value.

**Aurora PostgreSQL branch (`aurora-postgresql`)**

5. Select the single current instance whose role is `Writer`, even when the user
   supplied a reader or reader endpoint. Stop if there is not exactly one
   writer, its ID is not allowlisted, or its cluster writer endpoint is not
   allowlisted.
6. For that writer, call `get_instance_config`,
   `get_instance_metrics(instance_id=<writer>, period_minutes=60)`, and
   `get_parameter_group(instance_id=<writer>, filter_modified=True)`. Run query
   2.1 against the allowlisted cluster writer endpoint and database.
7. Include CloudWatch `BufferCacheHitRatio`; report `No data` or an error as
   unavailable. `CACHE_FIT_GATE: OBSERVATION_ONLY` remains unchanged even for a
   perfect ratio. You MUST NOT interpret `100%` as “all recent I/O was served
   from cache,” proof that the working set fits, proof that the current setting
   is correct, or permission to alter the recommended policy; state only the
   metric's reported value and the observation-only gate. FreeableMemory is only
   an availability/reclaimability observation: never call it wasted or unused
   and never use it to size `shared_buffers`.
8. After all other evidence, call
   `list_rds_instances(expected_writer_id="<writer-id>")`. The analysis is
   incomplete until this call returns `SHARED_BUFFERS_FINAL_GATE: PASS`.
   - On `FAIL`, discard the mixed evidence and restart once. Stop without a
     recommendation or reader question if the second final gate fails.
   - On `PASS`, perform a final output-contract check before responding:
     - Every evidence-ledger field appears as an exact individual line.
     - Aurora output contains
       `SHARED_BUFFERS_RECOMMENDED_POLICY: USE_VERIFIED_AURORA_ENGINE_DEFAULT`.
     - An unresolved numeric recommendation contains
       `RECOMMENDED_SHARED_BUFFERS: UNKNOWN` and no formula, percentage, page,
       byte, MiB, or GiB target.
     - No sibling setting is described as a hint, suggestion, signal,
       indication, consistency check, formula-derived default, likely source, or
       evidence for `shared_buffers`.
     - A perfect cache-hit ratio is described only as an observation and does
       not change the policy.
     If any check fails, revise the answer before returning it. Then copy the
     exact `REQUIRED_READER_QUESTION` emitted by the tool as the final line:
     **Would you like me to repeat the same analysis for the allowlisted Aurora
     readers?**
9. Do not analyze readers automatically. If the user approves, use each reader's
   allowlisted instance ID and individual instance endpoint. Never use the
   load-balanced cluster reader endpoint.

**RDS for PostgreSQL branch (`postgres`)**

5. Use the selected allowlisted standalone DB instance ID and its individual
   allowlisted endpoint. Aurora writer, cluster-endpoint, final-writer-gate, and
   reader-question requirements do not apply.
6. Call `get_instance_config`,
   `get_instance_metrics(instance_id=<instance>, period_minutes=60)`, and
   `get_parameter_group(instance_id=<instance>, filter_modified=True)`. Run query
   2.1 and query 6.3 against the connected allowlisted database.
7. Report query 6.3's current-database cache-hit ratio with
   `CACHE_FIT_GATE: OBSERVATION_ONLY`. Do not request Aurora CloudWatch
   `BufferCacheHitRatio` and do not ask the Aurora reader question.

#### Fail-closed interpretation rules

- A cache-hit ratio does not prove the active working set fits in
  `shared_buffers`, does not establish a target, and does not predict a specific
  future performance change.
- `effective_cache_size` is a planner assumption, not evidence of the correct
  buffer allocation.
- `get_parameter_group` inspects only the DB instance parameter group. For
  Aurora it cannot identify the attached cluster parameter group or prove a
  cluster-level source, override, default, or formula.
- Do not transfer memory behavior between Aurora and RDS PostgreSQL, between
  engine families, or between standard and Optimized Reads instance classes.
- Keep factual observations, `UNKNOWN` evidence, interpretation, and proposed
  changes in separate sections. A proposed change is prohibited while a required
  provenance, default, sizing, or final-writer gate is unresolved.

AWS reference:

- [Aurora Optimized Reads and `shared_buffers`](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.optimized.reads.html)

## Workflows 4-8: targeted investigations

For index, SQL-plan, replication, connection/lock, and pre-upgrade procedures,
retrieve and follow the reference artifact titled
`postgresql-dba-mcp: investigation-workflows` (source file
`references/investigation-workflows.md`). Do not pass a truncated
`normalized_query_preview` to `explain_query`, claim a fingerprint is reversible,
broaden database privileges for convenience, drop an index or replication slot
from one observation, terminate a session without owner and impact context, or
treat readiness evidence as upgrade approval.

## Reporting format

For every targeted investigation or explicitly requested Markdown
investigation, return:

1. **Scope** — approved account/Region, engine type/version, instance/database,
   and time window without exposing credentials.
2. **Evidence** — exact tools and query IDs used.
3. **Observations** — factual outputs and trends.
4. **Interpretation** — hypotheses with confidence and alternatives.
5. **Risk** — customer impact and urgency.
6. **Next read-only checks** — evidence still needed.
7. **Proposed changes** — only when requested, with approval, impact, rollback,
   and maintenance-window requirements.

For a health-check request, call
`run_full_health_check(report_format="markdown")`. The MCP validates and returns
all 26 sections as one marker-bounded tool result. In AWS DevOps Agent, direct
the user to the expandable **Output** panel for the authoritative complete
report; the managed primary chat may add its own summary. Do not claim that the
custom skill can force or suppress that managed final-response format. For a
pre-upgrade request, use the Markdown readiness workflow. Reports are on-screen
only; there is no downloadable-file or HTML delivery.
