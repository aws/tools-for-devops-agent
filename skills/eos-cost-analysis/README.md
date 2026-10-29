# EOS Cost Analysis — Skill

## Purpose

Discovers AWS resources approaching or past End of Standard Support and calculates the Extended Support cost impact across your AWS environment. Covers EKS, RDS/Aurora, Lambda, ElastiCache, and OpenSearch — the services that incur Extended Support charges. It verifies each engine version's EOS date from AWS documentation, retrieves live Extended Support pricing from the AWS Pricing API, and separates the cost a customer is incurring today (reactive) from the cost that switches on as resources cross their EOS dates (proactive).

## Key Capabilities

- Discovers resources with deprecated versions across 5 AWS services (multi-account supported)
- Validates EOS dates per exact engine + version against AWS documentation (no guessing, no date bleed between engine families)
- Retrieves live Extended Support pricing from the AWS Pricing API with Year 1/2 vs Year 3 tiering
- Handles RDS Multi-AZ cost doubling and instance class to vCPU mapping
- Flags deprecated Lambda runtimes as a security risk (no ES charge but patching stops)
- Produces a structured report plus a per-resource CSV artifact, splitting current (reactive) from projected (proactive) cost

## Prerequisites

- AWS DevOps Agent space with the `use_aws` and `verify_aws_claim` tools available
- Resource discovery permissions (EKS, RDS, Lambda, ElastiCache, OpenSearch read-only `List`/`Describe` calls) are already covered by the `AIDevOpsAgentAccessPolicy` managed policy — no extra IAM is required for discovery
- For live Extended Support pricing, grant the AWS Pricing API actions (`pricing:GetProducts`, `pricing:GetAttributeValues`, `pricing:DescribeServices`) by setting `EnableEosCostAnalysis` in [`cloudformation/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies.yaml)
- For multi-account analysis: associate secondary accounts in DevOps Agent settings
- AWS Support plan: Business, Enterprise On-Ramp, or Enterprise (required for DevOps Agent)

> **Note on the OpenSearch IAM prefix:** the OpenSearch discovery actions live under the `es:` IAM prefix (`es:ListDomainNames`, `es:DescribeDomain`, `es:DescribeDomains`), even though the `use_aws` calls in SKILL.md use the `opensearch` API client name. The managed policy already grants these, so you do not need to add them yourself.

## Limitations

- Covers five services only — EKS, RDS/Aurora, Lambda, ElastiCache, and OpenSearch. Other services that may have Extended Support are out of scope.
- Cost figures are estimates based on on-demand AWS Pricing API rates; they do not account for Savings Plans, Reserved Instances, private pricing, or credits. Verify against your bill before acting.
- EOS dates depend on AWS documentation lookups at runtime. If a version's date cannot be confirmed, it is reported as `UNVERIFIED` rather than guessed.
- Scans of large organizations (hundreds or thousands of accounts) may return partial results if time or API limits are reached; the report notes which accounts completed.
- Read-only — the skill never modifies, upgrades, or deletes resources.

## Agent Types

This skill installs for **All agents** (`GENERIC`), so it loads wherever an EOS cost question comes up:

- **Chat tasks** — conversational, ad-hoc EOS cost queries and analysis
- **Custom agents** — scheduled/automated EOS posture reports through the [eos-cost-analysis custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/eos-cost-analysis), which uses the skill

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/eos-cost-analysis` directory.

**Option B: Upload as a zip file**

1. Zip the `eos-cost-analysis/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r eos-cost-analysis.zip eos-cost-analysis/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `eos-cost-analysis.zip` file (max 6 MB).
5. In the **Agent Type** field, select **"All agents"**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage the skill — useful for CI/CD pipelines or automation workflows. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

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
