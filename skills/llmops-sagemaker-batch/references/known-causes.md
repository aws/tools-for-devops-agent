# Known Causes — SageMaker batch transform break-fix

Documented causes for the batch transform errors operators report most, for answering a stated error
directly (SKILL.md, *Break-fix first*). Each bullet names the AWS page it rests on; verify against
that page before you answer. A cause tied to an `LLM-SM-BATCH-*` id is reported as that finding with
the catalog severity; a cause with no id is **guidance**, cited by URL, never given an invented id.
Where AWS says nothing (for example on input "mount" errors), say so rather than filling the gap.

## 1. Parsing errors on records that "look like valid JSON"

- **`SplitType` = `Line` splits records on newline boundaries**, so a pretty-printed JSON document or a wrapping JSON array is cut into fragments that do not parse; each record must be one complete object per line (JSON Lines). The default `SplitType` `None` sends the whole object as one request (LLM-SM-BATCH-001) ([TransformInput](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_TransformInput.html), [batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).
- **Set `ContentType` to the MIME type the container expects** — SageMaker sends it with each HTTP call. For JSON Lines input use `application/jsonlines` with `SplitType` and `AssembleWith` `Line`, and AWS recommends `Accept` `application/jsonlines` for batch transform responses ([TransformInput](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_TransformInput.html), [associate predictions with inputs](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform-data-processing.html), [common inference formats](https://docs.aws.amazon.com/sagemaker/latest/dg/cdf-inference.html)).
- **CSV with embedded newlines is not supported** by batch transform ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).

## 2. Timeouts on large records

- **The per-invocation timeout is `ModelClientConfig.InvocationsTimeoutInSeconds`** (default 600, range 1–3600), separate from how long the whole job runs; `InvocationsMaxRetries` (0–3, default 3) sets the retries ([ModelClientConfig](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ModelClientConfig.html)).
- **`MaxPayloadInMB` must be at least the size of one record and at most 100 MB**, and `MaxConcurrentTransforms × MaxPayloadInMB` must not exceed 100 MB ([CreateTransformJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html), [batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).

## 3. Slow job with idle instances on one large file

- **Batch transform maps S3 objects to instances, so one input file is processed by one instance and the rest sit idle**; split the input into several files, and use `SplitType` `Line` with `BatchStrategy` `MultiRecord` to build mini-batches up to `MaxPayloadInMB`. AWS says the ideal `MaxConcurrentTransforms` equals the number of compute workers (LLM-SM-BATCH-002) ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html), [CreateTransformJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html)).

## 4. Capacity versus quota at start

- **`ResourceLimitExceeded` is an account resource limit** — request an increase through Service Quotas ([CreateTransformJob errors](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html), [quotas](https://docs.aws.amazon.com/sagemaker/latest/dg/regions-quotas.html)).
- **`InsufficientInstanceCapacity` means AWS lacks capacity for that request right now**; EC2 documents retrying after a few minutes, requesting fewer instances, or using a different instance type. A quota increase does not add capacity — this skill's reading ([EC2 insufficient capacity](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/troubleshooting-launch.html)).

## 5. Output access or KMS errors

- **Batch transform runs as the role in the `CreateModel` request**, and for `TransformOutput.KmsKeyId` AWS states the key policy must grant that role; an IAM policy alone has no effect on a KMS key unless the key policy allows it (LLM-SM-BATCH-001, LLM-SM-BATCH-004 for the missing CMK) ([TransformOutput](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_TransformOutput.html), [key policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html)).

## 6. Success status but records missing, or intermittent internal errors

- **An output file is written only when every record in its input file succeeded**, named `<input>.out`, so a missing `.out` names the input file to inspect (LLM-SM-BATCH-003) ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).
- **Read the container log group `/aws/sagemaker/TransformJobs`** (streams `[job]/[instance-id]-[timestamp]`, plus `/data-log`) to tell a container error from a service error before retrying ([log groups](https://docs.aws.amazon.com/sagemaker/latest/dg/logging-cloudwatch.html)).

## 7. Predictions cannot be matched to input rows

- **Use `DataProcessing`**: `InputFilter` selects what the model sees, `JoinSource` = `Input` joins each prediction to its input record, and `OutputFilter` keeps the ID and prediction columns; for JSON or JSON Lines input the prediction lands in the reserved `SageMakerOutput` key, and predictions are listed in the same order as the input records ([associate predictions with inputs](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform-data-processing.html), [batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)).

## 8. Batch transform or a real-time endpoint?

- **AWS positions batch transform for inference on large datasets when you do not need a persistent endpoint**; a periodic bulk scoring run with no live caller fits it, while an endpoint keeps incurring charges until it is deleted. Problems with the endpoint itself belong to `llmops-sagemaker-inference-endpoints` ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html), [UpdateEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_UpdateEndpoint.html)).
