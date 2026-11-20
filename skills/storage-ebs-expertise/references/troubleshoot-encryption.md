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
3. **Read who may use the key.** `GetKeyPolicy` and `ListGrants`. The principal attaching or starting (the user or role, and the instance's service path through Amazon EBS) must be allowed to use the key. Report the missing permission by name, as found in the policy.
4. **Sharing across accounts.**
   - A snapshot encrypted with the default AWS managed key cannot be shared. Copy it with a customer managed key first.
   - With a customer managed key, share the snapshot (`createVolumePermission`) and also allow the destination account in the key policy.
   - For cross-Region copies, the destination needs a key in the destination Region.
5. **Encryption by default.** `GetEbsEncryptionByDefault` and `GetEbsDefaultKmsKeyId` per Region. The setting is per Region and applies to new volumes and snapshot copies.
6. **Re-encrypting an existing volume.** There is no in-place change. Proposed steps: create a snapshot, copy it with encryption and the chosen key (or create a volume from the snapshot with encryption on), create the new volume, stop the application, swap the volumes, verify, then retire the old volume. The agent proposes these steps; it does not run them.

## Decision rules

- Key state first, then key policy and grants, then sharing.
- If the key is usable and permissions look correct, check whether the error mentions a different key ID than the one on the volume.
- Never suggest disabling encryption as a fix.

## What to report

The verdict template in [finding-logic.md](finding-logic.md). Binding layer is "Not applicable" unless a performance question is also asked. Evidence includes the key ID as returned by the API, its state, its manager, and the policy statement or grant that is missing.

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
