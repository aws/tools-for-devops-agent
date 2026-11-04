# Service Specifics - Amazon Forecast

Load only when the failing call is a Forecast operation.

> **Service status:** Amazon Forecast is **no longer available to new customers**; existing
> customers continue to use it as normal (confirmed: AWS docs). Diagnosing an existing
> deployment is in scope; never advise standing up a new Forecast workload.

Forecast is the counterpoint to Personalize in this skill. Where Personalize *requires* a
bucket policy naming the service principal, Forecast is **role-based**: you pass a
`RoleArn` in the job's `S3Config`, Forecast assumes it, and that role's own permissions are
what reach S3 and KMS. There is no mandatory `forecast.amazonaws.com` bucket policy for
same-account access. The engine must not apply the Personalize two-sided-bucket-policy
pattern here - it is the wrong model and would send the customer chasing a grant Forecast
does not need.

Two Forecast-specific traps surface as the wrong error code and must not be read as plain
IAM denials:
- **Cross-account role passing is forbidden** - not merely unconfigured. Passing a role from
  another account returns `InvalidInputException`, not `AccessDenied`.
- **A VPC-only bucket returns `AccessDenied`** even when IAM is perfect, because Forecast does
  not communicate with VPCs - a structural cause wearing an IAM error code.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `CreateDatasetImportJob` (import) | ✓ | ✓ | ✓ | ✓ | only if bucket policy restricts | ✓ |
| `CreateForecastExportJob` (output) | ✓ | ✓ | ✓ | ✓ | only if bucket policy restricts | ✓ |
| `CreateAutoPredictor`, `CreateForecast` (no S3) | ✓ | n/a | n/a | n/a | n/a | ✓ |

Import and export jobs pass a role via `S3Config.RoleArn`, so hops 1-4 apply. Hop 5 (the
bucket resource policy) is applicable only when the bucket carries a policy that restricts
the role - unlike Personalize, a grant to `forecast.amazonaws.com` is NOT required for
same-account access; the passed role's own identity policy is the grant.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Bulk import | `forecast:CreateDatasetImportJob` | `arn:aws:forecast:<region>:<account>:dataset-import-job/<dsName>/<jobName>` |
| Export forecast | `forecast:CreateForecastExportJob` | `arn:aws:forecast:<region>:<account>:forecast-export-job/<name>/<jobName>` |
| Pass the role | `iam:PassRole` | `arn:aws:iam::<account>:role/<forecastRole>` |

## The failure modes

| # | Hop | What is missing | When it surfaces | Who needs the fix |
|---|---|---|---|---|
| 1 | 1 | Caller lacks `forecast:CreateDatasetImportJob` | Immediately - `AccessDeniedException` | Caller's identity policy |
| 2 | 2 | Caller lacks `iam:PassRole` for the Forecast role | Immediately - `AccessDeniedException` | Caller's identity policy |
| 3 | 3 | Role trust policy omits `forecast.amazonaws.com` | Immediately - role cannot be assumed | Role trust policy |
| 4 | 4 | Passed role lacks `s3:GetObject`/`s3:ListBucket` (input) or `s3:PutObject` (output), or KMS access | **Minutes later** - job `FAILED`, S3/KMS access error | Passed role's permissions |

**KMS note:** if `S3Config.KMSKeyArn` is set, the passed role must allow the key, and the
key + role must match the `EncryptionConfig` given at `CreateDataset`. A mismatch between the
import job's key/role and the dataset's `EncryptionConfig` fails even when each looks correct
on its own. (Confirmed: AWS CLI reference, `create-dataset-import-job`.)

## Non-denial and misleading-error causes (closed vocabulary)

Per `finding-logic.md` "Root cause selection" case 3b, the two structural causes below take
the non-denial root-cause form; every hop keeps its evidence-based verdict. Emit each only
from evidence actually read.

**Cross-account role passing (returns `InvalidInputException`, not `AccessDenied`):**

      **Root cause:** 🚫 Not an access denial — the role in `S3Config.RoleArn` belongs to
      account `[roleAccount]`, not the calling account `[callerAccount]`; Forecast rejects a
      cross-account role with `InvalidInputException`

"Passing a role across Amazon Web Services accounts is not allowed. If you pass a role that
isn't in your account, you get an `InvalidInputException` error." (Confirmed: AWS API
reference.) No IAM change fixes this - the role must live in the calling account.

**VPC-only bucket (returns `AccessDenied`, but no grant fixes it):**

      **Root cause:** 🚫 Not an access denial — bucket `[bucket]` allows only VPC access, and
      Amazon Forecast does not communicate with VPCs; the `AccessDenied` is structural, not an
      IAM gap

This one is a **misleading error code**: the symptom is `AccessDenied`, so it reads as a
permissions problem, but adding permissions to the role will not fix it. Detect it from the
bucket policy's `aws:SourceVpc`/`aws:SourceVpce` condition, not from the error string.
(Confirmed: AWS docs - "Using S3 buckets that only allow VPC access will result in an
`AccessDenied` error.")

## Role requirements

### Trust policy (with confused-deputy conditions)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "forecast.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "<accountId>" },
        "ArnLike": { "aws:SourceArn": "arn:aws:forecast:<region>:<accountId>:*" }
      }
    }
  ]
}
```

AWS documents `aws:SourceAccount`/`aws:SourceArn` confused-deputy conditions for the Forecast
role; their absence is a security finding, not a denial cause.

## Diagnostic sequence

1. **Did the Create call succeed?** If no: caller's `forecast:Create*` (hop 1), `iam:PassRole`
   (hop 2), role trust policy naming `forecast.amazonaws.com` (hop 3).
2. **`InvalidInputException` on the Create call?** Check whether `S3Config.RoleArn` is in the
   caller's own account - a cross-account role is rejected outright. Non-denial form.
3. **For `FAILED` jobs:** read the passed role's S3 (and KMS) permissions (hop 4). There is
   no required service-principal bucket policy to check (contrast Personalize).
4. **`AccessDenied` that the role's permissions do not explain?** Check the bucket policy for
   a VPC-only condition - Forecast can't reach a VPC-restricted bucket. Structural, non-denial.
5. **KMS involved?** The passed role needs the key, and it must match the dataset's
   `EncryptionConfig`.

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis uses
`forecast:Describe*`/`List*` (dataset/import-job reads) plus the shared `s3:GetBucketPolicy`,
`kms:GetKeyPolicy`, `iam:GetRole`/`GetRolePolicy`, and `organizations:*` reads. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): `forecast:Describe*` and
`forecast:List*` are granted to the agent role. If a read is refused at runtime, mark the
affected hop `CANNOT_DETERMINE` naming the operation rather than inferring a pass.

Match condition keys (`aws:SourceAccount`/`aws:SourceArn`) **case-insensitively** - IAM
evaluates them case-insensitively and tooling stores them in varying case, so a
case-sensitive match can miss a policy that is present.

## References

- Set Up Permissions for Amazon Forecast (no-new-customers status, no-VPC/AccessDenied, confused deputy): https://docs.aws.amazon.com/forecast/latest/dg/aws-forecast-iam-roles.html
- create-dataset-import-job (S3Config RoleArn + KMS, EncryptionConfig match): https://docs.aws.amazon.com/cli/v1/reference/forecast/create-dataset-import-job.html
- Forecast API reference, S3Config (cross-account role passing → InvalidInputException): https://docs.aws.amazon.com/aws-sdk-php/v3/api/api-forecast-2018-06-26.html
