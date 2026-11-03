# Service Specifics - Amazon Transcribe

Load only when the failing call is a Transcribe operation.

Transcribe is the service where **the identity that needs S3/KMS permission depends on which
path the job uses**, and getting that wrong is the common failure:

- **Caller-credentials path (standard batch):** `StartTranscriptionJob` with
  `OutputBucketName` (and/or an output KMS key). The **caller** - the principal that invoked
  `StartTranscriptionJob` - is the identity that must have the S3 write and KMS permission.
  There is no passed role. (Confirmed: AWS docs - "The user calling the
  `StartTranscriptionJob` operation must have permission to use the specified KMS key.")
- **DataAccessRole path:** `InputDataConfig.DataAccessRoleArn` (custom language model
  training, Call Analytics, and cross-account input). Transcribe assumes this **role** to
  reach the input S3 location, so the role - not the caller - needs the S3 permission.
  (Confirmed: AWS docs - the role "has permissions to access the Amazon S3 bucket that
  contains your input files. If the role ... doesn't have the appropriate permissions ...
  your request fails.")

Asking "what does the Transcribe role need" is the wrong question until you know which path
the job uses - exactly as with Textract's sync/async split, but here the axis is
caller-creds vs passed-role.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `StartTranscriptionJob` with `OutputBucketName` (caller-creds) | ✓ | n/a | n/a | n/a (caller's own S3/KMS) | ✓ (bucket/key policy) | ✓ |
| `StartTranscriptionJob`/`StartCallAnalyticsJob` with `DataAccessRoleArn` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Service-managed output bucket (temp URI) | ✓ | n/a | n/a | n/a | n/a | ✓ |

When the job uses the service-managed output bucket, no customer S3 permission is needed for
output at all - the result is retrieved via a temporary URI. Do not report a missing output
grant in that case.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Start transcription | `transcribe:StartTranscriptionJob` | `*` |
| Start call analytics | `transcribe:StartCallAnalyticsJob` | `*` |
| Pass the data access role | `iam:PassRole` | `arn:aws:iam::<account>:role/<transcribeDataAccessRole>` |

## The failure modes

| # | Path | What is missing | Who needs the fix |
|---|---|---|---|
| 1 | either | Caller lacks `transcribe:StartTranscriptionJob` | Caller's identity policy |
| 2 | caller-creds | **Caller** lacks `s3:PutObject` on `OutputBucketName`, or `kms:GenerateDataKey`/`Decrypt` on the output key | Caller's identity policy (NOT a service role) |
| 3 | data-access-role | Caller lacks `iam:PassRole` for the data access role | Caller's identity policy |
| 4 | data-access-role | Role trust policy omits `transcribe.amazonaws.com` | Role trust policy |
| 5 | data-access-role | Role lacks `s3:GetObject`/`s3:ListBucket` on the input (or KMS to decrypt input) | Data access role's permissions |

**The most common Transcribe mistake:** granting a service role S3/KMS access for a standard
batch job that uses `OutputBucketName`, then finding it still fails - because that path runs
on the **caller's** credentials and ignores the role. Check which path the job used before
deciding whose permissions to fix.

## Non-denial causes (closed vocabulary)

Per `finding-logic.md` "Root cause selection" case 3b, emit the non-denial form only from
evidence actually read:

**KMS key specified without an output bucket** - `StartTranscriptionJob` requires
`OutputBucketName` whenever `OutputEncryptionKMSKeyId` is set; omitting it is a validation
error, not an access denial.

      **Root cause:** 🚫 Not an access denial — an output KMS key was specified without
      `OutputBucketName`, which Transcribe rejects as a validation error

(Confirmed: AWS docs - "If you specify a KMS key to encrypt your output, you must also
specify an output location in the `OutputBucketName` parameter.")

## Data access role requirements (DataAccessRole path)

### Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "transcribe.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "<accountId>" },
        "ArnLike": { "aws:SourceArn": "arn:aws:transcribe:<region>:<accountId>:*" }
      }
    }
  ]
}
```

AWS documents these confused-deputy conditions for the Transcribe role: `aws:SourceAccount`
plus `aws:SourceArn` in the form `arn:aws:transcribe:<region>:<accountId>:*` (use the full
resource ARN where known; wildcard the resource portion otherwise). (Confirmed: AWS docs -
Transcribe "Cross-service confused deputy prevention" and the identity-based policy examples.)

### Input access (role) / output access (caller)

- Input (role path): `s3:GetObject` + `s3:ListBucket` on the input location; `kms:Decrypt`
  if the input is SSE-KMS.
- Output (caller-creds path): `s3:PutObject` on `OutputBucketName`; `kms:GenerateDataKey` +
  `kms:Decrypt` on the output key, held by the **caller**.

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis uses
`transcribe:Get*`/`List*` (job reads) plus the shared `s3:GetBucketPolicy`, `kms:GetKeyPolicy`,
and `iam:GetRole`/`GetRolePolicy` reads. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): it grants **no**
`transcribe:*` actions - like Lex and Textract, Transcribe is unreadable without the opt-in
read policy. Until that delta is deployed, state the gap plainly and mark the affected reads
`CANNOT_DETERMINE` rather than inferring a pass. Match
condition keys case-insensitively (`AWS:` vs `aws:`).

## Diagnostic sequence

1. **Which path?** `OutputBucketName` set and no `DataAccessRoleArn` → caller-creds: check the
   CALLER's `s3:PutObject` and output-KMS permission. `DataAccessRoleArn` set → role path.
2. **Role path, Create denied?** Caller `transcribe:Start*` (hop 1), `iam:PassRole` (hop 2),
   role trust naming `transcribe.amazonaws.com` (hop 3), then role S3/KMS (hop 4).
3. **KMS specified but no `OutputBucketName`?** Validation error, non-denial form.
4. **Service-managed output bucket?** No customer output grant is needed - do not flag one.

## References

- Amazon Transcribe identity-based policy examples (role must access S3 + KMS; confused-deputy assume-role example): https://docs.aws.amazon.com/transcribe/latest/dg/security_iam_id-based-policy-examples.html
- Cross-service confused deputy prevention (aws:SourceArn arn:aws:transcribe:region:account:*): https://docs.aws.amazon.com/transcribe/latest/dg/security-iam-confused-deputy.html
- StartTranscriptionJob (caller must hold the output KMS key; KMS requires OutputBucketName): https://docs.aws.amazon.com/sdk-for-ruby/v2/api/Aws/TranscribeService/Types/StartTranscriptionJobRequest.html
- InputDataConfig.DataAccessRoleArn (role Transcribe assumes for input S3): https://docs.aws.amazon.com/sdk-for-cpp/latest/api/aws-cpp-sdk-transcribe/html/class_aws_1_1_transcribe_service_1_1_model_1_1_input_data_config.html
