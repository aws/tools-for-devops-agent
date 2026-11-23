# ECS Operations Review — AWS DevOps Agent Skill

An end-to-end Amazon ECS operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). It assesses an ECS service against the ECS Best Practices Guide across six review pillars and produces a prioritized, remediation-linked report artifact per service, plus recommended CloudWatch alarms for IDR onboarding.

It is **strictly read-only**: it uses only `describe*` / `list*` / `get*` AWS API operations (ECS, CloudWatch, IAM, Application Auto Scaling, ELB, ECR, EC2, GuardDuty, Compute Optimizer). It never runs a mutating call; remediations are drafted for human approval, not applied.

> ⚠️ **Non-production disclaimer.** This skill is sample code, not intended for
> production use without additional review and testing. Users should validate in
> a non-production environment first.

## What It Does

1. **Parse the service ARN** (`arn:aws*:ecs:*:*:service/*/*`) and validate region.
2. **Collect configuration data** across the API tier dependency chain — Tier 1 (`ecs.describeServices`) must succeed first; non-Tier-1 access errors mark dependent checks N/A and continue.
3. **Resolve the compute platform** — Fargate (± Spot), EC2 ASG capacity provider, ECS Managed Instances, launchType-only, or ECS Anywhere — from the capacity provider strategy and `ecs.describeCapacityProviders`; this decision drives check applicability in every pillar.
4. **Run pillar checks** — read `references/checks.md` (the index) first, then each `references/pillars/<pillar>.md` one at a time, grading ✓ / ✗ / N/A with evidence, severity, and a recommendation.
5. **Report** — write a per-service artifact following `references/report-format.md`: workload details, per-pillar scorecards for all 6 pillars, prioritized action plan, detailed findings, a Recommended CloudWatch Alarms table, access limitations, and a review summary.

Pillars graded: **Resiliency & HA (REL), Observability (OBS), Security (SEC), Operations (OPS), Performance (PERF), and Additional Analysis (ADD)**.

## Data Sources

| Source | Used for | Required? |
|--------|----------|-----------|
| Read-only AWS APIs (AWS CLI / SDK / AWS API MCP) | All configuration data across the six pillars | Yes |
| CloudWatch `getMetricStatistics` | 7-day baseline (CPU, memory, task count) + `describeAlarms` | Yes (limitation noted if <7 days) |
| AWS Knowledge MCP | Doc-link lookups for findings and alarm recommendations | Yes |

## Agent Types

Intended for these agent types (selected in the Operator Web App at upload time):

- **On-demand** — conversational invocation in Chat ("run an ECS operations review on service X", "ECS security review").

Select **Generic** to make the skill available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

An existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. Read-only permissions

The Agent Space IAM role needs read-only (`describe*` / `list*` / `get*`) access to: ECS, CloudWatch, CloudWatch Logs, IAM, Application Auto Scaling, Elastic Load Balancing v2, ECR, EC2/VPC, GuardDuty, and Compute Optimizer. The DevOps Agent managed policy **`AIDevOpsAgentAccessPolicy`** covers all of these except one: it grants no `compute-optimizer` actions, so the PERF8 rightsizing check needs `compute-optimizer:GetECSServiceRecommendations` added. Deploy `cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml` with `EnableEcsOperationReview=true` to attach it as a gated inline policy. Without it the skill still runs — PERF8 is marked N/A under the access-limitation protocol. No cluster-level access entry or kubectl connectivity is required — ECS is assessed entirely through AWS control-plane APIs.

### 3. AWS Knowledge MCP

Used for documentation-link lookups on findings and alarm recommendations. This is built into AWS DevOps Agent.

## Uploading to AWS DevOps Agent

Grant the read-only permissions in [Prerequisites](#prerequisites) first, including `compute-optimizer:GetECSServiceRecommendations` if you want the PERF8 rightsizing check, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand operations reviews and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `ecs-operation-review`, or filter by AWS service **Amazon ECS**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust thresholds in `references/alarm-thresholds.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/ecs-operation-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f ecs-operation-review.zip
   zip -r ecs-operation-review.zip ecs-operation-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l ecs-operation-review.zip | tail -1   # expect 11 files
   ```

2. Check that the zip has this structure:

   ```text
   ecs-operation-review.zip
   └── ecs-operation-review/
       ├── SKILL.md                # required: frontmatter with name and description
       └── references/
           ├── checks.md           # checks index (read first)
           ├── alarm-thresholds.md
           ├── common-checks-coverage.md
           ├── report-format.md
           └── pillars/            # 6 files: one per pillar (REL/OBS/SEC/OPS/PERF/ADD)
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `ecs-operation-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## Usage

In Chat, use natural language:

- *"Run an ECS operations review on service `arn:aws:ecs:us-east-1:111122223333:service/prod/web`."*
- *"ECS security review for the `web` service in cluster `prod`."*
- *"Assess reliability and cost for my ECS services."*

The agent validates the service ARN, collects read-only AWS data, grades the six pillars, and writes a per-service review artifact.

## Evaluation

The `evals/` directory holds an evaluation harness:

- `eval_queries.json` — routing checks (does the right query trigger the skill?).
- `evals.json` — skill-knowledge evals (six pillars, read-only contract, ARN validation, coverage gate, alarm deliverable), run against `evals/files/service-context.json`.

Run them with your skill-eval runner. Record results in `evals/TESTING.md` (model × eval-suite pass-rate matrix) and re-run after any change to the frontmatter or workflow steps. Results are recorded from real runs, never fabricated.

## Severity

Internally the skill grades on `Critical / High / Medium / Low / Info` tiers; the report writer maps these to customer-facing descriptive labels (see `references/report-format.md`). It never emits internal severity numbers in customer-facing output.

## Source attribution

- [About AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html)
- [Amazon ECS Best Practices Guide](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/intro.html)

## License

Internal use.
