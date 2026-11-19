# Firehose Operational Review — AWS DevOps Agent Skill

A comprehensive Amazon Data Firehose (formerly Amazon Kinesis Data Firehose) operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments aligned with the [Amazon Data Firehose Developer Guide](https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html) and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html). Generates a shareable report artifact for the review.

## Purpose

Firehose delivery streams are often set up once and left running, so delivery lag, throttling, missing backup configuration, disabled encryption, and cost inefficiencies (uncompressed or row-oriented output) tend to go unnoticed until data is lost or a bill spikes. This skill gives the DevOps Agent a structured, read-only methodology to assess delivery streams against Firehose best practices and surface those gaps with actionable, severity-ranked findings.

## Key Capabilities

- Discovers delivery streams and their full configuration — source type (Direct PUT, Kinesis Data Streams, MSK), destination (S3, Redshift, OpenSearch, OpenSearch Serverless, Splunk, HTTP endpoint, Snowflake, Iceberg), buffering hints, compression, encryption, backup mode, transform, and format conversion
- Collects `AWS/Firehose` CloudWatch metrics for ingestion, delivery success, data freshness, throttling, source lag, transform/conversion failures, dynamic partitioning, and KMS errors
- Compares observed throughput against per-stream and per-Region service quotas
- Analyzes against seven pillars — **Security, Reliability, Performance, Service Quotas, Cost Optimization, Operational Excellence, Sustainability** — with the review framed as an overall best-practices assessment
- Assigns severity levels (CRITICAL, HIGH, MEDIUM, LOW, INFO) based on data-loss risk, blast radius, and operational impact
- Produces a persisted Markdown report artifact for sharing with stakeholders

All data is gathered through native AWS APIs (`firehose`, `cloudwatch`, `servicequotas`). The skill performs **no data-plane record puts** and reads no delivered record content, transform Lambda code, or destination data.

## Limitations

- Metric-driven checks (delivery lag, throttling, success ratio, source lag) rely on `AWS/Firehose` metrics, which only exist for streams that have ingested data in the analysis window. Reviewing an idle stream still produces a configuration report, but metric-driven findings will be empty.
- IAM analysis is limited to flagging obvious `*`-resource usage at INFO severity — it is not a full least-privilege audit.
- Direct PUT throughput defaults vary by Region and scale proportionally; the skill reads the actual limits from the `*PerSecondLimit` metrics rather than assuming fixed values.
- Sub-second ingestion bursts may not appear in the 1-minute aggregated metrics.

## Agent Types

This skill is intended for the following agent types (selected in the Operator Web App at upload time):

- **On-demand** — conversational invocation in Chat ("review my Firehose streams", "why is my Firehose lagging").

Select **Generic** instead if you want the skill available to all agent types. When using this skill through the [aws-operation-review custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/aws-operation-review), select **Generic** so the custom agent can load it.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

The Agent Space's IAM role must have read access to Firehose, CloudWatch, and Service Quotas APIs. Verify these are present before running the review:

- `firehose:ListDeliveryStreams`, `firehose:DescribeDeliveryStream`, `firehose:ListTagsForDeliveryStream`
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:DescribeAlarms`
- `servicequotas:GetServiceQuota`, `servicequotas:ListServiceQuotas`

The skill operates entirely in **read-only** mode: it never calls `Create*`, `Update*`, `Delete*`, `PutRecord*`, or any other data-plane or mutating API.

### 3. Ingestion activity (recommended)

Most CloudWatch-based checks rely on `AWS/Firehose` metrics, which only exist for streams that have ingested data in the analysis window. Reviewing an account with no recent Firehose traffic still produces a configuration report, but metric-driven findings will be empty.

## Uploading to AWS DevOps Agent

Complete the [prerequisites](#prerequisites) first (the Agent Space with the target account, and the IAM permissions), or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended, or **Generic** for the custom agent | Yes: files and agent types | Re-upload a new zip |

This skill is built for on-demand reviews and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need. The exception is the [aws-operation-review custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/aws-operation-review): to use the skill through it, upload the zip (Option B) and leave **Generic** selected so the custom agent can load it.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `firehose-operation-review`, or filter by AWS service **Amazon Data Firehose**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust thresholds in `references/metrics-thresholds.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/firehose-operation-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f firehose-operation-review.zip
   zip -r firehose-operation-review.zip firehose-operation-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l firehose-operation-review.zip | tail -1   # expect 4 files
   ```

2. Check that the zip has this structure:

   ```text
   firehose-operation-review.zip
   └── firehose-operation-review/
       ├── SKILL.md                          # required: frontmatter with name and description
       ├── references/
       │   ├── best-practices-checklist.md
       │   └── metrics-thresholds.md
       └── assets/
           └── report-template.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `firehose-operation-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**. To use the skill through the aws-operation-review custom agent, leave **Generic** selected instead.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

In the DevOps Agent Chat, use natural language:

- *"Run a Firehose operational review for all regions."*
- *"Review my delivery stream `orders-stream` in `us-east-1` for best practices."*
- *"Why is my Firehose delivery lagging?"*
- *"Audit Firehose reliability and cost optimization."*
- *"Check my Firehose throttling and service quota utilization."*
- *"ORR for our Kinesis Firehose delivery streams."*

The agent will:

- Collect all data automatically (no prompts for confirmation).
- Use only AWS APIs — no record puts, no delivered content read.
- Generate a report artifact named `firehose-review-<stream-or-account>-<region>-<YYYY-MM-DD>.md`.

Once finished, the artifact is persisted on the **Artifacts** page in the DevOps Agent web app.

## Skill Contents

```
firehose-operation-review/
├── SKILL.md                           # main skill instructions (with frontmatter)
├── README.md                          # this file
├── CHANGELOG.md                       # version history
├── .skilleval.yaml                    # skill-eval audit config
├── references/
│   ├── best-practices-checklist.md    # checklist mapped to Firehose best practices
│   └── metrics-thresholds.md          # CloudWatch metric thresholds & severity rules
├── assets/
│   └── report-template.md             # report artifact structure loaded in Step 5
└── evals/                             # evaluation data (not included in upload zip)
    ├── evals.json                     # eval definitions (hand-written)
    ├── files/                         # fixture data for functional runs
    │   └── firehose-context.json
    ├── structure/                     # structure-test results (one file per run)
    │   └── structure-tests-results-v<N>.json
    ├── best-practices/                # best-practices results, one dir per run
    │   └── v<N>/
    │       ├── benchmark.json
    │       └── iteration-<n>/
    │           └── best-practices-tests-results.json
    └── functional/                    # functional results, one dir per run
        └── v<N>/
            ├── benchmark.json
            ├── evals.json
            ├── _metadata.json
            └── iteration-<n>/
                └── <scenario>/
                    ├── with_skill/
                    └── without_skill/
```

## Best-Practices Pillars Covered

| # | Pillar | Checks | Reference |
|---|--------|--------|-----------|
| 1 | Security | Encryption at rest, customer-managed KMS, destination S3 encryption, KMS key health, IAM scoping, VPC connectivity, cross-account/PrivateLink destinations, HTTPS endpoints, error logging | [Data protection](https://docs.aws.amazon.com/firehose/latest/dev/encryption.html) |
| 2 | Reliability | Data freshness, delivery success ratio, S3 backup, retry duration, source read lag, transform/conversion failures | [Troubleshooting](https://docs.aws.amazon.com/firehose/latest/dev/troubleshoot-common-issues.html) |
| 3 | Performance | Throttling, buffering hints, Splunk ack latency, dynamic partitioning limits | [Data delivery](https://docs.aws.amazon.com/firehose/latest/dev/basic-deliver.html) |
| 4 | Service Quotas | Streams per Region, per-stream throughput, Iceberg-table limits, quota-utilization alarming | [Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html) |
| 5 | Cost Optimization | Compression, columnar format conversion, buffer sizing, dynamic partitioning efficiency, idle streams | [Firehose pricing](https://aws.amazon.com/firehose/pricing/) |
| 6 | Operational Excellence | Error logging, CloudWatch alarm coverage, tagging/ownership, IaC-managed config, transform observability, error-prefix runbooks | [Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html) |
| 7 | Sustainability | Data reduction (compression/columnar), efficient object sizing, idle-stream decommissioning, downstream retention/tiering | [Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html) |

> **Best Practices** is the overarching framing for the whole review (see
> `references/best-practices-checklist.md`), not a separate pillar — every finding maps to
> a checklist item under one of the seven pillars above.

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity (delivery stalled, KMS key failures) | 24–48 hours |
| HIGH | Significant gap that could lead to data loss or incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |

## Related

- [aws-operation-review custom agent](../../custom-agents/aws-operation-review/) — routes to this skill for Firehose reviews
- [AWS DevOps Agent skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review
> and testing. Validate in a non-production environment first. Proposed IAM policies are
> suggestions derived from observed evidence — review and narrow them before applying, and
> never apply an IAM change you have not read.
