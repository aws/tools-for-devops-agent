# EOS Cost Analysis — Skill

## Purpose

Discovers AWS resources approaching or past End of Standard Support and calculates the Extended Support cost impact across your AWS environment. Covers EKS, RDS/Aurora, Lambda, ElastiCache, and OpenSearch — the services that incur Extended Support charges. It verifies each engine version's EOS date from AWS documentation, retrieves live Extended Support pricing from the AWS Pricing API, and separates the cost a customer is incurring today (reactive) from the cost that switches on as resources cross their EOS dates (proactive).

## Key Capabilities

- Discovers resources with deprecated versions across 5 AWS services (multi-account supported)
- Validates EOS dates per exact engine + version against AWS documentation (no guessing, no date bleed between engine families)
- Retrieves live Extended Support pricing from the AWS Pricing API with Year 1/2 vs Year 3 tiering
- Counts every billed RDS instance (Multi-AZ standbys, read replicas), prices Aurora members one by one, and prices Aurora Serverless v2 per ACU-hour
- Prices OpenSearch from the published normalization factors, and at the instance's own rate during an extension period
- Flags deprecated Lambda runtimes as a security risk (no ES charge but patching stops)
- Produces a structured report plus a per-resource CSV artifact, splitting current (reactive) from projected (proactive) cost

## Prerequisites

- AWS DevOps Agent space with the `use_aws` and `verify_aws_claim` tools available
- Resource discovery permissions (EKS, RDS, Lambda, ElastiCache, OpenSearch read-only `List`/`Describe` calls) are already covered by the `AIDevOpsAgentAccessPolicy` managed policy — no extra IAM is required for discovery
- For live Extended Support pricing, grant the AWS Pricing API actions (`pricing:GetProducts`, `pricing:GetAttributeValues`, `pricing:DescribeServices`) by setting `EnableEosCostAnalysis` in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml)
- For multi-account analysis: associate secondary accounts in DevOps Agent settings

> **Note on the OpenSearch IAM prefix:** the OpenSearch discovery actions live under the `es:` IAM prefix (`es:ListDomainNames`, `es:DescribeDomain`, `es:DescribeDomains`), even though the `use_aws` calls in SKILL.md use the `opensearch` API client name. The managed policy already grants these, so you do not need to add them yourself.

## Limitations

- Covers five services only — EKS, RDS/Aurora, Lambda, ElastiCache, and OpenSearch. Other services that may have Extended Support are out of scope.
- Cost figures are estimates based on on-demand AWS Pricing API rates; they do not account for Savings Plans, Reserved Instances, private pricing, or credits. Verify against your bill before acting.
- EOS dates depend on AWS documentation lookups at runtime. If a version's date cannot be confirmed, it is reported as `UNVERIFIED` rather than guessed, and kept out of the totals.
- Aurora Serverless v2 cost depends on ACU usage. Without CloudWatch `ServerlessDatabaseCapacity` data it is reported as `USAGE_DEPENDENT`, with the rate and capacity range.
- The OpenSearch normalization factors and the extension-period version list in `references/billing-rules.md` are dated copies of AWS documentation and must be kept current.
- Scans of large organizations (hundreds or thousands of accounts) may return partial results if time or API limits are reached; the report notes which accounts completed.
- Read-only — the skill never modifies, upgrades, or deletes resources.

## Agent Types

This skill installs for **Generic** (`GENERIC`), so it loads wherever an EOS cost question comes up:

- **On-demand** — conversational, ad-hoc EOS cost queries and analysis
- **Custom agents** — scheduled/automated EOS posture reports through the [eos-cost-analysis custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/eos-cost-analysis), which uses the skill

## Uploading to AWS DevOps Agent

Grant the AWS Pricing API permissions listed in [Prerequisites](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **Generic** (`GENERIC`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **Generic** recommended | Yes: files and agent types | Re-upload a new zip |

This skill uses **Generic**, so it loads for every agent type. That lets it answer ad-hoc EOS cost questions on demand and also lets the [eos-cost-analysis custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/eos-cost-analysis) load it for scheduled reports.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `eos-cost-analysis`, or filter by AWS service such as **Amazon RDS** or **Amazon EKS**.
4. Choose **Details** and check that the agent type is **Generic**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to refresh the OpenSearch normalization factors or extension-period versions in `references/billing-rules.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/eos-cost-analysis/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f eos-cost-analysis.zip
   zip -r eos-cost-analysis.zip eos-cost-analysis/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l eos-cost-analysis.zip | tail -1   # expect 2 files
   ```

2. Check that the zip has this structure:

   ```text
   eos-cost-analysis.zip
   └── eos-cost-analysis/
       ├── SKILL.md                          # required: frontmatter with name and description
       └── references/
           └── billing-rules.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `eos-cost-analysis.zip`, or browse to it.
6. For **Agent Type**, leave **Generic** selected.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

### Chat (ad-hoc)

Upload the skill and ask EOS-related questions directly in the built-in DevOps Agent chat:

- "What's my EOS cost exposure?"
- "Check which EKS clusters are in Extended Support"
- "Full EOS analysis across all services and accounts"
- "What RDS instances are approaching end of support?"

### Custom agent (scheduled/automated)

Create a dedicated custom agent for recurring runs that produce reports on a weekly or monthly cadence — no human prompt needed. See the [eos-cost-analysis custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/eos-cost-analysis) for setup, then:

- Configure a weekly or monthly schedule under the agent's settings
- Each run produces a new artifact version, so you can track EOS cost drift week over week

## Related

- [eos-cost-analysis custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/eos-cost-analysis) — system prompt and setup guide for the dedicated agent
- [eks-upgrade-readiness skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/eks-upgrade-readiness) — for EKS upgrade execution and pre-upgrade readiness checks once this skill has flagged a cluster's EOS cost exposure
- [analytics-opensearch-expertise skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/analytics-opensearch-expertise) — for OpenSearch domain health assessments beyond version lifecycle and EOS cost
- [Amazon RDS Extended Support](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/extended-support.html)
- [Amazon ElastiCache Extended Support](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/extended-support-versions.html)
- [Amazon OpenSearch Service version support](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html#choosing-version)

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without
> additional review and testing. Validate in a non-production environment first.
> Cost figures are estimates based on on-demand AWS Pricing API rates and AWS
> documentation lookups at runtime; verify against your bill before making decisions.
