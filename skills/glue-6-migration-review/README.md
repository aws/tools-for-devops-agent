# Glue 6.0 Migration Review — AWS DevOps Agent Skill

An AWS Glue version-migration assessment skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). It analyzes an existing AWS account for AWS Glue for Apache Spark jobs still running on a version earlier than **Glue 6.0** and guides the migration, aligned with [Migrating AWS Glue for Spark jobs to AWS Glue version 6.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-60.html). Generates a shareable report artifact for the reviewed scope.

> **Disclaimer:** This skill is provided as **sample code**, not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions, cost estimates, and migration steps against your organization's policies before relying on it.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to produce three deliverables, in order:

1. **Step 1 — Legacy job inventory table.** Discover Glue jobs in the configured account/regions, keep only Spark jobs on a version earlier than 6.0, and list each with its Glue version, worker configuration, auto-scaling, execution class, last run, and owner tag.
2. **Step 2 — Per-job cost summary.** From each job's historical run performance (`GetJobRuns`, CloudWatch, optional Cost Explorer), compute the trailing-window DPU-hours and estimated current cost, then project the estimated Glue 6.0 cost and savings using the published ~30% price reduction.
3. **Step 3 — Migration guide.** A per-job (and shared) step-by-step upgrade plan covering the Spark/Scala/Python runtime jump, breaking changes, configuration changes, a validation plan, and rollback — ordered by migration risk/effort.

A report artifact is generated for the scope, named `glue-6-migration-<scope>-<YYYY-MM-DD>.md`.

All data is gathered through native AWS APIs (`glue`, `cloudwatch`, `ce`). The skill operates entirely in **read-only** mode and never starts a job run or mutates a job.

## Agent Types

- **On-demand** — conversational invocation in Chat ("find my Glue jobs on old versions", "plan a Glue 6.0 migration").
- **Evaluation** — proactive modernization/cost-optimization recommendations.

Select **Generic** to make it available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

The Agent Space's IAM role must have read access to Glue, CloudWatch, and (optionally) Cost Explorer and the tagging API. The AWS managed read-only policy typically covers these — verify in your account before running the review:

- `glue:ListJobs`, `glue:GetJob`, `glue:GetJobs`, `glue:BatchGetJobs`
- `glue:GetJobRuns`, `glue:GetJobRun`
- `glue:GetTags`
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics`
- `ce:GetCostAndUsage` (optional — corroborate historical Glue spend)
- `tag:GetResources` (optional — tag-based scoping and cost allocation)

The skill operates entirely in **read-only** mode: it never calls `CreateJob`, `UpdateJob`, `DeleteJob`, `StartJobRun`, `UpdateDevEndpoint`, or any mutating API.

### 3. Job run history (for Step 2)

Cost estimation requires each job to have run history retrievable via `glue:GetJobRuns` within the analysis window (default trailing 30 days). Jobs with no runs in the window are reported as `NOT_ASSESSED` for cost.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

From the `skills/` directory in this repo:

```bash
cd skills
zip -r glue-6-migration-review.zip glue-6-migration-review/ -x 'glue-6-migration-review/evals/*'
```

Constraints (enforced at upload time):

- Total zip size ≤ **6 MB**.
- `SKILL.md` is required and must include `name` and `description` frontmatter.
- A `scripts/` directory is **not** allowed — uploads containing scripts are rejected.

`evals/` is excluded from the upload (it's only used for offline evaluation).

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Click **Add skill** → **Upload skill**.
3. Drag and drop `glue-6-migration-review.zip`.
4. Select agent types: **On-demand** and **Evaluation** (or leave **Generic**).
5. Review the validation results and click **Upload**.

## Usage

In the DevOps Agent Chat, use natural language:

- *"Find all Glue jobs on versions earlier than 6.0 in us-east-1."*
- *"Which of my Glue jobs are on Glue 3.0 or 4.0? Show me a table."*
- *"Estimate the cost of migrating my Glue jobs to 6.0 based on last month's runs."*
- *"Build a Glue 6.0 migration plan for my account."*

The agent collects data automatically and generates a report artifact for the scope, named `glue-6-migration-<scope>-<YYYY-MM-DD>.md`.

## Skill Contents

```
glue-6-migration-review/
├── SKILL.md                          # main skill instructions (with frontmatter)
├── README.md                         # this file
├── CHANGELOG.md
├── references/
│   ├── version-feature-matrix.md     # Glue version → Spark/Scala/Python runtime & migration status
│   ├── cost-model.md                 # DPU-hour cost model & Glue 6.0 savings projection
│   └── migration-runbook.md          # per-job step-by-step migration procedure
└── evals/                            # evaluation data (not included in upload zip)
```

## Deliverables

| Step | Deliverable | Reference |
|---|---|---|
| 1 | Legacy Glue job inventory table (jobs earlier than 6.0) | [Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) |
| 2 | Per-job cost summary + estimated Glue 6.0 savings | [Glue pricing](https://aws.amazon.com/glue/pricing/) |
| 3 | Migration guide (runtime jump, breaking changes, validation, rollback) | [Migrating to Glue 6.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-60.html) |

## Notes on Estimates

Cost figures are **estimates** derived from published pricing and each job's historical DPU-hours, not from a billed invoice. The skill presents the conservative price-only projection (Glue 6.0 ~30% lower per-DPU-hour) as the headline and recommends validating against Cost Explorer for authoritative spend. Confirm the live per-DPU-hour rate and version support windows on the AWS Glue pricing and release-notes pages before relying on a report.
