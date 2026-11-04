# Service Specifics - Amazon Personalize

Load only when the failing call is a Personalize operation.

Personalize is the service where the **bucket policy is mandatory, not optional**. Unlike
services where a correctly-scoped service role is sufficient, Amazon Personalize requires
BOTH a policy on the service role (Side A) AND a resource policy on the S3 bucket that names
`personalize.amazonaws.com` (Side B). A service role with perfect S3 permissions still fails
if the bucket has no policy granting the Personalize service principal - the single most
common Personalize import failure, and the one a role-only inspection reports as "looks
correct." (Confirmed: AWS docs - "Attach a policy to the Amazon Personalize service role ...
AND attach a bucket policy to the Amazon S3 bucket ... so Amazon Personalize can access
them.")

Personalize also does **not communicate with VPCs**, which turns a VPC-only bucket policy
into a structural, non-IAM failure rather than a permissions gap.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `CreateDatasetImportJob` (bulk import) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `CreateBatchInferenceJob` / `CreateBatchSegmentJob` (output) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `CreateSolution`, `CreateCampaign` (no S3) | ✓ | n/a | n/a | n/a | n/a | ✓ |

Import and batch-output jobs pass the Personalize **service role** and touch S3, so the full
chain applies. Hop 5 (resource policy) is where Personalize departs from a role-only model:
the S3 bucket policy naming `personalize.amazonaws.com` is a REQUIRED grant, not an optional
hardening step. Solution/campaign creation touches no S3 and is single-hop on the caller.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Bulk import | `personalize:CreateDatasetImportJob` | `arn:aws:personalize:<region>:<account>:dataset-import-job/<name>` |
| Batch inference output | `personalize:CreateBatchInferenceJob` | `arn:aws:personalize:<region>:<account>:batch-inference-job/<name>` |
| Batch segment output | `personalize:CreateBatchSegmentJob` | `arn:aws:personalize:<region>:<account>:batch-segment-job/<name>` |
| Pass the service role | `iam:PassRole` | `arn:aws:iam::<account>:role/<personalizeServiceRole>` |

## The failure modes

| # | Hop | What is missing | When it surfaces | Who needs the fix |
|---|---|---|---|---|
| 1 | 1 | Caller lacks `personalize:CreateDatasetImportJob` | Immediately - `AccessDeniedException` | Caller's identity policy |
| 2 | 2 | Caller lacks `iam:PassRole` for the service role | Immediately - `AccessDeniedException` on the Create call | Caller's identity policy |
| 3 | 3 | Service role trust policy omits `personalize.amazonaws.com` | Immediately - role cannot be assumed | Service role trust policy |
| 4 | 4 | Service role's own policy lacks `s3:GetObject`/`s3:ListBucket` (input) or `s3:PutObject` (output) | **Minutes later** - job `FAILED`, "Insufficient privileges for accessing data in S3" | Service role's permissions (Side A) |
| 5 | 5 | **S3 bucket has no policy granting `personalize.amazonaws.com`** | **Minutes later** - job `FAILED`, same S3 error | S3 bucket policy (Side B) |

**Modes 4 and 5 produce the identical error** - "Unable to Import Data into Personalize from
S3 / Insufficient privileges for accessing data in S3" (confirmed: AWS re:Post). The error
does not tell you which side is missing, which is why both must be read. Side A is the role
owner's fix; Side B is the bucket owner's - frequently different teams.

**The required bucket policy (Side B):**

```json
{
  "Version": "2012-10-17",
  "Id": "PersonalizeS3BucketAccessPolicy",
  "Statement": [
    {
      "Sid": "PersonalizeS3BucketAccessPolicy",
      "Effect": "Allow",
      "Principal": { "Service": "personalize.amazonaws.com" },
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::<bucket>", "arn:aws:s3:::<bucket>/*"]
    }
  ]
}
```

Batch-output buckets additionally need `s3:PutObject` in both the role policy and this bucket
policy. (Confirmed: AWS docs, "Giving Amazon Personalize access to Amazon S3 resources.")

## Non-denial causes and the closed vocabulary

Personalize has a cause that **resembles an access error but is not an authorization
denial**: a VPC-only bucket policy. Personalize does not communicate with VPCs, so a bucket
whose policy allows access only from a VPC/VPC-endpoint cannot be reached by the service at
all - no IAM hop denied, the request simply cannot arrive. Assigning `DENIED_BY` would assert
a denial that never happened.

Per `finding-logic.md` "Root cause selection" case 3b, this takes the non-denial root-cause
form; every hop keeps its own evidence-based verdict:

      **Root cause:** 🚫 Not an access denial — bucket `[bucket]` restricts access to a VPC,
      and Amazon Personalize does not communicate with VPCs

Emit this only from the bucket policy actually read (a `Condition` on `aws:SourceVpc` /
`aws:SourceVpce`). Where that read was unavailable it is `CANNOT_DETERMINE` naming the
operation, never inferred from the absence of a denial. The genuine Side A / Side B S3 gaps
(modes 4 and 5) are real permission gaps and keep `DENIED_BY (service-specific)`.

(Confirmed: AWS docs - "Because Amazon Personalize doesn't communicate with AWS VPCs, Amazon
Personalize can't interact with Amazon S3 buckets that allow only VPC access.")

## Service role requirements

### Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "personalize.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "<accountId>" },
        "ArnLike": { "aws:SourceArn": "arn:aws:personalize:<region>:<accountId>:*" }
      }
    }
  ]
}
```

AWS documents these confused-deputy conditions for the Personalize role: set `aws:SourceArn`
to `arn:aws:personalize:<region>:<accountId>:*` (the wildcard applies to all Personalize
resources) plus `aws:SourceAccount`. Their absence is a security finding, not a denial cause.
(Confirmed: AWS docs, "Cross-service confused deputy prevention.")

### KMS - both sides, like S3

If the data is encrypted with a customer managed key, the key is a two-sided grant of its
own: **both** `personalize.amazonaws.com` AND the Personalize service role need key
permissions. Grant one and not the other and the job still fails. (Confirmed: AWS docs - "you
must grant Amazon Personalize and your Amazon Personalize IAM service role permission to use
your key.")

### Cross-account S3

When the bucket is in a different account from the Personalize dataset, the bucket policy
must name the **IAM service role ARN** as an `AWS` principal (not only the service
principal): e.g. `"Principal": { "AWS": "arn:aws:iam::111122223333:role/<serviceRole>" }`.
(Confirmed: AWS re:Post - cross-account import requires the service role ARN in the bucket
policy Principal.)

## Diagnostic sequence

1. **Did the Create call succeed?** If no: caller's `personalize:Create*` (hop 1), then
   `iam:PassRole` (hop 2), then the service role trust policy (hop 3).
2. **For post-submission `FAILED` jobs:** the error is the generic "Insufficient privileges
   for accessing data in S3" - it does NOT distinguish the two sides. Read BOTH:
   - Side A: the service role's own S3 policy (`s3:GetObject`+`s3:ListBucket` for input,
     `s3:PutObject` for output).
   - Side B: the bucket policy for a statement granting `personalize.amazonaws.com`.
3. **Is the bucket VPC-restricted?** A bucket policy conditioned on `aws:SourceVpc`/
   `aws:SourceVpce` is a structural failure, not an IAM gap - report the non-denial form.
4. **Cross-account bucket?** The bucket policy must name the service role ARN as an `AWS`
   principal. **KMS involved?** Both the service principal and the role need key permissions.

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis uses
`personalize:Describe*`/`List*` (job and dataset reads) plus the shared `s3:GetBucketPolicy`,
`kms:GetKeyPolicy`, `iam:GetRole`/`GetRolePolicy`, and `organizations:*` reads the engine
already relies on. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): `personalize:Describe*`
and `personalize:List*` are granted to the agent role. If a read is refused at runtime, mark
the affected hop `CANNOT_DETERMINE` naming the operation rather than inferring a pass.

When comparing condition keys (`aws:SourceAccount`/`aws:SourceArn` here), match
**case-insensitively** - IAM evaluates condition keys case-insensitively and tooling stores
them in varying case, so a case-sensitive string match can miss a policy that is actually
present.

## References

- Giving Amazon Personalize access to Amazon S3 (service-role policy + required bucket policy + no-VPC note): https://docs.aws.amazon.com/personalize/latest/dg/granting-personalize-s3-access.html
- Setting up permissions / creating the Personalize service role: https://docs.aws.amazon.com/personalize/latest/dg/aws-personalize-set-up-permissions.html
- Giving Amazon Personalize permission to use your AWS KMS key (both-sides KMS): https://docs.aws.amazon.com/personalize/latest/dg/granting-personalize-key-access.html
- Troubleshooting import "Insufficient privileges" + cross-account role-ARN principal: https://repost.aws/knowledge-center/personalize-troubleshoot-import-job
- Cross-service confused deputy prevention (trust-policy SourceArn/SourceAccount): https://docs.aws.amazon.com/personalize/latest/dg/cross-service-confused-deputy-prevention.html
