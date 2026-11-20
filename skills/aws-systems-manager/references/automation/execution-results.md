# Execution results: worked examples

Responses recorded from real executions in a test account, with identifiers replaced by
placeholders and timestamps and request IDs removed. Fields not used for diagnosis are omitted.
`describe-automation-executions` and `describe-automation-step-executions` return these fields.

## Success: one resource

`AWS-RestartEC2Instance` on one instance.

`describe-automation-executions --filters Key=ExecutionId,Values=<id>`:

```json
[
  {
    "AutomationExecutionId": "00000001-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Success",
    "Mode": "Auto",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    }
  }
]
```

`describe-automation-step-executions`:

```json
[
  {
    "StepName": "stopInstances",
    "Action": "aws:changeInstanceState",
    "StepStatus": "Success"
  },
  {
    "StepName": "startInstances",
    "Action": "aws:changeInstanceState",
    "StepStatus": "Success"
  }
]
```

## Failed: an API call in a step failed

`AWS-RestartEC2Instance` with an instance ID that isn't valid. The step's `FailureDetails` names the API, the error code and the message. The next step stays `Pending`.

`describe-automation-executions --filters Key=ExecutionId,Values=<id>`:

```json
[
  {
    "AutomationExecutionId": "00000002-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Failed",
    "Mode": "Auto",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "FailureMessage": "Automation Step Execution fails when it is changing the state of each instance. Get Exception from StopInstances API of ec2 Service. Exception Message from StopInstances API: [The instance ID 'i-0123456789abcdef0' is malformed (Service: AmazonEC2; Status Code: 400; Error Code: InvalidInstanceID.Malformed; Proxy: null)]. Please refer to Automation Service Troubleshooting Guide for more diagnosis details."
  }
]
```

`describe-automation-step-executions`:

```json
[
  {
    "StepName": "stopInstances",
    "Action": "aws:changeInstanceState",
    "StepStatus": "Failed",
    "FailureMessage": "Automation Step Execution fails when it is changing the state of each instance. Get Exception from StopInstances API of ec2 Service. Exception Message from StopInstances API: [The instance ID 'i-0123456789abcdef0' is malformed (Service: AmazonEC2; Status Code: 400; Error Code: InvalidInstanceID.Malformed; Proxy: null)]. Please refer to Automation Service Troubleshooting Guide for more diagnosis details.",
    "FailureDetails": {
      "FailureStage": "Invocation",
      "FailureType": "Action",
      "Details": {
        "APIName": [
          "StopInstances"
        ],
        "ErrorCode": [
          "InvalidInstanceID.Malformed"
        ],
        "ExceptionMessage": [
          "The instance ID 'i-0123456789abcdef0' is malformed (Service: AmazonEC2; Status Code: 400; Error Code: InvalidInstanceID.Malformed; Proxy: null)"
        ],
        "ServiceName": [
          "ec2"
        ],
        "StatusCode": [
          "400"
        ]
      }
    }
  },
  {
    "StepName": "startInstances",
    "Action": "aws:changeInstanceState",
    "StepStatus": "Pending"
  }
]
```

## TimedOut: a wait step never reached its condition

A runbook with an `aws:waitForAwsResourceProperty` step and `timeoutSeconds: 30` waiting for a state that never occurs.

`describe-automation-executions --filters Key=ExecutionId,Values=<id>`:

```json
[
  {
    "AutomationExecutionId": "00000003-0000-4000-8000-000000000000",
    "DocumentName": "ssm-skill-test-Wait",
    "AutomationExecutionStatus": "TimedOut",
    "Mode": "Auto",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "FailureMessage": "Step timed out while step is Poll action status for completion. Please refer to Automation Service Troubleshooting Guide for more diagnosis details."
  }
]
```

`describe-automation-step-executions`:

```json
[
  {
    "StepName": "Sleep",
    "Action": "aws:sleep",
    "StepStatus": "Success"
  },
  {
    "StepName": "WaitForImpossibleState",
    "Action": "aws:waitForAwsResourceProperty",
    "StepStatus": "TimedOut",
    "FailureMessage": "Step timed out while step is Poll action status for completion. Please refer to Automation Service Troubleshooting Guide for more diagnosis details.",
    "FailureDetails": {
      "FailureStage": "PostVerification",
      "Details": {
        "ErrorMessage": [
          "Step has not completed"
        ]
      }
    }
  }
]
```

## Cancelled: stopped by a person

A runbook stopped with `stop-automation-execution --type Cancel` during an `aws:sleep` step.

`describe-automation-executions --filters Key=ExecutionId,Values=<id>`:

```json
[
  {
    "AutomationExecutionId": "00000004-0000-4000-8000-000000000000",
    "DocumentName": "ssm-skill-test-Wait",
    "AutomationExecutionStatus": "Cancelled",
    "Mode": "Auto",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    }
  }
]
```

`describe-automation-step-executions`:

```json
[
  {
    "StepName": "Sleep",
    "Action": "aws:sleep",
    "StepStatus": "Cancelled"
  },
  {
    "StepName": "WaitForImpossibleState",
    "Action": "aws:waitForAwsResourceProperty",
    "StepStatus": "Pending"
  }
]
```

## Failed: an approver rejected

A runbook with an `aws:approve` step, rejected with `send-automation-signal --signal-type Reject`. While it waits, the status is `Waiting`.

`describe-automation-executions --filters Key=ExecutionId,Values=<id>`:

```json
[
  {
    "AutomationExecutionId": "00000005-0000-4000-8000-000000000000",
    "DocumentName": "ssm-skill-test-Approve",
    "AutomationExecutionStatus": "Failed",
    "Mode": "Auto",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "FailureMessage": "arn:aws:sts::123456789012:assumed-role/Admin/example-session rejected step Approve with comment : \"ssm skill test\"."
  }
]
```

`describe-automation-step-executions`:

```json
[
  {
    "StepName": "Approve",
    "Action": "aws:approve",
    "StepStatus": "Failed",
    "FailureMessage": "arn:aws:sts::123456789012:assumed-role/Admin/example-session rejected step Approve with comment : \"ssm skill test\"."
  },
  {
    "StepName": "AfterApproval",
    "Action": "aws:sleep",
    "StepStatus": "Pending"
  }
]
```

## Success: rate control across three instances

`--targets Key=tag:<key>,Values=<value> --target-parameter-name InstanceId --max-concurrency 1 --max-errors 0` with an alarm. The parent resolves the tag to instance IDs; each child runs one instance, one after another.

Parent:

```json
[
  {
    "AutomationExecutionId": "00000006-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Success",
    "Mode": "Auto",
    "TargetParameterName": "InstanceId",
    "Targets": [
      {
        "Key": "tag:ssm-skill-test",
        "Values": [
          "true"
        ]
      }
    ],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "MaxConcurrency": "1",
    "MaxErrors": "0",
    "AlarmConfiguration": {
      "IgnorePollAlarmFailure": false,
      "Alarms": [
        {
          "Name": "ssm-skill-test-cpu"
        }
      ]
    }
  }
]
```

Children (`--filters Key=ParentExecutionId,Values=<id>`):

```json
[
  {
    "AutomationExecutionId": "00000007-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Success",
    "Mode": "Auto",
    "Target": "i-1234567890abcdef0_1",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "ParentAutomationExecutionId": "00000006-0000-4000-8000-000000000000"
  },
  {
    "AutomationExecutionId": "00000008-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Success",
    "Mode": "Auto",
    "Target": "i-1234567890abcdef0_2",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "ParentAutomationExecutionId": "00000006-0000-4000-8000-000000000000"
  },
  {
    "AutomationExecutionId": "00000009-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Success",
    "Mode": "Auto",
    "Target": "i-1234567890abcdef0_3",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "ParentAutomationExecutionId": "00000006-0000-4000-8000-000000000000"
  }
]
```

## Failed: MaxErrors 0 stopped the run

Three targets passed with `Key=ParameterValues`, the first not valid, `--max-concurrency 1 --max-errors 0`. Only the first child ran; the parent ended `Failed`. With `--max-errors 1` and two bad targets, two children ran and the third target never started.

Parent:

```json
[
  {
    "AutomationExecutionId": "00000010-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Failed",
    "Mode": "Auto",
    "TargetParameterName": "InstanceId",
    "Targets": [
      {
        "Key": "ParameterValues",
        "Values": [
          "i-0123456789abcdef0",
          "i-1234567890abcdef0_2",
          "i-1234567890abcdef0_3"
        ]
      }
    ],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "MaxConcurrency": "1",
    "MaxErrors": "0"
  }
]
```

Children:

```json
[
  {
    "AutomationExecutionId": "00000011-0000-4000-8000-000000000000",
    "DocumentName": "AWS-RestartEC2Instance",
    "AutomationExecutionStatus": "Failed",
    "Mode": "Auto",
    "Target": "i-0123456789abcdef0",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "FailureMessage": "Automation Step Execution fails when it is changing the state of each instance. Get Exception from StopInstances API of ec2 Service. Exception Message from StopInstances API: [The instance ID 'i-0123456789abcdef0' is malformed (Service: AmazonEC2; Status Code: 400; Error Code: InvalidInstanceID.Malformed; Proxy: null)]. Please refer to Automation Service Troubleshooting Guide for more diagnosis details.",
    "ParentAutomationExecutionId": "00000010-0000-4000-8000-000000000000"
  }
]
```

## Cancelled: an alarm fired during the run

Rate-controlled run with `--alarm-configuration 'Alarms=[{Name=<alarm>}],IgnorePollAlarmFailure=false'`. The alarm entered `ALARM` 20 seconds in; the run was cancelled within about 40 seconds and the second target never started.

Parent:

```json
[
  {
    "AutomationExecutionId": "00000012-0000-4000-8000-000000000000",
    "DocumentName": "ssm-skill-test-Wait",
    "AutomationExecutionStatus": "Cancelled",
    "Mode": "Auto",
    "TargetParameterName": "InstanceId",
    "Targets": [
      {
        "Key": "ParameterValues",
        "Values": [
          "i-1234567890abcdef0_1",
          "i-1234567890abcdef0_2"
        ]
      }
    ],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "MaxConcurrency": "1",
    "MaxErrors": "0",
    "FailureMessage": "Cancelled due to Alarm(s)",
    "AlarmConfiguration": {
      "IgnorePollAlarmFailure": false,
      "Alarms": [
        {
          "Name": "ssm-skill-test-cpu"
        }
      ]
    },
    "TriggeredAlarms": [
      {
        "Name": "ssm-skill-test-cpu",
        "State": "ALARM"
      }
    ]
  }
]
```

Children:

```json
[
  {
    "AutomationExecutionId": "00000013-0000-4000-8000-000000000000",
    "DocumentName": "ssm-skill-test-Wait",
    "AutomationExecutionStatus": "Cancelled",
    "Mode": "Auto",
    "Target": "i-1234567890abcdef0_1",
    "Targets": [],
    "ResolvedTargets": {
      "ParameterValues": [],
      "Truncated": false
    },
    "ParentAutomationExecutionId": "00000012-0000-4000-8000-000000000000"
  }
]
```

## Rejected at start: an alarm was already in ALARM

The same command, started while the alarm was in `ALARM`. No execution is created:

```
aws: [ERROR]: An error occurred (InvalidAutomationExecutionParametersException) when calling the StartAutomationExecution operation: The following Cloudwatch alarm(s) were not in a compliant state: ssm-skill-test-cpu in state: ALARM
```
