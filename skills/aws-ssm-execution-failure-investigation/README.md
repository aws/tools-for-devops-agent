# AWS SSM Execution Failure Investigation

This skill lets AWS DevOps Agent investigate a Systems Manager Automation execution, a Run
Command command or a State Manager association that failed, did nothing, or reported
Success without doing its work. It follows the chain down to each node, reports every
cause with its evidence, and ends with the fix the operator applies. It reads only.

Version: 1.5.0, an internal revision (see CHANGELOG.md). `metadata.version` stays `1.0.0`
until the skill merges upstream.

> **Review flag:** elevated risk. The skill reads command output, logs and documents that
> can hold secrets (sensitive data), and the README carries optional IAM guidance (extra
> read permissions, and `kms:Decrypt`, which IAM rates as Write). It needs DevOps Agent
> service-team or AppSec review before publication.

## Purpose

Systems Manager failures are often hidden one hop away from where the agent first looks:
a command that reports Success because only the last line's exit code counts, an error
past the 24,000-character output cut, a tagged fleet where some nodes never got an
invocation and others were stopped by the error limit, a runbook whose failure message
only names a child execution, or an association that never starts because its role cannot
be assumed. Without this skill the agent tends to read the visible end of the output as
where the script stopped, report one cause for a fleet with three, blame an association's
targets for a trust-policy problem, and end with a question instead of a fix. With it, the
agent walks parent execution, child executions, steps, commands and node invocations,
checks for the output cut and reads the full output from CloudWatch Logs, compares the
tagged nodes with the invocations created, separates trust from permission, and ends with
the operator's fix.

## Key Capabilities

- Walks nested Automation runs (`aws:executeAutomation`, `aws:runCommand`) down to the
  failing node invocation
- Reads every node invocation of a command, groups them by status detail (failed, never
  delivered, terminated by the error limit) and gives one cause and one fix per group
- Finds tagged nodes that got no invocation because they are not managed nodes
- Detects the output cut, reads the full output from CloudWatch Logs, and reports output
  that exists only in S3 as not observable
- Applies the last-exit-code rule to commands that report Success while an earlier step
  failed
- Separates assume-role trust problems, `iam:PassRole` problems and missing permissions,
  from the role's trust policy and CloudTrail errors
- Gives a managed-node checklist (identity, metadata endpoint, routes, interface endpoints
  and private DNS, security groups, ACLs) and the in-guest commands for the operator
- Labels each cause as proven or as a hypothesis; ends every answer with the fix as steps
  and a proposed document diff

## Prerequisites

- An AWS DevOps Agent space with the account that owns the execution, command or
  association.
- Investigation IAM permissions, all read-only: `ssm:Describe*`, `ssm:List*`,
  `ssm:GetCommandInvocation`, `ssm:GetDocument`, `logs:DescribeLogStreams`,
  `logs:GetLogEvents`, `logs:FilterLogEvents`, `cloudtrail:LookupEvents`, `iam:GetRole`, `iam:GetRolePolicy`,
  `iam:ListAttachedRolePolicies`, `iam:GetPolicy`, `iam:GetPolicyVersion`,
  `iam:GetInstanceProfile` and `ec2:Describe*`. The `AIDevOpsAgentAccessPolicy` managed
  policy covers all of them.

### Optional: extra read permissions

Two reads are not in `AIDevOpsAgentAccessPolicy`. Without them the skill still works: it
reads execution inputs from the step inputs, and reports S3-only command output as not
observable and asks the operator for it. The skill never proposes these grants as the fix
for an incident; adding them is your own choice. If you want the agent to read them, add to the
investigation role:

`ssm:GetAutomationExecution` returns the execution's input parameters, which can hold
secrets.

```json
{"Version":"2012-10-17","Statement":[
 {"Sid":"ReadAutomationExecutions","Effect":"Allow","Action":"ssm:GetAutomationExecution",
  "Resource":"arn:aws:ssm:REGION:ACCOUNT:automation-execution/*"},
 {"Sid":"ReadCommandOutput","Effect":"Allow","Action":"s3:GetObject",
  "Resource":"arn:aws:s3:::COMMAND-OUTPUT-BUCKET/COMMAND-OUTPUT-PREFIX/*"}]}
```

Both are read actions. Command output can hold secrets that scripts print, so grant
`s3:GetObject` only on the command-output bucket and its key prefix, never on `*`. When
commands set no `OutputS3KeyPrefix`, objects start with the command ID: use
`arn:aws:s3:::COMMAND-OUTPUT-BUCKET/*` for that dedicated bucket only.

If the bucket uses SSE-KMS, the role also needs `kms:Decrypt` on that key, which IAM rates
at the Write access level. Scope it to the key and to S3 use only; without it the output
stays not observable:

```json
{"Sid":"DecryptCommandOutput","Effect":"Allow","Action":"kms:Decrypt",
 "Resource":"arn:aws:kms:REGION:ACCOUNT:key/KEY-ID",
 "Condition":{"StringEquals":{"kms:ViaService":"s3.REGION.amazonaws.com"},
  "StringLike":{"kms:EncryptionContext:aws:s3:arn":"arn:aws:s3:::COMMAND-OUTPUT-BUCKET/*"}}}
```

These statements need DevOps Agent service-team or AppSec review before publication.

## Limitations

- Read-only. The skill never sends a command, starts or re-runs an automation or an
  association, or changes a document, default version, association, role or node. Every
  fix is a proposal for the operator.
- In-guest state (agent log, proxy, local DNS, clock, mounts) is not observable; the skill
  gives the operator the commands to run on the node.
- Command output kept only in S3 is not observable without the optional read permission.
- AWS-managed policy content cannot be read; the skill carries the core managed-node
  actions it needs to compare against.
- Child executions in an account or Region not associated with the agent space are not
  observable.
- Throttling and cross-account runs were not tested live.

## Agent Types

This skill is used by the following agent types:

- **Incident RCA**: root cause analysis when an Automation execution, command or
  association fails, or an alarm on its outcome fires
- **Chat tasks**: questions about a specific execution, command or association

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

In the DevOps Agent web app, go to Settings, then Add Skill, then Import from repository,
and point to the `skills/aws-ssm-execution-failure-investigation` directory. When prompted,
select the agent types **Incident RCA** and **Chat tasks**. See
[Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

**Option B: Upload as a zip file**

1. Zip the skill directory, including only allowed extensions:

   ```bash
   cd skills
   zip -r aws-ssm-execution-failure-investigation.zip aws-ssm-execution-failure-investigation/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, open the **Skills** page.
3. Choose **Add skill**, then **Upload skill**, and drop in
   `aws-ssm-execution-failure-investigation.zip`.
4. Select the agent types **Incident RCA** and **Chat tasks**, then choose **Upload**.

## How to Use This Skill

### Investigation

- "Automation execution 0123abcd-0123-4567-89ab-0123456789ab of the runbook ReleaseOrchestrator failed in us-east-1. What is the root cause?"
- "The State Manager association 0123abcd-0123-4567-89ab-0123456789ab in us-east-1 should run the TagAudit runbook every 30 minutes, but the audit never happens. Why?"

### Chat

- "Command 0123abcd-0123-4567-89ab-0123456789ab reports Success on both web nodes, but the app is still on the old version. Why?"
- "Command 0123abcd-0123-4567-89ab-0123456789ab failed on i-0123456789abcdef0 and the output just stops. What went wrong?"
- "Our release command was meant to reach every node tagged Fleet=web, but only one got it. What happened to the others?"

## Non-production disclaimer

> This skill is sample code, not intended for production use without additional review and testing. Users should validate it in a non-production environment first. Its investigation uses only read calls (Describe, Get and List calls, CloudWatch Logs reads and CloudTrail lookups); it never sends a command through Run Command, never starts or re-runs an automation or association, and never changes a document, association, role or node. Every fix it gives is a proposal for you to review and apply yourself. It reads output that can hold secrets and is told not to repeat them; review answers before sharing. You are responsible for reviewing the IAM permissions you grant and the findings it produces before acting on them.
