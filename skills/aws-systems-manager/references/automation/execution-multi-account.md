# Running an automation in several accounts or Regions

Source: [Running automations in multiple AWS Regions and accounts](https://docs.aws.amazon.com/systems-manager/latest/userguide/running-automations-multiple-accounts-regions.html).

## Roles

| Role | Where | Purpose |
|---|---|---|
| `AWS-SystemsManager-AutomationAdministrationRole` | The central account only | Lets Automation run in other accounts and Regions. Passed as `AutomationAssumeRole` |
| `AWS-SystemsManager-AutomationExecutionRole` | Every target account | Assumed by the administration role to run the automation in that account |

AWS publishes CloudFormation templates for both roles on the page above. Deploy the execution role
to target accounts with CloudFormation StackSets. The person who starts the automation needs
`iam:PassRole` on the administration role.

To target organizational units, start the automation from the organization's management account
or a delegated administrator for Systems Manager. A custom runbook must be shared with every
target account.

Before preparing a multi-account command, check that the roles exist:

```bash
aws iam get-role --role-name AWS-SystemsManager-AutomationAdministrationRole
```

If it doesn't exist, the setup hasn't been done. Point the user to the page above instead of
building a command.

## Rate control at two levels

| Level | Settings | Controls |
|---|---|---|
| Locations (account-Region pairs) | `TargetLocationMaxConcurrency`, `TargetLocationMaxErrors` in each `--target-locations` entry | How many account-Region pairs run at once, and how many may fail |
| Resources in each location | `--max-concurrency`, `--max-errors` (or `TargetsMaxConcurrency`, `TargetsMaxErrors` in the entry) | How many resources in one account-Region pair run at once, and how many may fail |

Apply the defaults from [references/automation/execution.md](references/automation/execution.md) at both levels: start with one location
(`TargetLocationMaxConcurrency` `1`, `TargetLocationMaxErrors` `0`), and use `MaxConcurrency` `1`
or at most `10%` and `MaxErrors` `0` inside each location. Consider running the first account and
Region on its own before running the rest.

## Command

```bash
aws ssm start-automation-execution --region <central-region> \
  --document-name AWS-RestartEC2Instance \
  --parameters AutomationAssumeRole=arn:aws:iam::123456789012:role/AWS-SystemsManager-AutomationAdministrationRole \
  --target-parameter-name InstanceId \
  --targets Key=tag:<tag-key>,Values=<tag-value> \
  --max-concurrency 1 --max-errors 0 \
  --alarm-configuration 'Alarms=[{Name=<alarm-name>}],IgnorePollAlarmFailure=false' \
  --target-locations '[{
      "Accounts": ["111122223333"],
      "Regions": ["us-east-1"],
      "ExecutionRoleName": "AWS-SystemsManager-AutomationExecutionRole",
      "TargetLocationMaxConcurrency": "1",
      "TargetLocationMaxErrors": "0"
  }]'
```

`Accounts` takes account IDs, OU IDs or the organization root ID. Add
`"IncludeChildOrganizationUnits": true` to include child OUs, and `"ExcludeAccounts"` to leave
accounts out.

If the alarm enters `ALARM`, Automation cancels the automation and runs any `onCancel` steps the
runbook defines.

## Monitoring

Monitor the parent execution in the central account as described in [references/automation/execution.md](references/automation/execution.md). The steps of the
parent return the `AutomationExecutionId` of the child automation in each target account. To read
a child, call `describe-automation-executions` or `describe-automation-step-executions` in that
account and Region with that ID.
