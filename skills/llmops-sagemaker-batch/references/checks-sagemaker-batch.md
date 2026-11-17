# Checks — SageMaker batch transform / offline scoring (LLM-SM-BATCH-*)

Covers Amazon SageMaker batch transform jobs used for offline LLM scoring — failure, right-sizing, output integrity, and encryption.

Each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation`

Family code: **SM** = SageMaker for LLMs. Family prefix: `LLM-SM-`; the `LLM-SM-BATCH-*` sub-family covers batch transform.

Severity scale: CRITICAL > HIGH > MEDIUM > LOW > INFO. A *tuning or right-sizing judgment* with no AWS-published number is marked `workload-specific` at severity INFO; a *binary present/absent/failed* state (a job FAILED, no checkpoint produced, access denied) keeps its catalog severity even when AWS publishes no number.

## Batch transform / offline scoring (LLM-SM-BATCH-*)

Batch Transform is the offline-scoring path for LLMs (bulk classification, offline generation). Covers failure, right-sizing, output integrity, and encryption.

| check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation |
|---|---|---|---|---|---|
| LLM-SM-BATCH-001 | Reliability | HIGH | `DescribeTransformJob` `TransformJobStatus` = `Failed` — read `FailureReason` for input-data format mismatch, a `ContentType`/`SplitType` the container rejects, or an S3 access error on the input/output path. | Fix the indicated cause (correct `ContentType`/`SplitType`/`BatchStrategy`, or grant the role S3 access to input/output prefixes) and resubmit; validate a small sample first. | https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html |
| LLM-SM-BATCH-002 | Performance | LOW | Batch job runs with `MaxConcurrentTransforms` = 1 / default and no `MaxPayloadInMB` tuning on a large dataset — under-parallelized, long wall-clock and higher cost. Threshold `workload-specific`. | Raise `MaxConcurrentTransforms` and tune `MaxPayloadInMB`/`BatchStrategy` to the record size so instances are saturated; re-measure throughput. | https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html |
| LLM-SM-BATCH-003 | Operational Excellence | MEDIUM | Job reports `Completed` but the output S3 prefix is empty or has fewer `.out` objects than input records (`ListObjectsV2`) — partial/failed scoring masked by a success status. | Inspect the transform logs for skipped/failed records, reconcile output count against input, and reprocess the missing records; do not consume a partial output set as complete. | https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html |
| LLM-SM-BATCH-004 | Security | MEDIUM | Transform output written without a `TransformOutput.KmsKeyId` where the scored data is sensitive — offline LLM outputs land in S3 without a customer-managed key. | Set `TransformOutput.KmsKeyId` to a CMK and confirm the output bucket enforces encryption; grant the role KMS encrypt. | https://docs.aws.amazon.com/sagemaker/latest/dg/encryption-at-rest.html |
