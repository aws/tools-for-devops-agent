# Amazon SageMaker AI Operational Review — AWS DevOps Agent Skill

Performs a strictly read-only operational review of Amazon SageMaker AI workloads — endpoints, training jobs, pipelines, notebooks, feature store, model registry, and Studio domains — across **8 pillars and 20 checks**, producing a severity-ranked **Amazon SageMaker AI Operational Review** report with one recommendation per High or Medium finding.

## Purpose

Teams running SageMaker AI at scale accumulate posture drift that no single console page surfaces: Studio domains left on `PublicInternetOnly`, endpoints without autoscaling, notebooks without a customer-managed key, endpoints idle for months still billing, quotas quietly approaching their limit. This skill gives AWS DevOps Agent the check definitions, severity model, and report format to assess all of it in one pass from native AWS control-plane and CloudWatch APIs, and to return findings ordered by how much they matter.

It is designed for recurring review cadences — a weekly or monthly operational review meeting, a pre-launch readiness check, or an ad-hoc audit of a newly inherited account.

## Key Capabilities

- **20 checks across 8 pillars** — Security, Performance, Cost Optimization, Service Quotas, Resiliency, Operational Excellence, Sustainability, and Best Practices. `references/pillar-checks.md` is the authoritative definition of each check's APIs, logic, thresholds, and output fields.
- **Uniform severity ranking** — every finding is High, Medium, Low, or Informational (for inventory checks with no pass/fail signal), and the Executive Summary ranks them most-severe first.
- **Exactly one recommendation per High or Medium finding** — concrete and SageMaker-specific, never generic advice.
- **Multi-account and multi-region** — regions are discovered via Cost Explorer with a `sagemaker:List*` sweep as fallback, so a payer-scoped Cost Explorer miss never produces a false "no activity" result.
- **Dual-signal autoscaling detection** — an endpoint counts as autoscaled via managed instance scaling *or* a classic Application Auto Scaling target on `sagemaker:variant:DesiredInstanceCount`. Only endpoints with neither signal are flagged, which avoids falsely flagging endpoints scaled through Application Auto Scaling alone.
- **Per-check failure isolation** — a denied or failing API becomes an error row on that check and the review continues; an AccessDenied is reported as "not evaluated — permission not granted" rather than a false "none found".
- **Well-Architected grounding** — the Best Practices pillar's recommendations cite the public AWS Machine Learning, Generative AI, and Agentic AI lenses.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with each account you want to review configured as a cloud source, and the `use_aws` tool available to the agent.

### 2. IAM permissions

Nearly every API this skill calls is already covered by the AWS-managed [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html) attached to the DevOps Agent role:

- `sagemaker:List*`, `sagemaker:Describe*`, `sagemaker:ListTags`
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics`
- `application-autoscaling:DescribeScalableTargets`, `application-autoscaling:DescribeScalingPolicies`
- `servicequotas:GetServiceQuota`
- `ce:GetCostAndUsage`, `ce:GetDimensionValues` (region discovery)
- `health:DescribeEvents`, `health:DescribeAffectedEntities` (Lifecycle Events check)

`sts:GetCallerIdentity`, used to default the review to the current account, needs no grant — the call cannot be restricted by IAM policy and succeeds for any authenticated principal.

**One add-on permission** is not in the managed policy: `savingsplans:DescribeSavingsPlans`, used by the Savings Plan check. It is optional — without it that single check reports "not evaluated — permission not granted" and the other 19 run normally. To grant it, either deploy the repo's CloudFormation template with `EnableSageMakerOpsReview=true`:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies \
  --parameter-overrides ExistingRoleName=<YOUR-DEVOPS-AGENT-ROLE-NAME> EnableSageMakerOpsReview=true \
  --capabilities CAPABILITY_NAMED_IAM
```

…or attach the sample policy directly:

```bash
aws iam put-role-policy \
  --role-name <YOUR-DEVOPS-AGENT-ROLE-NAME> \
  --policy-name DevOpsAgentSkill-SageMakerOpsReview \
  --policy-document file://references/iam-policy.json
```

The skill operates strictly **read-only**: no `Create*`, `Update*`, or `Delete*` calls, no endpoint invocation, no job launches, and no data-plane calls of any kind — it never reads an inference payload.

### 3. Support plan and account placement

- The **Resiliency → SageMaker Lifecycle Events** check calls the AWS Health API, which requires a **Business or Enterprise Support** plan. Without one, the check reports that it was not evaluated.
- The **Cost Optimization → Savings Plan** check is only meaningful from the **management/payer account**; in a linked account it will legitimately return no plans.

### 4. SageMaker AI workloads with activity (recommended)

Latency and Stale Endpoint checks read `AWS/SageMaker` CloudWatch metrics, which only publish after an endpoint receives invocations, and Service Quotas utilization only scores when usage metrics exist. Reviewing an idle account produces "No data" rows rather than false findings.

## Limitations

- **Control-plane and metrics only.** The skill reports configuration and CloudWatch signals. It cannot assess model quality, training convergence, data drift, or anything requiring inference payloads or job artifacts.
- **`Check Encryption` covers notebook instances only.** Training jobs and endpoint configs are deliberately excluded to keep the review within the agent's context budget; use the Security pillar's VPC checks and your own KMS policy audit for those.
- **No cost figures.** Cost Explorer is used for region discovery, not spend attribution. The Savings Plan check reports coverage and expiry, not dollar savings.
- **Point-in-time.** Findings reflect state at run time. Service Quotas utilization in particular is scored over a fixed trailing 24-hour window, so a spike outside that window is not visible.
- **Best Practices pillar is advisory.** It emits Well-Architected-grounded guidance, not per-resource findings, and calls no APIs.
- **Large estates may need scoping.** Accounts with many endpoints across many regions can exhaust the agent's run budget; scope to a subset of regions or pillars if a run times out.

## Agent Types

**Chat tasks** and **Evaluation**. The skill is intended for on-demand and scheduled review runs, not live incident response — for SageMaker access failures during an incident, use the `aiml-access-diagnostics` skill instead.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

Build the archive from **inside** the skill directory so `SKILL.md` sits at the archive root — nesting it under a subdirectory causes `Failed to get skill resource` errors at load time:

```bash
cd skills/sagemaker-ops-review
zip -qrD ../sagemaker-ops-review.zip . \
  -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

The resulting `sagemaker-ops-review.zip` contains:

```
SKILL.md                    # frontmatter + skill instructions (required, at root)
references/
├── pillar-checks.md        # the authoritative 20 check definitions
└── iam-policy.json         # sample add-on policy (savingsplans:DescribeSavingsPlans)
```

`README.md`, `CHANGELOG.md`, `.skilleval.yaml`, and `evals/` are excluded — they are repo and offline-evaluation artifacts, not part of the runtime skill.

Constraints enforced at upload time:

- Total zip size ≤ **6 MB**.
- `SKILL.md` is required and must include `name` and `description` frontmatter.
- A `scripts/` directory is **not** allowed — uploads containing scripts are rejected.

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Choose **Add skill** → **Upload skill**.
3. Drag and drop `sagemaker-ops-review.zip` (or browse to it).
4. Select agent type: **Generic** / **All agents**. This is required if you intend to drive the skill from the [`aws-operation-review` custom agent](../../custom-agents/aws-operation-review/) — narrowing the skill to **On-demand** / **Evaluation** keeps it out of the custom agent's skill picker, leaving that agent with no checks to run. Narrow the agent types only if you are driving the skill from Chat alone.
5. Review the validation results.
6. Choose **Upload**.

## How to Use This Skill

### Chat tasks

Full review of the current account:

> Run an Amazon SageMaker AI operational review for this account.

Scoped to specific regions and accounts:

> Run a SageMaker AI operational review for accounts 111122223333 and 444455556666 in us-east-1 and eu-west-1.

Single pillar:

> Review just the Security pillar of my SageMaker AI workloads — domains, notebooks, and endpoint VPC configuration.

Targeted question that still routes through the check definitions:

> Which of my SageMaker endpoints have no autoscaling and haven't been invoked in 90 days?

Quota headroom before a launch:

> Check my SageMaker service quota utilization in us-west-2 before we scale up training.

### Evaluation

Point an Evaluation agent at the skill and schedule it — weekly ahead of an operational review meeting, or monthly as a posture check. The report is produced in full each run, so successive runs are directly comparable.

For a ready-made scheduled configuration, use the [`aws-operation-review` custom agent](../../custom-agents/aws-operation-review/), which loads this skill for SageMaker AI reviews and supports schedule triggers.

## Report Structure

The skill produces a single Markdown report with a fixed structure:

1. `# Amazon SageMaker AI Operational Review` header with Account IDs, Regions, and Date Range.
2. The **AI Disclaimer** blockquote, verbatim.
3. **Executive Summary** — counts by severity, then High and Medium findings most-severe first, each with its recommendation.
4. One `##` section per in-scope pillar, each with a `###` sub-section per check carrying **Guidance**, optional **AI Insights**, **Data** (a table including a `severity` column where the check defines one), and **Recommendations** (one per High/Medium finding, omitted when the check has none).

If every in-scope check across every in-scope account and region returns no resources, the skill reports the single line "No SageMaker AI activity detected." instead of an empty report.

## Skill Contents

| File | Purpose |
|---|---|
| `SKILL.md` | Skill instructions — scope confirmation, check execution rules, severity model, and report format |
| `references/pillar-checks.md` | Authoritative definition of all 20 checks: APIs, logic, thresholds, severity mapping, output fields |
| `references/iam-policy.json` | Sample add-on IAM policy for the permission outside `AIDevOpsAgentAccessPolicy` |

## Troubleshooting

| Issue | Resolution |
|---|---|
| "No SageMaker AI activity detected" | Confirm the DevOps Agent role has `sagemaker:List*` / `sagemaker:Describe*` in the target account and region, and that the region is actually in scope |
| A check reports "not evaluated — permission not granted" | Grant the missing permission (see Prerequisites §2). The other checks are unaffected |
| Service Quotas Check shows "Unknown" risk | Usage metrics only publish while a resource is in use; a quota with no recent usage has no utilization to score |
| Latency or Stale Endpoints show "No data" | `AWS/SageMaker` endpoint metrics only publish after invocations — an endpoint with no traffic has no datapoints |
| Lifecycle Events check not evaluated | The AWS Health API requires a Business or Enterprise Support plan |
| Savings Plan check returns nothing in a linked account | Savings Plans are visible from the management/payer account only |
| The run times out | Reduce scope — fewer regions, or a subset of pillars and checks |

## Customization

- **Change a check** — edit `references/pillar-checks.md`. It is the single source of truth for APIs, logic, thresholds, and output fields; `SKILL.md` defers to it.
- **Change severity mappings** — also in `references/pillar-checks.md`, per check. Keep the four-level scale (High / Medium / Low / Informational) so the Executive Summary stays coherent.
- **Change scope defaults** — tell the agent which pillars, checks, accounts, and regions you want when you invoke it.

## Related

- [`aws-operation-review` custom agent](../../custom-agents/aws-operation-review/) — loads this skill for SageMaker AI operational reviews, on demand or on a schedule.
- [`aiml-access-diagnostics`](../aiml-access-diagnostics/) — diagnoses IAM and access failures for SageMaker and Bedrock calls; use during an incident rather than a posture review.
- [`service-quota-check`](../service-quota-check/) — general-purpose, all-service quota checking. This skill's Service Quotas pillar is SageMaker-specific and scoped to seven verified SageMaker quota codes.
- AWS Well-Architected lenses grounding the Best Practices pillar: [Machine Learning](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/machine-learning-lens.html) · [Generative AI](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html) · [Agentic AI](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentic-ai-lens.html)

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate it in a non-production environment first. It performs read-only operational analysis and makes no changes to your AWS resources, but you are responsible for reviewing the IAM permissions you grant and for validating the findings and recommendations it produces before acting on them.
