# Sustainability Operation Review — AWS DevOps Agent Skill

A workload sustainability review for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html) that assesses all 29 best practices of the [AWS Well-Architected Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html). It measures resource intensity (vCPU-hours, storage, and data transfer per unit of business output) from the workload topology and CloudWatch, uses carbon emissions and water withdrawal data from the [AWS Sustainability API](https://docs.aws.amazon.com/sustainability/latest/APIReference/Welcome.html) or a console CSV export as context, and produces a shareable report of severity-ranked findings stated in resource terms.

> **Non-production disclaimer:** This skill is sample code, not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM policy below before you apply it.

## Key Capabilities

- **All 29 Sustainability Pillar best practices** (SUS01–SUS06), each graded `MET`, `PARTIAL`, `NOT MET`, `N/A`, or `NEEDS HUMAN INPUT` with evidence.
- **Resource intensity KPIs are the assessment; emissions are context.** Compute, storage, and network use per unit of business output are attributable to the customer. Reported MTCO2e also moves with methodology, grid intensity, AWS renewable procurement, and other customers' usage, so the skill never attributes a change in it to the customer without ruling those out, and never states impact in MTCO2e.
- **Emissions-versus-topology sanity check.** Zero emissions next to a sizeable fleet, or emissions shares that don't match where the resources are, mean the inputs cover different scopes, and are reported as a finding.
- **Cost–carbon divergence.** Tests five patterns where Cost Explorer spend and resource use diverge, such as commitments, free inbound transfer, and paid-for idle capacity.
- **Graviton assessment (SUS05-BP02).** Per-service eligibility, effort bands (optionally rated by AWS Compute Optimizer), and a migration order, with no CO2e saving estimated.
- **AI/ML coverage** for Amazon SageMaker AI and Amazon Bedrock: accelerator-hours, endpoint utilization, training configuration, and tokens, mapped to the Machine Learning and Generative AI Lenses.
- **Emissions by linked account, service, and Region.** 14 months of Scope 1–3 carbon, location- and market-based, with a per-account breakdown from a management account. Annual water withdrawals are reported for disclosure only.
- **CSV fallback.** Attach a carbon or water report from **Reports** in the [AWS Sustainability console](https://docs.aws.amazon.com/sustainability/latest/userguide/csv-reports.html) instead of, or as well as, granting API access. It is also the fallback for water when the water API call is unavailable, and is validated before use.
- **Read-only, and always finishes.** No `Create*`, `Modify*`, `Delete*`, or `Terminate*` calls, and a full report even without emissions data.

## Prerequisites

### 1. An Agent Space with the accounts to review

An existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with each account to review connected as a cloud source.

### 2. IAM permissions

The default `AIDevOpsAgentAccessPolicy` managed policy grants no `sustainability:` or `dlm:` actions; it already grants `ce:GetCostAndUsage` (through `ce:Get*`) and the other reads the review makes. Add the policy below inline to the DevOps Agent IAM role in every account you review: the primary account role and any secondary account roles. These actions fall inside the agent's [permission guardrail](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-limiting-agent-access-in-an-aws-account.html), which includes the `ReadOnlyAccess` managed policy, so the inline grant takes effect.

| Action | Need |
|---|---|
| `sustainability:GetEstimatedCarbonEmissions` | Required for carbon data from the API; without it, attach a CSV export |
| `sustainability:GetEstimatedCarbonEmissionsDimensionValues` | Optional |
| `sustainability:GetEstimatedWaterAllocation`, `sustainability:GetEstimatedWaterAllocationDimensionValues` | Water; without them, attach a water CSV export |
| `dlm:GetLifecyclePolicies` | Snapshot lifecycle evidence (SUS04-BP03) |
| The four `compute-optimizer:` actions and `ecr:BatchGetImage` | Optional: Graviton effort ratings and arm64 image checks |

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SustainabilityCarbonAndWater",
      "Effect": "Allow",
      "Action": [
        "sustainability:GetEstimatedCarbonEmissions",
        "sustainability:GetEstimatedCarbonEmissionsDimensionValues",
        "sustainability:GetEstimatedWaterAllocation",
        "sustainability:GetEstimatedWaterAllocationDimensionValues"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SnapshotLifecyclePolicies",
      "Effect": "Allow",
      "Action": "dlm:GetLifecyclePolicies",
      "Resource": "*"
    },
    {
      "Sid": "OptionalGravitonAssessment",
      "Effect": "Allow",
      "Action": [
        "compute-optimizer:GetEnrollmentStatus",
        "compute-optimizer:GetEC2InstanceRecommendations",
        "compute-optimizer:GetAutoScalingGroupRecommendations",
        "compute-optimizer:GetRDSDatabaseRecommendations",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

`Resource` must be `*`: none of the `sustainability:`, `dlm:`, or `compute-optimizer:` actions supports resource-level permissions (`ecr:BatchGetImage` can be scoped to repository ARNs). Find the role names in the **Cloud** section of the Agent Space's **Capabilities** tab, save the policy as `sustainability-operation-review-policy.json`, and attach it:

```bash
aws iam put-role-policy \
  --role-name <devops-agent-role-name> \
  --policy-name sustainability-operation-review \
  --policy-document file://sustainability-operation-review-policy.json
```

A role without `AIDevOpsAgentAccessPolicy` also needs `ce:GetCostAndUsage` for the cost–carbon check. Compute Optimizer returns recommendations only for [opted-in](https://docs.aws.amazon.com/compute-optimizer/latest/ug/getting-started.html) accounts.

### 3. Region restrictions must exempt Sustainability and Cost Explorer

If the role carries an `aws:RequestedRegion` restriction, exempt `sustainability:*` and `ce:*`. The Sustainability API is global and Cost Explorer is served from `us-east-1`, so both calls fail otherwise.

### 4. A business output metric (strongly recommended)

A CloudWatch metric counting the workload's unit of work, such as orders, is the denominator of every intensity KPI. Without one, the skill falls back to requests, invocations, or data processed, and states the caveat.

### 5. Optional data sources

CloudWatch agent memory and disk metrics, Container Insights, VPC Flow Logs, GPU metrics, and `Environment` tags each let the review grade practices it would otherwise infer or mark `NEEDS HUMAN INPUT`.

## Limitations

- **Monthly data.** Carbon for a month is published by the 21st of the following month ([key concepts](https://docs.aws.amazon.com/sustainability/latest/userguide/key-concepts.html)), so before the 21st the latest month can be two months back.
- **Only Amazon EC2, Amazon S3, and Amazon CloudFront are broken out by service.** Everything else, SageMaker AI and Bedrock included, is "Other".
- **No workload-level emissions.** The API groups by account, Region, and service only; a member account sees only its own data.
- **Water is annual and withdrawal-only**, covers AWS data center operations only, and creates no findings.
- **No CO2e estimates** for Graviton migrations or AI/ML workloads.
- **Four practices need human input:** SUS02-BP05, SUS03-BP03 (in part), SUS03-BP04, and SUS06-BP05.
- **Not for per-instance rightsizing** (use [AWS Compute Optimizer](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html)) **or incident-time analysis**: there is no live carbon signal.

## Agent Types

The `SKILL.md` frontmatter sets `metadata.aws-devops-agent-skills.agent-types` to `"CHAT, PREVENTION"`:

- **Chat tasks** (`CHAT`): on-demand reviews. The primary mode.
- **Improvement** (`PREVENTION`): proactive efficiency recommendations.

Not the incident agents: emissions data is monthly, so it can't inform an active incident. If console labels differ, match by the API value in [Managing assets](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html).

## Installing the Skill

See [AWS DevOps Agent skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) for both options.

### Option A: Import from repository

Needs any GitHub account [connected](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) to your Agent Space.

1. In the Agent Space Operator Web App, go to **Knowledge** → **Skills** → **Add skill** → **Import from repository**.
2. Enter `https://github.com/aws/tools-for-devops-agent/tree/main/skills/sustainability-operation-review`.
3. Select the agent types **Chat tasks** and **Improvement**, deselect **All agents**, and choose **Import skill**.

To update, open the skill and choose **Sync**.

### Option B: Upload a zip

Build the zip from inside the skill folder so `SKILL.md` is at the root of the archive:

```bash
cd skills/sustainability-operation-review
zip -r ../sustainability-operation-review.zip SKILL.md references assets -i '*.md'
unzip -l ../sustainability-operation-review.zip   # first entry: SKILL.md, with no leading folder
```

A zip that contains the folder itself uploads without error, but the skill's reference files then fail to load. Upload it from **Knowledge** → **Skills** → **Add skill** → **Upload skill**, select **Chat tasks** and **Improvement**, deselect **All agents**, and choose **Upload**.

### After installing or updating

Wait about 15 minutes, then start a new chat to test. A chat started within minutes of an upload may fail to read the skill's reference files and does not recover.

## How to Use This Skill

The agent asks for the scope and business output metric if you don't give them, and produces a report artifact named `sustainability-review-<workload-name>-<YYYY-MM-DD>.md`.

**Chat tasks**

- *"Run a sustainability review for the checkout workload. Business output is the `Orders/Completed` CloudWatch metric."*
- *"Break down our carbon emissions for the last 12 months by linked account and by service."*
- *"We deleted 40 TB of S3 data last quarter and our reported emissions went up. Why?"*
- *"How efficient are our SageMaker endpoints and Bedrock usage, from a sustainability point of view?"*

**With a CSV export.** Download a report from **Reports** in the AWS Sustainability console and attach it to the chat:

- *"Run a sustainability review for the orders workload using the attached monthly carbon emissions report."*
- *"The water API call isn't available to us. Use the attached annual water allocation report for the water section."*

**Improvement**

- *"Find architecture-level efficiency improvements in our production workloads."*
- *"Where would Graviton reduce our resource footprint?"*

## Skill Contents

```
sustainability-operation-review/
├── SKILL.md                              # critical rules and the nine-step workflow
├── README.md
├── CHANGELOG.md
├── references/
│   ├── workload-model.md                 # topology layers and workload shapes
│   ├── proxy-metrics.md                  # KPIs, sanity check, cost–carbon divergence
│   ├── framing-and-attribution.md        # emissions-as-context rules, explaining changes
│   ├── emissions-collection.md           # carbon and water calls, publication timing, missing data
│   ├── emissions-api-reference.md        # API parameters, IAM, methodology notes
│   ├── csv-emissions-input.md            # carbon and water CSV exports
│   ├── sus-best-practices-checklist.md   # the 29 practices: evidence, severity, guards
│   ├── ai-ml-workloads.md                # SageMaker AI and Bedrock
│   └── graviton-migration.md             # Graviton eligibility, effort, migration order
├── assets/
│   └── report-template.md                # report structure and severity definitions
└── evals/                                # evals.json and skill evaluation results (not published)
```

## Best Practices Covered

| Focus Area | Best practices | Agent-assessable | Reference |
|---|---|---|---|
| SUS01 Region Selection | 1 | 1 | [SUS 1](https://docs.aws.amazon.com/wellarchitected/latest/framework/a-region-selection.html) |
| SUS02 Alignment to Demand | 6 | 5 | [SUS 2](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-02.html) |
| SUS03 Software and Architecture Patterns | 5 | 3 | [SUS 3](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-03.html) |
| SUS04 Data Patterns | 8 | 8 | [SUS 4](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-04.html) |
| SUS05 Hardware and Services | 4 | 4 | [SUS 5](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-05.html) |
| SUS06 Development and Deployment | 5 | 4 | [SUS 6](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-06.html) |
| **Total** | **29** | **~25** | |

## Severity Definitions

| Severity | Definition | Timeline |
|---|---|---|
| CRITICAL | Large, unambiguous waste: significant resource consumption with no business value | 30 days |
| HIGH | Substantial efficiency gap with a clear remediation path | 30 days |
| MEDIUM | Meaningful improvement opportunity, or one requiring design change | 90 days |
| LOW | Minor optimization or governance gap | Next planning cycle |
| INFO | Observation, or outside the agent's visibility | N/A |

Severity reflects resource-footprint impact and remediation effort, not operational risk. A CRITICAL sustainability finding is not an outage risk.

## References

- [AWS Sustainability User Guide](https://docs.aws.amazon.com/sustainability/latest/userguide/what-is-sustainability.html) and [calculation methodology](https://docs.aws.amazon.com/sustainability/latest/userguide/methodology.html)
- [Machine Learning Lens](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/machine-learning-lens.html) and [Generative AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html)
- [AWS Graviton](https://aws.amazon.com/ec2/graviton/)

## License

This skill is licensed under the Apache-2.0 License. See the repository [LICENSE](https://github.com/aws/tools-for-devops-agent/blob/main/LICENSE).
