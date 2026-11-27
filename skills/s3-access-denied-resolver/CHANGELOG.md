# Changelog

## 1.0.0

- Initial release. Read-only diagnosis of Amazon S3 403 AccessDenied. Walks the
  ten layers that can deny a request (SCP/RCP, VPC endpoint policy, Block Public
  Access, bucket policy, access point policy, identity policy, permissions
  boundary, session policy, Object Ownership/ACLs, KMS key policy), names the
  denying layer and statement, and proposes a policy diff for human review.
- Assigns each layer one verdict from a closed set (`DENIED_BY`,
  `WOULD_ALSO_DENY`, `ALLOWED_BUT_UNVERIFIABLE`, `CANNOT_DETERMINE`,
  `NOT_APPLICABLE`). There is no plain "allowed" verdict.
- Reads policy documents directly and uses IAM policy simulation only to
  corroborate, because simulation does not evaluate VPC endpoint or session
  policies.
- Separates same-account rules (an allow in the identity or the resource-based
  policy is enough) from cross-account rules (both are required).
- Reads object metadata only and skips `HeadObject` unless it is already
  permitted, because `s3:GetObject` also allows reading object contents.
- Checks causes outside the ten layers when every layer is clean: Requester
  Pays, Object Lock, SSE-C blocking and access point network origin.
- Denial-message wording in `references/denial-message-hints.md` comes from the
  Amazon S3 User Guide topic on 403 errors. KMS error wording is not documented
  there and is not matched as fixed text.
- Functional scenarios plant one fault each:
  - 01 bucket policy denies `s3:GetObject` to all principals except one named
    role.
  - 02 key policy denies `kms:Decrypt` to all principals except one named role,
    while the reader's identity policy allows it.
  - 03 permissions boundary allows only `s3:ListBucket`.
  - 04 identity policy grants `s3:GetObject` on the bucket ARN instead of
    `bucket/*`.
  - 05 gateway endpoint policy allows only a different bucket, reached from a
    private-subnet instance with SSM access.
- Not covered: an SCP/RCP scenario (needs an Organizations test account),
  Block Public Access, access point, session policy and ACL scenarios.
- Falls back to AWS Config, the owning CloudFormation stack, CloudTrail and an
  operator-supplied paste when the Agent Space refuses bucket-level S3 reads, and
  names the source each verdict rests on.
