# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker batch transform / offline-scoring review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

---

## SageMaker batch transform (BATCH)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTransformJobs` / `DescribeTransformJob` | `TransformJobStatus`, `FailureReason`, `TransformInput` (`ContentType`/`SplitType`), `TransformOutput.KmsKeyId`, `MaxConcurrentTransforms`, `MaxPayloadInMB`, `BatchStrategy` | LLM-SM-BATCH-001..004 |
| `s3:ListObjectsV2` on the transform output prefix | `.out` object count vs input record count (partial-scoring detection) | LLM-SM-BATCH-003 |
