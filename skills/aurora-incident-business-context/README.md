# Aurora/RDS Incident Business Context (Skill)

Enriches an Amazon Aurora or Amazon RDS incident investigation with business
context — dependent services, estimated cost of downtime, compliance
reporting exposure, and recent-change correlation — so AWS DevOps Agent's
technical root-cause findings come with an answer to "who does this affect
and what does it cost us."

> ⚠️ This skill is sample code, not intended for production use without
> additional review and testing. Users should validate in a non-production
> environment first.

## What it does

DevOps Agent's built-in investigation tools (CloudWatch, Performance
Insights, RDS/Aurora logs) answer *what* is technically wrong. This skill
adds the *business* half of the incident report: which teams/services are
affected, a defensible dollar estimate of downtime cost, which compliance
reporting obligations could apply (for the compliance owner to assess), and
whether a recent change correlates with the incident.

It is evidence-driven, not generative — it tells the agent **where to look**
(resource tags, AWS Config history, CloudTrail, customer-supplied
dependency maps) and **how to reason** about what it finds. It does not
invent dependency graphs, dollar figures, or compliance frameworks. If the
evidence isn't tagged or configured in the account, the skill says so and
asks the operator, rather than guessing.

## Prerequisites

For the skill to find real evidence (rather than reporting gaps), the
target account should have some of the following in place:

- **IAM permissions** on the DevOps Agent role. All four are read-only.
  `AIDevOpsAgentAccessPolicy` already covers `rds:ListTagsForResource`,
  `tag:GetResources` and `cloudtrail:LookupEvents`. It doesn't cover
  `config:GetResourceConfigHistory`, which the recent-change check uses. Add
  it with the `EnableAuroraIncidentBusinessContext` parameter of
  [`devops-agent-skill-policies.yaml`](../../cloudformation/devops-agent-skill-policies/).
  Without it, the skill falls back to CloudTrail and says that Config
  history wasn't readable.
- **Resource tags** on the Aurora/RDS resource, e.g. `DependentServices`,
  `OnCallTeam`, `RevenuePerMinute`, `SLAThresholdMinutes`,
  `DataClassification`, `Compliance`. None are required for the skill to
  activate — it degrades gracefully to "no evidence found" per category.

## Uploading to AWS DevOps Agent

Set up the IAM permission and resource tags in [Prerequisites](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **Incident RCA** (`INCIDENT_RCA`) and **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **Incident RCA** and **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill adds business impact to Aurora and RDS incident investigations, during root cause analysis or when you ask in chat, so target **Incident RCA** and **On-demand**. **Generic** would load it for every agent type, incident triage and evaluation included, and add business-impact context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aurora-incident-business-context`, or filter by AWS service **Amazon RDS**.
4. Choose **Details** and check that the agent types listed are **Incident RCA** and **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the tag keys the skill looks for in `references/evidence-sources.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aurora-incident-business-context/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aurora-incident-business-context.zip
   zip -r aurora-incident-business-context.zip aurora-incident-business-context/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aurora-incident-business-context.zip | tail -1   # expect 2 files
   ```

2. Check that the zip has this structure:

   ```text
   aurora-incident-business-context.zip
   └── aurora-incident-business-context/
       ├── SKILL.md                          # required: frontmatter with name and description
       └── references/
           └── evidence-sources.md
   ```

   The zip leaves out `evals/`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aurora-incident-business-context.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **Incident RCA** and **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to use it with DevOps Agent

Install the skill in your Agent Space (Investigations and/or Chat
subagents, depending on where you want business-context enrichment
available). It activates automatically once DevOps Agent is investigating
an Aurora/RDS alarm and the reasoning trace calls for business impact.

You can also invoke it on demand in chat, e.g.:

> Investigate the Aurora cluster `example-cluster` — the
> `example-cluster-connections-high` alarm is firing. Once you've found the
> technical root cause, tell me who's affected, what this costs us, and
> whether we have a compliance reporting deadline.

## Origin

Adapted from the business-context enrichment logic prototyped in the
Aurora MySQL Incident Investigation with AWS DevOps Agent demo (GenAI Ops
Demo Library), currently proposed in
[aws-samples/sample-aws-genai-ops-demos#95](https://github.com/aws-samples/sample-aws-genai-ops-demos/pull/95). That demo originally shipped this as a
Lambda-backed mock MCP server returning synthetic example data
(fictional dependency graph, a fixed revenue figure, canned compliance
thresholds) for demonstration purposes. This skill generalizes that same
reasoning into an evidence-based framework suitable for real accounts,
with no infrastructure to deploy.

The demo above shows this skill's reasoning in action against a live
incident (connection storm, CPU spike, deadlock, or failover on a real
Aurora MySQL cluster) — see its README for a runnable, end-to-end
walkthrough.
