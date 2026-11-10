# Fix patterns

Each pattern implements a check in [references/automation/hardening-detection-rules.md](references/automation/hardening-detection-rules.md); the source for the
rule is cited there. Patterns are YAML; in JSON, escape each `\` in a pattern as `\\`.

## Apply: parameter validation (check 3)

Add `allowedPattern` to every `String` and `StringList` parameter that has neither
`allowedPattern` nor `allowedValues`. Infer the pattern from how the steps use the parameter, and
keep it as narrow as the use allows; a pattern that rejects valid values breaks the runbook.

| Value | Pattern |
|---|---|
| EC2 instance ID | `^i-(?:[a-f0-9]{8}\|[a-f0-9]{17})$` |
| Other EC2 IDs | the same form with the prefix: `vpc-`, `subnet-`, `sg-`, `vol-`, `snap-`, `ami-`, `eni-` |
| IAM role ARN | `^arn:aws[a-z-]*:iam::\d{12}:role/[\w+=,.@/-]+$` |
| Any ARN, partition part | start with `^arn:aws[a-z-]*:` instead of `^arn:aws:` |
| Optional value | append `\|^$` so the empty default still passes |

(The `\|` in the table is a literal `|` in the pattern.)

Tighten weak patterns the same way: add `^` and `$`, replace `.*` and `.+`, remove `*` and empty
strings from `allowedValues` (if nothing valid remains, use `allowedPattern` instead). Use
`minChars`, `maxChars`, `minItems` and `maxItems` for length limits.

## Apply: step limits (check 5)

Lower a `timeoutSeconds` above the action's documented maximum to that maximum: 600 for
`aws:executeScript`, 25 for `aws:executeAwsApi`, 2592000 for `aws:approve`.

## Apply: invalid parameter type (check 10)

Replace `type: SecureString` with `type: String` holding the Parameter Store parameter's name, and
apply the secrets fix below.

## Propose: command injection (check 1)

**Parameter in a command.** Constrain it so it can't carry shell metacharacters:

BEFORE:
```yaml
parameters:
  LogPath:
    type: String
mainSteps:
  - name: Collect
    action: aws:runCommand
    inputs:
      DocumentName: AWS-RunShellScript
      InstanceIds: ['{{InstanceId}}']
      Parameters:
        commands: ['tar czf /var/tmp/logs.tgz {{LogPath}}']
```

AFTER:
```yaml
parameters:
  LogPath:
    type: String
    description: (Required) Absolute path of the log directory.
    allowedPattern: '^/[A-Za-z0-9._/-]{1,255}$'
```

**Step output in a command.** `allowedPattern` can't validate it. Move the command into
`aws:executeScript`, pass the value through `InputPayload`, check it, and pass it as an argument,
not as shell text:

```yaml
  - name: Process
    action: aws:executeScript
    timeoutSeconds: 600
    inputs:
      Runtime: python3.11
      Handler: handler
      InputPayload:
        ResourceName: '{{GetResource.Name}}'
      Script: |-
        import re
        import subprocess
        def handler(events, context):
            name = events['ResourceName']
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', name):
                raise ValueError('Unexpected resource name format')
            subprocess.run(['/usr/local/bin/process', name], check=True)
```

**Custom Command document called by the runbook.** Add `interpolationType: ENV_VAR` to its string
parameters and use the environment variable (`$SSM_<ParameterName>`) in the command. This needs
SSM Agent 3.3.2746.0 or later on the instances.

## Propose: secrets (check 2)

Replace the secret parameter with a parameter holding the Parameter Store `SecureString` name, and
read the value at run time. The value never appears in the document, the command text or the
execution's parameters.

BEFORE:
```yaml
parameters:
  DbPassword:
    type: String
mainSteps:
  - name: Configure
    action: aws:runCommand
    inputs:
      DocumentName: AWS-RunShellScript
      InstanceIds: ['{{InstanceId}}']
      Parameters:
        commands: ['configure-db --password {{DbPassword}}']
```

AFTER:
```yaml
parameters:
  DbPasswordParameterName:
    type: String
    description: (Required) Name of the SecureString parameter that holds the database password.
    allowedPattern: '^[a-zA-Z0-9_./-]{1,1011}$'
mainSteps:
  - name: Configure
    action: aws:runCommand
    inputs:
      DocumentName: AWS-RunShellScript
      InstanceIds: ['{{InstanceId}}']
      Parameters:
        commands:
          - |
            DB_PASSWORD=$(aws ssm get-parameter --name '{{DbPasswordParameterName}}' --with-decryption --query Parameter.Value --output text)
            printf '%s' "$DB_PASSWORD" | configure-db --password-stdin
            unset DB_PASSWORD
```

`configure-db --password-stdin` stands in for whatever non-argument input the real tool accepts
(standard input, an environment variable for that one command, or a file readable only by its
owner that is deleted afterwards). The instance profile needs `ssm:GetParameter` on that parameter
and `kms:Decrypt` on its key.

Remove any `outputs` entry or print statement that contains the secret. Report success or failure
instead.

For a hard-coded credential: remove it, store it as a `SecureString` parameter, apply the pattern
above, and tell the user to rotate it.

## Propose: role (check 4)

```yaml
assumeRole: '{{AutomationAssumeRole}}'
parameters:
  AutomationAssumeRole:
    type: AWS::IAM::Role::Arn
    description: (Required) ARN of the role that Automation assumes to run this runbook.
```

## Propose: cancel routing (check 6)

If `onCancel` routes to an action that can't be a target, point it at a cleanup step of a
supported action type, such as `aws:executeAwsApi` or `aws:executeScript`, and keep that path
short enough to finish within two minutes.

## Propose: approval steps (check 7)

Reduce `Approvers` to at most 10 entries (use an IAM group or role to cover more people), set
`MinRequiredApprovals` no higher than the number of approvers, and rename the notification topic
so it starts with `Automation`. For a runbook that must run with `TargetLocations`, flag the
approval step: approvals aren't supported there.

## Propose: cross-account role assumption (check 8)

Take the role ARN as a parameter with an ARN pattern. For a role owned by a third party, add an
`ExternalId` parameter and pass it to `AssumeRole`:

```yaml
parameters:
  TargetRoleArn:
    type: String
    allowedPattern: '^arn:aws[a-z-]*:iam::\d{12}:role/[\w+=,.@/-]+$'
  ExternalId:
    type: String
    allowedPattern: '^[\w+=,.@:/-]{2,1224}$'
mainSteps:
  - name: AssumeTargetRole
    action: aws:executeAwsApi
    inputs:
      Service: sts
      Api: AssumeRole
      RoleArn: '{{TargetRoleArn}}'
      RoleSessionName: Automation
      ExternalId: '{{ExternalId}}'
```

## Propose: TLS verification (check 9)

Remove `--no-verify-ssl`, `-k`, `--insecure`, `verify=False`, `PYTHONHTTPSVERIFY=0` and
`NODE_TLS_REJECT_UNAUTHORIZED=0`, and change `http://` endpoints to `https://`. If a command
fails without the flag, the certificate problem has to be fixed where the endpoint is hosted.
