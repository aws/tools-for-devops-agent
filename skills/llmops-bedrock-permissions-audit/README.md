# llmops-bedrock-permissions-audit

> **Non-production disclaimer.** This skill is an operational aid for auditing which long-lived
> credentials can invoke Amazon Bedrock models. AWS does not run it as a service, and no service
> level agreement applies. It only **reads** IAM configuration: it reports findings and suggests
> policy templates, and it changes nothing in your accounts. Treat its output as advice to check,
> run it against a non-production account before you rely on it, and review each policy template
> before you use it.

## What It Does

In the AWS accounts connected to an Agent Space, `llmops-bedrock-permissions-audit` finds the
long-lived credentials that can invoke Amazon Bedrock models (IAM user access keys, root access
keys, and long-term Amazon Bedrock and Claude Platform on AWS API keys) and gives each one:

- a risk tier from Critical to Info;
- the reasons for that tier and one recommended action;
- one or more `LLM-BPA-###` check-ids from `references/checks-credentials.md` (LLM-BPA-001 to
  LLM-BPA-015), each with an AWS documentation citation.

For a full audit, an inventory of keys or a request for everything, the recommended answer is the
skill's report: a findings table, a summary, a per-account table, what was not evaluated, and the
limitations. A narrower question, such as one user or key, a GuardDuty finding, what an SCP would
break or how to phase out long-term API keys, gets a direct answer. In any format, every answer
keeps the same must-keep items: the credentials the question needs, what each can do in Amazon
Bedrock (its grant and tier), the recommended action as steps for you to take, the scope limits
that change the conclusion, a statement that the audit changed nothing, masked account and key IDs,
and an AWS documentation link for each action. Some questions add statements of their own: an API
key inventory says that IAM does not report when an Amazon Bedrock API key was last used, so
whether a key is in use is unknown; a question about who made calls says that the audit covers IAM
users and their long-lived keys only and that only AWS CloudTrail shows who did; a question about
an SCP's impact gives the rollout steps (review with the workload owners, test on a sandbox
organizational unit, then attach).

AWS DevOps Agent can run the audit itself or hand it to a sub-agent with the prompt in
`assets/delegation-prompt.md`. The sub-agent's reply starts with the answer for you, about 10
lines at most: first "This was a read-only audit; nothing was changed.", then each credential the
question needs with its grant and tier, each recommended action on one line with its AWS
documentation link, and the scope notes the question needs. Supporting detail follows, and the
reply stays short. When you ask for a full report, an inventory or everything, the report follows
after a separator.

Answers end without offers of more work, follow-up suggestions or questions; the recommended
actions are your next steps. The skill also carries four suggested policies under
`assets/remediation/`, including one that blocks long-term Amazon Bedrock API keys and leaves
short-term ones working, and one that blocks every Amazon Bedrock API key. It never applies them
and never offers to: it hands each policy or command to you to review and apply.

The skill is Markdown only: no `scripts/` directory and no executable file, so it uploads without a
sandbox.

How the audit works:

- **Scope.** The accounts connected to the Agent Space (primary and secondary), each read with the
  Agent Space role in that account, or only the accounts, users or keys you name. The skill never
  calls `sts:AssumeRole` or AWS Organizations.
- **Output.** A Markdown answer in the Agent Space chat or investigation: the full report, or a
  direct answer to a narrower question. The skill writes no files.
- **Work budget.** By default at most 100 users inventoried and 20 principals evaluated per account,
  applied to each connected account in turn, one account at a time. Every principal it did not
  evaluate is listed, and the users it did not inventory are counted. You can raise or lower the
  budget in your request, and name a dormant threshold other than the default of 90 days.
- **Masking.** Always on: no account ID in full, including the accounts that policies name
  (accounts appear by alias or by their last four digits); key IDs masked to their last four
  characters, and never shown as their prefix plus 8 or more characters; no text of any policy
  document.
- **Who applies the rules.** AWS DevOps Agent, from the written catalog. Counts come from counting
  rows, and every computed age shows the raw dates it came from.
- **Policy evaluation.** The skill reads the policies with `iam:GetAccountAuthorizationDetails`,
  `iam:GetPolicy` and `iam:GetPolicyVersion`, and applies an explicit deny before an allow. When an
  AWS managed policy's document cannot be read, it uses its own description of
  `AdministratorAccess`, `PowerUserAccess`, `AmazonBedrockFullAccess` and
  `AmazonBedrockLimitedAccess`, and any other AWS managed policy it needs makes GRANT `unknown`. It
  asks the AWS tool for only the entries it needs, and never evaluates a preview or a summary of a
  result. An escalation or canary action allowed only under a condition it cannot evaluate is not
  counted, and a warning names it.

AWS DevOps Agent's AWS tool does not run `iam:SimulatePrincipalPolicy` or
`iam:GenerateCredentialReport`, so the skill uses neither. To decide whether a credential can invoke
Amazon Bedrock models, it reads each evaluated user's inline, group and managed policies and
evaluates them itself by following written steps, instead of asking the IAM policy simulator. The
result therefore depends on the agent applying those steps correctly, and it can vary between runs.
The skill does not evaluate permissions boundaries, so a user with one is reported as `unknown`. It
reads identity-based policies only, so service control policies do not change the result. It
evaluates conditions only on eight keys whose values AWS documents for requests signed with a
long-lived credential, such as `aws:MultiFactorAuthPresent`, which those requests never carry. When
any other condition, or a policy it cannot read, could change the answer, it reports `unknown` with
the reason and keeps the finding visible. Without report generation, the skill learns from
`iam:GetAccountSummary` only whether a root access key exists, and it reads the key's state, age and
last use only from a credential report that already exists. When it cannot read one, it rates a
present root key Critical with its state unconfirmed and tells the requester to run
`aws iam generate-credential-report` and ask again. The skill still reads IAM users' access keys and
MFA directly.

This skill belongs to the `llmops-agent` custom agent, which is fully self-contained with no external
skill dependencies.

### When NOT to use it

- Throttling, quotas, cost or token spend of Amazon Bedrock calls, including cost per IAM user or
  API key → `llmops-capacity-cost`.
- Service-vs-config triage of a live failure or slowdown → `llmops-incident-triage`.
- Amazon Bedrock Guardrails configuration → `llmops-guardrails`.
- A failing Amazon Bedrock call from an application, a role, an IAM user or an Amazon Bedrock API
  key, such as `AccessDeniedException` on `InvokeModel` or an authentication error, model access,
  invocation logging and inference profiles → `llmops-bedrock-configuration`, which checks the
  caller's permissions itself. This skill answers who can call, not why a call fails.
- Knowledge bases / RAG → `llmops-rag-knowledge`.
- Amazon Bedrock Agents and Amazon Bedrock AgentCore → `llmops-agent-runtime`.
- Model-output quality / evaluation → `llmops-quality-evaluation`.
- Amazon SageMaker for LLMs → the `llmops-sagemaker-*` skills: `llmops-sagemaker-inference-endpoints` (real-time endpoints), `llmops-sagemaker-training`, `llmops-sagemaker-serverless-async`, `llmops-sagemaker-batch`, `llmops-sagemaker-evaluation`, `llmops-sagemaker-model-registry`.
- Which model a key invoked and when: use AWS CloudTrail and GuardDuty AI Protection.
- IAM roles, federated users and IAM Identity Center users: they have no long-lived keys and are out
  of scope; whether a role's `bedrock:InvokeModel*` grants are least privilege →
  `llmops-bedrock-configuration`.
- An audit of a whole AWS Organization, or of accounts not connected to the Agent Space: the skill
  audits only the connected accounts.

## Prerequisites

### IAM permissions in each audited account

The skill reads IAM with the IAM role that the Agent Space uses in each account: the primary account
role, or a secondary account role. That role needs these read-only actions:
`iam:ListAccountAliases`, `iam:GetAccountSummary`, `iam:GetCredentialReport`,
`iam:ListServiceSpecificCredentials`, `iam:ListUsers`, `iam:GetUser`, `iam:ListAccessKeys`,
`iam:GetAccessKeyLastUsed`, `iam:ListMFADevices`, `iam:GetAccountAuthorizationDetails`,
`iam:GetPolicy`, `iam:GetPolicyVersion` and `iam:GetContextKeysForPrincipalPolicy`.

This policy grants exactly these actions. It has no AWS Organizations or AWS STS action:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockPermissionsAuditIamReadOnly",
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
    }
  ]
}
```

`iam:GetAccountAuthorizationDetails` lets the role read the policy documents of every IAM user and
group in the account; the skill keeps only the users it evaluates and their groups. The default AWS
DevOps Agent policy already reads every role and its policies.

The default AWS DevOps Agent policy, `AIDevOpsAgentAccessPolicy` (version v12 at the time of
writing), grants five of them: `iam:ListAccountAliases`, `iam:ListUsers`, `iam:GetUser`,
`iam:GetPolicy` and `iam:GetPolicyVersion`, and also every role read (`iam:GetRole`,
`iam:GetRolePolicy`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies` and `iam:ListRoles`).
It does not grant `iam:GetAccountSummary`, `iam:GetCredentialReport`,
`iam:ListServiceSpecificCredentials`, `iam:ListAccessKeys`, `iam:GetAccessKeyLastUsed`,
`iam:ListMFADevices`, `iam:GetAccountAuthorizationDetails` or
`iam:GetContextKeysForPrincipalPolicy`. Save the policy above as a JSON file, and add it as an
inline policy on the Agent Space role in every account you want audited, with credentials for that
account:

```bash
aws iam put-role-policy \
  --role-name <agent-space-role-name> \
  --policy-name llmops-bedrock-permissions-audit-readonly \
  --policy-document file://<path-to-saved-policy-file>
```

Replace `<agent-space-role-name>` with the name of the role the Agent Space uses in that account,
and `<path-to-saved-policy-file>` with the path of the file you saved. Running it again replaces the
earlier version of the inline policy.

The `llmops-agent` IAM templates under `automation/` (CloudFormation and Terraform) do not include
this skill yet, so add this policy by hand.

**The permission guardrail.** AWS DevOps Agent applies a permission guardrail, a session policy, to
every session it opens in your account. The agent's effective permissions are the overlap of your
role's policies and that guardrail. The guardrail allows the default `AIDevOpsAgentAccessPolicy`
permissions, every action in the `ReadOnlyAccess` managed policy, and a few listed additions, and
nothing more. `ReadOnlyAccess` includes `iam:Get*` and `iam:List*`, so every action above is inside
the guardrail. AWS states that it has tested only the permissions in `AIDevOpsAgentAccessPolicy`
with the agent; adding others is your decision under the shared responsibility model. See
[Limiting Agent Access in an AWS Account](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-limiting-agent-access-in-an-aws-account.html).

AWS DevOps Agent's AWS tool also rejects IAM calls that name an AWS managed policy, so the skill
makes none. The tool shows a large result only as a preview, so the skill asks for fewer entries and
never summarises an IAM result. For the same reason, every file of the skill has at most 32,000
characters, so that AWS DevOps Agent can return it whole; if a file still comes back as a preview,
the agent names it and stops. Keep each file within that size when you extend the skill.

IAM API calls have no charge.

### Agent Space

An Agent Space with the accounts you want audited connected to it. The skill audits only those
accounts.

## Uploading to AWS DevOps Agent

See [DevOps Agent Skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
for the full procedure.

Package the skill as a zip with `SKILL.md` at the **archive root** (not nested under a folder). Zip
from **inside** the skill directory:

```bash
cd skills/llmops-bedrock-permissions-audit && zip -r ../llmops-bedrock-permissions-audit.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/llmops-bedrock-permissions-audit.zip` containing `SKILL.md`, `references/` and
`assets/` at the top level, with the repo-management files excluded. The repository's `.gitignore`
excludes the zip.

In the Agent Space Operator Web App, open the **Knowledge** page, choose the **Skills** tab, choose
**Add skill**, then **Upload skill**, and choose the zip file (ZIP files only, at most 6 MB).

> **CRITICAL:** When uploading, select **All agents** as the Agent Type. The custom `llmops-agent` can
> only load the skill if it is published to all agents — selecting a single built-in agent type will
> prevent the custom agent from seeing it.

To run the audit from the [`llmops-agent`](../../custom-agents/llmops-agent/) custom agent, also
assign this skill in the custom agent's **Skills** setting.
The agent needs the `use_aws` tool for the IAM calls, and tools can be assigned to a custom agent
only through Chat. See
[Creating a custom agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-creating-a-custom-agent.html)
and [Executing custom agents](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html).

## Usage Examples

Ask for a full report to get the skill's report template, or ask a narrower question to get a
direct answer with the same must-keep items.

- "Give me a full report of the IAM users and long-lived keys in our connected accounts that can
  invoke Amazon Bedrock models." → every LLM-BPA check.
- "GuardDuty raised Impact:IAMUser/AnomalousModelInvocation for the user ci-bot. Give me a full report
  on that user's credentials, then on the rest of the account." → that user's credentials first,
  then the account-wide audit.
- "Give me a full report of every long-term Amazon Bedrock API key in our accounts." → LLM-BPA-009,
  010, 011, 013 and 014.
- "We deactivated the access key of a user with AdministratorAccess. Give me a full report: is that
  enough?" → LLM-BPA-013.
- "Before we attach an SCP that denies Amazon Bedrock to IAM users, give me a full report of the
  users it would affect." → the audit rows that the SCP would affect, and the SCP template.
- "Give me a full report on the account prod-workloads with a 30-day dormant threshold." → every
  LLM-BPA check, with LLM-BPA-006 and LLM-BPA-007 at 30 days.

## Limitations

- Service control policies and resource control policies are not evaluated. The skill reads
  identity-based policies only, so a principal shown as able to invoke Amazon Bedrock may be
  blocked at the organization level.
- The skill reads the policies itself instead of using AWS's policy simulator, because AWS DevOps
  Agent's AWS tool does not run the simulator. The result depends on the agent applying the written
  steps correctly, and it can vary between runs.
- Access through `sts:AssumeRole` is not followed. A user whose own policy cannot invoke Amazon
  Bedrock, but who can assume a role that can, is reported as unable to invoke.
- Conditions the skill cannot evaluate, and permissions boundaries, give GRANT `unknown`. It
  evaluates condition tests only on condition keys whose value AWS documents for a request signed
  with a long-lived credential, for example the MFA keys, which such requests never carry. When a
  condition it cannot evaluate could change whether the credential can invoke Amazon Bedrock, or a
  permissions boundary applies, the row is shown for review. An escalation or canary action allowed
  only under such a condition is not counted, and a warning names it.
- Only long-lived credentials are audited. IAM roles, federated users and IAM Identity Center
  users are out of scope, although they can use Amazon Bedrock too.
- IAM does not report when a long-term API key was last used, so API keys are never counted as
  dormant. "Last used" for an access key is its last call to any AWS service.
- Root access key details come from an existing IAM credential report, which can be up to four hours
  old. The skill never generates a report, and reads one only when the AWS tool returns it as text.
- The skill reads policy documents to evaluate them: the identity-based policies of the users it
  evaluates and of their groups. It never reproduces them.
- Who can re-enable an inactive key is not evaluated.
- Commercial AWS partition only.
- A point-in-time snapshot of IAM configuration. It does not show whether a key was used to invoke
  models; GuardDuty AI Protection detects that.
- The work budget bounds each run. The report lists every principal it did not evaluate and counts
  the users it did not inventory. You can ask for a larger budget in your request.
- AWS DevOps Agent applies the rules from the written catalog. Each row shows its evidence so you can
  check it.

## Version History

See the `CHANGELOG.md` file in this directory.
