# S3 authorization layers, account rules and caveats

## The ten layers

S3 evaluates every layer that applies to the request. Any explicit deny wins,
and the request also needs an allow (see the account rules below). The table
lists the layers in the order to read them, outermost first.

| # | Layer | Read with | Typical denial |
|---|---|---|---|
| 1 | SCP / RCP (Organizations) | `organizations:ListPoliciesForTarget`, `DescribePolicy` | Explicit deny on `s3:*` outside approved regions or principals |
| 2 | VPC endpoint policy | `ec2:DescribeVpcEndpoints` | Endpoint policy scoped to other buckets |
| 3 | Block Public Access | `s3:GetPublicAccessBlock` (bucket), `s3control:GetPublicAccessBlock` (account) | Public grant ignored or rejected |
| 4 | Bucket policy | `s3:GetBucketPolicy` | Explicit deny (`aws:SourceVpce`, `aws:SecureTransport`, `aws:PrincipalOrgID`, `aws:PrincipalArn`) or no allow for a cross-account caller |
| 5 | Access point policy | `s3:GetAccessPointPolicy` | Access point does not delegate, or bucket does not delegate to access points |
| 6 | Identity policy | `iam:ListAttachedRolePolicies`, `GetPolicyVersion`, `ListRolePolicies`, `GetRolePolicy` | No allow for the action or resource ARN (bucket vs `bucket/*`) |
| 7 | Permissions boundary | `iam:GetRole`, `iam:GetPolicyVersion` | Boundary omits the action |
| 8 | Session policy | CloudTrail `AssumeRole` event for the session, if readable | Session policy narrower than the role |
| 9 | Object Ownership / ACLs | `s3:GetBucketOwnershipControls`, `GetObjectAcl` | Object owned by another account under `ObjectWriter`; ACL-based grant ignored under `BucketOwnerEnforced` |
| 10 | KMS key policy and grants | `s3:GetBucketEncryption`, `kms:GetKeyPolicy`, `ListGrants`; `s3:HeadObject` only if granted | Caller lacks `kms:Decrypt` / `kms:GenerateDataKey`; cross-account key not shared |

`Read with` lists API operations. The IAM action behind a few differs from the
API name (for example `GetBucketEncryption` needs `s3:GetEncryptionConfiguration`);
the README lists the IAM actions.

## Account rules

- **Same account:** an allow in the identity policy or in the resource-based policy (bucket or access point) is enough, unless a boundary, session policy or SCP also applies. An explicit deny anywhere still wins. A missing allow in one policy is not a finding if the other allows.
- **Cross-account:** the request needs an allow in **both** the identity policy (caller's account) and the bucket policy (bucket's account), plus KMS key-policy access if the object uses a customer managed key. Say which account you could not read.
- **Messages:** S3 names the denying policy type only for same-account or same-organization callers. A cross-account caller outside the organization gets a bare "Access Denied", so walk every layer.

## Simulation caveats

`iam:SimulatePrincipalPolicy` does not evaluate VPC endpoint policies, does not
fully evaluate SCPs or RCPs without context, and cannot see session policies.
Never report a layer as allowed only because simulation said so.

## Other causes outside the ten layers

If every layer comes back clean, check these before concluding: Requester Pays
enabled on the bucket (request needs the requester-pays header), S3 Object Lock
on a permanent delete, a bucket that blocks SSE-C writes, and an access point
whose network origin is a VPC the request does not come from.

## When a direct read is blocked

In some environments the agent's S3 read tool refuses bucket-level calls
(`GetBucketPolicy`, `GetBucketEncryption`, `GetBucketOwnershipControls`,
`GetPublicAccessBlock`) with "blocked by policy and was not executed". Do not retry
the same call. Try these sources in order, and use the first that answers:

1. **AWS Config.** `GetResourceConfigHistory` or `BatchGetResourceConfig` for
   `AWS::S3::Bucket`. The latest configuration item holds the bucket policy
   (`BucketPolicy`), Block Public Access (`PublicAccessBlockConfiguration`),
   default encryption (`ServerSideEncryptionConfiguration`) and the ACL
   (`AccessControlList`). It is only as current as the last recorded change, and it
   exists only where Config records S3 buckets.
2. **The owning CloudFormation stack.** If the bucket carries an
   `aws:cloudformation:stack-name` tag, `GetTemplate` shows the policy the stack
   deployed. It does not show changes made outside the stack.
3. **CloudTrail.** `LookupEvents` for the failed request. The `errorMessage` names
   the denying policy type, which narrows the layer even when no document can be read.
4. **Ask the operator.** Name the exact command to run and the output to paste back,
   for example `aws s3api get-bucket-policy --bucket <bucket>`.

Say which source each verdict rests on. A policy read from Config or a template may
be stale, so mark that layer `ALLOWED_BUT_UNVERIFIABLE` rather than treating the
read as final unless it names the denying statement. If none of the four answers a
layer, mark it `CANNOT_DETERMINE` and say what would resolve it.

