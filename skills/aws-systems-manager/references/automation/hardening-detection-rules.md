# Detection rules

Each check names the public documentation it relies on. Page names used below:

| Short name | Page |
|---|---|
| Parameters | [Data elements and parameters](https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-syntax-data-elements-parameters.html) |
| Schemas | [Schemas, features, and examples](https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-schemas-features.html) |
| Sharing | [Sharing SSM documents](https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-ssm-sharing.html) |
| Actions | [Systems Manager Automation actions reference](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-actions.html), section "Properties shared by all actions" |
| Resource types | [Using inputs from other AWS services](https://docs.aws.amazon.com/systems-manager/latest/userguide/populating-input-parameters.html) |
| Running | [Running an automation](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-working-executing.html) |
| Script considerations | [Considerations for scripts in runbooks](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-document-script-considerations.html) |
| Parameter Store in Run Command | [Using Parameter Store parameters in Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-param-runcommand.html) |
| Security best practices | [Security best practices for Systems Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/security-best-practices.html) |
| Data protection | [Data protection in Systems Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/data-protection.html) |
| ARNs | [IAM identifiers: ARN format](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html) |
| External ID | [Access to AWS accounts owned by third parties](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_third-party.html) |

Action pages are linked where used.

## 1. Command injection (Critical)

Commands run in `aws:runCommand` steps (through `AWS-RunShellScript`, `AWS-RunPowerShellScript` or
another Command document) and in `aws:executeScript` scripts that start processes.

Find:

1. Every `{{ParameterName}}` inside `aws:runCommand` → `inputs.Parameters.commands`, or inside any
   other input of a Command document that ends up in a command line.
2. Every `{{StepName.OutputName}}` used in the same places.
3. In `aws:executeScript`, values from `InputPayload` passed to `subprocess` with `shell=True`,
   `os.system`, or PowerShell `Invoke-Expression`.

Flag:

- A parameter in a command with no `allowedPattern`, or with a pattern that allows shell
  metacharacters such as `;`, `|`, `&`, `` ` ``, `$`, `(`, `)`, `<`, `>`, quotes or newlines.
  Schemas, "Parameter security best practices": use `allowedPattern` to restrict parameter values
  and properly escape special characters.
- A step output used in a command, always. `allowedPattern` validates parameter input before the
  execution starts (Parameters: "If the user input doesn't match the allowed pattern, the
  execution fails to start"), so it can't validate values produced at run time.
- A custom Command document called by the runbook whose string parameters are used in commands
  without `interpolationType: ENV_VAR`. Schemas: "Always use `interpolationType: "ENV_VAR"` for
  string parameters that will be used in command execution." Sharing: it treats "parameter inputs
  as string literals rather than potentially executable commands." SSM Agent versions earlier than
  3.3.2746.0 ignore it (Schemas).

## 2. Secrets (Critical)

Find:

- Literal credentials in step inputs or scripts: AWS access key IDs (`AKIA` followed by 16
  upper-case letters or digits), private keys, passwords assigned to variables, connection strings
  with a user and password, bearer tokens.
- Parameters that carry a secret value: names such as `Password`, `Secret`, `Token`, `ApiKey`,
  `Credential`, or descriptions saying the value is secret. Don't flag names where "key" means an
  identifier, such as `KeyName`, `KmsKeyId`, `S3Key` or `TagKey`.
- A secret parameter or secret value used in command text, written to a step `outputs` entry, or
  printed (`echo`, `Write-Host`, `print`).

Flag each, citing:

- Data protection: never put confidential or sensitive information into free-form text fields;
  document content and parameter values are such fields.
- Security best practices: "Use SecureString parameters to encrypt and protect secret data."
- Parameter Store in Run Command: SSM documents don't support references to `SecureString`
  parameters; retrieve the value before passing it. So the runbook should take the parameter's
  name, and read the value at run time inside the command or script.
- Parameters: a document parameter can't be of type `SecureString`.

## 3. Parameter validation (High; Critical when the parameter reaches a command)

For each parameter (Parameters lists the constraint fields `allowedValues`, `allowedPattern`,
`minItems`, `maxItems`, `minChars`, `maxChars`; `minLength` and `maxLength` don't exist):

- `String` or `StringList` with neither `allowedPattern` nor `allowedValues`: flag.
- A pattern with no `^` and `$` anchors, or that is `.*` or `.+`: flag as weak.
- `allowedValues` containing `*` or an empty string: flag.
- A resource ID pattern that accepts the wrong length. EC2 resource IDs have 8 or 17 hexadecimal
  characters after the prefix; Parameters gives `^i-(?:[a-f0-9]{8}|[a-f0-9]{17})$` for instance
  IDs. The same form applies to `vpc-`, `subnet-`, `sg-`, `vol-`, `snap-`, `ami-` and `eni-` IDs.
- An ARN pattern fixed to `arn:aws:`. ARNs: the partitions are `aws`, `aws-cn` and `aws-us-gov`;
  match the partition with `arn:aws[a-z-]*:`.

Note that validation runs twice, with the Java regex library at the API and Go `regexp` in SSM
Agent (Parameters), so a pattern must be valid in both: no lookahead or backreferences.

## 4. Role (High)

- An `aws:executeScript` step that calls AWS APIs, in a document with no `assumeRole`: flag.
  Script considerations: an assume role is always required if the script calls AWS API
  operations; without one the script runs without any permissions.
- Any other document with steps that call AWS APIs and no `assumeRole`: flag as a
  recommendation. Running: without a service role, the automation runs in the context of the user
  who starts it; a role is required for automations that run longer than 12 hours.
- `assumeRole` hard-coded to a role ARN instead of `{{AutomationAssumeRole}}`: flag; the runbook
  can't be used in another account.

## 5. Step limits (Medium)

| Action | Documented limit | Flag |
|---|---|---|
| [`aws:executeAwsApi`](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-action-executeAwsApi.html) | Runs for at most 25 seconds | A `timeoutSeconds` above 25 |
| [`aws:executeScript`](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-action-executeScript.html) | Runs for at most 600 seconds | A `timeoutSeconds` above 600, or a script that waits or polls for longer |
| [`aws:changeInstanceState`](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-action-changestate.html) | Default timeout 3600 seconds; for `running` it also waits for instance and system status `OK` | Nothing by default |
| [`aws:approve`](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-action-approve.html) | Default timeout 7 days, maximum 30 days | A `timeoutSeconds` above 2592000 |
| [`aws:runCommand`](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-action-runcommand.html) | The `TimeoutSeconds` input (30 to 2592000) is the time to deliver the command to SSM Agent, not how long it may run | A `TimeoutSeconds` input used as if it limited run time; use the step's `timeoutSeconds` or the Command document's execution timeout |

## 6. Failure and cancel routing (Medium)

From Actions:

- `onFailure` must be `Abort`, `Continue` or `step:<step_name>`; the default is `Abort`. Flag any
  other value, or a `step:` target that doesn't exist.
- `onCancel` must be `Abort` or `step:<step_name>`. It can't route to `aws:approve`,
  `aws:copyImage`, `aws:createImage`, `aws:createStack`, `aws:createTags`, `aws:loop`,
  `aws:pause`, `aws:runInstances` or `aws:sleep`. Flag a target of those types.
- Automation runs the cancellation workflow for at most two minutes. Flag an `onCancel` path whose
  steps can take longer.
- List every `onFailure: Continue` with its step as information (not a finding), so the author can
  confirm the runbook should carry on after that step fails.

## 7. Approval steps (Medium)

From [`aws:approve`](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-action-approve.html):

- `Approvers` is required, with at most 10 entries. `MinRequiredApprovals` defaults to 1 and can't
  exceed the number of approvers.
- A `NotificationArn` topic name must start with `Automation`.
- `aws:approve` doesn't support multi-account and multi-Region automations. Flag an approval step
  in a runbook intended to run with `TargetLocations`.
- `Message` is at most 4096 characters.

## 8. Cross-account role assumption (Medium)

A step that calls `sts:AssumeRole` (through `aws:executeAwsApi` or a script):

- Flag a hard-coded role ARN; take it as a parameter with an ARN `allowedPattern`.
- If the role belongs to a third party, flag a missing `ExternalId`. External ID: the external ID
  prevents the confused deputy problem when a third party assumes a role in your account or
  assumes roles on behalf of different customers. It isn't required for roles between accounts
  you own, and AWS doesn't treat it as a secret.

## 9. TLS verification disabled (High)

Flag `--no-verify-ssl`, `curl -k` or `--insecure`, `PYTHONHTTPSVERIFY=0`,
`NODE_TLS_REJECT_UNAUTHORIZED=0`, `verify=False` in Python requests, and `http://` endpoints for
AWS or internal APIs. Data protection: use SSL/TLS to communicate with AWS resources; Systems
Manager API endpoints only support HTTPS.

## 10. Document structure (Low)

- `schemaVersion` must be `"0.3"` and `mainSteps` is required (Parameters, Schemas).
- Parameter `type` must be one of `String`, `StringList`, `Integer`, `Boolean`, `MapList`,
  `StringMap` (Parameters), or an AWS resource type such as `AWS::EC2::Instance::Id`,
  `AWS::S3::Bucket::Name`, `AWS::IAM::Role::Arn` or their `List<...>` forms (Resource types).
  Flag `SecureString` or any other value.
- Step `name` must match `[a-zA-Z0-9_]+` (Actions).
