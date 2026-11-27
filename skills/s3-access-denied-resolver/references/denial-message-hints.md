# Reading S3 AccessDenied messages

Same-account and same-organization S3 403 responses, and the matching CloudTrail
`errorMessage`, name the policy type that denied the request. Map the wording to
a starting layer. The wording below is taken from the Amazon S3 User Guide topic
"Troubleshoot access denied (403 Forbidden) errors in Amazon S3".

| Message wording | Start at layer |
|---|---|
| `with an explicit deny in a service control policy, with policy ARN: ...` | 1 |
| `because no service control policy allows the s3:<Action> action` | 1 |
| `with an explicit deny in a resource control policy, with policy ARN: ...` | 1 |
| `because no VPC endpoint policy allows the s3:<Action> action` | 2 |
| `with an explicit deny in a VPC endpoint policy` | 2 |
| `because public ACLs are prevented by the BlockPublicAcls setting in S3 Block Public Access` | 3 |
| `because public policies are prevented by the BlockPublicPolicy setting in S3 Block Public Access` | 3 |
| `because no resource-based policy allows the s3:<Action> action` | 4 or 5 (also 3 when `IgnorePublicAcls` is on) |
| `with an explicit deny in a resource-based policy` | 4 or 5 (also 3 when `RestrictPublicBuckets` is on) |
| `because no identity-based policy allows the s3:<Action> action` | 6 |
| `with an explicit deny in an identity-based policy, with policy ARN: ...` | 6 |
| `because no permissions boundary allows the s3:<Action> action` | 7 |
| `with an explicit deny in a permissions boundary, with policy ARN: ...` | 7 |
| `because no session policy allows the s3:<Action> action` | 8 |
| `with an explicit deny in a session policy, with policy ARN: ...` | 8 |

## Notes

- Explicit denials from SCPs, RCPs, identity policies, session policies and
  permissions boundaries include the policy ARN. Resource-based and VPC
  endpoint denials do not.
- When several policy types, or several reasons, deny a request, the message
  reports only one. Check the other layers anyway.
- Block Public Access reuses the resource-based wording for `IgnorePublicAcls`
  (implicit) and `RestrictPublicBuckets` (explicit). Read the layer 3 settings
  before concluding the bucket policy is wrong.
- Cross-account callers outside the same organization, and directory-bucket
  requests, get a bare `Access Denied` with no hint. Walk every layer.
- S3 documents that same-organization requests denied by a VPC endpoint policy
  may not get the enhanced message. Walk layer 2 when the caller is in a private
  subnet and the message is bare.
- An SSE-KMS failure is raised by KMS and names a `kms:` action. The S3 topic
  does not give its exact wording, so treat any `kms:Decrypt` or
  `kms:GenerateDataKey` mention as a pointer to layer 10 rather than matching
  fixed text.
