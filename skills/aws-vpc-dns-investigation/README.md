# AWS VPC DNS Investigation

This skill tells the AWS DevOps Agent when to reach for the
[aws-vpc-dns-diagnostics MCP server](https://github.com/aws/tools-for-devops-agent/tree/main/mcp/aws-vpc-dns-diagnostics-mcp) and in
what order to use its tools, so a cold symptom like "this name will not resolve"
leads to a consistent investigation instead of an ad hoc one.

## ⚠️ Important Notice

This skill is sample code, not intended for production use without additional
review and testing. Users should validate in a non-production environment first.
It is read-only: it drives observation and simulation tools and takes no action on
your DNS configuration.

## Purpose

The MCP server's bundled runbooks tell the agent how to interpret a DNS result once
it has already decided to look. Nothing tells it when to look, or that the VPC
attribute check has to come before any interpretation. This skill supplies that
activation trigger and the investigation sequence.

The sequence matters because VPC DNS failures are ordered. `enableDnsSupport`
gates the entire VPC resolver, so a resolution result read before that attribute is
checked can be attributed to the wrong cause. Likewise, an answer from an unknown
resolver is not evidence until you know which resolver answered, and agreement
between resolvers is not the same as correctness.

## Key Capabilities

- Recognize VPC DNS symptoms from an operator's description without being told to
  use the skill
- Enforce the precondition order: VPC attributes and host context before any
  interpretation of a resolution result
- Drive live, multi-resolver comparison from inside the affected subnet, including
  resolver identity, rather than resolving from the agent's own vantage point
- Route a proposed DNS change through symbolic simulation before it is recommended
- Load the matching pattern runbook for a signature instead of reasoning from
  general knowledge
- Report cross-account opaque constructs and missing SSM reachability as boundaries
  rather than inferring past them

## Prerequisites

- The `aws-vpc-dns-diagnostics` MCP server registered in your Agent Space with its
  tools allowlisted. The server and its deployment instructions are in this
  repository at [`mcp/aws-vpc-dns-diagnostics-mcp/`](https://github.com/aws/tools-for-devops-agent/tree/main/mcp/aws-vpc-dns-diagnostics-mcp)
- The scoped IAM roles deployed in each target account, and those account IDs
  supplied in the server's `AllowedAccounts` parameter. There is no default and a
  wildcard is refused
- For the Mode A live probe tools, the target EC2 instance reachable through SSM:
  interface endpoints for `ssm`, `ssmmessages`, and `ec2messages`, and an instance
  role with `AmazonSSMManagedInstanceCore`
- No additional DevOps Agent role permissions. The agent calls the MCP server,
  which assumes its own scoped roles in the target accounts

## Limitations

- The skill is guidance only. Without the MCP server registered and allowlisted,
  none of the tools it references are callable
- Mode A requires SSM reachability to the target instance. An instance that is not
  SSM-managed can be reasoned about from configuration but not probed
- Cross-account constructs shared with the target account may be enumerable while
  their contents remain opaque. These are reported as unknown, not absent
- Simulation is symbolic. It predicts the effect of a change on resolution and does
  not apply, stage, or validate the change against the live control plane

## Agent Types

- **On-demand** - conversational DNS diagnosis and pre-change validation
- **Incident RCA** - automated investigation where a failure may have a DNS cause

## Uploading to AWS DevOps Agent

Register the `aws-vpc-dns-diagnostics` MCP server and deploy its IAM roles first (see [Prerequisites](#prerequisites)), or add the skill as **Inactive** until they're in place. The skill references the server's tools by name, and trigger behavior can't be validated until those tools are present in the Agent Space. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

This skill drives DNS diagnosis and pre-change validation on demand and checks for a DNS cause during root cause analysis, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, mitigation and evaluation included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-vpc-dns-investigation`, or filter by AWS service **Amazon Route 53**.
4. Choose **Details** and check that the agent types listed are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the tool sequence for live diagnosis in `SKILL.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-vpc-dns-investigation/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-vpc-dns-investigation.zip
   zip -r aws-vpc-dns-investigation.zip aws-vpc-dns-investigation/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-vpc-dns-investigation.zip | tail -1   # expect 1 file
   ```

2. Check that the zip has this structure:

   ```text
   aws-vpc-dns-investigation.zip
   └── aws-vpc-dns-investigation/
       └── SKILL.md                      # required: frontmatter with name and description
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-vpc-dns-investigation.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

### Chat

- "secretsmanager.us-east-1.amazonaws.com returns NXDOMAIN from this instance but works from another one."
- "Our app is reaching a public IP for a service we put behind an interface endpoint."
- "Would enabling private DNS on this VPC endpoint break anything?"
- "What would a Resolver FORWARD rule for '.' pointing at on-prem do to the names that resolve today?"
- "Show me the effective DNS configuration for this VPC, including anything inherited from a Route 53 Profile."

### Investigation

- "An application started failing after a network change last night. Resolution looks wrong from the subnet."
- "Half our instances can reach the internal API by hostname and half cannot."
- "A service endpoint stopped resolving after we associated a Route 53 Profile."
- "IPv6 clients get a different answer than IPv4 clients for the same name."

## Learn More

- [aws-vpc-dns-diagnostics MCP server](https://github.com/aws/tools-for-devops-agent/blob/main/mcp/aws-vpc-dns-diagnostics-mcp/README.md)
- [Architecture](https://github.com/aws/tools-for-devops-agent/blob/main/mcp/aws-vpc-dns-diagnostics-mcp/docs/ARCHITECTURE.md)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
