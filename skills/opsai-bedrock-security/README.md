# opsai-bedrock-security

> **Non-production.** This skill performs a **read-only** review of Amazon Bedrock security and
> produces derived operational guidance. It is not an AWS service, carries no SLA, and changes nothing.
> Validate every remediation against current AWS documentation before acting in a production account.

## Purpose

`opsai-bedrock-security` reviews the two sides of Amazon Bedrock security:

- **Who can call Bedrock.** It audits the long-lived credentials that can invoke Amazon Bedrock models
  (IAM user access keys, root access keys, and long-term Amazon Bedrock and Claude Platform on AWS API
  keys), decides for each whether it can invoke models and how exposed it is, and names the one
  action to take first.
- **What protects the calls.** It reviews Amazon Bedrock Guardrails: whether a production model path has
  a guardrail, whether it is strong enough, blocks rather than only detects, is the version production
  enforces, and was ever validated. It also troubleshoots guardrail behaviour, limits and latency,
  including how-to questions with no account to read.

It merges the earlier Bedrock permissions audit and guardrails skills into one
install.

## Key Capabilities

- Runs the **LLM-BPA** check family for long-lived credentials and the **LLM-GRD** family for
  guardrails. Each finding carries a check-id, a tier or severity, and an AWS-doc citation.
- Evaluates each IAM user's policies with written steps, because AWS DevOps Agent's AWS tool does not
  run the IAM policy simulator, and says when GRANT is `unknown` and why.
- Inventories long-term Bedrock API keys, plans their phase-out, triages GuardDuty AI Protection
  findings such as `Impact:IAMUser/AnomalousModelInvocation`, and shows what an SCP denying Bedrock to
  IAM users would break.
- Resolves which guardrail and version each production path actually enforces, catching the DRAFT
  trap, detect-only filters and a disabled input or output side.
- Answers guardrail questions from pasted evidence without inspecting the connected account, using
  documented service limits and behaviour.
- Masks account IDs and key IDs, never reproduces a policy document or blocked content, and never
  invokes a guardrail.
- Works on its own. When a question reaches into a failing call, cost, knowledge bases, agents,
  SageMaker, live incidents or output quality, it uses the matching OpsAI skill if installed, or runs
  a fallback check and recommends that skill.

## Prerequisites

### Credential audit: IAM permissions in each audited account

The skill reads IAM with the role the Agent Space uses in each account. That role needs these
read-only actions: `iam:ListAccountAliases`, `iam:GetAccountSummary`, `iam:GetCredentialReport`,
`iam:ListServiceSpecificCredentials`, `iam:ListUsers`, `iam:GetUser`, `iam:ListAccessKeys`,
`iam:GetAccessKeyLastUsed`, `iam:ListMFADevices`, `iam:GetAccountAuthorizationDetails`,
`iam:GetPolicy`, `iam:GetPolicyVersion` and `iam:GetContextKeysForPrincipalPolicy`.

`AIDevOpsAgentAccessPolicy` (version v12 at the time of writing) grants five of them:
`iam:ListAccountAliases`, `iam:ListUsers`, `iam:GetUser`, `iam:GetPolicy` and `iam:GetPolicyVersion`.
`iam:GetAccountAuthorizationDetails` lets the role read the policy documents of every IAM user and group
in the account; the skill keeps only the users it evaluates and their groups.

### Guardrails review

Already in `AIDevOpsAgentAccessPolicy`: `bedrock:GetGuardrail`; `bedrock:List*` (guardrails, enforced
guardrail configuration, agents, aliases, flows); `bedrock:GetAgent`, `bedrock:GetAgentAlias`;
`bedrock:GetModelInvocationLoggingConfiguration`; `organizations:DescribeEffectivePolicy` (policy type
`BEDROCK_POLICY`); `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`; `logs:DescribeLogGroups`,
`logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`; `kms:DescribeKey`.

Not in it: `bedrock:GetFlow` (guardrail configuration on Amazon Bedrock Flows nodes) and
`bedrock:GetAgentVersion` (the guardrail recorded on the version an alias serves). Without them the
skill reports that resolution as a disclosed permission gap, not as an absent guardrail.

### One inline policy for both areas

This policy grants every action above that `AIDevOpsAgentAccessPolicy` lacks. It has no AWS
Organizations or AWS STS action:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockSecurityIamReadOnly",
      "Effect": "Allow",
      "Action": [
        "iam:ListAccountAliases",
        "iam:GetAccountSummary",
        "iam:GetCredentialReport",
        "iam:ListServiceSpecificCredentials",
        "iam:ListUsers",
        "iam:GetUser",
        "iam:ListAccessKeys",
        "iam:GetAccessKeyLastUsed",
        "iam:ListMFADevices",
        "iam:GetAccountAuthorizationDetails",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
        "iam:GetContextKeysForPrincipalPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockGuardrailResolutionReadOnly",
      "Effect": "Allow",
      "Action": [
        "bedrock:GetFlow",
        "bedrock:GetAgentVersion"
      ],
      "Resource": "*"
    }
  ]
}
```

Save it as a JSON file and add it as an inline policy on the Agent Space role in every account you
want reviewed, with credentials for that account:

```bash
aws iam put-role-policy \
  --role-name <agent-space-role-name> \
  --policy-name opsai-bedrock-security-readonly \
  --policy-document file://<path-to-saved-policy-file>
```

Running it again replaces the earlier version of the inline policy.

**The permission guardrail.** AWS DevOps Agent applies a session policy to every session it opens in
your account, so the agent's effective permissions are the overlap of your role's policies and that
guardrail. It allows the `AIDevOpsAgentAccessPolicy` permissions, every action in the `ReadOnlyAccess`
managed policy and a few listed additions. Every action above is in `ReadOnlyAccess`. AWS states that
it has tested only the permissions in `AIDevOpsAgentAccessPolicy` with the agent; adding others is your
decision under the shared responsibility model. See [Limiting Agent Access in an AWS
Account](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-limiting-agent-access-in-an-aws-account.html).

AWS DevOps Agent's AWS tool rejects IAM calls that name an AWS managed policy ARN and all
`iam:Simulate*` calls, so the skill makes none. It shows a large result only as a preview, so the
skill asks for fewer entries and never summarises an IAM result. For the same reason **every file of
the skill has at most 32,000 characters**, so AWS DevOps Agent can return it whole. Keep each file
within that size when you extend the skill. IAM API calls have no charge.

No write, modify or delete permission is needed or used. `bedrock:ApplyGuardrail` and
`bedrock:InvokeGuardrailChecks` are never called: both invoke the guardrail and are billable.

### Agent Space

An Agent Space with the accounts you want reviewed connected to it. The credential audit covers only
those accounts.

## Limitations

- Service control policies and resource control policies are not evaluated by the credential audit.
  A principal shown as able to invoke Amazon Bedrock may be blocked at the organization level.
- The skill reads policies itself instead of using the policy simulator, so the result depends on the
  agent applying the written steps correctly and can vary between runs.
- Access through `sts:AssumeRole` is not followed. A user who can only invoke through an assumed role is
  reported as unable to invoke.
- Conditions the skill cannot evaluate, and permissions boundaries, give GRANT `unknown`, and the row is
  shown for review.
- Only long-lived credentials are audited. IAM roles, federated users and IAM Identity Center users are
  out of scope, although they can use Amazon Bedrock too.
- IAM does not report when a long-term API key was last used, so API keys are never counted as dormant.
  "Last used" for an access key is its last call to any AWS service.
- Root access key details come from an existing credential report, which can be up to four hours old.
  The skill never generates one.
- It is a point-in-time snapshot of configuration: it does not show whether a key was used to invoke
  models (GuardDuty AI Protection detects that), and it never tests a guardrail.
- A work budget bounds each run; the report lists what it did not evaluate. Commercial AWS partition
  only. Who can re-enable an inactive key is not evaluated.

## Agent Types

Installed as **GENERIC** (all agents), so it loads for chat and for incident investigations.

## Uploading to AWS DevOps Agent

```bash
cd skills/opsai-bedrock-security && zip -r ../opsai-bedrock-security.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/opsai-bedrock-security.zip` with `SKILL.md`, `references/` and `assets/` at the
top level. In the AWS DevOps Agent console, open your Agent Space, choose **Skills**, upload the zip,
and make it available to **All agents**.

## How to Use This Skill

Credential audit:

- "Give me a full report of which IAM users and long-lived access keys in our connected accounts can
  invoke Amazon Bedrock."
- "List every long-term Amazon Bedrock API key and tell me which ones to phase out."
- "GuardDuty raised `Impact:IAMUser/AnomalousModelInvocation` for user ci-bot. What can that key do?"
- "We deactivated the only access key of an admin user. Is that enough?"
- "Before we attach an SCP that denies Amazon Bedrock to IAM users, what would it break?"

Guardrails:

- "Is anything actually protecting our customer-facing assistant on Bedrock?"
- "Our guardrail looks strong in the console but doesn't block in production."
- "Tool results get through even though every content filter is on HIGH."
- "Why is the same prompt blocked on one call and allowed on the next?"
- "Streaming got slower after we attached a guardrail. Can we make it faster?"
- "CreateGuardrailVersion fails with ServiceQuotaExceededException."

## Related skills

All optional. This skill uses them when they are installed:
[`opsai-bedrock-review`](../../skills/opsai-bedrock-review/) (why a call fails, model access,
knowledge bases), [`opsai-capacity-cost`](../../skills/opsai-capacity-cost/) (spend and quotas),
[`opsai-bedrock-agentcore`](../../skills/opsai-bedrock-agentcore/) (agents),
[`opsai-incident-triage`](../../skills/opsai-incident-triage/) (live failures), and the
`opsai-ml-eval-check`, `opsai-sagemaker-inference` and `opsai-sagemaker-training` skills.

## Author

[@cswingchan](https://github.com/cswingchan)

## Version History

See the `CHANGELOG.md` file in this directory.
