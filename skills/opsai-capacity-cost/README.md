# opsai-capacity-cost

A skill for [AWS DevOps Agent](https://aws.amazon.com/devops-agent/) that reviews Amazon Bedrock
spend and capacity in your AWS account. It answers three questions: where your Bedrock spend goes,
whether the capacity you pay for is used, and how close your traffic runs to your Bedrock quotas.

The skill is read-only. It never creates, resizes or deletes a resource, and never changes a quota.
When a change is recommended, it gives you the exact command to run.

> **Please note.** This skill is sample code, not an AWS service, and carries no SLA. Figures labelled
> `(billed)` are read from AWS Cost Explorer. Figures labelled `(estimated)` are calculated from token
> metrics and published prices and are not your invoice. Severity response times are guidance, not AWS
> commitments. Review each recommendation against current AWS documentation before acting on it in a
> production account.

## Contents

- [Who it is for](#who-it-is-for)
- [How it works](#how-it-works)
- [Checks](#checks)
- [What every answer includes](#what-every-answer-includes)
- [How quota limits are read](#how-quota-limits-are-read)
- [Scope and related skills](#scope-and-related-skills)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Example questions](#example-questions)
- [Limitations](#limitations)
- [Version history](#version-history)

## Who it is for

Platform, FinOps and on-call teams that run production workloads on Amazon Bedrock and need to
answer questions such as "why did the bill rise this month", "is our Provisioned Throughput idle" or
"how much quota headroom do we have before we get throttled", with figures read from the account
rather than estimated by hand.

## How it works

The DevOps Agent loads this skill when you ask about Bedrock cost or capacity in chat. The skill
then reads data from the connected account through the agent's `use_aws` tool and returns findings
with the evidence behind each one. A full review runs in this order:

1. **Scope.** Confirms the Region, the time window, and the models and inference profiles in use.
   Defaults are stated so you can correct them.
2. **Spend.** Reads billed spend per model from Cost Explorer across every service name Bedrock bills
   under, then compares it day by day with CloudWatch token counts. Tokens with no billed line, billed
   lines with no tokens, and days billed at $0 are listed rather than explained away.
3. **Cost checks.** Looks for output-token drift, prompt caching that is not paying off, batch
   candidates, model fit and invocation-log retention (the LLM-COST checks below).
4. **Provisioned Throughput.** Compares committed model units with observed throughput, and checks
   the model version against its end-of-life date.
5. **Quota headroom and throttling.** Reads throttles and the peak tokens per minute, and when the
   question calls for it, the applied quota for the exact model and the way it is called.
6. **Alarms.** Recommends CloudWatch alarms for token spend, quota use and throttling, with the source
   of each threshold.
7. **Report.** Returns the findings. For a full review, the report follows
   `assets/capacity-cost-report-template.md`.

Each step is bounded. If an API call is denied or a metric has no data, the skill records the gap,
skips only the checks that depend on it and continues. A partial review with its gaps listed is a
valid result.

## Checks

Each finding carries a check ID, a severity, the value observed in your account and a link to the AWS
documentation it is based on.

| Check ID | What it finds | Severity |
|---|---|---|
| LLM-PT-001 | Provisioned Throughput that is `InService` but mostly unused | HIGH |
| LLM-PT-002 | On-demand traffic held near its throttle limit with no Provisioned Throughput | MEDIUM |
| LLM-PT-003 | Provisioned Throughput on a model version near or past end of life | MEDIUM |
| LLM-COST-001 | A small number of requests produce most of the output tokens (unbounded `maxTokens`) | MEDIUM |
| LLM-COST-002 | Repeated prompt prefixes with no prompt caching, or cache writes far above cache reads | MEDIUM |
| LLM-COST-003 | Large jobs that can tolerate delay running on-demand instead of batch inference | MEDIUM |
| LLM-COST-004 | A high-cost model used for simple, high-volume tasks | MEDIUM |
| LLM-COST-005 | A cross-Region inference profile whose billed rate has not been confirmed | INFO |
| LLM-COST-006 | Invocation logs stored with no retention policy | MEDIUM |
| LLM-INV-002 | Calls to a model ID directly when a cross-Region inference profile exists for it | HIGH |
| LLM-INV-007 | Sustained throttling with no backoff retry and no inference-profile spreading | MEDIUM |

A finding is raised only when the data supports it. When a confirming signal is missing, for
example when invocation logging is disabled, the finding is reported as `INFO (unconfirmed)` and the
missing signal is named.

**Severity guide.** CRITICAL: active impact or large waste, act within 24 to 48 hours. HIGH: serious
risk, act within a week. MEDIUM: gap against best practice, act within 30 days. LOW: hardening.
INFO: informational, or the confirming signal was unavailable.

## What every answer includes

- **Labelled figures.** Every dollar amount is marked `(billed)` or `(estimated)`. Billed figures
  name the Cost Explorer grouping and service names that were read. Estimated figures show the
  calculation.
- **Price sources.** Prices come from you, the AWS Price List API or the Bedrock pricing page, and the
  source is named. A figure with no price source is marked "unpriced" rather than guessed.
- **The time window**, with the end date stated as exclusive, so you know which days are included.
- **What was not checked**, and why: Regions, denied API calls, metrics with no data.
- **Commands, not changes.** Any recommended change is given as the AWS CLI command or
  infrastructure-as-code snippet for you to review and run.
- **No account IDs or secret values** in the answer.

## How quota limits are read

Bedrock enforces token-per-minute, request-per-minute and token-per-day quotas per model, and the
applied values differ by account and Region. The Service Quotas API cannot search a quota by name:
finding one Bedrock quota by listing them all means paging through more than 50 pages of results,
which takes the agent over ten minutes. To keep answers fast and accurate, the skill:

1. **Reads the quota only when it is needed.** That is when you ask for the limit, the headroom, the
   size of an increase or a percent-of-quota alarm, or when your account shows throttles. Otherwise
   the answer says that headroom was not computed and why.
2. **Uses a verified table of quota codes.** `references/quota-codes.md` holds 133 codes for 46 model
   families, each checked against Service Quotas on 2026-11-12. The skill takes the code for your
   model and the way you call it (direct, cross-Region or global inference profile), reads the applied
   value with a single `GetServiceQuota` call, and checks that the returned quota name matches your
   model before using it. Values are always read from your account, never taken from the table or
   from documentation.
3. **Asks you for the code when the model is not in the table.** The skill answers with your throttle
   data and peak usage first, then names the exact quota it needs, for example "Cross-region model
   inference tokens per minute for Anthropic Claude Sonnet 5", and tells you where to find the code:
   in the console under Service Quotas, Amazon Bedrock, searching for that name, or with the AWS CLI
   command it provides. It lists every quota only if you ask it to.

Quotas are presented as a table:

| Quota name | Code | Applied value | Adjustable |
|---|---|---|---|
| Cross-region model inference tokens per minute for Anthropic Claude Sonnet 5 | L-D4FBCF4E | `<value in your account>` | `<Yes or No>` |

Headroom is reported as your peak `EstimatedTPMQuotaUsage` divided by the applied quota, with the
statistic, period and window stated.

## Scope and related skills

This skill covers Bedrock spend, Provisioned Throughput, quotas, throttling capacity and the cost of
invocation-log storage. Questions outside that scope belong to these skills. Related skills are optional: when one is installed this skill uses it for that part, otherwise it runs a short fallback check and recommends installing it.

| Question | Skill |
|---|---|
| Bedrock configuration, invocation logging setup, IAM scope of `InvokeModel`, knowledge bases and RAG | `opsai-bedrock-review` |
| Guardrails configuration (Guardrail spend stays with this skill) | `opsai-bedrock-security` |
| Bedrock Agents and AgentCore | `opsai-bedrock-agentcore` |
| SageMaker endpoints, batch and endpoint cost | `opsai-sagemaker-inference` |
| SageMaker training and model registry | `opsai-sagemaker-training` |
| Throttling or errors happening right now | `opsai-incident-triage` |
| Model quality after a model change | `opsai-ml-eval-check` |
| Price quotes for future usage | [AWS Pricing Calculator](https://calculator.aws/) |

## Prerequisites

**Account setup**

- An AWS DevOps Agent Agent Space with the `use_aws` tool enabled.
- AWS Cost Explorer enabled in the account. If it was enabled recently, allow up to 24 hours before
  cost data is available. Without Cost Explorer the skill still runs, and reports spend as
  `(estimated)` from token metrics.
- Optional: Bedrock model invocation logging. When it is enabled, the skill uses the log data to
  confirm LLM-COST-001 and LLM-COST-002. When it is not, those checks are reported as unconfirmed.

**IAM permissions**

The agent role needs these read-only actions in each account and Region you want reviewed:

| Service | Actions | Used for |
|---|---|---|
| Amazon Bedrock | `bedrock:ListFoundationModels`, `bedrock:GetFoundationModel`, `bedrock:ListInferenceProfiles`, `bedrock:GetInferenceProfile`, `bedrock:ListProvisionedModelThroughputs`, `bedrock:GetProvisionedModelThroughput`, `bedrock:GetModelInvocationLoggingConfiguration` | Models, profiles, Provisioned Throughput, log destination |
| AWS Cost Explorer | `ce:GetCostAndUsage`, `ce:GetDimensionValues` | Billed spend per model |
| AWS Price List | `pricing:GetProducts`, `pricing:DescribeServices`, `pricing:GetAttributeValues` | Per-token prices for estimates |
| Service Quotas | `servicequotas:GetServiceQuota`, `servicequotas:ListServiceQuotas`, `servicequotas:ListRequestedServiceQuotaChangeHistory` | Applied quotas and headroom |
| Amazon CloudWatch | `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics` | Token counts, throttles, quota usage |
| Amazon CloudWatch Logs | `logs:DescribeLogGroups`, `logs:StartQuery`, `logs:GetQueryResults` | Log retention, output-token and cache analysis |
| Amazon S3 | `s3:GetBucketLifecycleConfiguration` | Retention of an S3 log destination, if one is configured |

The default DevOps Agent policy, `AIDevOpsAgentAccessPolicy`, does not include the `pricing:*`
actions. Add them to the agent role. Without them the skill reads prices from the Bedrock pricing
page and, if that page cannot be read, marks the affected figures "unpriced".

No write permissions are required. If a call is denied, the skill names the API, skips only the checks
that need it and lists the gap in the answer.

## Installation

Build the archive so that `SKILL.md` sits at the root of
the zip:

```bash
cd skills/opsai-capacity-cost && zip -r ../opsai-capacity-cost.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

The archive contains `SKILL.md`, `references/` and `assets/`. In the Agent Space console, open
**Skills**, choose **Import skill** and upload the archive.

> **Set the Agent Type to "All agents".** A custom agent such as `llmops-agent` can only load a skill
> that is registered for all agents. A skill registered under any narrower type is not visible to it.

Do not upload with `devops-agent skills upload-skill`. That command creates a new asset on every run
instead of a new version, which leaves two active copies of the same skill.

## Example questions

- "Why is our Bedrock bill so high this month, and which model is driving it?" Billed spend per model,
  compared day by day with token counts.
- "Some tokens show in CloudWatch but cost $0 in Cost Explorer. Why?" The days and quantities
  affected, and where to confirm the reason in the billing console.
- "We bought Provisioned Throughput. Is it being used?" Committed model units against observed
  throughput (LLM-PT-001), and the steps to stop paying for an idle commitment.
- "Should this nightly summarization job move to batch inference?" A batch against on-demand
  comparison (LLM-COST-003).
- "Can a smaller model handle our classification traffic?" A what-if cost comparison (LLM-COST-004),
  with a quality evaluation required before switching.
- "Is prompt caching paying off?" Cache reads against cache writes per model (LLM-COST-002).
- "What is our tokens-per-minute limit for Claude Sonnet 5, and how close are we to it?" The applied
  quota, your peak usage and the headroom.
- "Our invocation logs keep growing. What does that cost us?" The log group's retention setting
  (LLM-COST-006) and the command to set one.
- "How should we alarm on token spend and quota?" Recommended alarms with their thresholds and the
  source of each.

## Limitations

- **Connected account only.** The skill reads the account and Regions the Agent Space is connected
  to. Cost Explorer is account-wide; metrics, quotas and Provisioned Throughput are read per Region.
- **Billing lag.** Cost Explorer data can lag by up to 24 hours. The current day is reported as "not
  billed yet" and the previous day may be incomplete.
- **Cross-Region inference.** Traffic sent through a `us.`, `eu.` or `global.` inference profile is
  billed and metered in the Region the request was sent from, not where it was served.
- **Quota usage is approximate.** `EstimatedTPMQuotaUsage` is an estimate published by Bedrock.
  Output tokens count against the quota at a higher weight than input tokens for some models, and the
  skill reports the weight it measures.
- **Per-team spend.** Spend per team, application or caller is billed only when application
  inference profiles with cost allocation tags, or IAM principal attribution in the Cost and Usage
  Report, are in place. Otherwise the split is an estimate and is labelled as one.
- **Newer models.** A model not yet in the quota code table requires you to supply the quota code
  (see "How quota limits are read").
  

## Author

Ines Attia

## Version History

See the `CHANGELOG.md` file in this directory.
