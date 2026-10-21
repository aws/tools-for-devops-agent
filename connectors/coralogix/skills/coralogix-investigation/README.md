# Coralogix Investigation

This skill teaches AWS DevOps Agent to query Coralogix logs, traces and metrics through the Coralogix MCP server during incident investigations and troubleshooting chats.

## ⚠️ Important Notice

This skill is provided as sample code. It is read-only: it queries Coralogix and does not change anything in your Coralogix account or your AWS resources. Before relying on it in production, validate its behavior in a non-production environment and confirm that the Coralogix API key the connection uses has only the read permissions it needs.

## Purpose

During an incident, much of the evidence often sits in Coralogix: the error logs, the failing spans and the metrics that show when the problem started. AWS DevOps Agent can call the Coralogix MCP tools without this skill, but it may filter on field names that do not exist in your account, pull raw logs instead of aggregates, or read an empty result as proof that nothing failed. This skill gives the agent a repeatable workflow: set the incident and baseline windows, find the service's names in Coralogix, measure the symptom with aggregate queries, find what changed, confirm with a few raw records, and report each finding with the query and numbers behind it.

## Key Capabilities

- Find the Coralogix application, subsystem, span service and metric labels that belong to an affected service or alert
- Find when errors started, which error templates are new, and how the incident compares with a baseline
- Find failing or slow operations, downstream calls and database calls from spans and Span Metrics
- Follow one request across services by trace ID and find its logs
- Find and check CPU, memory and other saturation metrics for the affected workload
- Report findings with the query, time window and numbers behind each one, and state what could not be checked

## Prerequisites

- A Coralogix account connected to your Agent Space, either through the Coralogix connector or with the Coralogix MCP server registered as a custom MCP server. See [Connect AWS DevOps Agent to Coralogix](https://coralogix.com/docs/user-guides/mcp-server/aws-devops-agent/)
- A dedicated personal Coralogix API key with read access to the data the agent queries: Query logs, Query metrics and Query spans (`ReadData`)
- These tools allowlisted in the Agent Space: `query_dataprime`, `query_promql_instant` and `query_promql_range`. All three are read-only
- For span and trace queries, traces sent to Coralogix. For the span-metric PromQL patterns, Coralogix Span Metrics enabled

## Limitations

- The skill reads data only. It does not create or change alerts, dashboards or any other Coralogix configuration
- Coralogix documents that MCP queries read archive storage, so logs kept only in Frequent Search may not appear in results
- Field names in the log body and infrastructure metric names depend on how each account sends data. The agent spends a few extra queries to find them
- Span and Span Metrics patterns need traces in Coralogix. Without them, the agent relies on logs and metrics
- Tool names match version 2 of the Coralogix MCP server tool set
- Real User Monitoring (RUM) data is covered only by a short pointer in the reference

## Agent Types

This skill is used by the following agent types:

- **Incident Triage** - checks whether an alert reflects a real change in errors, latency or traffic
- **Incident RCA** - gathers log, trace and metric evidence for the root cause
- **Chat tasks** - answers questions about service behavior from Coralogix data

## Uploading to AWS DevOps Agent

When you connect Coralogix from **Add a capability**, the console offers this skill for a one-click install. You can also add it in any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/coralogix-investigation` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository, including this one, even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `coralogix-investigation/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r coralogix-investigation.zip coralogix-investigation/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `coralogix-investigation.zip` file (max 6 MB).
5. Select the agent types: **Incident Triage**, **Incident RCA** and **Chat tasks**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage skills from code, for example in a CI/CD pipeline. Assign the skill to the `INCIDENT_TRIAGE`, `INCIDENT_RCA` and `CHAT` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

### Chat

- "Show me the error logs for the checkout service in Coralogix over the last hour, grouped by message."
- "Did p95 latency for the payments API change compared with yesterday?"
- "Which downstream call is failing for the orders service?"
- "Find the logs in Coralogix for trace 4bf92f3577b34da6a3ce929d0e0e4736."

### Investigation

- An investigation opened by a Coralogix alert, such as "High 5xx rate on api-gateway"
- "The checkout service started failing at 14:05 UTC. Find what changed."
- "Latency on the payments API doubled after the last deployment. Find the slow operation or dependency."
- "Orders are timing out. Check whether the database calls or the pods' CPU and memory explain it."

## Learn More

- [Connect AWS DevOps Agent to Coralogix](https://coralogix.com/docs/user-guides/mcp-server/aws-devops-agent/)
- [Coralogix MCP server tool catalog](https://coralogix.com/docs/user-guides/mcp-server/tools/catalog/)
- [DataPrime reference](https://coralogix.com/docs/dataprime/introduction/welcome-to-the-dataprime-reference/)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
