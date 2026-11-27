---
name: s3-access-denied-resolver
description: >-
  Diagnose an Amazon S3 403 AccessDenied. Use this skill whenever an S3 request
  fails with AccessDenied or 403 Forbidden: GetObject, PutObject, ListBucket,
  HeadObject or CopyObject calls, messages such as "is not authorized to
  perform: s3:" or "explicit deny in a resource-based policy", a kms:Decrypt
  denial on an SSE-KMS object, a cross-account bucket that cannot be read, or a
  private-subnet instance that gets 403 through an S3 gateway endpoint. Walks
  the ten layers that can deny an S3 request (SCP/RCP, VPC endpoint policy,
  Block Public Access, bucket policy, access point policy, identity policy,
  permissions boundary, session policy, Object Ownership/ACLs, KMS key policy),
  names the denying layer and statement, and proposes the smallest fix for human
  review. Not for 503 SlowDown, replication or lifecycle issues, CloudFront
  403s, Lake Formation access, Bedrock or SageMaker role denials, or a
  least-privilege review with no observed failure. Read-only.
metadata:
  author: saadnu-aws
  version: "1.0.0"
  summary: "Read-only root-cause diagnosis for S3 403 AccessDenied: walks ten authorization layers, names the denying layer and statement, and proposes a fix for human review."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Amazon S3, AWS IAM, Amazon VPC, AWS CloudTrail, AWS Config"
  aws-devops-agent-skills.technical-domains: "Storage, Security"
---

# S3 Access Denied Resolver

Find out why an S3 request was denied. Walk the S3 authorization layers, name
the layer that denied the request, and propose a scoped fix for human review.
Read-only throughout. Never apply a policy change.

## Checklist

- [ ] **Step 1 - Classify:** confirm an observed S3 403/AccessDenied (not throttling, not CloudFront, not Lake Formation). Stop otherwise.
- [ ] **Step 2 - Pin the request:** principal ARN, action, bucket, key, request path (internet, gateway endpoint, interface endpoint, access point), and whether caller and bucket are in different accounts.
- [ ] **Step 3 - Read the denial:** if a CloudTrail event or error message exists, read the policy-type hint in it first (see [references/denial-message-hints.md](references/denial-message-hints.md); load it only when a message or CloudTrail `errorMessage` exists); it narrows the search.
- [ ] **Step 4 - Collect evidence, policy reads first:** read each layer's document directly. Use `SimulatePrincipalPolicy` only as corroboration. If a read is refused as "blocked by policy", do not retry it; load [references/layers.md](references/layers.md#when-a-direct-read-is-blocked) for the fallback sources.
- [ ] **Step 5 - Walk the layers:** evaluate all ten layers; do not stop at the first one that passes.
- [ ] **Step 6 - Assign verdicts** from the closed set below.
- [ ] **Step 7 - Propose a fix:** the smallest change at the denying layer, as a diff. Label any later blockers.
- [ ] **Step 8 - Validate before presenting:** confirm each `DENIED_BY` verdict rests on a policy statement you read, not on an assumption or a simulation result alone; confirm the proposed diff touches only the denying layer and does not widen access beyond the failing request; confirm every layer you could not read is `CANNOT_DETERMINE`.
- [ ] **Step 9 - Deliver the report** in the format below.

## The ten layers

S3 evaluates every layer that applies to the request. Any explicit deny wins, and the request also needs an allow. The layers, outermost first: 1 SCP/RCP, 2 VPC endpoint policy, 3 Block Public Access, 4 bucket policy, 5 access point policy, 6 identity policy, 7 permissions boundary, 8 session policy, 9 Object Ownership/ACLs, 10 KMS key policy and grants.

Load [references/layers.md](references/layers.md#the-ten-layers) at Step 4 for the API call that reads each layer and its typical denial. Load [references/layers.md](references/layers.md#account-rules) at Step 6, before assigning verdicts, for the same-account and cross-account allow rules. Load [references/layers.md](references/layers.md#other-causes-outside-the-ten-layers) only when every layer comes back clean.

## Verdicts (closed set)

- `DENIED_BY` - this layer denies the request. Name one root-cause layer: the one the denial message names, otherwise the first denying layer in table order.
- `WOULD_ALSO_DENY` - another layer that denies, or would still deny once the root cause is fixed.
- `ALLOWED_BUT_UNVERIFIABLE` - the document read allows the request, but conditions or context could not be fully checked.
- `CANNOT_DETERMINE` - the layer could not be read (missing permission, other account). State what is needed.
- `NOT_APPLICABLE` - the layer does not apply (for example, no endpoint in the path, SSE-S3 encryption).

There is no plain "allowed" verdict.

## Report format

1. **Root cause** - one sentence naming the layer and the statement (Sid or policy name).
2. **Layer table** - all ten layers with verdict and one-line evidence.
3. **Proposed fix** - JSON diff for the denying layer only, with a note that it is for human review.
4. **Subsequent blockers** - any `WOULD_ALSO_DENY` layers and their fixes.
5. **Could not check** - every `CANNOT_DETERMINE` layer and what access would resolve it.

## Gotchas

- A "blocked by policy" refusal on an S3 read is a platform limit, not a finding about the bucket. Use the fallback sources, state which one you used, and never infer a layer's content from the refusal.
- `SimulatePrincipalPolicy` ignores VPC endpoint policies and session policies and only partly evaluates SCPs and RCPs. A simulation result of "allowed" is never a verdict on its own.
- A cross-account caller outside the organization gets a bare "Access Denied" with no policy type, so the message cannot narrow the search. Walk every layer.
- A missing allow in the identity policy is not a finding when the bucket policy allows a same-account caller, and the reverse. Check both before flagging.
- A resource ARN of `arn:aws:s3:::bucket` covers bucket-level actions such as `ListBucket` only. Object actions need `arn:aws:s3:::bucket/*`.
- A KMS key policy that allows only the account root does not by itself give the role `kms:Decrypt`. The role's identity policy must also allow it.
- Fixing the root-cause layer often exposes the next denial (for example, the key policy after the bucket policy). Report those as `WOULD_ALSO_DENY` up front.

## Output discipline

Do not narrate API calls or paste raw policy documents. Speak only when starting,
asking a question, or delivering the report.

## Safety

Read-only. Never call `PutBucketPolicy`, `PutPublicAccessBlock`, `PutKeyPolicy`,
`PutRolePolicy`, or any other write API. Read object metadata only: never read
object contents, and skip `HeadObject` when it is not already permitted. Redact
account IDs and ARNs from example output when the user asks for a shareable
version.
