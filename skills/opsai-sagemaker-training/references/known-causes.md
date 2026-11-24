# Known Causes — SageMaker training and Model Registry break-fix

Documented causes for the training errors and Model Registry problems operators report most, for
answering a stated error or symptom directly (SKILL.md, *Break-fix first*). Sections 1–7 cover
training / customization jobs; sections 8–14 cover the Model Registry. Each bullet names the AWS page
it rests on; verify against that page before you answer. A cause tied to an `LLM-SM-TRAIN-*` or
`LLM-SM-REG-*` id is reported as that finding with the catalog severity; a cause with no id is
**guidance**, cited by URL, never given an invented id. Where AWS says nothing (for example whether a
model package group can span Regions, or whether auto-created lineage entities can be tagged), say so
rather than filling the gap.

## 1. Access errors — which identity, which policy

- **`not authorized to perform: iam:PassRole` when creating the job** is the *caller's* permission, not the execution role's: whoever calls `CreateTrainingJob` must be allowed `iam:PassRole` on the role it passes, usually scoped with `iam:PassedToService` = `sagemaker.amazonaws.com`. Fix the caller's policy, not the execution role ([troubleshooting IAM](https://docs.aws.amazon.com/sagemaker/latest/dg/security_iam_troubleshoot.html), [passing roles](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).
- **S3 access denied although the execution role "has S3"** — the `CreateTrainingJob` execution role needs `s3:ListBucket` on the input bucket and `s3:GetObject`/`s3:PutObject` on the input and output prefixes, plus `kms:Decrypt` when the input is SSE-KMS encrypted; check the bucket policy as well as the role (LLM-SM-TRAIN-005) ([CreateTrainingJob execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).
- **KMS error although the role's IAM policy allows `kms:Decrypt`/`GenerateDataKey`** — an IAM policy has no effect on a KMS key unless the key policy allows it; for `OutputDataConfig.KmsKeyId` AWS states the key policy must grant the role you pass to `CreateTrainingJob`. Add a key-policy statement naming the execution role ARN with the needed actions, or confirm the key policy delegates to IAM (LLM-SM-TRAIN-005) ([key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html), [OutputDataConfig](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_OutputDataConfig.html)).
- **An output or volume key also needs its own action** — AWS lists `kms:Encrypt` for an output key and `kms:CreateGrant` for a volume key on the training execution role ([CreateTrainingJob execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).

## 2. Failed fast with no CloudWatch logs

- **Read `FailureReason` first**, then the log group `/aws/sagemaker/TrainingJobs` (streams `[training-job-name]/algo-[n]-[timestamp]`) ([DescribeTrainingJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeTrainingJob.html), [log groups](https://docs.aws.amazon.com/sagemaker/latest/dg/logging-cloudwatch.html)).
- **No log stream at all is also what an execution role without CloudWatch Logs permissions looks like** — AWS's training-role policy includes `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` and `logs:DescribeLogStreams`; check them before concluding the container never started ([CreateTrainingJob execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).
- **An image the role cannot pull** fails before any training code runs — the same policy lists `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer` and `ecr:BatchGetImage` for the training image repository ([CreateTrainingJob execution role](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)).

## 3. Capacity versus quota

- **`ResourceLimitExceeded` is an account resource limit** — request an increase through Service Quotas (LLM-SM-TRAIN-003) ([CreateTrainingJob errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTrainingJob.html), [quotas](https://docs.aws.amazon.com/sagemaker/latest/dg/regions-quotas.html)).
- **`InsufficientCapacityError` means SageMaker found no capacity for the requested instance type within the pending wait** (`MaxPendingTimeInSeconds`, 30 minutes to 28 days); the documented options are an ordered list of candidate instance types, a longer wait, or another instance type or Region ([training capacity](https://docs.aws.amazon.com/sagemaker/latest/dg/train-get-capacity.html)). EC2's equivalent launch error is `InsufficientInstanceCapacity` ([EC2 insufficient capacity](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/troubleshooting-launch.html)). A quota increase does not add capacity — this skill's reading, consistent with the catalog row (LLM-SM-TRAIN-002).

## 4. Spot interruptions and checkpoints that do not resume

- **Managed spot needs `EnableManagedSpotTraining` and `MaxWaitTimeInSeconds` larger than `MaxRuntimeInSeconds`**; AWS recommends checkpointing for anything but short jobs, and algorithms that cannot checkpoint are capped at a 3600-second wait ([managed spot training](https://docs.aws.amazon.com/sagemaker/latest/dg/model-managed-spot-training.html)).
- **Writing checkpoints is not resuming from them.** SageMaker syncs the local checkpoint directory (default `/opt/ml/checkpoints`) with the checkpoint S3 URI you configure and copies existing checkpoints back into the container at job start; a custom script must save to that local path *and load from it* on start, otherwise it starts from scratch ([checkpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/model-checkpoints.html)).
- **Checkpoints added to S3 after the job started are not copied into the running container** — only what exists at start is restored ([checkpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/model-checkpoints.html)).

## 5. Out of memory partway through

- **Tell host memory from GPU memory before resizing**: `/aws/sagemaker/TrainingJobs` publishes `MemoryUtilization` (container memory) and `GPUMemoryUtilization` (summed across GPUs, so 0–400% on four GPUs) per `[job]/algo-[n]` host; the one that peaks before the failure names the resource to scale ([job metrics](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html)).

## 6. Distributed or VPC-mode jobs that hang or time out

- **Multi-node jobs in a VPC need a security-group rule allowing inbound traffic between members of the same security group**, and EFA-enabled instances need both inbound and outbound all-traffic rules within the group; single-node runs never exercise this path ([training in a VPC](https://docs.aws.amazon.com/sagemaker/latest/dg/train-vpc.html)).
- **A VPC with no internet access has no route to S3 or other services** unless you create an Amazon S3 VPC endpoint, interface VPC endpoints for other AWS services, or a NAT gateway for services and resources without one ([training in a VPC](https://docs.aws.amazon.com/sagemaker/latest/dg/train-vpc.html)).

## 7. Loss curve printed to stdout but not in the console

- **SageMaker only publishes custom training metrics it is told to parse**: define `MetricDefinitions` (a name plus a regular expression) in `AlgorithmSpecification`, and make sure the regex matches the exact log line the script writes ([define training metrics](https://docs.aws.amazon.com/sagemaker/latest/dg/define-train-metrics.html)).

## 8. Registry: a pipeline or training run finished but no model version appears

- **Registration is an explicit step**: a version is created by a `RegisterModel` step in a SageMaker pipeline, or by calling `CreateModelPackage` with the model package group name; a training job alone does not add a version. Distinguish this from an access error before changing permissions (LLM-SM-REG-001 when a customized artifact was never registered) ([register a model version](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-version.html)).

## 9. Registry: anyone can deploy an unapproved version

- **Gate deployment on `ModelApprovalStatus`**: versions move between `PendingManualApproval`, `Approved` and `Rejected`, and with the SageMaker project templates a change to `Approved` starts CI/CD deployment, so deploy only from `Approved` versions (LLM-SM-REG-002 when a pending or rejected version is served) ([update approval status](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html)).

## 10. Registry: sharing across accounts, or one view across teams

- **Cross-account use needs resource policies on three things**: the model package group, the ECR repository with the inference image, and the S3 bucket with the artifacts; AWS also requires a KMS key on the training job's output data config for cross-account deployment (LLM-SM-REG-004 for an absent or over-broad group policy) ([deploy from another account](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-deploy.html)).
- **Discoverability across accounts goes through AWS RAM sharing** of the model package groups; the consumer sees shared groups only once the owner attaches the resource policies ([cross-account discoverability](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-ram.html)).

## 11. Registry: endpoint config from a model package fails on its instance type

- **The package records the instance types it supports** in `InferenceSpecification` (`SupportedRealtimeInferenceInstanceTypes`, `SupportedTransformInstanceTypes`); compare the requested type with that list first, and either choose a listed type or register a version that lists it, before treating it as capacity or quota ([InferenceSpecification](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_InferenceSpecification.html)).

## 12. Registry: lineage and console visibility

- **SageMaker creates lineage tracking entities automatically** for jobs, models, model packages and endpoints when the data is available — a context per model package group and an artifact per model package — and tracks S3 artifacts by the URI passed to the Create API, not by file hash (LLM-SM-REG-003 when a package has no upstream link) ([auto-created tracking entities](https://docs.aws.amazon.com/sagemaker/latest/dg/lineage-tracking-auto-creation.html)).

## 13. Registry: managed MLflow calls fail

- **Match the MLflow client to the tracking server version** and install the `sagemaker-mlflow` plugin, which signs requests with SigV4 and lets you connect by tracking-server ARN; AWS lists the client version to use per server version ([MLflow client compatibility](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow-track-experiments.html)).

## 14. Registry: promoting the exact artifact that passed evaluation

- **Deploy the registered version, not a retrained copy**: a model version holds the model artifacts and optionally inference code, and cross-account deployment reads the same version through the group's resource policy, so promoting that version (an approval change, then deploy by its ARN) guarantees the same artifact, while retraining creates a different one — this skill's reading ([register a model version](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-version.html), [deploy from another account](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-deploy.html)).
