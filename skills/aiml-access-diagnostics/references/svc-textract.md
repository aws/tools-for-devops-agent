# Service Specifics - Amazon Textract

Load only when the failing call is a Textract operation.

Textract is the service where the **notification pipeline** creates a hidden dependency
chain that is invisible to the caller. A `StartDocumentAnalysis` call succeeds immediately
(it is asynchronous), but the job fails silently minutes later because the service role
cannot publish to SNS or read from S3. The caller sees a successful API response followed
by a job that never completes - and there is no access error anywhere the caller can see it.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `DetectDocumentText`, `AnalyzeDocument` (synchronous) | ✓ | n/a | n/a | n/a | n/a | ✓ |
| `StartDocumentTextDetection`, `StartDocumentAnalysis` (async) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `GetDocumentTextDetection`, `GetDocumentAnalysis` (polling) | ✓ | n/a | n/a | n/a | n/a | ✓ |

Synchronous calls (`DetectDocumentText`, `AnalyzeDocument`) accept the document inline or
from S3. When from S3, the **caller** must have `s3:GetObject` - Textract reads via the
caller's credentials, not a service role. No role is passed.

Asynchronous calls pass a service role via `NotificationChannel.RoleArn`. This role needs
SNS publish AND the document must be accessible. The full 6-hop chain applies - and hops
2-4 are where most async failures hide.

**The split personality is the diagnostic key.** Sync and async Textract have completely
different permission models. Sync = caller's credentials. Async = service role. Asking
"what permissions does Textract need?" is the wrong question - it depends entirely on
which API the customer is calling.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Sync document detection | `textract:DetectDocumentText` | `*` (no resource-level constraint) |
| Sync document analysis | `textract:AnalyzeDocument` | `*` |
| Start async detection | `textract:StartDocumentTextDetection` | `*` |
| Start async analysis | `textract:StartDocumentAnalysis` | `*` |
| Poll for results | `textract:GetDocumentTextDetection` | `*` |
| Poll for results | `textract:GetDocumentAnalysis` | `*` |
| Start expense analysis | `textract:StartExpenseAnalysis` | `*` |
| Start lending analysis | `textract:StartLendingAnalysis` | `*` |

**Textract's detection and analysis actions do not support resource-level permissions** - they use `Resource: "*"`. (Adapter resources are the exception - they have their own ARNs - but they are not on the detect/analyze call path.)
This means hop 5 is `NOT_APPLICABLE` for the caller's own call - but hop 5 IS applicable
for the S3 bucket policy and SNS topic policy that the service role accesses.

## The five failure modes

| # | Hop | What is missing | When it surfaces | Who needs the fix |
|---|---|---|---|---|
| 1 | 1 | Caller lacks `textract:StartDocumentAnalysis` | Immediately - API returns `AccessDeniedException` | Caller's identity policy |
| 2 | 2 | Caller lacks `iam:PassRole` for the Textract service role | Immediately - `AccessDeniedException` on the Start call | Caller's identity policy |
| 3 | 3 | Service role trust policy omits `textract.amazonaws.com` | Immediately - an assume-role failure (likely `InvalidParameterException`; the exact code/message was not doc-confirmed — treat the role-not-assumable *condition* as the finding, not a quoted string) | Service role trust policy |
| 4 | 4 | Service role cannot `sns:Publish` to the notification topic | **Minutes later** - job completes but notification never arrives | Service role's permissions |
| 5 | 4 | Service role cannot `s3:GetObject` on the input document | **Minutes later** - job status becomes `FAILED` | Service role's permissions OR S3 bucket policy |

**Mode 4 is the ghost failure.** The `StartDocumentAnalysis` call succeeds (returns a
JobId). The job itself may even succeed. But the customer never receives the SNS
notification, so from their perspective the job "hangs forever." The polling approach
(`GetDocumentAnalysis`) still works - but if the customer relies on the notification
pattern (which AWS documentation recommends), they will wait indefinitely.

There is no error code or CloudTrail event that the customer can easily find. The
failed `sns:Publish` is logged under the Textract service principal, not the customer's
principal. The customer must look for the *absence* of an event (no notification
received) rather than the presence of an error.

**Mode 5 has two sub-variants.** The service role needs `s3:GetObject`, and separately
the S3 bucket policy must not deny the role. In cross-account scenarios (document in
account A, Textract job in account B), BOTH the role's identity policy AND the bucket's
resource policy must allow. Additionally, if the bucket uses SSE-KMS, the role needs
`kms:Decrypt` on the CMK - a third policy that must align.

## Non-denial causes and the closed vocabulary

Textract has causes that **resemble an access error but are not an authorization denial**:
a document-size rejection and an S3 region mismatch. Neither is an authorization decision in
the six-hop chain — they are validation/region failures. Assigning `DENIED_BY` to them
asserts a denial that never happened. They take the non-denial root-cause form:

      **Root cause:** 🚫 Not an access denial — <one-line statement>

See `finding-logic.md` "Root cause selection", case 3b. Modes 4 and 5 (the service role's
missing `sns:Publish` / `s3:GetObject`) are genuine permission gaps and keep
`DENIED_BY (service-specific)` — and NOTE the `AmazonTextract` SNS topic-name issue is one of
them, not a non-denial cause: it is an implicit deny from the managed policy's
`AmazonTextract*` resource scope (see "Service-role SNS scope" below). Every hop keeps its own evidence-based verdict.

> **Note:** the asynchronous diagnosis rides the shared S3/SNS/KMS and data-access-role
> resource-policy reads the skill already performs; it needs no `textract:*`-specific action
> (the same pattern Comprehend uses). If a `textract:*` `Describe`/`List` read turns out to be
> required, it is an additive, read-only permission.

## Service-role SNS scope — the `AmazonTextract` topic-name convention (IAM, not a naming rule)

**This is a permissions cause, not a Textract API naming rule.** A topic whose name does
not start with `AmazonTextract` fails *only* when the service role relies on the AWS-managed
`AmazonTextractServiceRole` policy, which scopes `sns:Publish` to the pattern
`arn:aws:sns:*:*:AmazonTextract*` (confirmed: managed-policy JSON). A non-matching topic ARN
falls outside that grant, so the service role gets an **implicit deny** on `sns:Publish` and
the completion notification never publishes (surfaces as the Mode-4 ghost failure — a JobId
returns, no notification arrives).

There is no evidence Textract's API validates the topic name independently of IAM: a service
role with a **custom** policy granting `sns:Publish` on the actual topic ARN publishes fine
regardless of the name. So the `AmazonTextract` prefix is a convention that exists to let the
managed policy's wildcard match — not a hard service-side requirement.

**How to check**
- Read the service role's `sns:Publish` grant. If it is the managed `AmazonTextractServiceRole`
  (or any policy scoped to `AmazonTextract*`) AND the `NotificationChannel.SNSTopicArn` name
  does not start with `AmazonTextract`, the grant does not cover the topic.
- If the role has a custom `sns:Publish` grant naming the real topic ARN, the prefix is
  irrelevant — look elsewhere.

**Finding body**
- verdict: `DENIED_BY` (service-specific) — hop 4/5, the service role's `sns:Publish` on the
  topic ARN. This is a real implicit deny, not a non-denial cause.
- body: "The Textract service role's `sns:Publish` permission does not cover topic
  `[topicArn]`. The role uses a policy scoped to `arn:aws:sns:*:*:AmazonTextract*` (the
  managed `AmazonTextractServiceRole` pattern), and `[topicName]` does not start with
  `AmazonTextract`, so the grant does not match — an implicit deny, and the completion
  notification is never published. Fix EITHER by renaming the topic to begin with
  `AmazonTextract`, OR by granting `sns:Publish` on this topic's exact ARN in the role's
  policy. There is no Textract-side naming requirement independent of this IAM scope."

## Non-IAM cause 2 - Document format or size

Textract has hard limits on document size (sync: 10 MB, single page; async: 500 MB for PDF).
Exceeding size returns `DocumentTooLargeException`; a malformed/invalid document returns
`InvalidParameterException` — not an access error. But customers often conflate "the job
failed" with "permissions are wrong." (Confirmed: 10 MB sync / 500 MB async PDF and the
sync single-page constraint are documented; the exact async page-count ceiling was not
doc-confirmed this pass — state size limits, not a specific page number, unless verified.)

**How to check**
- Error code is `DocumentTooLargeException` or `InvalidParameterException` mentioning size
- Document metadata (S3 object size, page count)

## Non-IAM cause 3 - S3 object not in the same region as the API call

Textract requires the S3 bucket and the API endpoint to be in the same region. A
document in `us-west-2` with a `StartDocumentAnalysis` call to `us-east-1` fails with
`InvalidS3ObjectException` - which looks like a permissions problem (customer assumes
"can't access the object") but is actually a region mismatch.

**Finding body**
- verdict: none — region mismatch, not a hop verdict. See "Non-denial causes" above.
- root-cause line: "**Root cause:** 🚫 Not an access denial — S3 bucket in `[bucketRegion]`, Textract call in `[apiRegion]`"
- body: "S3 bucket `[bucket]` is in `[bucketRegion]` but the Textract call targets
  `[apiRegion]`. Textract requires the document and the API endpoint to be in the same
  region." (Confirmed: `InvalidS3ObjectException` — "Amazon Textract is unable to access
  the S3 object specified in the request" — is the documented exception; a cross-region
  bucket is one trigger, alongside a genuine access or path problem.)

## Service role requirements (Modes 2-5)

### Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": {
    "Sid": "ConfusedDeputyPrevention",
    "Effect": "Allow",
    "Principal": {
      "Service": "textract.amazonaws.com"
    },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "aws:SourceAccount": "<accountId>"
      },
      "ArnLike": {
        "aws:SourceArn": "arn:aws:textract:<region>:<accountId>:*"
      }
    }
  }
}
```

Without confused-deputy conditions, the trust policy is vulnerable. AWS documentation
explicitly recommends `SourceAccount` and `SourceArn` conditions. Their absence is a
finding (not a denial cause, but a security gap).

### Permissions policy (minimum for async with notification)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:<region>:<account>:AmazonTextract*"
    }
  ]
}
```

This is what `AmazonTextractServiceRole` managed policy grants - ONLY `sns:Publish` to
`AmazonTextract*` topics. It does NOT grant S3 read access. A service role with only the
managed policy attached will still fail if Textract needs to read from S3 (the default
for async operations where the document is in S3).

**The managed policy gap is the most common failure.** Customers follow the docs, attach
`AmazonTextractServiceRole`, and assume the role has everything it needs. It does not.
It has SNS publish only. S3 access must be granted separately on the same role.

### Additional permissions for S3-based documents

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject"],
  "Resource": "arn:aws:s3:::<bucket>/<prefix>/*"
}
```

### Additional permissions for SSE-KMS encrypted documents or output

```json
{
  "Effect": "Allow",
  "Action": ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey"],
  "Resource": "arn:aws:kms:<region>:<account>:key/<keyId>"
}
```

`kms:GenerateDataKey` is needed only when Textract writes encrypted output to S3.
`kms:Decrypt` alone is sufficient for reading encrypted input.

## Hop 2 - PassRole specifics

The caller needs `iam:PassRole` with the service role in `Resource`:

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::<account>:role/<textractServiceRole>",
  "Condition": {
    "StringEquals": {
      "iam:PassedToService": "textract.amazonaws.com"
    }
  }
}
```

**Common miss**: The caller has `textract:Start*` but forgot `iam:PassRole`. The error
is `AccessDeniedException` on the Start call - but the error message may reference IAM
rather than Textract, confusing the customer into thinking their Textract permissions
are wrong.

## Diagnostic sequence

1. **Is this sync or async?** If `DetectDocumentText`/`AnalyzeDocument` - the caller
   needs S3 access directly. No role involved. If `Start*` - a service role is involved.
2. **Did the Start call succeed?** If yes, the problem is post-submission (mode 4 or 5).
   If no, the problem is pre-submission (mode 1, 2, or 3).
3. **For Start failures:** Check caller has `textract:Start*` (hop 1), then `iam:PassRole`
   (hop 2), then the role's trust policy (hop 3). The error message often hints which.
4. **For post-submission failures:** Check job status via `GetDocumentAnalysis`. If
   `FAILED` - S3 access issue (mode 5). If `SUCCEEDED` but no notification - SNS publish
   issue (mode 4).
5. **For S3 issues:** Is the bucket cross-account? Is it KMS encrypted? Is the document
   in the same region?
6. **For SNS issues:** Does the topic name start with `AmazonTextract`? Does the role
   have `sns:Publish`?

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis would use `textract:Get*`/`List*` (async job-status reads) plus the shared `s3:GetBucketPolicy`, `kms:GetKeyPolicy`, `iam:GetRole`/`GetRolePolicy`, `sns:GetTopicAttributes`/`List*`, and `organizations:*`. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): it grants **no** `textract:*` actions - like Lex and Transcribe, Textract is unreadable without the opt-in read policy, so the job-status read is refused. The shared S3/KMS/IAM/SNS reads that establish the role and resource policies are available. Until that delta is deployed, state the gap plainly and mark the affected `textract:*` reads `CANNOT_DETERMINE` naming the operation rather than inferring a pass.

Match condition keys (`aws:SourceAccount`/`aws:SourceArn`) case-insensitively - IAM evaluates them case-insensitively and tooling stores them in varying case, so a case-sensitive string match can miss a policy that is actually present.

## References

- Configuring Textract for async operations (SNS `AmazonTextract` prefix, service role, trust policy): https://docs.aws.amazon.com/textract/latest/dg/api-async-roles.html
- NotificationChannel (RoleArn + SNSTopicArn): https://docs.aws.amazon.com/textract/latest/APIReference/API_NotificationChannel.html
- DocumentTooLargeException (10 MB sync / 500 MB async PDF): https://docs.aws.amazon.com/aws-sdk-php/v3/api/api-textract-2018-06-27.html
- Cross-service confused deputy prevention (SourceAccount/SourceArn): https://docs.aws.amazon.com/textract/latest/dg/api-async-roles.html
