# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker Model Registry governance review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

---

## SageMaker model registry (REG)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListModelPackages` / `DescribeModelPackage` | registry lineage / approval status (`ModelApprovalStatus`, source training-job and dataset lineage, model package group policy, artifact `KmsKeyId`) | LLM-SM-REG-001, 002, 003, 004 |
