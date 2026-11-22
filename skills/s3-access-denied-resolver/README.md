# S3 Access Denied Resolver

Read-only DevOps Agent skill that diagnoses an Amazon S3 403 AccessDenied. It
walks the ten layers that can deny an S3 request (SCP/RCP, VPC endpoint policy,
Block Public Access, bucket policy, access point policy, identity policy,
permissions boundary, session policy, Object Ownership/ACLs, KMS key policy),
names the layer and statement that denied the request, and proposes the
smallest fix as a diff for the operator to review.

Scope: S3 general purpose buckets. It is not for 503 SlowDown, CloudFront 403s,
Lake Formation access, or Bedrock/SageMaker role denials.

Taskei: V2468933301.

> **Non-production disclaimer.** Provided for demonstration and evaluation.
> Read-only: it never changes a bucket policy, key policy, role, endpoint or
> any other resource. Apply any proposed change through your own
> change-management and IaC process. Not an AWS service; no warranty.

## Prerequisites

- An AWS DevOps Agent Agent Space with the target account associated.
- The read-only IAM actions below. The Agent Space role can use only actions
  that both its own policies and the DevOps Agent permission guardrail allow.

**Covered by `AIDevOpsAgentAccessPolicy`** (checked against policy version v16):

| Service | IAM actions |
|---|---|
| S3 | `s3:GetBucketPolicy`, `s3:GetBucketOwnershipControls`, `s3:GetBucketPublicAccessBlock`, `s3:GetEncryptionConfiguration`, `s3:GetBucketAcl`, `s3:GetAccessPointPolicy` |
| IAM | `iam:GetRole`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRolePolicy`, `iam:GetPolicyVersion` |
| KMS | `kms:GetKeyPolicy`, `kms:ListGrants` |
| EC2 | `ec2:DescribeVpcEndpoints` (through `ec2:Describe*`) |
| CloudTrail | `cloudtrail:LookupEvents` |
| Organizations (optional) | `organizations:ListPoliciesForTarget`, `organizations:DescribePolicy` (through `organizations:List*` and `Describe*`); only useful from the management or a delegated-administrator account |

**Not covered. Add as an inline policy on the Agent Space role.** The guardrail
allows all of them through `ReadOnlyAccess`:

| IAM action | Used for |
|---|---|
| `s3:GetAccountPublicAccessBlock` | Account-level Block Public Access (layer 3) |
| `s3:GetObjectAcl` | Object ACL and owner (layer 9) |
| `iam:SimulatePrincipalPolicy` | Corroborating the policy read; never the only evidence |
| `s3:GetObject` | `HeadObject` metadata for the object's encryption key. Optional, see the warning below |

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetAccountPublicAccessBlock",
        "s3:GetObjectAcl",
        "iam:SimulatePrincipalPolicy"
      ],
      "Resource": "*"
    }
  ]
}
```

Without these, the skill reports the affected layer as `CANNOT_DETERMINE` and
says which access would resolve it. It still diagnoses layers 1 to 8.

> **Agent Space tool limit.** In testing, the Agent Space refused direct bucket-level
> S3 reads (`GetBucketPolicy`, `GetBucketEncryption`, `GetBucketOwnershipControls`,
> `GetPublicAccessBlock`, `ListBuckets`) with "blocked by policy and was not
> executed", in many runs, including after adding the actions above. Added IAM permissions
> did not reliably lift it. The skill then falls back to AWS Config, the owning CloudFormation
> stack and CloudTrail, and otherwise reports `CANNOT_DETERMINE`. For those
> fallbacks, add the read actions below.

| IAM action | Used for |
|---|---|
| `config:GetResourceConfigHistory`, `config:BatchGetResourceConfig` | Bucket policy, Block Public Access, encryption and ACL from the last recorded configuration, where Config records S3 buckets |
| `cloudformation:GetTemplate`, `cloudformation:DescribeStackResources` | The policy a stack deployed, for stack-managed buckets |

> **`s3:GetObject` can read object contents.** `HeadObject` needs the
> `s3:GetObject` permission, which also allows reading the object body. The
> skill reads metadata only, but the permission does not enforce that. Do not
> grant it by default. If you grant it, scope `Resource` to the buckets under
> investigation. Without it, the skill uses the bucket's default encryption for
> layer 10 and says the object-level key was not checked.

IAM action names differ from API names in a few places:
`GetBucketEncryption` needs `s3:GetEncryptionConfiguration`,
`GetPublicAccessBlock` needs `s3:GetBucketPublicAccessBlock` (bucket) or
`s3:GetAccountPublicAccessBlock` (account, through S3 Control), and
`HeadObject` needs `s3:GetObject`.

## Setup

Add the `s3-access-denied-resolver` folder to your Agent Space as a skill. It
targets the `CHAT` and `INCIDENT_RCA` agent types.

## Sample prompts

- "GetObject on my-bucket/data.csv returns 403 AccessDenied from my Lambda. Which layer denies it?"
- "A role in another account cannot read objects from our bucket even though we added it to the bucket policy."
- "EC2 in a private subnet gets 403 on S3 through the gateway endpoint. Why?"

## Tested scenarios

The functional evals plant one fault each in a test account (a bucket, a reader
role and the object `test/hello.txt`) and ask the agent why the read fails:

| Planted fault | Expected verdict |
|---|---|
| Bucket policy denies `s3:GetObject` to all principals except one named role | Layer 4 `DENIED_BY` |
| Key policy denies `kms:Decrypt` to all principals except one named role; the reader's identity policy allows it | Layer 10 `DENIED_BY` |
| Permissions boundary allows only `s3:ListBucket` | Layer 7 `DENIED_BY` |
| Identity policy grants `s3:GetObject` on the bucket ARN, not `bucket/*` | Layer 6 `DENIED_BY` |
| Gateway endpoint policy allows only a different bucket, read from a private-subnet instance | Layer 2 `DENIED_BY` |

Not covered: an SCP/RCP scenario (needs an Organizations test account), and
Block Public Access, access point, session policy and ACL scenarios.

## Evaluation

`evals/` holds the `skill-eval` evals. The functional cases run one prompt per
scenario above, one prompt that asks the skill
to apply the fix itself, and four prompts it should not trigger on.

## Owner

saadnu-aws
