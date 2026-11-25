# IAM denial reference

Read this before you write any IAM finding or fix (SKILL.md step 6). The rules in step 6
always apply; this file gives the detail behind them.

## Calls (all read-only)

- Find the role: the `AutomationAssumeRole` parameter of the association or execution
  (step `Inputs` show it when the execution parameters are not readable).
- Read its trust policy (`iam:GetRole`, `AssumeRolePolicyDocument`) and its permissions
  (`iam:ListAttachedRolePolicies`, `iam:GetRolePolicy`, `iam:GetPolicy` and
  `iam:GetPolicyVersion` for customer-managed policies).
- Read CloudTrail (`cloudtrail:LookupEvents`, `EventName` `StartAutomationExecution`
  around the association's run time, and events whose user is the assumed-role session)
  for `errorCode` and `errorMessage`. CloudTrail events can take up to about 15 minutes
  to appear.

## Trust, PassRole or permission

- **Trust problem**: no execution was created, or the start failed with "The defined
  assume role is unable to be assumed" (`InvalidAutomationExecutionParametersException`).
  The trust policy does not allow `ssm.amazonaws.com` to call `sts:AssumeRole`, or a
  condition (`aws:SourceAccount`, `aws:SourceArn`) excludes this account or
  execution, or the role does not exist. Fix: the trust policy.
- **PassRole problem**: the caller who starts the run (or created the association)
  is denied `iam:PassRole` on the role. Fix: the caller's policy.
- **Permission problem**: the execution started, then a step was denied (the step
  `FailureMessage`, and the CloudTrail `errorCode` under the assumed-role session when
  the call is a management event). Fix: **list only the IAM actions that are
  missing**, each with its resource and the principal it is missing on, for the
  operator to add to that principal's own policy. Do not write a policy document.

## Reading a permission denial

- **Which principal:** take it from the denial (`assumed-role/NAME/...` for a role,
  `user/NAME` for a user), not from `AutomationAssumeRole`. A denial is proven only
  from CloudTrail for that session, or a non-script step's `FailureMessage`. A denial
  seen only in command or log output is a hypothesis: confirm it in CloudTrail first.
  A command step's output can point to the node's instance-profile role, a multi-account run the target
  account's role, and a run without an assume role the caller. Name that principal
  in the fix.
- **Read the reason in the denial first.** Only "because no identity-based policy
  allows ..." means a missing grant on that principal. A named other policy ("because no
  permissions boundary allows", "... no service control policy allows", "... no
  session policy allows", "... no resource-based policy allows", or "with an
  explicit deny in ...") means adding a grant to the role changes nothing: report
  that policy type as a proven cause, with the automation reference's explicit-deny
  row, and list no action to add. A message with no reason clause, or one you don't
  recognise, proves nothing: handle it as an encoded message (below). When a
  message carries both a readable reason and an encoded blob, the readable reason
  decides.
- **Proven action:** when the message names the action and the identity-policy
  reason ("is not authorized to perform: ec2:CreateSnapshot on resource: ...
  because no identity-based policy allows the ec2:CreateSnapshot action"), list
  exactly that action and resource. If the principal has a permissions boundary
  (`PermissionsBoundary` in `iam:GetRole` for a role; for a user, `iam:GetUser`), add that the boundary must also allow the action;
  whether it does is a hypothesis unless you read it.
- **Encoded or reason-less message:** nothing is proven. List candidates "to confirm
  before granting": the call's own action, `<prefix>:<eventName>` (the prefix from
  the Service Authorization Reference, not the host name, for example
  `monitoring.amazonaws.com` is `cloudwatch:`; version suffixes removed); and the
  side actions the request shows, for example `ec2:CreateTags` for
  `TagSpecifications`, or `iam:PassRole` for an instance profile or role parameter.
  Ask the operator to decode the message (`aws sts decode-authorization-message
  --encoded-message ...`, their action). A decoded implicit deny still doesn't say
  which policy type lacks the allow: propose the grant on the principal only when
  its boundary is read and is absent or allows the action, and no SCP is suspected;
  otherwise keep it labelled "hypothesis".
- **Already allowed:** count an action as allowed only when an `Allow` statement you
  read matches this action, this resource and conditions that hold here. Then the
  denial comes from another policy (boundary, SCP, resource or session policy):
  report it as a hypothesis, with the automation reference's row for "the role's
  policies allow the action", and list no action to add. AWS-managed
  policies attached to the role can't be read through DevOps Agent: say that
  whether they allow the action is not observable, and keep the candidates.
- **Not observable:** when no message or event names the action (CloudTrail
  `LookupEvents` holds management events only, so data-plane denials such as S3
  object reads leave none), say so and ask the operator for the decoded message.
- **Resource:** every action you name carries the full resource ARN(s) it is needed
  on, never "your volumes" or "scoped to the snapshot". Copy an ARN the denial names
  ("on resource: arn:..."). Build any other from the request's IDs in the format the
  Service Authorization Reference gives for that resource type, leaving empty the
  fields that format has none of (an S3 bucket is `arn:aws:s3:::NAME`; an IAM role has
  no Region; an EC2 snapshot has no account). Take the partition (`aws`,
  `aws-us-gov`, `aws-cn`) from the principal's ARN, the Region from the incident's
  Region or the resource, and the account from the resource's owner (for an EC2
  volume, the `OwnerId` of the instance's reservation in `ec2:DescribeInstances`),
  which in a multi-account run can differ from the role's account. For example the
  volume `arn:aws:ec2:us-east-1:123456789012:volume/vol-0123456789abcdef0` and the new
  snapshot `arn:aws:ec2:us-east-1::snapshot/*` (commercial-partition examples; in
  another partition the `aws` field changes). If you cannot build an ARN from what you
  read, say which part is unknown; never fill it with a guess. If the
  customer scopes the volume by a resource-tag condition, that condition must not
  also apply to the new snapshot, which has no tags yet (a condition on the
  snapshot's tags uses `aws:RequestTag`). For `iam:PassRole` the resource is the
  role's ARN copied from the `Arn` that `iam:GetRole` returns (or that
  `iam:GetInstanceProfile` returns for an instance profile's role), since a role can
  have a path such as `/service-role/` that a hand-built ARN would drop, with an `iam:PassedToService` condition naming
  the service that receives the role (`ec2.amazonaws.com` for an instance profile,
  `ssm.amazonaws.com` for an Automation assume role). When the action has no
  resource-level permissions (the action is a read with no resource types in the
  Service Authorization Reference, as for most `Describe*` actions), write `*` as its resource and say why: the action
  cannot be scoped to an ARN. That is the only case without an ARN.
- A step reports one denial at a time: once the operator adds the action, it may
  fail on the next one. Say so; do not guess further actions.
- Never propose a wildcard action (`*`, `<prefix>:*`) or an AWS-managed or
  administrator policy. Mark IAM writes, `sts:AssumeRole`, KMS, secrets and
  `ssm:SendCommand` **security-sensitive**: say what each allows, ask the owner to
  confirm, and add the narrowest condition.
