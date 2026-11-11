# IAM Policy Deployment

`iam-policy.json` is the least-privilege policy for this skill: 38 read-only
actions and no action that can change infrastructure. The full action list,
grouped by service, is in the [skill README](../README.md#iam-permissions).

## Apply the policy

Attach it as an inline policy to the IAM role that AWS DevOps Agent uses for
the connected account:

```bash
aws iam put-role-policy \
  --role-name <your-devops-agent-role> \
  --policy-name FSxONTAPDiagnosticReadOnly \
  --policy-document file://iam-policy.json
```

For a CloudFormation deployment, add the same statements as an inline policy
on the Agent Space role, following
[`cloudformation/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies.yaml)
in the `aws/tools-for-devops-agent` repository.

## What the policy does not grant

- No write permissions of any kind: no `fsx:Create*`, `fsx:Update*`, `fsx:Delete*`, `cloudwatch:Put*` or `backup:Delete*`
- No `secretsmanager:` permissions; no ONTAP credentials are needed
- No ONTAP management endpoint access

Keep the role limited to this policy. The read-only boundary is what
guarantees that no change can be made, independently of the skill's own
instructions.

## Customer managed KMS keys

`kms:DescribeKey` also needs the key policy to allow the role. Without it the
KMS check is reported as a data gap.
