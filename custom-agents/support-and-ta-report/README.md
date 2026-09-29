# Daily Support & Trusted Advisor Report — Custom Agent

> ⚠️ **Non-production disclaimer:** This custom agent is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

## Purpose

This custom agent produces a daily reliability report that combines two signals: the top 5 AWS services generating the most support cases (per account) and the Trusted Advisor recommendations in error/red status that need immediate attention (per account). It highlights overlap between the two and rolls everything into a prioritized "Improvements" list, refreshing a single persisted artifact on each run so the report stays current without duplicating.

## Key Capabilities

- Ranks the top 5 AWS services by support case count per account over the trailing 12 months
- Lists all critical (error/red) Trusted Advisor recommendations per account
- Cross-references the two data sets to flag compounding risk (same account/service in both)
- Builds a tiered **Improvements** list (HIGHEST / HIGH / MEDIUM) that covers every critical Trusted Advisor finding and every top-5 support-case row exactly once
- Writes a text summary to the run journal and maintains a single "Daily Support & Trusted Advisor Report" artifact (refresh, not duplicate)

## Important behavior note

Custom agents in AWS DevOps Agent execute as **asynchronous invocations** — "Run Now" on the agent page and "run the agent" in Chat both kick off a background run tracked in the **History** tab. This is platform behavior and cannot be switched to an interactive session ([Executing custom agents](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html)). This agent is well suited to a **schedule trigger** for a recurring morning report.

## Prerequisites

- An AWS DevOps Agent space
- The [`support-and-ta` skill](../../skills/support-and-ta/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose **"All agents"** in the "Agent Type" field when importing the skill, even though the skill's README lists "Chat tasks"
- The Optira support-case insights MCP server deployed and connected to your Agent Space as a capability provider, registered with the server name **`optirainsight-lambda-mcp`** so the tool names match this agent's system prompt (`optirainsight-lambda-mcp_get_support_insights`, `optirainsight-lambda-mcp_get_trusted_advisor_recommendations`). This MCP server is maintained in its own repository — deploy and register it from there: [`optira-core/es-optira-mcp`](https://github.com/aws-solutions-library-samples/guidance-for-generating-support-case-insights-on-aws/tree/main/optira-core/es-optira-mcp)
- The underlying data access that MCP server requires: an AWS Support plan (Business, Enterprise On-Ramp, or Enterprise) and Trusted Advisor data collected into the Optira data foundation
- No direct AWS CLI or Support/Trusted Advisor API access is needed for the agent itself — all data access goes through the connected MCP server

> If you register the MCP server under a different name, update the tool names in `SYSTEM_PROMPT.md` accordingly — the prefix must match the registered server name.

## Creating the Agent

The MCP server must already be registered as an account-level capability provider and connected to your Agent Space before creating this agent — see [Prerequisites](#prerequisites) above and the MCP server's own repository: [`optira-core/es-optira-mcp`](https://github.com/aws-solutions-library-samples/guidance-for-generating-support-case-insights-on-aws/tree/main/optira-core/es-optira-mcp).

1. In the DevOps Agent web app, go to the **Agents** page.
2. In the **Custom Agents** section, click **Create agent**, then click **Form**.
3. Fill out the form:
   - **Name** — `support-and-ta-report` (lowercase letters, numbers, hyphens only).
   - **System prompt** — copy the content of `SYSTEM_PROMPT.md` from this directory and paste it in.
   - **Skills** — select the `support-and-ta` skill.
   - **Tools** — select `get_support_insights` and `get_trusted_advisor_recommendations` from the `optirainsight-lambda-mcp` MCP server.
4. Click **Create agent**, then verify both tools appear under **Tools** on the agent's page. Without them, the agent cannot reach support-case or Trusted Advisor data at all.

> Only the MCP tools need to be assigned. Producing **artifacts** and **recommendations** is a built-in capability of every custom agent — the agent activates those tools automatically from the system prompt's instructions, with no assignment or extra skill required ([Custom agent outputs](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-custom-agent-outputs.html)).

### Alternative: assign tools through Chat

You can also add or change tools on an existing agent through Chat — useful when editing an agent you already created:

1. On the agent's page, click **Edit**, then select **Chat**. A new chat opens.
2. Once DevOps Agent finishes loading the agent's context, type:

   ```text
   Add the get_support_insights and get_trusted_advisor_recommendations tools from the optirainsight-lambda-mcp MCP server to this custom agent.
   ```

## Executing the Agent

You can execute the agent on-demand from the custom agent page (**Run Now**), on a schedule (recommended for the daily morning report), or through Chat. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) for more information. You can also pass a custom prompt, for example to change the reporting window:

- "Run the support-and-ta-report agent for the last 6 months instead of 12."

Track progress and results on the agent's page under the **History** tab. The report is persisted on the **Artifacts** page as "Daily Support & Trusted Advisor Report" and is refreshed in place on each run.

## Related

- [support-and-ta skill](../../skills/support-and-ta/) — the domain knowledge and report structure this agent follows
- [Optira support-case insights MCP server](https://github.com/aws-solutions-library-samples/guidance-for-generating-support-case-insights-on-aws/tree/main/optira-core/es-optira-mcp) — the external MCP server (its own repository) that provides the `get_support_insights` and `get_trusted_advisor_recommendations` tools
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
