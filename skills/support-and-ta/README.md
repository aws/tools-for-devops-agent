# Support Cases & Critical Trusted Advisor Report Skill

This skill enables the AWS DevOps Agent to produce a combined reliability report: the top AWS services generating support cases (grouped by service and account) alongside the Trusted Advisor recommendations that need immediate attention (error/red status), each tagged with the account ID, and the overlap between the two.

> ⚠️ **Non-production disclaimer:** This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

## Purpose

Support-case volume and critical Trusted Advisor findings are stronger signals together than apart: a service with both rising case volume and a red Trusted Advisor finding in the same account is a recurring operational risk rather than an isolated incident. This skill gathers both data sets, ranks and filters them, and cross-references them per account so teams can focus on what needs action first.

## Key Capabilities

- Ranks the **top 5 AWS services** by support case count (per account) over a configurable window (default: trailing 12 months)
- Surfaces **critical (error/red) Trusted Advisor recommendations** per account, with flagged resource counts and regions
- **Cross-references** the two data sets to flag account/service pairs that appear in both
- Always tags findings with the **account ID** so multi-account results stay unambiguous
- Structures the output as a three-section report suitable for a recurring daily/periodic run

## Prerequisites

- An AWS DevOps Agent space
- The Optira support-case insights MCP server deployed and connected to your Agent Space as a capability provider, exposing the `get_support_insights` and `get_trusted_advisor_recommendations` tools. This MCP server is maintained in its own repository — deploy and register it from there: [`optira-core/es-optira-mcp`](https://github.com/aws-solutions-library-samples/guidance-for-generating-support-case-insights-on-aws/tree/main/optira-core/es-optira-mcp)
- Underlying data access required by that MCP server: an AWS Support plan (Business, Enterprise On-Ramp, or Enterprise) and Trusted Advisor data collected into the Optira data foundation

> This skill reaches AWS Support and Trusted Advisor **only** through the connected MCP server's tools — it does not call the Support or Trusted Advisor APIs directly, so no additional agent IAM permissions are required for the skill itself.

## Limitations

- Support case data is only available for up to 24 months after creation (upstream Support API limit)
- Trusted Advisor "critical" is scoped to `status: error` findings only; `warning`/`ok` items are out of scope for the critical section
- The support-case section is intentionally limited to the top 5 services by case count, not an exhaustive list
- Accuracy of counts and identifiers depends on the MCP server's underlying data being current

## Agent Types

This skill is used by the following agent types:

- **Chat tasks** — on-demand or recurring combined support-case and Trusted Advisor reporting

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/support-and-ta` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** If you also plan to use this skill from the `support-and-ta-report` custom agent, choose **"All agents"** in the "Agent Type" field when importing, so the custom agent can load it.

**Option B: Upload as a zip file**

1. Zip the `support-and-ta/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r support-and-ta.zip support-and-ta/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `support-and-ta.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks** (or **All agents** if pairing with the custom agent).
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills — useful for CI/CD pipelines or automation workflows. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

This skill is most suitable for chat and recurring reporting. Below are sample prompts.

### Chat

- "Give me a combined support case and critical Trusted Advisor report for all accounts over the last 12 months."
- "Which are the top 5 services by support case count per account, and do any have red Trusted Advisor findings?"
- "List all Trusted Advisor recommendations in error status by account, and flag any that overlap with our highest-volume support-case services."
- "Produce today's support and Trusted Advisor reliability report."

### Recurring (custom agent)

Pair this skill with the [`support-and-ta-report`](../../custom-agents/support-and-ta-report/) custom agent to run it on a schedule and refresh a persisted "Daily Support & Trusted Advisor Report" artifact.

## Related

- [Optira support-case insights MCP server](https://github.com/aws-solutions-library-samples/guidance-for-generating-support-case-insights-on-aws/tree/main/optira-core/es-optira-mcp) — the external MCP server (its own repository) that provides the `get_support_insights` and `get_trusted_advisor_recommendations` tools this skill uses
- [support-and-ta-report custom agent](../../custom-agents/support-and-ta-report/) — runs this skill on a schedule and maintains the report artifact
