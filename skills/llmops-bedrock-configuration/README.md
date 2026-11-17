# llmops-bedrock-configuration

> **Non-production.** This skill performs a **read-only** Amazon Bedrock configuration and access
> review and produces derived operational guidance. It is not an AWS service, carries no SLA, and its
> severity windows are operational guidance — not AWS-published commitments. Validate every remediation
> against current AWS documentation before acting in a production account.

## What It Does

Reviews an Amazon Bedrock deployment for **configuration correctness and model access** and renders a
posture report. It runs the **LLM-INV** check family (LLM-INV-001 through LLM-INV-015):

- Model invocation logging enabled, delivering, and encrypted (001 / 005 / 010)
- Cross-region inference profiles vs bare model IDs (002)
- Model lifecycle / deprecation (003)
- Least-privilege `bedrock:InvokeModel*` IAM scope (004)
- Streaming vs buffered, Converse API adoption, batch vs on-demand, `maxTokens`, throttle handling, Prompt Management (006–009, 011, 012)
- Access denial — IAM implicitDeny vs SCP explicitDeny, and model access + marketplace subscription (013 / 014 / 015)

Every finding carries a check-id, a severity, and an AWS-doc citation. The skill is read-only and
never mutates a resource.

This skill belongs to the `llmops-agent` custom agent, which is fully self-contained and has no
external skill dependencies.

## Prerequisites

Read-only (or least-privilege) credentials granting these actions:

- `bedrock:GetModelInvocationLoggingConfiguration`
- `bedrock:ListFoundationModels`, `bedrock:GetFoundationModel`
- `bedrock:ListInferenceProfiles`, `bedrock:GetInferenceProfile`
- `bedrock:GetFoundationModelAvailability` (AWS CLI 2.27.42 or later)
- `bedrock:ListModelInvocationJobs`, `bedrock:ListPrompts`
- `iam:ListRoles`, `iam:GetRole`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`,
  `iam:GetRolePolicy`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:SimulatePrincipalPolicy`
- `organizations:DescribeOrganization`; `organizations:ListPoliciesForTarget` and
  `organizations:DescribePolicy` work only from the management account or a delegated administrator
- `cloudtrail:LookupEvents` (InvokeModel and Converse are management events)
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData` (`AWS/Bedrock` invocation and log-delivery metrics)
- `logs:DescribeLogGroups`, `logs:DescribeLogStreams`, `logs:DescribeMetricFilters`, `logs:StartQuery`,
  `logs:GetQueryResults`
- For an S3 logging destination: `s3:GetEncryptionConfiguration`, `s3:GetBucketPolicyStatus`,
  `s3:GetBucketPublicAccessBlock`, `s3:ListBucket`

Several of these are often denied (the DevOps Agent role is denied `iam:SimulatePrincipalPolicy`).
The skill records each denied call, uses the fallback in `references/diagnosis-playbook.md`, and
discloses what stays unconfirmed.

## Uploading to AWS DevOps Agent

Build the skill archive so `SKILL.md` sits at the **root** of the zip (zip from inside the skill
directory):

```
cd skills/llmops-bedrock-configuration && zip -r ../llmops-bedrock-configuration.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

**Select Agent Type "All agents" when uploading.** A custom agent (such as `llmops-agent`) cannot load
a skill that is scoped to a narrower agent type — scoping to anything other than "All agents" makes the
skill invisible to the custom agent.

## Usage

Examples that trigger this skill:

- "Is my Bedrock set up correctly? Check my configuration."
- "`InvokeModel` is returning `AccessDeniedException` — is it IAM, an SCP, or model access?"
- "Is model invocation logging enabled, and is it encrypted?"
- "Are we calling a bare model ID instead of a cross-region inference profile?"
- "Is the model we use deprecated or end-of-life?"
- "Is `bedrock:InvokeModel` scoped to specific model ARNs or wildcarded?"

The agent runs the read-only review procedure and returns findings against
`assets/bedrock-configuration-report-template.md`.

## Author

Ankur Sinha

## Version History

See the `CHANGELOG.md` file in this directory.
