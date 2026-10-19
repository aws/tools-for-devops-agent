---
name: glue-6-migration-review
description: >
  Analyze an existing AWS account for AWS Glue for Apache Spark jobs still
  running on a version earlier than Glue 6.0, and guide a migration to Glue 6.0.
  Uses read-only Glue control-plane, CloudWatch metrics, and Cost Explorer /
  pricing calls to (1) inventory every pre-6.0 Glue job with its version, worker
  configuration, and job details in a table, (2) produce a per-job cost summary
  and projected Glue 6.0 savings based on each job's historical run performance,
  and (3) generate a step-by-step migration guide covering version, Spark, Scala,
  and Python runtime changes, breaking changes, and a validation plan.

  Use when a user asks to find, inventory, assess, or plan a migration of AWS
  Glue jobs to Glue 6.0, estimate the cost impact of upgrading Glue jobs, or list
  Glue jobs on older versions. Triggers on phrasings like "migrate my Glue jobs
  to 6.0", "find Glue jobs on old versions", "which Glue jobs are on Glue 3.0 /
  4.0 / 5.0", "Glue 6.0 upgrade plan", "cost of moving Glue jobs to 6.0", "Glue
  version upgrade assessment", or "audit Glue job versions".

  Do NOT use for authoring Glue ETL scripts or job code from scratch, Glue Data
  Catalog / crawler design, Glue DataBrew, EMR or self-managed Spark clusters,
  Lambda (use the Lambda skill), or EC2 (use the EC2 skill).
metadata:
  author: awslokesh
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "AWS Glue, Amazon CloudWatch, AWS Cost Explorer"
  aws-devops-agent-skills.technical-domains: "Analytics, Data Integration, ETL"
---

# AWS Glue 6.0 Migration Review

Analyze an AWS account for AWS Glue for Apache Spark jobs running on a version
earlier than 6.0, and guide the migration to
[AWS Glue 6.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-60.html).
The review is read-only and produces three deliverables in order: a **legacy job
inventory table**, a **per-job cost summary** with projected Glue 6.0 savings,
and a **migration guide**.

## When to Use

Activate this skill when the user asks to:
- Find or inventory AWS Glue jobs running on versions earlier than 6.0
- Assess or plan a migration of Glue jobs to Glue 6.0
- Estimate the cost impact / savings of upgrading Glue jobs to 6.0
- Produce a Glue version-upgrade assessment or roadmap

Do **not** activate for:
- Authoring new Glue ETL scripts or job code from scratch
- Glue Data Catalog, crawler, or DataBrew design
- Amazon EMR or self-managed Apache Spark clusters
- AWS Lambda (use the `lambda-operational-review` skill) or EC2 (use the
  `ec2-operation-review` skill)

## Critical Warnings

- **This skill is read-only.** Every command is a `Get*`, `List*`, `Batch Get*`,
  or read-only CloudWatch / Cost Explorer call. The agent does NOT call
  `UpdateJob`, `StartJobRun`, `CreateJob`, `DeleteJob`, `UpdateDevEndpoint`, or
  any mutating API. All migration steps are recommendations for the operator to
  apply after review.
- **Do not run or start a job to reproduce behavior.** All performance and cost
  analysis comes from historical job-run metrics only.
- **Cost figures are estimates.** Projected Glue 6.0 costs are derived from the
  published Glue 6.0 pricing change and each job's historical DPU-hours, not from
  a billed invoice. Always label them as estimates and state the assumptions.
- **UNKNOWN ≠ current.** Any job whose version, worker type, or run history
  cannot be determined MUST be reported as `NOT_ASSESSED` with the reason, never
  silently assumed to be on 6.0 or excluded.

## Glue Version Baseline

Glue 6.0 is the target. Treat any Spark job on **Glue 0.9, 1.0, 2.0, 3.0, 4.0, or
5.0** as a migration candidate. See `references/version-feature-matrix.md` for
the Spark / Scala / Python runtime that each Glue version pins, deprecation
status, and the runtime jumps involved in moving to 6.0 (for example, Glue 6.0
moves to Apache Spark 4.1.1, Scala 2.13, and Python 3.13). Do not hardcode these
in the report — read them from the matrix so the skill stays current.

## Step 1: List Legacy Glue Jobs (Inventory Table)

Ask the user for scope (specific job names, a tag, "all jobs" in named regions,
or "all jobs in all regions"). If no scope is given, default to all configured
account regions. If a named job is not found, list the closest candidates and ask
before proceeding — do not silently substitute.

Per region (skip empty regions):

```
glue.ListJobs                          # job name inventory
glue.BatchGetJobs                      # per job: GlueVersion, WorkerType, NumberOfWorkers,
                                       #   MaxCapacity, Command (glueetl / gluestreaming / pythonshell),
                                       #   Timeout, MaxRetries, ExecutionClass (STANDARD/FLEX),
                                       #   DefaultArguments (e.g. --enable-auto-scaling), Connections
glue.GetTags                           # job tags (environment, owner, cost center)
glue.GetJobRuns                        # recent run history per job (for Steps 2 & 3)
```

Determine each job's `GlueVersion`. Include **only** jobs on a version earlier
than 6.0 (Spark `glueetl` / `gluestreaming` jobs; note Python-shell and Ray jobs
separately, since their upgrade path differs). Render an inventory table:

| Job Name | Region | Type | Glue Version | Worker Type | # Workers / Max Capacity | Auto Scaling | Execution Class | Last Run | Owner/Tag |
|---|---|---|---|---|---|---|---|---|---|

End Step 1 with a one-line count: number of legacy jobs found, grouped by Glue
version. If no legacy jobs are found, state that clearly and stop.

## Step 2: Cost Summary per Job (from Historical Performance)

For each legacy job, pull run history via `glue.GetJobRuns` (default: trailing 30
days, or a window the user specifies) and, where available, per-run metrics via
`cloudwatch.GetMetricData` (Namespace `Glue`, dimensions `JobName` /
`JobRunId` / `Type`). Optionally corroborate billed spend with
`ce.GetCostAndUsage` filtered to the Glue service and job tags.

Per job compute, from `GetJobRuns`:
- Run frequency and count over the window
- `ExecutionTime` (billed seconds) per run and the DPU-seconds
  (`DPUSeconds` when present, else derived from worker type × workers ×
  duration)
- Total **DPU-hours** over the window and the resulting current cost

Then project the Glue 6.0 cost using the model in `references/cost-model.md`
(which captures the Glue 6.0 per-DPU-hour pricing change and any expected
runtime/startup improvements). Present a per-job cost table:

| Job Name | Glue Version | Runs (window) | Avg Duration | Total DPU-hrs | Est. Current Cost | Est. Glue 6.0 Cost | Est. Savings | Notes |
|---|---|---|---|---|---|---|---|---|

Add a totals row. State the pricing assumptions, the region price used, and that
figures are estimates. Where run history is missing, mark the row `NOT_ASSESSED`
and explain (job never ran in the window, metrics disabled, etc.). Do not invent
run counts or durations.

## Step 3: Migration Guide

Produce an actionable, per-job (and shared) migration guide using
`references/migration-runbook.md`. Cover:

1. **Runtime jump** — the Spark, Scala, and Python version change from the job's
   current Glue version to 6.0 (read from the version-feature matrix), and what
   that implies for the job's code and dependencies.
2. **Breaking changes & code review** — Spark API removals/behavior changes,
   Python version changes (3.x jump), connector/format changes (e.g. Iceberg
   version), and any deprecated Glue features the job uses. Point at the AI-powered
   Spark Upgrades feature where it applies.
3. **Configuration changes** — `GlueVersion` update, worker-type re-evaluation,
   auto-scaling, and job-argument review.
4. **Validation plan** — clone the job to a non-production copy or use a
   dev/test version, run against representative data, compare output correctness
   and the run metrics captured in Step 2, then cut over.
5. **Rollback** — keep the prior job definition/version so the operator can
   revert if validation fails.

Order the guide by migration risk/effort (lowest-risk jobs first) and reference
each job's findings from Steps 1 and 2.

## Step 4: Generate the Report

Produce one report artifact for the reviewed scope, named
`glue-6-migration-<scope>-<YYYY-MM-DD>.md`, containing, in order:

1. **Summary** — account/region scope, count of legacy jobs by Glue version,
   total estimated current cost and total estimated Glue 6.0 savings for the
   window.
2. **Step 1 — Legacy job inventory table.**
3. **Step 2 — Per-job cost summary table** with totals and stated assumptions.
4. **Step 3 — Migration guide**, ordered by risk/effort, with per-job notes.
5. **Coverage note** — jobs assessed vs `NOT_ASSESSED` (missing version, run
   history, metrics, or permissions) and why.

## Prerequisites

Requires the DevOps Agent's primary cloud-source role to have read access to
Glue, CloudWatch, and (optionally) Cost Explorer and the tagging API. See the
README for the exact IAM action list. The skill never calls a mutating Glue API
and never starts a job run.
