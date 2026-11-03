# Service Specifics - Amazon Rekognition

Load only when the failing call is a Rekognition operation.

Rekognition has the same **sync-vs-async split personality** as Textract, plus a third mode
(stream processors). The permission model depends entirely on which API is called:

- **Synchronous image ops** (`DetectLabels`, `DetectModerationLabels`, `DetectFaces` from S3)
  read S3 with the **caller's** credentials - no service role. The caller needs
  `s3:GetObject`.
- **Asynchronous video ops** (`StartLabelDetection`, `StartFaceDetection`,
  `StartContentModeration`) pass a **service role** via `NotificationChannel` to publish
  completion status to SNS.
- **Stream processors** (`CreateStreamProcessor`) pass a service role for Kinesis (and, for
  some types, S3 + SNS).

> **Feature status:** Rekognition **Streaming Video** and **Bulk Image Analysis** are no
> longer available to new customers (confirmed: AWS docs); other Rekognition features are
> unaffected. Diagnosing an existing stream processor is in scope; do not advise creating one.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `DetectLabels`, `DetectModerationLabels` (sync, from S3) | ✓ | n/a | n/a | n/a (caller's own S3) | n/a | ✓ |
| `StartLabelDetection`, `StartContentModeration` (async video) | ✓ | ✓ | ✓ | ✓ | ✓ (SNS topic policy) | ✓ |
| `CreateStreamProcessor` (streaming) | ✓ | ✓ | ✓ | ✓ | ✓ (Kinesis/S3/SNS) | ✓ |

For sync image ops the "role" is the caller itself - asking "what does the Rekognition role
need" is the wrong question, exactly as with Textract. Async and stream-processor ops pass a
service role and the full chain applies.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Sync detect (image) | `rekognition:DetectModerationLabels` | `*` |
| Start async video | `rekognition:StartLabelDetection` | `*` |
| Create stream processor | `rekognition:CreateStreamProcessor` | `arn:aws:rekognition:<region>:<account>:streamprocessor/<name>` |
| Pass the service role | `iam:PassRole` | `arn:aws:iam::<account>:role/<rekognitionServiceRole>` |

## The failure modes

| # | Hop | What is missing | When it surfaces | Who needs the fix |
|---|---|---|---|---|
| 1 | 1 | Caller lacks the `rekognition:*` action | Immediately - `AccessDeniedException` | Caller's identity policy |
| 2 | 1/4 | **Sync from S3**: the caller lacks `s3:GetObject` on the image | Immediately | Caller's identity policy (not a service role) |
| 3 | 2 | Caller lacks `iam:PassRole` for the service role (async/stream) | Immediately | Caller's identity policy |
| 4 | 3 | Service role trust policy omits `rekognition.amazonaws.com` | Immediately - role not assumable | Service role trust policy |
| 5 | 4/5 | **Async**: service role's `sns:Publish` does not cover the notification topic | **After analysis** - no completion notification | Service role's permissions (see below) |
| 6 | 4 | **Stream processor**: role lacks Kinesis read (video stream) / write (data stream), or S3/SNS | At create/run | Service role's permissions |

## Service-role SNS scope - the `AmazonRekognition` prefix (IAM, not a naming rule)

Like Textract, this is a **permissions** cause, not a Rekognition API naming rule. The managed
`AmazonRekognitionServiceRole` policy grants `sns:Publish` only to topics **prefixed
`AmazonRekognition`**. A `NotificationChannel` SNS topic whose name does not start with
`AmazonRekognition` falls outside that grant, so the role gets an **implicit deny** on
`sns:Publish` and the completion status is never published.

- verdict: `DENIED_BY` (service-specific) - a real implicit deny, not a non-denial cause.
- **How to check:** if the role uses `AmazonRekognitionServiceRole` (or any policy scoped to
  `AmazonRekognition*`) AND the topic name does not start with `AmazonRekognition`, the grant
  does not match. A custom `sns:Publish` grant naming the real topic ARN makes the prefix
  irrelevant.
- **Fix:** rename the topic to begin with `AmazonRekognition`, OR grant `sns:Publish` on the
  topic's exact ARN.

(Confirmed: AWS docs - "`AmazonRekognitionServiceRole` gives Amazon Rekognition Video access
to Amazon SNS topics that are prefixed with *AmazonRekognition*"; and the `NotificationChannel`
SNS topic "must have a topic name that begins with *AmazonRekognition* if you are using the
AmazonRekognitionServiceRole permissions policy.")

## Stream processor specifics

A stream processor passes a role that needs, depending on type:
- **Face search:** read the Kinesis **video** stream and write the Kinesis **data** stream.
- **Label detection / security monitoring:** read the Kinesis video stream, plus `s3:PutObject`
  to the output bucket and `sns:Publish` to the topic.

**KMS is two-sided** for an encrypted output bucket: the key policy must name the stream
processor's IAM role (`kms:Decrypt`, `kms:GenerateDataKey*`) AND the role's own policy must
allow the key. (Confirmed: AWS docs - the label-detection setup adds a key-policy statement
naming the label-detection role.)

## Service role trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "rekognition.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "<accountId>" },
        "ArnLike": { "aws:SourceArn": "arn:aws:rekognition:<region>:<accountId>:*" }
      }
    }
  ]
}
```

AWS documents these confused-deputy conditions for the Rekognition Video role: `aws:SourceArn`
in the form `arn:aws:rekognition:<region>:<account>:*` (wildcard the resource portion when it
is not known) plus `aws:SourceAccount`. Their absence is a security finding, not a denial
cause. (Confirmed: AWS docs, "Cross-service confused deputy prevention.")

## Diagnostic sequence

1. **Sync or async or stream?** Sync image op = caller's own `s3:GetObject`, no role. Async
   video / stream processor = service role, full chain.
2. **Async video, no completion notification?** Check the service role's `sns:Publish` scope
   against the topic name - the `AmazonRekognition` prefix trap (implicit deny, DENIED_BY).
3. **Stream processor failing?** Check the role's Kinesis read/write, and S3/SNS for
   label/security types; KMS both-sides if the output bucket is encrypted.
4. **Create call denied?** Caller `rekognition:*` (hop 1), `iam:PassRole` (hop 2), role trust
   naming `rekognition.amazonaws.com` (hop 3).

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis uses
`rekognition:Describe*`/`List*` (stream-processor reads) plus the shared `s3:GetBucketPolicy`,
`kms:GetKeyPolicy`, `iam:GetRole`/`GetRolePolicy`, and role S3/SNS/Kinesis permission reads.
Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): `rekognition:Describe*`
and `rekognition:List*` are granted to the agent role. If a read is refused at runtime, mark
the affected hop `CANNOT_DETERMINE` naming the operation rather than inferring a pass.

Match condition keys **case-insensitively** - the SNS topic policy and the role's
`aws:SourceAccount`/`aws:SourceArn` conditions can be stored in varying case (`AWS:` vs
`aws:`); IAM evaluates them case-insensitively, so a case-sensitive string match can miss a
policy that is actually present.

## References

- Configuring Amazon Rekognition Video (service role, SNS `AmazonRekognition` prefix): https://docs.aws.amazon.com/rekognition/latest/dg/api-video-roles.html
- Giving Rekognition Video access to your resources (stream processor roles; streaming closed to new customers): https://docs.aws.amazon.com/rekognition/latest/dg/api-streaming-video-roles.html
- Label-detection stream processor setup (Kinesis + S3 + SNS + KMS both-sides): https://docs.aws.amazon.com/rekognition/latest/dg/streaming-labels-setting-up.html
- NotificationChannel (SNS topic must begin with AmazonRekognition under the managed policy): https://docs.aws.amazon.com/sdk-for-ruby/v3/api/Aws/Rekognition/Types/NotificationChannel.html
- Cross-service confused deputy prevention (trust-policy SourceArn/SourceAccount): https://docs.aws.amazon.com/rekognition/latest/dg/cross-service-confused-deputy-prevention.html
