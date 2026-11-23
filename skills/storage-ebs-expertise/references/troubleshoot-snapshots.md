# Troubleshoot: snapshots, AMIs, lifecycle and recovery

## When this path applies

- "Which snapshots can I safely delete?", "my snapshot costs keep going up"
- A cross-Region or cross-account snapshot copy did not arrive
- AMI creation is stuck or slow
- Questions about Amazon Data Lifecycle Manager, AWS Backup snapshots or Recycle Bin
- Recovering a deleted snapshot or volume

## Procedure

Run per Region.

1. **Inventory.** `DescribeSnapshots --owner-ids self`: ID, source `VolumeId`, size, `StartTime`, `State`, `Progress`, `StorageTier`, tags.
2. **Map AMI dependencies.** `DescribeImages --owners self`: build a map from every `BlockDeviceMappings[].Ebs.SnapshotId` to its AMI.
3. **Check the source volume.** `DescribeVolumes` for each source `VolumeId`. Record whether it still exists.
4. **Check sharing.** `DescribeSnapshotAttribute --attribute createVolumePermission`. A non-empty list means the snapshot is shared with other accounts or public.
5. **Identify management by tags, never by names.**
   - `aws:dlm:*` tags: managed by Amazon Data Lifecycle Manager.
   - `aws:backup:*` tags, or an AWS Backup recovery point for the source volume from `ListRecoveryPointsByResource` called with the parameter `{"ManagedByAWSBackupOnly": true}`: managed by AWS Backup. Without that parameter, the call also returns Amazon EBS snapshots that AWS Backup did not create, so a manual snapshot would be misread as managed by AWS Backup.
   - A name or description that looks like a policy name is not evidence.
6. **Check reversibility.** Recycle Bin `ListRules --resource-type EBS_SNAPSHOT` and Amazon Data Lifecycle Manager `GetLifecyclePolicies`. If a read is held behind an approval gate or denied, say that reversibility is unconfirmed and list it under Gaps.
7. **Check locks.** `DescribeLockedSnapshots`. A locked snapshot cannot be deleted while the lock applies. It gets the Locked tier.
8. **Classify** each snapshot with the tier table below and report.

## Decision rules

### Safety tiers

Check the rows top to bottom. The first row that matches decides the tier.

| Condition | Tier | Action |
|---|---|---|
| Backs a registered AMI | **Do not delete** | The AMI depends on it. If the AMI is no longer needed, deregister the AMI first. The root snapshot of a registered AMI cannot be deleted |
| Shared with other accounts or public | **Coordinate first** | Deleting it breaks the other accounts. Confirm with them |
| Locked (listed by `DescribeLockedSnapshots`) | **Locked** | Cannot be deleted while the lock applies. Report the lock mode and expiry from `DescribeLockedSnapshots`. Do not propose deletion. If the operator wants it gone, they decide on the lock first, per the snapshot lock guide |
| Managed by AWS Backup: the snapshot has an `aws:backup:*` tag, or `ListRecoveryPointsByResource` with `ManagedByAWSBackupOnly` set to true returns it. A recovery point from a call without that parameter is not evidence, because that call also lists snapshots that AWS Backup did not create | **Manage in AWS Backup** | Change retention in AWS Backup, not with Amazon EC2 calls |
| Managed by Amazon Data Lifecycle Manager (`aws:dlm:*` tags), or the source volume still exists (any snapshot of a volume that still exists, manual or not) | **Verify** | Confirm the owner and the retention need. For DLM snapshots, adjust the policy retention instead of deleting by hand. For a manual snapshot of an existing volume, ask whether it is still a needed restore point |
| Source volume gone, no AMI, not shared, not locked, not managed | **Needs owner review** | Do not recommend deletion. This snapshot may be the only remaining copy of the data. List it for the owner and ask them to confirm that they no longer need the data before anyone deletes it |

Every snapshot matches at least one row, and the first match decides. An AMI-backing, shared or locked snapshot can never be in the Needs owner review tier. Age alone never decides a tier. No tier is a deletion recommendation: the skill only reports what it found, and the owner decides.

### Cost

- Snapshots are incremental. Deleting a snapshot might not reduce storage cost, because other snapshots can reference its blocks. Any savings figure is an upper bound. Do not type a price; link the pricing page.
- For snapshots kept for compliance and rarely read, snapshot archive offers up to 75 percent lower storage cost for snapshots kept 90 days or longer. Archived snapshots convert to full snapshots, so check the size first.

### Cross-Region or cross-account copy did not arrive

1. In the destination, `DescribeSnapshots` for the copy: `State` (`pending`, `completed`, `error`) and `Progress`.
2. Encrypted source: the destination needs a usable AWS KMS key in the destination Region, and for cross-account copies the source key must be shared with the destination account. See [troubleshoot-encryption.md](troubleshoot-encryption.md).
3. Cross-account: the source must be shared with the destination account (`createVolumePermission`).
4. Check the concurrent copy quota in Service Quotas (see the Capacity and quota headroom section of [review-operational.md](review-operational.md)).

### AMI creation stuck or slow

The AMI stays `pending` until its backing snapshots complete. Read `DescribeImages` state and then `DescribeSnapshots` `State` and `Progress` for each backing snapshot. A large first snapshot takes longer because it is a full copy. If `Progress` does not change across several reads, follow the escalation rules in [finding-logic.md](finding-logic.md).

### Recovering deleted snapshots or volumes

- If a Recycle Bin rule matched the resource when it was deleted, it can be restored within the rule's retention period. Read `ListRules` and `GetRule`.
- If no rule matched, the deletion is permanent. Say so plainly. AWS Backup recovery points or older snapshots of the same volume can be alternatives.

### Escalation

Escalate on a snapshot stuck in `pending` with no progress, a delete that fails with an unexpected error, or a billing amount that does not match the snapshot inventory. Use the evidence pack in [finding-logic.md](finding-logic.md).

## What to report

The verdict template in [finding-logic.md](finding-logic.md). For questions about which snapshots can be deleted, the Answer lists the snapshots in the Needs owner review tier and asks the owner to confirm, for each one, that they no longer need the data. Evidence is a table: snapshot ID, tier, reason (AMI ID, shared with, `aws:dlm:*` policy ID, source volume state), size. Gaps say whether reversibility was confirmed.

## Safety rules

- This path is read-only.
- Deleting is a manual step for the customer, not a directed action. AWS DevOps Agent refuses delete-class operations, even with operator approval, so never propose `DeleteSnapshot` or `DeregisterImage` as a directed action.
- Give manual steps only after the owner has confirmed, for each snapshot, that they no longer need it. The customer runs them with their own credentials, one snapshot at a time:
  1. Re-read the snapshot with `aws ec2 describe-snapshots --snapshot-ids <snapshot-id>` and confirm it is the one the owner approved.
  2. If it backs an AMI the owner no longer needs, deregister the AMI first: `aws ec2 deregister-image --image-id <image-id>`.
  3. Delete the snapshot: `aws ec2 delete-snapshot --snapshot-id <snapshot-id>`.
- Never generate shell loops that delete in bulk.
- State for each snapshot whether a Recycle Bin rule will catch it if the customer deletes it.

## Sources

- AWS DevOps Agent directed actions (Operations the agent will not perform): https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-working-with-directed-actions.html

- Snapshots (incremental): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html
- Deleting a snapshot (AMI root snapshot, AWS Backup snapshots): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-snapshot.html
- Recycle Bin: https://docs.aws.amazon.com/ebs/latest/userguide/recycle-bin.html
- Amazon Data Lifecycle Manager: https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html
- Snapshot archive: https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive.html
- Copy a snapshot: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-copy-snapshot.html
- Share a snapshot: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modifying-snapshot-permissions.html
- Share the KMS key: https://docs.aws.amazon.com/ebs/latest/userguide/share-kms-key.html
- Snapshot lock: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshot-lock.html
- AWS Backup ListRecoveryPointsByResource (ManagedByAWSBackupOnly): https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_ListRecoveryPointsByResource.html
- Amazon EBS pricing: https://aws.amazon.com/ebs/pricing/
