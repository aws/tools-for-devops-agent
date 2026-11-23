# aws-routing skill

An AWS routing subject matter expert skill for path selection, BGP traffic engineering, and route
evaluation across AWS networking services (Cloud WAN, Direct Connect, Transit Gateway, VPC, VPN).
It provides **read-only** analysis, recommendations, and troubleshooting grounded in public AWS
documentation and field-proven patterns.

## What it does

- Explains and applies the route-evaluation order for Cloud WAN CNEs, DXGW path selection, TGW route
  tables, and VPC route tables.
- Advises on BGP traffic engineering: LP communities (`7224:7100/7200/7300`), AS-path prepending
  (within-region only), MED, and longest-prefix-match.
- Analyzes DX + VPN redundancy, active/active vs active/passive, and failover behavior.
- Flags non-deterministic path selection and recommends deterministic alternatives.
- Produces read-only validation commands (`describe-*`, `get-*`, `list-*`).

## Prerequisites

- No write permissions required — the skill is read-only.
- To run the suggested validation commands, the operator needs read-only access to the relevant
  networking APIs (e.g., `ec2:Describe*`, `directconnect:Describe*`, `networkmanager:Get*`).

## Uploading to AWS DevOps Agent

The skill is read-only and needs no setup in your Agent Space. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

This skill answers routing design questions on demand and explains path selection during root cause analysis, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, mitigation and evaluation included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-routing`, or filter by AWS service **AWS Transit Gateway**.
4. Choose **Details** and check that the agent types listed are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to add your own design patterns to `references/tgw-routing-patterns.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-routing/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-routing.zip
   zip -r aws-routing.zip aws-routing/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-routing.zip | tail -1   # expect 6 files
   ```

2. Check that the zip has this structure:

   ```text
   aws-routing.zip
   └── aws-routing/
       ├── SKILL.md                      # required: frontmatter with name and description
       └── references/
           ├── tgw-routing-patterns.md
           ├── dx-routing-patterns.md
           ├── cloudwan-dx-routing-patterns.md
           ├── vpn-dx-redundancy-patterns.md
           └── networking-strategic-questions.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-routing.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to use it

Ask routing questions in natural language, for example:
- "Why is my Cloud WAN traffic for an aggregate prefix leaving the local region instead of using the
  local Direct Connect?"
- "How do I make a Transit Gateway prefer one Direct Connect location over another?"
- "Is my DX + VPN design active/active or active/passive, and will failover be deterministic?"

The skill will trace the path, apply the evaluation logic, cite the relevant AWS documentation, and
suggest read-only commands to validate.

## Structure

```
aws-routing/
├── SKILL.md            # Activation metadata + instructions
├── references/         # Detailed routing mechanics and patterns
├── README.md           # This file
├── CHANGELOG.md        # Version history
└── evals/              # Functional and trigger tests
```

## Disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and
> testing. Validate all routing guidance in a non-production environment first. Recommendations are
> based on public AWS documentation and field experience and may change as AWS services evolve.
