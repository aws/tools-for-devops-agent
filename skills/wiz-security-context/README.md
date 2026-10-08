# Wiz Security Context

This skill enables the AWS DevOps Agent to query the Wiz MCP server during an operational investigation, adding security context from the Wiz Security Graph so the agent can tell an operational issue apart from a security incident.

## ⚠️ Important Notice

This skill is provided as sample code. It is read-only - it queries the Wiz MCP server for security context and does not take any action on your resources. Before relying on it in production, validate its behavior in a non-production environment and confirm the authenticating Wiz user has only the read permissions it needs.

## Security and Trust

This skill is intentionally a thin stub. Rather than embedding the workflow, it directs AWS DevOps Agent to fetch the current security-auditing workflow from the `devops_resource_auditing_skill` tool on your own Wiz MCP server. That workflow comes from a first-party, trusted source:

- The Wiz MCP server is one you explicitly register, authenticate to via OAuth, and allowlist in your Agent Space - not arbitrary external content.
- The fetched workflow is read-only guidance for querying Wiz; it drives no changes to your resources.
- Keeping the workflow server-side lets Wiz maintain and improve it as new capabilities ship, so you always run the current version without updating this skill.

## Purpose

Operational incidents and security incidents often start with the same symptoms. A CPU spike could be a scaling problem or a cryptominer. A latency anomaly could be a bad deployment or data exfiltration. Operational telemetry alone cannot distinguish the two. This skill has the AWS DevOps Agent query Wiz for the affected resource's security context - vulnerabilities, misconfigurations, exposed secrets, data findings, active threats, malware, detections, and toxic combinations - and classify the situation as an operational issue, a security issue, or a Wiz coverage gap, so the right response path is chosen before a human has to switch tools.

## Key Capabilities

- Resolve an affected AWS resource in the Wiz inventory from an ID, ARN, name, or IP
- Retrieve the resource's security posture: vulnerabilities, misconfigurations, exposed secrets, data findings, active threats, malware, and detections
- Surface exploitable, internet-exposed, and toxic-combination risks that turn an operational symptom into a likely incident
- Classify the situation as operational, security-related, or a coverage gap, with the Wiz evidence behind the decision
- Confirm when a resource is clean, letting the investigation confidently rule out a security cause

## Prerequisites

- A Wiz tenant monitoring the affected AWS account
- The Wiz MCP server registered in your Agent Space, with the `?toolset=devops` tools allowlisted. Register the endpoint `https://mcp.app.wiz.io/?toolset=devops`, which exposes the `devops_resource_auditing_skill` tool used to fetch the workflow. The fetched workflow directs the agent to call the other `?toolset=devops` tools, so allowlist the full toolset. All of these tools are read-only, so allowlisting the toolset preserves the read-only guarantee
- OAuth authentication as a Wiz user with permission to read resources, findings, issues, threats, and detections

## Limitations

- This skill is a stub. It depends on the `devops_resource_auditing_skill` tool being available on the connected Wiz MCP server. If the server is unreachable or the tool is not allowlisted, the workflow cannot be fetched
- Security context is only available for resources monitored by Wiz. Resources not connected to Wiz are reported as a coverage gap
- Findings are only as current as the most recent Wiz scan of the resource
- The skill reads security context and classifies the situation; it does not take remediation actions on the resource

## Agent Types

This skill is used by the following agent types:

- **Chat tasks** - conversational security-context lookups for a resource
- **Incident RCA** - automated root cause analysis where an operational anomaly may have a security cause

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/wiz-security-context` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository, including this one, even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `wiz-security-context/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r wiz-security-context.zip wiz-security-context/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `wiz-security-context.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks** and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills - useful for CI/CD pipelines or automation workflows. Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

### Chat

- "Is the CPU spike on instance i-0abc123def456789 a security issue or an operational one?"
- "Check whether the database sending unusual outbound traffic has any active threats or exposed secrets in Wiz."
- "Does the web server throwing 500 errors have any exploitable, internet-facing vulnerabilities?"
- "Is this resource monitored by Wiz, and does it have any open critical findings?"

### Investigation

- "Investigate a CPU spike on our backend service - it could be a scaling problem or a compromise."
- "The checkout service started failing with no recent deployment. Check whether this is security-related."
- "We're seeing unexpected outbound traffic from an EC2 instance. Determine if it is an operational issue or an active attack."
- "Latency jumped on an internet-facing service. Rule out a security cause before we scale."

## Learn More

- [Build AI Security Agents with Wiz MCP](https://www.wiz.io/blog/introducing-wiz-mcp)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
