# Automation and State Manager reference

## Calls (all read-only)

| Call | What it gives | Notes |
|---|---|---|
| `ssm:DescribeAutomationExecutions` | `AutomationExecutionStatus`, `FailureMessage`, `DocumentName`, `DocumentVersion`, `ExecutedBy`, `ParentAutomationExecutionId`, `Mode`, `Target`, `ResolvedTargets`, `MaxConcurrency`, `MaxErrors`, `Outputs`, `AutomationType` | Filters: `ExecutionId`, `ParentExecutionId`, `DocumentNamePrefix`, `ExecutionStatus`, `StartTimeAfter`, `StartTimeBefore` |
| `ssm:DescribeAutomationStepExecutions` (`AutomationExecutionId`) | Per step: `StepName`, `Action`, `StepStatus`, `FailureMessage`, `FailureDetails`, `Inputs`, `Outputs`, `OnFailure`, `IsCritical`, `NextStep`, `TimeoutSeconds` | The main source for document-logic faults |
| `ssm:GetDocument` (`Name`, `DocumentVersion`) | Content of the version that ran | Read the version from the execution, not `$LATEST` |
| `ssm:DescribeDocument`, `ssm:ListDocumentVersions` | `DefaultVersion`, `LatestVersion`, versions with dates | Version drift (T10) |
| `ssm:DescribeAssociation`, `ssm:DescribeAssociationExecutions`, `ssm:DescribeAssociationExecutionTargets` | Association `Overview.Status`, `DetailedStatus`, parameters, targets; per run status and targets | `ssm:ListAssociations` to find one by document |
| `iam:GetRole`, `iam:ListAttachedRolePolicies`, `iam:GetRolePolicy`, `iam:GetPolicy`, `iam:GetPolicyVersion` | Trust policy and permissions of the assume role | AWS-managed policy content is not readable |
| `cloudtrail:LookupEvents` | `StartAutomationExecution` errors, step API errors under the role session, `UpdateDocument`, `UpdateDocumentDefaultVersion` | 90 days of management events; delivery lags up to about 15 minutes |

`ssm:GetAutomationExecution` (input `Parameters`, full step list) is not in
`AIDevOpsAgentAccessPolicy`. Read inputs from step `Inputs` instead; if it is denied,
say so rather than guessing a parameter.

## Walking nested runs

- `aws:executeAutomation`: the child's ID is in the step `Outputs` (`ExecutionId`), and the
  child lists the parent in `ParentAutomationExecutionId`. The parent step's
  `FailureMessage` names the child or says the child failed; the cause is in the child's
  steps.
- `aws:runCommand`: the step `Outputs` carry `CommandId` (and the step `Inputs` the
  document and targets). Continue with the Run Command reference.
- Rate-controlled runs (`Target` set): one child execution per target. List them with
  `ParentExecutionId` and group them by status, as for a fleet command.
- Cross-account or cross-Region runs: children run in the target account and Region. If
  that account is not associated with the agent space, the child is not observable: name
  the account and Region.

## Statuses that hide failures

- `OnFailure: Continue` or `IsCritical: false` lets a failed step leave the run `Success`.
  Read every step, not only the last.
- `aws:branch` with a `Default` path can skip the work when no choice matches.
- `NextStep` or `isEnd` can end a run before the work step.
- A Command document step skipped by a precondition shows `Success` with "Step execution
  skipped due to unsatisfied preconditions".

## Association statuses

- `Overview.Status` `Failed` with `DetailedStatus` `InvalidAutomationParameters` and no
  automation execution target: the automation never started. The most common cause is an
  `AutomationAssumeRole` that Systems Manager cannot assume. Check the role's trust policy
  and CloudTrail `StartAutomationExecution` (errorMessage "The defined assume role is unable
  to be assumed") before any theory about the association's targets.
- The `aws:NoOpAutomationTag` / `AWS-NoOpAutomationTarget-Value` target is what the console
  sets for an Automation association without real targets. It is normal.
- An association on `$DEFAULT` runs the default version, not the latest one.

## Trust and permission

| Symptom | Problem | Fix (proposed) |
|---|---|---|
| No execution; "unable to be assumed"; `InvalidAutomationExecutionParametersException` | Trust: `ssm.amazonaws.com` missing from the trust policy, a condition that excludes this account or execution, or no such role | Trust `ssm.amazonaws.com` with `sts:AssumeRole`, keeping an `aws:SourceAccount` (and if used `aws:SourceArn`) condition for this account |
| `AccessDenied` for `iam:PassRole` on the start | The caller, not the role | Allow `iam:PassRole` on that role for the caller, with `iam:PassedToService` `ssm.amazonaws.com` |
| A step fails with `UnauthorizedOperation`, `AccessDenied`, "is not authorized to perform: <action>" | Permission of the principal named in the denial (`assumed-role/NAME` or `user/NAME`: the assume role, a node's instance-profile role, or a target account's role), reason "no identity-based policy allows" | List the action the denial names and its resource ARN, for the operator to add to that principal. For an encoded message, the call's action and any side actions its request shows are candidates to confirm by decoding. No policy document; never a wildcard action |
| The denial says "with an explicit deny in ..." or "because no permissions boundary / service control policy / session policy / resource-based policy allows" | That policy, not the role's own grants (proven: the message names it) | Change or exempt in the named policy, by its owner; adding the action to the role changes nothing. SCPs are not readable from a member account |
| A step fails with AccessDenied and the role's policies allow the action | A permissions boundary, an SCP, a resource policy or a KMS key policy | Hypothesis: name which one, ask the operator; SCPs are not readable from a member account |

Example trust policy (proposed):

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
  "Principal":{"Service":"ssm.amazonaws.com"},"Action":"sts:AssumeRole",
  "Condition":{"StringEquals":{"aws:SourceAccount":"123456789012"}}}]}
```

`ExecutedBy` shows who started the run, not what the assume role may do.
