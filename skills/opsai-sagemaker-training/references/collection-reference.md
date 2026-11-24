# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker training / customization job review or a SageMaker Model Registry governance review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

**Permissions.** The AWS managed policy `AIDevOpsAgentAccessPolicy` grants every read below (`sagemaker:Describe*` / `List*`, `servicequotas:Get*` / `List*`, `s3:ListBucket` and the IAM role and policy reads), so this skill has no template parameter. Two calls are never made: `s3:GetObject` (and the HeadObject operation it authorizes), because it returns customer data, so artifact and channel checks list keys, sizes and `LastModified` with `s3:ListBucket` and say that object contents were not read; and `iam:SimulatePrincipalPolicy`, which the agent runtime refuses even when granted (fallback below). `sagemaker:GetModelPackageGroupPolicy` is not in the managed policy and is not called: the group's resource policy is reported as not evaluated.

---

## SageMaker training & customization (TRAIN)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTrainingJobs` / `DescribeTrainingJob` | `TrainingJobStatus`, `SecondaryStatus`, `FailureReason`, `InputDataConfig` channels/`S3Uri`, `ResourceConfig` instance type/count, `HyperParameters`, `ModelArtifacts.S3ModelArtifacts`, `BillableTimeInSeconds` | LLM-SM-TRAIN-001..008 |
| `sagemaker:DescribeTrainingJob` on a Nova customization job (customization runs as a recipe-driven SageMaker training job; describe it by its training-job name) | recipe S3 reference, status, `FailureReason`, hyperparameter map | LLM-SM-TRAIN-001, 004, 007 |
| `servicequotas:GetServiceQuota` / `servicequotas:ListServiceQuotas` (service-code `sagemaker`; the CLI is `aws service-quotas`) | the training instance-type quota `Value` (0 = customer quota block) | LLM-SM-TRAIN-003 |
| `s3:ListBucket` (the ListObjectsV2 call) on the training output prefix | whether a model artifact/checkpoint key was actually produced (keys, sizes, `LastModified`; contents not read) | LLM-SM-TRAIN-008 |
| `s3:ListBucket` (the ListObjectsV2 call) on the input-channel / recipe prefix | whether the data channel is non-empty and the recipe object key exists (contents not read) | LLM-SM-TRAIN-006, LLM-SM-TRAIN-005 |
| `iam:GetRole`, `iam:ListAttachedRolePolicies` / `iam:ListRolePolicies` / `iam:GetRolePolicy` / `iam:GetPolicy` / `iam:GetPolicyVersion` on the execution role | S3 read/write and KMS decrypt scope (evaluated statically), trust policy for `sagemaker.amazonaws.com` | LLM-SM-TRAIN-005 |

**Fallback for `iam:SimulatePrincipalPolicy`** (never called): evaluate the execution role's policies read above against the job's S3 prefixes and KMS key, label the verdict "evaluated from policy documents, not simulated", and say what static reading cannot see: bucket and key policies unless read, SCPs, permission boundaries unless `iam:GetRole` shows one and it is read, and session policies.

## SageMaker model registry (REG)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListModelPackages` / `DescribeModelPackage` | registry lineage / approval status (`ModelApprovalStatus`, source training-job and dataset lineage, artifact `KmsKeyId`; the model package group policy needs `sagemaker:GetModelPackageGroupPolicy`, which is not called) | LLM-SM-REG-001, 002, 003, 004 |
