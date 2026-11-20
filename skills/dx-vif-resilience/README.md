# dx-vif-resilience

> **⚠️ Sample code:** This skill is sample code, not intended for production
> use without additional review and testing. Validate in a non-production
> environment first.

Assesses **Layer-3 failover resilience** across redundant AWS Direct Connect
virtual interfaces: whether the same prefixes are actually exchanged across
redundant VIFs, in both directions (routes received from on-prem and routes
advertised by AWS). Layer-1/2 redundancy (connections, locations, devices) is
commonly reviewed; asymmetric BGP prefix advertisement — a silent blackhole
that only appears during real failover — rarely is. This skill closes that gap.

## What it does

1. Discovers the DX estate (connections, VIFs, gateways, resiliency groups).
2. Resolves intended redundant VIF sets: confirmed intent (memory) → declared
   intent (resiliency groups) → inference (gateway attachment, type, ASN) →
   user confirmation.
3. Runs deterministic CIDR coverage analysis per set, both directions, via the
   companion [`dx-resilience-mcp`](../../mcp/dx-resilience-mcp/) server.
4. Reports gaps, partial-supernet residuals, empty tables, default routes,
   device-diversity issues, and broken resiliency-group pairings — with
   plain-language customer actions.

**Strictly read-only.** The skill never mutates anything; the companion MCP
server's IAM role cannot be granted any mutating action.

## Prerequisites

- Deploy and register the [`dx-resilience-mcp`](../../mcp/dx-resilience-mcp/)
  server in your Agent Space (SAM template included there).
- The connected account must own the Direct Connect VIFs (read-only
  `directconnect:Describe*/List*/Get*` is granted by the MCP server's template).

## Uploading to AWS DevOps Agent

Deploy and register the [`dx-resilience-mcp`](https://github.com/aws/tools-for-devops-agent/blob/main/mcp/dx-resilience-mcp/) server first (see [Prerequisites](#prerequisites)), or add the skill as **Inactive** until it's done. Register it as `dx-resilience-mcp`: the skill's `enable_tools` IDs use that prefix, and the catalog copy can't be edited. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs Direct Connect resilience audits that an operator asks for in chat, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `dx-vif-resilience`, or filter by AWS service **AWS Direct Connect**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the `enable_tools` prefix in `SKILL.md` if you registered the MCP server under another name, or to choose different agent types.

1. Clone the repository, make your changes under `skills/dx-vif-resilience/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f dx-vif-resilience.zip
   zip -r dx-vif-resilience.zip dx-vif-resilience/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l dx-vif-resilience.zip | tail -1   # expect 3 files
   ```

2. Check that the zip has this structure:

   ```text
   dx-vif-resilience.zip
   └── dx-vif-resilience/
       ├── SKILL.md                # required: frontmatter with name and description
       └── references/
           ├── report-template.md
           └── dx-bgp-resilience-concepts.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `dx-vif-resilience.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## Usage

Example chat prompts (no need to name the skill):

- "Is my Direct Connect setup resilient? Will failover actually work?"
- "Check whether the same prefixes are advertised over dxvif-aaa and dxvif-bbb."
- "We lost traffic when a DX connection went down last month — audit our VIF route symmetry."

For recurring audits, use the companion
[`dx-resilience-auditor`](../../custom-agents/dx-resilience-auditor/) custom
agent with a schedule trigger.

## Agent types

Generic (Chat / On-demand recommended).
