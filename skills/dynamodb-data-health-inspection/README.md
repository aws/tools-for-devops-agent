# DynamoDB Data Health Inspection Skill

This skill enables the AWS DevOps Agent to diagnose data-level health issues in Amazon DynamoDB tables — hot partition keys, item sizes approaching the 400 KB limit, ineffective TTL, and unused indexes — using read-only analysis plus bounded, consent-gated item sampling.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
> This skill reads item data from the tables you point it at — review the sampling
> caps and the IAM scoping in **Prerequisites** before running it against a
> production table. Its findings are diagnostic guidance, not a substitute for your
> own judgment about your workload.

## Purpose

Existing DevOps Agent workflows can tell you *that* a DynamoDB table is throttling
or consuming unexpected capacity, using control-plane metadata and CloudWatch
metrics. They cannot tell you *why* when the cause lives in the data: a skewed
partition key, items approaching the 400 KB limit, a TTL that silently does nothing,
or an index nobody reads.

That evidence is only available from item-level reads. This skill combines
control-plane metadata, CloudWatch metrics, and Contributor Insights with **bounded,
consent-gated, value-redacting** data-plane sampling, then produces a rated report
with prioritized findings and remediation steps.

## Key Capabilities

- **Hot key detection** — reads Contributor Insights top contributors and correlates
  them with `ReadKeyRangeThroughputThrottleEvents` /
  `WriteKeyRangeThroughputThrottleEvents`, the direct hot-partition signals, to
  distinguish a confirmed hot partition from mere traffic concentration
- **Item size analysis** — sampled size distribution (median/p95/p99/max plus a
  histogram), items within 12.5 % of the 400 KB hard limit, size skew, and the
  specific attribute names driving bloat
- **TTL effectiveness** — detects TTL enabled but deleting nothing
  (`TimeToLiveDeletedItemCount`), items missing the TTL attribute, malformed TTL
  values (wrong type, or milliseconds where DynamoDB requires epoch **seconds**),
  and a genuine expired-item backlog beyond DynamoDB's documented deletion window
- **GSI/LSI utilization** — unused and write-only indexes over a 30-day window,
  over-broad projections with a storage amplification ratio, missing per-index
  autoscaling, GSI throttling that applies backpressure to the base table, and
  item collections approaching the 10 GB LSI limit
- **Two-phase execution** — everything measurable at zero data-plane cost runs
  first and reports on its own; sampling is offered separately with a stated cost
  budget

## Safety Posture

| Property | Behavior |
|---|---|
| Mutations | None. No `Put*`, `Update*`, `Delete*`, `Create*`, `BatchWriteItem`, or `TransactWriteItems` — the skill never changes a table or a feature's enablement state |
| Data-plane reads | `dynamodb:Scan` and `dynamodb:Query` only, only after explicit per-run consent, only within the caps below |
| Consent | Requested per table, per run. Never carried over |
| Sampling shape | Two passes: a **projected** pass (keys + TTL attribute only) at up to 1,000 items for TTL and key distribution, then a **full-item** pass at 100–200 items for size. Split because the agent aggregates per-item statistics in its own context, and a large payload cannot be totalled reliably |
| Caps | ≤ 1,000 items on the projected pass (10,000 absolute ceiling), 100–200 on the full-item pass, ≤ 4 Scan segments, `Limit` ≤ 250, eventually-consistent reads only, ≤ 60 s, abort on 1.5× cost overshoot |
| Full-table scans | Never |
| Already-throttling tables | Sampling is refused by default, since it would add read load to a table already shedding requests |
| Redaction | Item byte sizes, attribute names, and TTL timestamps are recorded. No other attribute value is recorded, echoed, or reported. Partition keys appear only as digests |
| Throttled sample | Aborts rather than retrying |
| No live table | Declines to run the inspection at all. With nothing to collect, the thresholds are unmeasurable, so it reasons from the reported symptoms without this skill's rule IDs or report format rather than forcing its four dimensions onto them |

## Prerequisites

- A DynamoDB table in an account the Agent Space role can reach
- IAM permissions beyond `AIDevOpsAgentAccessPolicy` — deploy
  `cloudformation/devops-agent-skill-policies.yaml` with
  `EnableDynamoDbDataHealthInspection=true`:

| Service | Actions |
|---|---|
| DynamoDB (control plane) | `DescribeTable`, `DescribeTimeToLive`, `DescribeContributorInsights`, `ListContributorInsights`, `ListTables`, `DescribeContinuousBackups`, `DescribeLimits` |
| DynamoDB (**data plane**) | `Scan`, `Query` |
| CloudWatch | `GetMetricData`, `GetMetricStatistics`, `GetInsightRuleReport`, `DescribeInsightRules`, `DescribeAlarms` |
| Application Auto Scaling | `DescribeScalableTargets` |

> **`dynamodb:Scan` and `dynamodb:Query` are data-plane permissions** — the only
> grants here that are not `Describe*`/`Get*`/`List*`. They let the role read item
> data from the tables in scope. Scope `Resource` to specific table ARNs rather than
> `*` wherever practical, and use the template's `AllowedRegions` parameter to
> restrict the regions the agent can reach.

- **Contributor Insights** should be enabled (throttled-keys-only mode is free unless
  throttling occurs) for hot-key findings. Without it, hot keys are reported as *not
  determinable* rather than as absent.

## Limitations

- **A `Scan` sample is not random.** Items are returned in partition-layout order, so
  sampled findings describe how data is *stored*, not how traffic is *distributed*.
  The skill never claims a hot key from sampling — that requires Contributor
  Insights.
- **Hot keys need Contributor Insights.** It must have been enabled *before* the
  window of interest; enabling it now does not produce retroactive data.
- **`ItemCount` and `TableSizeBytes` are approximate**, refreshed by DynamoDB roughly
  every six hours. Mean item size inherits that staleness.
- **LSI utilization is not measurable.** LSIs have no index-scoped CloudWatch
  metrics because they share the base table's partitions, so the skill never reports
  an LSI as unused.
- **Item collection size is estimated, not measured.** The exact figure requires
  `ReturnItemCollectionMetrics=SIZE` on a *write*, which is outside a read-only
  skill's scope.
- **Table size trend usually needs two runs.** `TableSizeBytes` is a point-in-time
  value, not a metric series, so "storage is growing" degrades to "trend not
  measured" on a first run.
- **Sampling costs read capacity.** `ProjectionExpression` does not reduce that cost
  — DynamoDB bills `Scan` on bytes examined, not bytes returned.
- **Item-size findings rest on a small sample.** The full-item pass is capped at
  100–200 items so the agent can total the sizes reliably in one pass, which on a large
  table is a weak sample. Findings carry an explicit confidence annotation and are
  severity-downgraded when the sample is too small to support the full severity. An
  absence in the sample is never reported as an absence in the table.
- **Needs a live table.** With nothing to collect the skill declines to run rather than
  applying its framing to a description. Measured on 40 real support cases diagnosed from
  narrative alone, forcing the framing without data *reduced* root-cause accuracy versus
  not using the skill, which is why the guard exists.
- Single-region per run. Global Tables must be inspected per replica region.

## Agent Types

- **Chat tasks** — conversational data health reviews and ad-hoc questions
- **Prevention** — proactive reviews before a traffic event, or on a schedule
- **Incident RCA** — explaining throttling that table-level metrics leave unexplained

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, import this skill directly from the repository. In the DevOps
Agent web app, go to Settings → Add Skill → Import from repository, then point to
the `skills/dynamodb-data-health-inspection` directory. See
[Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

> **Note:** You cannot connect the `aws` GitHub organization directly, because the
> GitHub connection setup requires admin rights on the organization. Connect your
> personal GitHub account and select any repository from it during setup. Once a
> connection exists, you can import skills from any public repository — including
> this one — even if it wasn't selected during setup.

**Option B: Upload as a zip file**

1. Zip the skill directory, including only allowed extensions:

   ```bash
   cd skills
   zip -r dynamodb-data-health-inspection.zip dynamodb-data-health-inspection/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, go to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop `dynamodb-data-health-inspection.zip` (max 6 MB).
5. Select the agent types: **Chat tasks**, **Prevention**, and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage skills programmatically — useful for
CI/CD. Assign the skill to the `CHAT`, `PREVENTION`, and `INCIDENT_RCA` agent types.
See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

Prompt naturally — don't name the skill. The agent activates it from the symptoms.

### Chat

- "Inspect the data health of the `orders-prod` DynamoDB table."
- "Our DynamoDB storage cost keeps climbing on `events-prod` and I don't know why."
- "TTL is enabled on `sessions-prod` but storage isn't going down. What's wrong?"
- "Are any items in `documents-prod` close to the 400 KB limit?"
- "Which GSIs on `orders-prod` are we paying for but not using?"
- "Review these tables for data health issues: `orders-prod`, `events-prod`, `sessions-prod`."
- "Check `catalog-prod` for schema anti-patterns before our Black Friday traffic."

### Prevention

- "Run a DynamoDB data health review across our production tables ahead of the
  holiday peak."
- "Audit item size distribution and index utilization on `orders-prod` monthly."

### Incident RCA

- "`orders-prod` is throttling but consumed capacity is only 30 % of provisioned.
  Why?"
- "We're getting `ItemCollectionSizeLimitExceededException` on some writes to
  `orders-prod` but not others."
- "The DynamoDB throttling alarm fired again on `events-prod` — figure out what in
  the data is causing it."

### What to expect

1. The agent reports everything measurable at **zero data-plane cost** first.
2. If per-item evidence would help, it presents a sampling plan with an item count
   and a read-unit budget, and **waits for your approval**. Declining still gets you
   a full report of the control-plane findings.
3. The final output is a rated report: dimensions matrix, prioritized findings with
   evidence, sampling provenance, and an ordered action list.

To keep a run at zero data-plane cost, say so up front — "control-plane only" or
"don't read any items".
