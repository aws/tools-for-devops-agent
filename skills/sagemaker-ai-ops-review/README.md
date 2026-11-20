# Amazon SageMaker AI Operational Review — AWS DevOps Agent Skill

Performs a strictly read-only operational review of Amazon SageMaker AI workloads — endpoints, training jobs, pipelines, notebooks, and Studio domains — across **8 pillars and 20 checks**, producing a severity-ranked **Amazon SageMaker AI Operational Review** report with one recommendation per High or Medium finding.

## Purpose

Teams running SageMaker AI at scale accumulate posture drift that no single console page surfaces: Studio domains left on `PublicInternetOnly`, endpoints without autoscaling, notebooks without a customer-managed key, endpoints idle for months still billing, quotas quietly approaching their limit. This skill gives AWS DevOps Agent the check definitions, severity model, and report format to assess all of it in one pass from native AWS control-plane and CloudWatch APIs, and to return findings ordered by how much they matter.

### Operational Readiness Review (ORR)

The primary use case is an **Operational Readiness Review (ORR)** — the review a team runs **before deploying a SageMaker AI workload to production**. Because every finding is severity-ranked and carries exactly one concrete remediation, the report works directly as the pre-production punch list: clear the High and Medium findings, then launch. The checks map onto the questions an ORR asks anyway — is the network posture locked down, is the endpoint going to scale under load, are we inside our quotas, is there an owner tag on it, will we see the data if it misbehaves.

It suits three cadences:

| When | Why |
|---|---|
| **Pre-production (ORR)** | Readiness gate before go-live — the High/Medium findings are the blocking list |
| **Recurring (weekly / monthly)** | Catch posture drift after launch; successive runs are directly comparable |
| **Ad hoc** | Audit of a newly inherited or unfamiliar account |

## Key Capabilities

- **20 checks across 8 pillars** — Security, Performance, Cost Optimization, Service Quotas, Resiliency, Operational Excellence, Sustainability, and Best Practices. `references/pillar-checks.md` is the authoritative definition of each check's APIs, logic, thresholds, and output fields.
- **Uniform severity ranking** — every finding is High, Medium, Low, or Informational (for inventory checks with no pass/fail signal), and the Executive Summary ranks them most-severe first.
- **Exactly one recommendation per High or Medium finding** — concrete and SageMaker-specific, never generic advice.
- **Multi-account and multi-region** — regions are discovered via Cost Explorer with a `sagemaker:List*` sweep as fallback, so a payer-scoped Cost Explorer miss never produces a false "no activity" result.
- **Dual-signal autoscaling detection, across all three scalable dimensions** — an endpoint counts as autoscaled via managed instance scaling *or* an Application Auto Scaling target **with a scaling policy attached**, on whichever dimension applies to the variant: `sagemaker:variant:DesiredInstanceCount` (instance-backed), `sagemaker:inference-component:DesiredCopyCount` (Inference Components), or `sagemaker:variant:DesiredProvisionedConcurrency` (serverless with provisioned concurrency). Only endpoints with neither signal are flagged, and the recommendation names the dimension that actually applies — so an Inference Component endpoint is never flagged for lacking a variant-level target it would never have.
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

Three of these are **global** APIs with no regional endpoints — `health`, `ce`, and `savingsplans`. The skill calls each once against `us-east-1` regardless of the regions under review, then filters AWS Health events down to the in-scope regions. This matters even when your review does not include `us-east-1`.

`sts:GetCallerIdentity`, used to default the review to the current account, needs no grant — the call cannot be restricted by IAM policy and succeeds for any authenticated principal.

**One add-on permission** is not in the managed policy: `savingsplans:DescribeSavingsPlans`, used by the Savings Plan check. It is optional — without it that single check reports "not evaluated — permission not granted" and the other 19 run normally. To grant it, either deploy the repo's CloudFormation template with `EnableSageMakerAIOpsReview=true`:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies \
  --parameter-overrides ExistingRoleName=<YOUR-DEVOPS-AGENT-ROLE-NAME> EnableSageMakerAIOpsReview=true \
  --capabilities CAPABILITY_NAMED_IAM
```

…or attach the sample policy directly:

```bash
aws iam put-role-policy \
  --role-name <YOUR-DEVOPS-AGENT-ROLE-NAME> \
  --policy-name DevOpsAgentSkill-SageMakerAIOpsReview \
  --policy-document file://references/iam-policy.json
```

The skill operates strictly **read-only**: no `Create*`, `Update*`, or `Delete*` calls, no endpoint invocation, no job launches, and no data-plane calls of any kind — it never reads an inference payload.

### 3. Support plan and account placement

- The **Resiliency → SageMaker Lifecycle Events** check calls the AWS Health API, which requires a **Business or Enterprise Support** plan. Without one, the check reports that it was not evaluated.
- The **Cost Optimization → Savings Plan** check is only meaningful from the **management/payer account**; in a linked account it will legitimately return no plans.

### 4. SageMaker AI workloads with activity (recommended)

Latency and Stale Endpoint checks read `AWS/SageMaker` CloudWatch metrics, which only publish after an endpoint receives invocations, and Service Quotas utilization only scores when usage metrics exist. Reviewing an idle account produces "No data" rows rather than false findings.

## Limitations

> These limitations are also restated in `SKILL.md`, because this README is **not** packaged into the uploaded skill — anything documented only here is invisible to the agent at run time.

- **Control-plane and metrics only.** The skill reports configuration and CloudWatch signals. It cannot assess model quality, training convergence, data drift, or anything requiring inference payloads or job artifacts.
- **`Check Encryption` covers notebook instances only.** Training jobs, processing jobs, endpoint configs, S3 model artifacts, and Feature Store stores are deliberately excluded to keep the review within the agent's context budget; use your own KMS policy audit for those. Note also what the check *means*: a notebook instance volume is always encrypted at rest — without a `KmsKeyId`, SageMaker AI uses a **system-managed key** — so the Medium finding is the absence of a **customer-managed** key, not an absence of encryption.
- **No Feature Store or Model Registry checks.** Neither feature groups nor model package groups are inventoried or assessed. The skill will say so rather than return a clean report that implies they passed.
- **No cost figures.** Cost Explorer is used for region discovery, not spend attribution. The Savings Plan check reports coverage and expiry, not dollar savings — and because it measures no spend at all, it never recommends a purchase off an assumed spend level. An account with no Savings Plan is reported as Informational, pointing you at Cost Explorer's own Savings Plans recommendations, which are computed from your real usage.
- **Point-in-time.** Findings reflect state at run time. Service Quotas utilization in particular is scored over a fixed trailing 24-hour window, so a spike outside that window is not visible.
- **Stale Endpoints needs 90 days of history.** An endpoint younger than the 90-day window is reported Informational with its age, never flagged idle — a newly deployed endpoint has no invocation history yet, which is not the same as being unused.
- **Best Practices pillar is advisory.** It emits Well-Architected-grounded guidance, not per-resource findings, and calls no APIs.
- **Large estates may need scoping.** Accounts with many endpoints across many regions can exhaust the agent's run budget; scope to a subset of regions or pillars if a run times out.

## Agent Types

**On-demand**. The skill is intended for on-demand and scheduled review runs, not live incident response — for SageMaker access failures during an incident, use the `aiml-access-diagnostics` skill instead.

## Uploading to AWS DevOps Agent

Complete the [prerequisites](#prerequisites) first, including the optional `savingsplans:DescribeSavingsPlans` permission, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand and scheduled reviews and isn't meant for live incident response, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need. For SageMaker AI access failures during an incident, use [`aiml-access-diagnostics`](../aiml-access-diagnostics/) instead. If you run the review from the [`aws-operation-review`](../../custom-agents/aws-operation-review/) custom agent and the skill doesn't appear in its **Skills** picker, upload it with Option B and leave **Generic** selected.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `sagemaker-ai-ops-review`, or filter by AWS service **Amazon SageMaker AI**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change a check's thresholds or severity mapping in `references/pillar-checks.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/sagemaker-ai-ops-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f sagemaker-ai-ops-review.zip
   zip -r sagemaker-ai-ops-review.zip sagemaker-ai-ops-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l sagemaker-ai-ops-review.zip | tail -1   # expect 3 files
   ```

2. Check that the zip has this structure:

   ```text
   sagemaker-ai-ops-review.zip
   └── sagemaker-ai-ops-review/
       ├── SKILL.md                    # required: frontmatter with name and description
       └── references/
           ├── pillar-checks.md        # the 20 check definitions
           └── iam-policy.json         # sample add-on policy (savingsplans:DescribeSavingsPlans)
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `sagemaker-ai-ops-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

### On-demand

Operational Readiness Review before a production launch — the primary use case:

> We're deploying this SageMaker AI workload to production next week. Run an Operational Readiness Review (ORR) and give me the blocking findings.

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

### Scheduled reviews

Run the skill on a schedule — weekly ahead of an operational review meeting, or monthly as a posture check. The report is produced in full each run, so successive runs are directly comparable.

To run it on a schedule, add this skill to the [`aws-operation-review`](../../custom-agents/aws-operation-review/) custom agent — the router that composes every `*-operation-review` skill — and attach a schedule trigger there. This skill intentionally ships no custom agent of its own.

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
| Latency numbers look implausibly large | They are **microseconds** — `152340` µs is 152 ms, not 152 s. The report labels the unit and gives the ms conversion; if a run omits the label, treat the figure as µs |
| A healthy endpoint is reported "not autoscaled" | Confirm which dimension it scales on. Inference Component endpoints scale on `sagemaker:inference-component:DesiredCopyCount`, not `sagemaker:variant:DesiredInstanceCount`. Also check a scaling **policy** is attached — a registered target with no policy never scales, and is reported as its own finding |
| Lifecycle Events check not evaluated | The AWS Health API requires a Business or Enterprise Support plan. If the run shows a connection or endpoint error rather than `SubscriptionRequiredException`, the call was made in the wrong region — Health is global and must be called in `us-east-1` |
| Savings Plan check returns nothing in a linked account | Savings Plans are visible from the management/payer account only. Like Health, it is a global API called in `us-east-1` |
| The run times out | Reduce scope — fewer regions, or a subset of pillars and checks |

## Customization

- **Change a check** — edit `references/pillar-checks.md`. It is the single source of truth for APIs, logic, thresholds, and output fields; `SKILL.md` defers to it.
- **Change severity mappings** — also in `references/pillar-checks.md`, per check. Keep the four-level scale (High / Medium / Low / Informational) so the Executive Summary stays coherent.
- **Change scope defaults** — just tell the agent which pillars, checks, accounts, and regions you want; the skill confirms scope in Step 1.

## Related

- [`aws-operation-review` custom agent](../../custom-agents/aws-operation-review/) — the router that composes this skill alongside the EKS, RDS/Aurora, and Bedrock operation-review skills. Select this skill in its **Skills** picker to run the review on demand or on a schedule.
- [`aiml-access-diagnostics`](../aiml-access-diagnostics/) — diagnoses IAM and access failures for SageMaker and Bedrock calls; use during an incident rather than a posture review.
- [`service-quota-check`](../service-quota-check/) — general-purpose, all-service quota checking. This skill's Service Quotas pillar is SageMaker-specific and scoped to seven verified SageMaker quota codes.
- AWS Well-Architected lenses grounding the Best Practices pillar: [Machine Learning](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/machine-learning-lens.html) · [Generative AI](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html) · [Agentic AI](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentic-ai-lens.html)

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate it in a non-production environment first. It performs read-only operational analysis and makes no changes to your AWS resources, but you are responsible for reviewing the IAM permissions you grant and for validating the findings and recommendations it produces before acting on them.
