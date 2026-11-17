# Known Causes — SageMaker Model Registry break-fix

Documented causes for the Model Registry problems operators report most, for answering a stated
symptom directly (SKILL.md, *Break-fix first*). Each bullet names the AWS page it rests on; verify
against that page before you answer. A cause tied to an `LLM-SM-REG-*` id is reported as that finding
with the catalog severity; a cause with no id is **guidance**, cited by URL, never given an invented
id. Where AWS says nothing (for example whether a model package group can span Regions, or whether
auto-created lineage entities can be tagged), say so rather than filling the gap.

## 1. A pipeline or training run finished but no model version appears

- **Registration is an explicit step**: a version is created by a `RegisterModel` step in a SageMaker pipeline, or by calling `CreateModelPackage` with the model package group name; a training job alone does not add a version. Distinguish this from an access error before changing permissions (LLM-SM-REG-001 when a customized artifact was never registered) ([register a model version](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-version.html)).

## 2. Anyone can deploy an unapproved version

- **Gate deployment on `ModelApprovalStatus`**: versions move between `PendingManualApproval`, `Approved` and `Rejected`, and with the SageMaker project templates a change to `Approved` starts CI/CD deployment, so deploy only from `Approved` versions (LLM-SM-REG-002 when a pending or rejected version is served) ([update approval status](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html)).

## 3. Sharing across accounts, or one view across teams

- **Cross-account use needs resource policies on three things**: the model package group, the ECR repository with the inference image, and the S3 bucket with the artifacts; AWS also requires a KMS key on the training job's output data config for cross-account deployment (LLM-SM-REG-004 for an absent or over-broad group policy) ([deploy from another account](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-deploy.html)).
- **Discoverability across accounts goes through AWS RAM sharing** of the model package groups; the consumer sees shared groups only once the owner attaches the resource policies ([cross-account discoverability](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-ram.html)).

## 4. Endpoint config from a model package fails on its instance type

- **The package records the instance types it supports** in `InferenceSpecification` (`SupportedRealtimeInferenceInstanceTypes`, `SupportedTransformInstanceTypes`); compare the requested type with that list first, and either choose a listed type or register a version that lists it, before treating it as capacity or quota ([InferenceSpecification](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_InferenceSpecification.html)).

## 5. Lineage and console visibility

- **SageMaker creates lineage tracking entities automatically** for jobs, models, model packages and endpoints when the data is available — a context per model package group and an artifact per model package — and tracks S3 artifacts by the URI passed to the Create API, not by file hash (LLM-SM-REG-003 when a package has no upstream link) ([auto-created tracking entities](https://docs.aws.amazon.com/sagemaker/latest/dg/lineage-tracking-auto-creation.html)).

## 6. Managed MLflow calls fail

- **Match the MLflow client to the tracking server version** and install the `sagemaker-mlflow` plugin, which signs requests with SigV4 and lets you connect by tracking-server ARN; AWS lists the client version to use per server version ([MLflow client compatibility](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow-track-experiments.html)).

## 7. Promoting the exact artifact that passed evaluation

- **Deploy the registered version, not a retrained copy**: a model version holds the model artifacts and optionally inference code, and cross-account deployment reads the same version through the group's resource policy, so promoting that version (an approval change, then deploy by its ARN) guarantees the same artifact, while retraining creates a different one — this skill's reading ([register a model version](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-version.html), [deploy from another account](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-deploy.html)).
