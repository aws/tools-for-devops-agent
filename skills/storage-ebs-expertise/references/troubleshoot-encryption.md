# Troubleshoot: encryption and AWS KMS

Built from public documentation; not yet live-tested. Validate this path in a non-production account before relying on it.

## When this path applies

- An encrypted volume will not attach, or an instance with encrypted volumes will not start.
- Sharing an encrypted snapshot or AMI with another account fails, or the other account cannot use it.
- Questions about encryption by default.
- Encrypting an existing unencrypted volume, or changing the key of an encrypted one.

## Procedure

1. **Read the volume or snapshot.** `DescribeVolumes` or `DescribeSnapshots`: `Encrypted`, `KmsKeyId`.
2. **Read the key.** AWS KMS `DescribeKey` on `KmsKeyId`: `KeyState` (Enabled, Disabled, PendingDeletion), `KeyManager` (AWS or CUSTOMER), Region.
   - Disabled or pending deletion: the key cannot be used, so the volume cannot be attached or used. Recommend re-enabling the key or cancelling the deletion, as a proposal (see Safety rules).
3. **Read who may use the key.** `GetKeyPolicy` and `ListGrants`. The principal attaching or starting (the user or role, and the instance's service path through Amazon EBS) must be allowed to use the key. When a volume is attached, Amazon EC2 calls AWS KMS `CreateGrant` and `Decrypt` for the volume's data key. The key policy and grants alone do not prove a permission failure:
   - **IAM policy.** Access to a key depends on the key policy, grants and the principal's IAM policies together. This skill cannot read IAM policies (they are not in its read-only allowlist). Ask the customer to check the IAM policies of the principal that made the call for the AWS KMS actions on this key, including any explicit Deny.
   - **The actual denial.** If the optional AWS CloudTrail `LookupEvents` is available, look for the AWS KMS events (`CreateGrant`, `Decrypt`, `GenerateDataKeyWithoutPlaintext`) on this key around the failure time and read their `errorCode` and `errorMessage` and the calling principal. Use the error text the customer saw as well.
   - Name a KMS permission failure as the cause only when the actual denial (from AWS CloudTrail or the customer's error text) matches the gap found in the key policy, grants or IAM policy. Otherwise report it as an unconfirmed likely cause, and list under Gaps what could not be checked (IAM policies, AWS CloudTrail).
4. **Sharing across accounts.**
   - A snapshot encrypted with the default AWS managed key cannot be shared. Copy it with a customer managed key first.
   - With a customer managed key, share the snapshot (`createVolumePermission`) and also allow the destination in the key policy. Cross-account use also needs an IAM policy in the destination account that allows the principal to use the key.
   - Keep any proposed cross-account access to the minimum: the specific principal that needs it (a named role or user in the destination account where the customer can name one, otherwise the destination account), the specific key, and only the actions the Amazon EBS share-the-key page lists (`kms:DescribeKey`, `kms:CreateGrant`, `kms:GenerateDataKey`, `kms:GenerateDataKeyWithoutPlaintext`, `kms:ReEncrypt`, `kms:Decrypt`). Limit `kms:CreateGrant` with the `kms:GrantIsForAWSResource` condition. In the destination IAM policy, set `Resource` to the key ARN, not `*`. Never use `"Principal": "*"`.
   - For cross-Region copies, the destination needs a key in the destination Region.
5. **Encryption by default.** `GetEbsEncryptionByDefault` and `GetEbsDefaultKmsKeyId` per Region. The setting is per Region and applies to new volumes and snapshot copies.
6. **Re-encrypting an existing volume.** There is no in-place change. Proposed steps: create a snapshot, copy it with encryption and the chosen key (or create a volume from the snapshot with encryption on), create the new volume, stop the application, swap the volumes, verify. The agent proposes these steps; it does not run them. Deleting the old volume is a manual step for the customer after the owner confirms the new volume is good, because AWS DevOps Agent refuses delete-class operations.

## Decision rules

- Key state first, then key policy, grants and IAM policy, then the actual denial, then sharing.
- If the key is usable and permissions look correct, check whether the error mentions a different key ID than the one on the volume.
- Never suggest disabling encryption as a fix.

## What to report

The verdict template in [finding-logic.md](finding-logic.md). Binding layer is "Not applicable" unless a performance question is also asked. Evidence includes the key ID as returned by the API, its state, its manager, the policy statement or grant that is missing, the AWS CloudTrail error if found, and whether the cause is confirmed or unconfirmed.

## Safety rules

- This path is read-only.
- No key policy change, grant change, key enable, deletion cancel, or encryption-by-default change runs without a directed action approved on the approval card.
- Never suggest disabling encryption or removing a key policy statement that other resources depend on.

## Sources

- Amazon EBS encryption: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption.html
- How Amazon EBS encryption works: https://docs.aws.amazon.com/ebs/latest/userguide/how-ebs-encryption-works.html
- Encryption by default: https://docs.aws.amazon.com/ebs/latest/userguide/encryption-by-default.html
- Share the KMS key for an encrypted snapshot: https://docs.aws.amazon.com/ebs/latest/userguide/share-kms-key.html
- Share a snapshot: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modifying-snapshot-permissions.html
- Copy a snapshot: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-copy-snapshot.html
- Allowing users in other accounts to use a KMS key (key policy and IAM policy both needed, least privilege): https://docs.aws.amazon.com/kms/latest/developerguide/key-policy-modifying-external-accounts.html
- Logging AWS KMS API calls with AWS CloudTrail: https://docs.aws.amazon.com/kms/latest/developerguide/logging-using-cloudtrail.html
