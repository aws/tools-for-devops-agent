# Changelog
## 1.0.0
- Evals: `tr-spot-interruption` is removed (scored the same with and without the skill in two runs).
- Evals: `reg-promote-without-retrain` is removed (general guidance, scored the same with and without the skill).
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- Evals: `training-job-failed-malformed-data` is replaced by `training-job-failed-internal-error`, which matches the eval account's failed job (AlgorithmError, SageMaker internal 500). `tr-execution-role-s3` states the bucket's SSE-KMS customer managed key.
- Evals: `tr-quota-resourcelimitexceeded`, `tr-passrole-denied` and `tr-job-fails-no-logs` are removed (scored the same with and without the skill); check-id assertions are dropped from questions that name no account resource.

- PR #268 review item 2 (evals): `capacity-vs-quota` names `InsufficientCapacityError`, the failure reason SageMaker reports, instead of EC2's `InsufficientInstanceCapacity`.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: `servicequotas:` prefix (was `service-quotas:`); artifact and channel checks use `s3:ListBucket` only (no HeadObject / `s3:GetObject`); `iam:SimulatePrincipalPolicy` replaced by a static policy read.
  - Report template: input-check hint reads `ListObjectsV2` key metadata (`s3:ListBucket`), no HeadObject.
- Initial release. Merges the earlier SageMaker training and Model Registry skills into one skill.
- Training / customization: Nova and JumpStart fine-tuning job failures, capacity vs quota, Pending-on-capacity, missing checkpoints, billed GPU cost (LLM-SM-TRAIN-001..008).
- Model Registry: registration, approval gating, lineage, package-group boundary and CMK encryption (LLM-SM-REG-001..004).
- Check-ids and severities unchanged; other families' ids removed from the shared references.
- Routes to other skills replaced by an optional Related skills section.
- `api-quirks.md` renumbered to traps §1–§7 (training §1–§5, registry "no datapoints" §6, `Approved` ≠ deployed §7); the "no datapoints" trap now states that the registry publishes no metric namespace.
- `known-causes.md` merged into one file: training §1–§7, Model Registry §8–§14.
- The registry catalog intro and report template no longer name the endpoint check-id for a deployed endpoint lacking lineage; they name the SageMaker endpoint area instead.
- Old evals results (structure, best-practices, functional) not carried over; best-practices and functional must be re-run.
