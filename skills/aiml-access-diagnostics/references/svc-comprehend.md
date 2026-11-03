# Service Specifics - Amazon Comprehend

Load only when the failing call is a Comprehend operation.

Comprehend is the service where the **data access role** creates a delayed failure that
surfaces nowhere the caller can see it. Like Textract, asynchronous jobs accept a role
and succeed at submission. Unlike Textract, Comprehend also uses the role to read input AND
write output - meaning the job can fail reading, fail writing, or both, and the error
appears only in the job status, not at the caller.

The added complexity over Textract: Comprehend jobs can optionally run inside a VPC. When
they do, Comprehend creates the elastic network interfaces itself from the subnets and
security groups you pass in `VpcConfig` - the data access role does NOT need EC2
permissions. The VPC failures are network-path problems (no S3/KMS VPC endpoint or NAT, or
a security group that blocks egress), which catch every customer who assumes the role is
the problem.

## Applicable hops

| Call | Hop 1 | Hop 2 | Hop 3 | Hop 4 | Hop 5 | Hop 6 |
|---|---|---|---|---|---|---|
| `DetectEntities`, `DetectSentiment`, `DetectKeyPhrases` (sync) | ✓ | n/a | n/a | n/a | n/a | ✓ |
| `StartEntitiesDetectionJob`, `StartSentimentDetectionJob` (async) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `CreateDocumentClassifier`, `CreateEntityRecognizer` (training) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `DescribeEntitiesDetectionJob`, `ListEntitiesDetectionJobs` (polling) | ✓ | n/a | n/a | n/a | n/a | ✓ |

Synchronous calls (`DetectEntities`, `DetectSentiment`) accept text inline - no S3, no
role, no downstream dependencies. They are single-hop problems. If they fail, it is
always the caller's permissions on the `comprehend:Detect*` action.

Asynchronous and training calls pass a `DataAccessRoleArn`. The full chain applies.

## Actions and resource ARNs

| Operation | IAM action | Resource ARN shape |
|---|---|---|
| Sync entity detection | `comprehend:DetectEntities` | `*` |
| Sync sentiment | `comprehend:DetectSentiment` | `*` |
| Sync key phrases | `comprehend:DetectKeyPhrases` | `*` |
| Sync PII detection | `comprehend:DetectPiiEntities` | `*` |
| Start async entities job | `comprehend:StartEntitiesDetectionJob` | `*` |
| Start async sentiment job | `comprehend:StartSentimentDetectionJob` | `*` |
| Start PII entities job | `comprehend:StartPiiEntitiesDetectionJob` | `*` |
| Train classifier | `comprehend:CreateDocumentClassifier` | `*` |
| Train recognizer | `comprehend:CreateEntityRecognizer` | `*` |
| Describe job | `comprehend:DescribeEntitiesDetectionJob` | `arn:aws:comprehend:<region>:<account>:entities-detection-job/<jobId>` |
| Use flywheel | `comprehend:StartFlywheelIteration` | `arn:aws:comprehend:<region>:<account>:flywheel/<flywheelName>` |

**Comprehend has a split resource model.** Most Start/Create actions use `Resource: "*"` -
there is no resource-level constraint on job submission. But Describe/Stop actions target
specific job ARNs. This means you cannot restrict WHO can submit jobs by ARN (only by action
or condition keys) - but you can restrict who can view or stop specific running jobs.

## The five failure modes

| # | Hop | What is missing | When it surfaces | Who needs the fix |
|---|---|---|---|---|
| 1 | 1 | Caller lacks `comprehend:Start*` | Immediately - `AccessDeniedException` | Caller's identity policy |
| 2 | 2 | Caller lacks `iam:PassRole` for the data access role | Immediately - `AccessDeniedException` | Caller's identity policy |
| 3 | 3 | Data access role trust policy omits `comprehend.amazonaws.com` | Immediately - `InvalidRequestException` ("The request is invalid" — a documented `StartEntitiesDetectionJob` error; the role cannot be assumed) | Data access role trust policy |
| 4 | 4a | Data access role cannot read from input S3 bucket | **Minutes later** - job status `FAILED`, message references S3 access | Data access role's permissions OR S3 bucket policy |
| 5 | 4b | Data access role cannot write to output S3 prefix | **Minutes later** - job status `FAILED` (completed processing but failed writing) | Data access role's permissions OR S3 bucket policy |

**Mode 4 and 5 are the same hop, different direction.** The data access role needs both
`s3:GetObject` + `s3:ListBucket` on the input path AND `s3:PutObject` on the output path.
Most customers grant one and forget the other. When the role can read but not write, the
job processes all documents, then fails at the end - wasting the entire compute time.

**Mode 3 has a console trap.** The Comprehend console role-creation wizard names the role
`AmazonComprehendServiceRole-*` and attaches the trust policy automatically. But if the
customer renames the role or creates it outside the console, the trust policy is frequently
missing. The console also only shows roles with names containing "Comprehend" and trust
policies including `comprehend.amazonaws.com` - a correctly-configured role with a different
naming convention will not appear in the console dropdown, leading customers to create
duplicates.

## Non-denial causes and the closed vocabulary

Comprehend has causes that **resemble an access error but are not an authorization
denial** — a VPC with no network path to S3/KMS, and a KMS call that fails inside the VPC.
In both, no IAM hop denied: the packets never reached the target, so there is no
authorization decision anywhere in the chain. Assigning `DENIED_BY` to either would assert
a denial that never happened, which is the error class this skill exists to prevent.

The six-token vocabulary in `finding-logic.md` is closed over **hop verdicts and finding
headings**, and neither cause is a hop verdict. No token is added. Instead:

- Every hop row keeps its own evidence-based verdict. A chain where nothing denied is
  reported as such, not bent to match the symptom.
- The finding renders under `### Service-specific: <cause name>`.
- The root-cause line takes the non-denial form, alongside the hop form and `❓ Undetermined`:

      **Root cause:** 🚫 Not an access denial — <one-line statement>

  See `finding-logic.md` "Root cause selection", case 3b. A non-denial root cause is only
  emitted from evidence actually read (the `VpcConfig` and route-table/endpoint state here);
  where that read was unavailable it is `CANNOT_DETERMINE` naming the operation, never
  inferred from the absence of a denial.

Comprehend's S3 read/write failures (modes 4 and 5) are different: the data access role
genuinely lacks an S3 permission, so those keep `DENIED_BY (service-specific)` as before.

## Non-IAM cause 1 - VPC network path (not role permissions)

When a job specifies `VpcConfig` (security groups + subnets), Comprehend creates the
elastic network interfaces itself and attaches them to its job containers. Per the
Comprehend VPC documentation: "Amazon Comprehend uses this information to create ENIs and
attach them to our job containers." The data access role does NOT need `ec2:*`
permissions - supplying valid subnets and security groups in `VpcConfig` is what is
required. A common mistake is copying a SageMaker or Glue execution-role pattern (which
does need EC2 permissions) onto a Comprehend data access role; Comprehend does not use it.

**The real VPC failure is the network path.** The ENI Comprehend creates inside your VPC
must still reach S3 (and KMS, if used). If the subnet has no S3 VPC endpoint and no NAT
gateway, or the security group blocks egress, the job fails with an S3 access error that
looks like mode 4 - but adding S3 permissions to the role will not fix it, because the
packets never leave the subnet. **Check the VPC route table and security group before
blaming the IAM role.**

**Finding body for VPC-network-path failure**
- verdict: none — this is not a hop verdict. Leave all six hop rows at their evidence-based
  verdicts. See "Non-denial causes and the closed vocabulary" above.
- root-cause line: "**Root cause:** 🚫 Not an access denial — the data access role has
  `s3:GetObject` but the job's VPC (`[subnetIds]`) has no route to S3"
- body: "The data access role has `s3:GetObject` permission but the Comprehend job runs in
  a VPC (`[subnetIds]`) with no route to S3. Add an S3 gateway VPC endpoint or a NAT
  gateway to the subnet route table. This is a network reachability issue, not an IAM
  issue — adding S3 permissions to the role will not fix it, because the packets never
  leave the subnet."

## Non-IAM cause 2 - Input data format mismatch

Comprehend jobs fail with `InvalidRequestException` when:
- ONE_DOC_PER_LINE format specified but input file is not newline-delimited
- S3 prefix contains no files (empty prefix)
- File encoding is not UTF-8

These are validation errors, not access errors. The job fails immediately at submission.

## Non-IAM cause 3 - KMS key inaccessible from VPC

When the job uses `VolumeKmsKey` or `OutputKmsKey` and runs in a VPC, the data access
role needs `kms:*` actions AND the VPC must have a KMS VPC endpoint (or NAT). The KMS
call originates from within the VPC - not from the Comprehend service. A role with correct
KMS permissions but a VPC with no KMS route will fail with a KMS access error that is
actually a network problem.

## Data access role requirements

### Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "comprehend.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "<accountId>"
        },
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:comprehend:<region>:<accountId>:*"
        }
      }
    }
  ]
}
```

Note: `ArnEquals` with a wildcard job suffix because the job ID is generated at submission
time - you cannot pre-populate it in the trust policy.

### Minimum permissions for async job (no VPC, no KMS)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::<inputBucket>",
        "arn:aws:s3:::<inputBucket>/<prefix>/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<outputBucket>/<outputPrefix>/*"
    }
  ]
}
```

**Common miss**: `s3:ListBucket` requires the bucket ARN without a path suffix.
`s3:GetObject` requires the object ARN with the path. Customers frequently write both
actions on the object ARN, which grants GetObject but silently fails ListBucket. The
job then fails with "Unable to list objects" - which looks like a GetObject failure but
is actually a ListBucket failure. The error message does not distinguish the two.

### Additional for VPC jobs

No extra role permissions are required - Comprehend creates the ENIs from the `VpcConfig`
you supply. Ensure the network path exists:
- S3 gateway VPC endpoint on the subnet's route table, OR a NAT gateway
- If KMS is used: KMS interface VPC endpoint, OR a NAT gateway
- Security group allows the required egress

### Additional for KMS-encrypted jobs

```json
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt",
    "kms:GenerateDataKey",
    "kms:DescribeKey",
    "kms:CreateGrant"
  ],
  "Resource": "arn:aws:kms:<region>:<account>:key/<keyId>"
}
```

`kms:CreateGrant` is required for `VolumeKmsKey` (Comprehend creates a grant on the key
for the duration of the job). Without it, the job fails with a KMS error that names the
key but does not mention grants. (Confirmed: AWS docs — "`kms:CreateGrant` permission is
required for volume encryption"; `kms:GenerateDataKey` for output encryption, `kms:Decrypt`
for encrypted input.)

## References

- Protect jobs with a VPC (ENI behavior): https://docs.aws.amazon.com/comprehend/latest/dg/usingVPC.html
- Role-based permissions for async operations (trust policy, S3 perms): https://docs.aws.amazon.com/comprehend/latest/dg/security_iam_id-based-policy-examples.html
- How Amazon Comprehend works with IAM (service/data-access role): https://docs.aws.amazon.com/comprehend/latest/dg/security_iam_service-with-iam.html
- CLI role creation + console naming constraint: https://docs.aws.amazon.com/comprehend/latest/dg/tutorial-reviews-create-role.html
- VPC + CMK enforcement condition keys: https://aws.amazon.com/blogs/machine-learning/enforce-vpc-rules-for-amazon-comprehend-jobs-and-cmk-encryption-for-custom-models/

## Hop 2 - PassRole specifics

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::<account>:role/<comprehendDataAccessRole>",
  "Condition": {
    "StringEquals": {
      "iam:PassedToService": "comprehend.amazonaws.com"
    }
  }
}
```

**Common confused-deputy trap**: A customer has a role that both Textract and Comprehend
use (common for document-processing pipelines). Their PassRole permission uses
`"iam:PassedToService": "textract.amazonaws.com"` - which blocks Comprehend from
receiving it. The error surfaces as `AccessDeniedException` on the Comprehend Start call,
but the customer checks the Comprehend actions (which are correct) and misses the PassRole
condition scoping it to the wrong service.

## Diagnostic sequence

1. **Is this sync or async?** Sync = single hop, check caller's `comprehend:Detect*`.
   Async/training = full chain.
2. **Did the Start/Create call succeed?** If no: check caller has `comprehend:Start*`
   (hop 1), then `iam:PassRole` with correct `PassedToService` (hop 2), then trust policy
   (hop 3).
3. **For post-submission failures:** Get job status via `DescribeEntitiesDetectionJob`.
   Read the `Message` field carefully - it usually names S3, KMS, or VPC.
4. **Does the job use VPC?** If yes: the role needs no EC2 permissions (Comprehend creates
   the ENIs). Check network reachability - S3/KMS VPC endpoint or NAT, and security group
   egress. Don't mistake a closed network path for an IAM problem.
5. **Input vs output failure:** If the message references the input prefix, it's read.
   If it references the output prefix (or says "unable to write"), it's write. They need
   different S3 actions.
6. **Cross-account S3?** Both the role's identity policy AND the bucket's resource policy
   must allow. Check both sides.
7. **Is KMS involved?** Check `VolumeKmsKey` and `OutputKmsKey` - each needs its own
   permissions, and if VPC, the network path to KMS must exist.

## Runtime permission reality and condition-key matching

Coverage is bounded by what the DevOps Agent role can read. This diagnosis uses `comprehend:Describe*`/`List*` (job-status reads) plus the shared `s3:GetBucketPolicy`, `kms:GetKeyPolicy`, `iam:GetRole`/`GetRolePolicy`, `ec2:Describe*` (VPC route-table, security-group, and endpoint checks), and `organizations:*` reads the engine already relies on. Confirmed by reading `AIDevOpsAgentAccessPolicy` (v12, 2026-11-02): `comprehend:Describe*` and `comprehend:List*` are granted to the agent role. If a read is refused at runtime, mark the affected hop `CANNOT_DETERMINE` naming the operation rather than inferring a pass.

Match condition keys (`aws:SourceAccount`/`aws:SourceArn`, and the `iam:PassedToService` scoping on the PassRole grant) case-insensitively - IAM evaluates them case-insensitively and tooling stores them in varying case, so a case-sensitive string match can miss a policy that is actually present.