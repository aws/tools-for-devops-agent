# analytics-opensearch-expertise

A read-only Amazon OpenSearch Service **domain health assessment** skill for AWS DevOps Agent. Given a domain ARN (or domain name + region), it runs control-plane API checks across cluster health, shard strategy, performance, security posture, and cost optimization, then produces a structured findings report with prioritized recommendations.

## What it does

Analyzes an OpenSearch domain across five categories:

1. **Cluster Health & Configuration** — status, node/AZ balance, dedicated masters, upgrade eligibility
2. **Storage & Shard Strategy** — EBS volume type, shard density, active vs. total shards, free storage
3. **Performance** — JVM pressure, CPU, search/indexing latency, HTTP errors, cluster status history
4. **Security & Access** — encryption at rest, node-to-node encryption, HTTPS enforcement, network exposure, access policy, fine-grained access control
5. **Cost Optimization** — instance right-sizing, storage tiering, reserved instance coverage

It is **100% control-plane / API-driven** — no data-plane access (no `_cluster/*` calls, no index reads), which makes it compatible with DevOps Agent without a custom MCP server.

## Prerequisites

**IAM permissions** the DevOps Agent execution role needs (all read-only):

- `es:DescribeDomain`
- `es:DescribeDomainHealth`
- `es:GetCompatibleVersions`
- `es:DescribeReservedInstances`
- `es:ListDomainNames`
- `cloudwatch:GetMetricData`

Most are covered by `AIDevOpsAgentAccessPolicy`; attach the supplemental policy for any gaps.

**AWS resources:** one or more OpenSearch Service domains in the target account/region.

## Uploading to AWS DevOps Agent

Check that the DevOps Agent role has the IAM permissions in [Prerequisites](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs an on-demand domain health assessment that you ask for in chat and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add assessment context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `analytics-opensearch-expertise`, or filter by AWS service **Amazon OpenSearch Service**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust the recommendations in `references/remediation-reference.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/analytics-opensearch-expertise/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f analytics-opensearch-expertise.zip
   zip -r analytics-opensearch-expertise.zip analytics-opensearch-expertise/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l analytics-opensearch-expertise.zip | tail -1   # expect 2 files
   ```

2. Check that the zip has this structure:

   ```text
   analytics-opensearch-expertise.zip
   └── analytics-opensearch-expertise/
       ├── SKILL.md                          # required: frontmatter with name and description
       └── references/
           └── remediation-reference.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `analytics-opensearch-expertise.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to use it with DevOps Agent

1. Add the skill to your Agent Space with the **On-demand** agent type, as described in [Uploading to AWS DevOps Agent](#uploading-to-aws-devops-agent).
2. Prompt in natural language without naming the skill, e.g.:
   - "Is my OpenSearch domain healthy? ARN: `arn:aws:es:us-east-1:123456789012:domain/my-domain`"
   - "Review the cluster configuration and security posture of this OpenSearch domain."
   - "Are there any cost savings available on my OpenSearch setup?"
3. Review the agent's reasoning trace to confirm the skill activated and the checks ran.

If the agent does not invoke the skill, refine the `description` field in `SKILL.md` (see "Optimizing description" in the Agent Skills specification).

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

## Maintainers

- genedragon
- prasadnu
