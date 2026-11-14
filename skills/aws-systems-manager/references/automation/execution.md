# AWS Systems Manager Automation Execution

Prepare, monitor and diagnose Automation executions. A person starts, stops and approves
executions. This chapter gives them the exact command and reads the result.

## When to use

- A runbook has been chosen and the user wants to run it, on one resource or many.
- An execution is in progress, waiting for approval, or has ended, and the user wants to know its
  state or why it failed.
- A user asks how rate control, alarm-based stopping or multi-account execution works.

If the runbook isn't chosen yet, find it first with the runbook discovery chapter
([references/automation/runbook-discovery.md](references/automation/runbook-discovery.md)).

## What the agent may do

| Action | API | Who does it |
|---|---|---|
| Read a runbook's parameters | `ssm:DescribeDocument` | Agent |
| Read execution status | `ssm:DescribeAutomationExecutions` | Agent |
| Read step status and failure details | `ssm:DescribeAutomationStepExecutions` | Agent |
| Resolve tag targets, check alarm state | `tag:GetResources`, `cloudwatch:DescribeAlarms` | Agent |
| Start an execution | `ssm:StartAutomationExecution` | A person, with the command the agent prepares |
| Stop an execution | `ssm:StopAutomationExecution` | A person |
| Approve or reject a waiting step | `ssm:SendAutomationSignal` | A person listed as an approver in the runbook |

The DevOps Agent managed policy grants the read actions and none of the others. Don't ask
for wider permissions to work around this.

## Workflow

Copy this checklist and work through the steps that apply:

- [ ] Step 1: Confirm the runbook and its risk
- [ ] Step 2: Build the start command, resolve the targets and check the alarm
- [ ] Step 3: Monitor the execution
- [ ] Step 4: Interpret the result
- [ ] Step 5: Give the stop or approval command, if needed
- [ ] Step 6: Check your answer, then present it

For a question about an existing execution, start at Step 3.

## Step 1: Confirm the runbook and its risk

1. Call `aws ssm describe-document --name <runbook> --region <region>`. Use its `Parameters` to
   build the command, and note `DocumentVersion`.
2. Set the risk tier: use the tier from the runbook catalog (`references/automation/catalog/`), or for a runbook outside
   it, classify its `mainSteps` the same way.
3. Find the parameter that identifies the resource (for example `InstanceId`). This is the target
   parameter for rate control.
4. Ask whether the target is production, if you don't know.

## Step 2: Build the start command

### One resource

```bash
aws ssm start-automation-execution --region <region> \
  --document-name <runbook> --document-version <version> \
  --parameters '{"InstanceId":["i-0123456789abcdef0"],"AutomationAssumeRole":["<role-arn>"]}'
```

- Pin `--document-version` to the version you confirmed, so the run uses the document you read.
- Pass `AutomationAssumeRole` when the runbook takes one. Without it the execution runs with the
  permissions of whoever starts it.

### Many resources: rate control

Always use rate control when a runbook will run against more than one resource. Name the target
parameter and choose the resources with `--targets`:

```bash
aws ssm start-automation-execution --region <region> \
  --document-name <runbook> --document-version <version> \
  --target-parameter-name InstanceId \
  --targets Key=tag:<tag-key>,Values=<tag-value> \
  --max-concurrency 1 --max-errors 0 \
  --alarm-configuration 'Alarms=[{Name=<alarm-name>}],IgnorePollAlarmFailure=false' \
  --parameters '{"AutomationAssumeRole":["<role-arn>"]}'
```

`--targets` accepts `Key=tag:<key>`, `Key=ResourceGroup` or `Key=ParameterValues` with an explicit
list of IDs.

Required defaults:

| Setting | Value | Why |
|---|---|---|
| `--max-concurrency` | `1` for `destructive` runbooks or when unsure; at most `10%` for `mutating-reversible` | Limits how many resources change at once |
| `--max-errors` | `0` | The run stops after the first failed target |
| `--alarm-configuration` | at least one alarm on the health of the affected service | The run stops when the service degrades |
| `IgnorePollAlarmFailure` | `false` | If the alarm can't be read, the run doesn't continue blind |

How the service applies these, as observed:

- With `MaxConcurrency` `1`, child executions run one at a time: each starts after the previous
  one ends.
- `MaxErrors` `N` stops the run when failures exceed `N`: with `0`, it stops after the first
  failed target; with `1`, after the second. Targets not yet started don't run, and the parent
  ends `Failed`.
- If any listed alarm is already in `ALARM`, the start call fails with
  `InvalidAutomationExecutionParametersException` ("alarm(s) were not in a compliant state"). Tell
  the user the alarm is firing; don't remove the alarm to get past it.
- If an alarm enters `ALARM` during the run, the parent and the running child end `Cancelled`, the
  parent's `FailureMessage` is `Cancelled due to Alarm(s)`, and `TriggeredAlarms` names the alarm.
  Stopping can take up to a minute after the alarm fires, so choose a `MaxConcurrency` that limits
  the damage in that time.

### Many accounts or Regions

To run across accounts or Regions from one place, add `--target-locations`. See
[references/automation/execution-multi-account.md](references/automation/execution-multi-account.md) for the role setup and command.

### Checks before handing over the command

1. Resolve the targets, so the person sees exactly which resources will change. For a tag target:
   `aws resourcegroupstaggingapi get-resources --tag-filters Key=<tag-key>,Values=<tag-value> --resource-type-filters <service>:<type>`
   (for example `ec2:instance`).
2. Check the alarm: `aws cloudwatch describe-alarms --alarm-names <alarm-name>`. If `StateValue`
   is `ALARM`, the start call will be refused; report that the service is already unhealthy.
3. Present the command with: the runbook and version, every parameter, the resolved targets, the
   tier and what it changes, and the alarm used.
4. For `mutating-reversible` runbooks, record the current state of each target so the change can
   be undone. A person must approve and run the command.
5. For `destructive` runbooks and resilience tests, say so explicitly. For a resilience test,
   confirm the target isn't production.

## Step 3: Monitor the execution

```bash
aws ssm describe-automation-executions --region <region> \
  --filters Key=ExecutionId,Values=<execution-id>
```

Read `AutomationExecutionStatus`, `FailureMessage`, `ResolvedTargets` and, when an alarm
configuration was set, `TriggeredAlarms`. For a rate-controlled run, list the child executions:

```bash
aws ssm describe-automation-executions --region <region> \
  --filters Key=ParentExecutionId,Values=<execution-id>
```

Each child has a `Target` and its own status. For the steps of one execution:

```bash
aws ssm describe-automation-step-executions --region <region> \
  --automation-execution-id <execution-id>
```

Each step has `StepName`, `Action`, `StepStatus` and, when it failed, `FailureMessage` and
`FailureDetails` (`FailureStage`, `FailureType`, and `Details` with the API name, error code and
exception message). Steps after a failure stay `Pending`.

Poll every 30 seconds or longer while the status is `Pending`, `InProgress`, `Waiting` or
`Cancelling`. Stop polling at a final status.

## Step 4: Interpret the result

| Status | Meaning | What to report |
|---|---|---|
| `Success` | Every step succeeded (for a rate-controlled run, every child) | The outputs, and for children the targets that ran |
| `Failed` | A step failed, an approver rejected, or `MaxErrors` was exceeded | The failing step's `FailureDetails`; for a rejection, the `FailureMessage` names who rejected and their comment |
| `TimedOut` | A step ran past its `timeoutSeconds` | The step, and what it was waiting for |
| `Cancelled` | Someone called `StopAutomationExecution`, or an alarm fired | If `FailureMessage` is `Cancelled due to Alarm(s)`, the alarm in `TriggeredAlarms` |
| `Waiting` | An `aws:approve` or `aws:pause` step is waiting for a signal | Who can approve (the step's `Approvers`) and the command below |

For a failure, link the error code to a cause before suggesting a fix:

| `FailureDetails.Details.ErrorCode` or message | Likely cause |
|---|---|
| An access-denied or unauthorized error code | The assume role (or the caller, when there is no assume role) lacks the permission for the API named in `APIName` |
| A "malformed" or "not found" error for a resource ID | The parameter value is wrong, or the resource is in another Region or account |
| `FailureStage: PostVerification` with "Step has not completed" | A wait step's condition never became true before its timeout |
| A throttling error code | Too many targets call the API at once; lower `MaxConcurrency` |

Worked examples of each status, from real executions, are in
[references/automation/execution-results.md](references/automation/execution-results.md).

## Step 5: Stop or approve

Give the person the command; don't run it.

```bash
# Stop an execution that is in progress
aws ssm stop-automation-execution --region <region> --automation-execution-id <execution-id> --type Cancel

# Approve or reject a step that is waiting
aws ssm send-automation-signal --region <region> --automation-execution-id <execution-id> \
  --signal-type Approve --payload Comment="<reason>"
aws ssm send-automation-signal --region <region> --automation-execution-id <execution-id> \
  --signal-type Reject --payload Comment="<reason>"
```

Only a principal listed in the step's `Approvers` can approve or reject. After a rejection the
execution ends `Failed`.

## Step 6: Check your answer

Before presenting a command, confirm:

- `--document-version` is the version `describe-document` returned.
- A multi-target or multi-location command has `--max-concurrency`, `--max-errors` and
  `--alarm-configuration` with the values in Step 2.
- The resolved targets you list are the ones the `--targets` value selects, and nothing else.
- The alarm was not in `ALARM` when you checked.

Before presenting a diagnosis, confirm that the status, failing step and error code you report
come from a `describe-automation-executions` or `describe-automation-step-executions` response in
this conversation, and that any cause you infer is labelled as inferred.

## Gotchas

- A rejected approval ends the execution as `Failed`, not with a separate status.
- `MaxErrors` counts failures above the threshold: `0` stops after the first failure.
- The children of a rate-controlled run are separate executions; filter by `ParentExecutionId` to
  see them. Each child has its own steps.
- An alarm that is already in `ALARM` stops the run before it starts; there is no execution ID to
  look up.
- `aws:runCommand`'s `TimeoutSeconds` input limits delivery to SSM Agent, not how long the
  command runs.

## Constraints

- Don't start, stop or signal an execution yourself.
- Don't propose a multi-target or multi-location command without `--max-concurrency`,
  `--max-errors` and `--alarm-configuration`.
- Don't suggest removing an alarm, raising `MaxErrors` or setting `IgnorePollAlarmFailure` to
  `true` to make a run proceed.
- Don't report an execution as fixed until `describe-automation-executions` returns `Success`
  and, for a rate-controlled run, every child is `Success`.
