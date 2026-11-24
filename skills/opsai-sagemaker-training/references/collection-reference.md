# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker training / customization job review or a SageMaker Model Registry governance review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

---

## SageMaker training & customization (TRAIN)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTrainingJobs` / `DescribeTrainingJob` | `TrainingJobStatus`, `SecondaryStatus`, `FailureReason`, `InputDataConfig` channels/`S3Uri`, `ResourceConfig` instance type/count, `HyperParameters`, `ModelArtifacts.S3ModelArtifacts`, `BillableTimeInSeconds` | LLM-SM-TRAIN-001..008 |
| `sagemaker:DescribeTrainingJob` on a Nova customization job (customization runs as a recipe-driven SageMaker training job; describe it by its training-job name) | recipe S3 reference, status, `FailureReason`, hyperparameter map | LLM-SM-TRAIN-001, 004, 007 |
| `servicequotas:GetServiceQuota` / `servicequotas:ListServiceQuotas` (CLI client `aws service-quotas`, service-code `sagemaker`) | the training instance-type quota `Value` (0 = customer quota block) | LLM-SM-TRAIN-003 |
| `s3:ListBucket` (ListObjectsV2) on the training output prefix (keys, sizes, dates; no object content) | whether a model artifact/checkpoint was actually produced | LLM-SM-TRAIN-008 |
| `s3:ListBucket` (ListObjectsV2) on the input-channel / recipe prefix | whether the data channel is non-empty and the recipe object exists (readability by the execution role is judged from its policies, not by reading the object) | LLM-SM-TRAIN-006, LLM-SM-TRAIN-005 |
| `iam:GetRole`, `iam:ListAttachedRolePolicies` / `iam:GetRolePolicy` / `iam:GetPolicyVersion` on the execution role | S3 read/write and KMS decrypt scope, trust policy for `sagemaker.amazonaws.com`, read action by action and labelled "read from policy documents, not simulated" (`iam:SimulatePrincipalPolicy` is refused in the DevOps Agent runtime) | LLM-SM-TRAIN-005 |

## SageMaker model registry (REG)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListModelPackages` / `DescribeModelPackage` | registry lineage / approval status (`ModelApprovalStatus`, source training-job and dataset lineage, model package group policy, artifact `KmsKeyId`) | LLM-SM-REG-001, 002, 003, 004 |
