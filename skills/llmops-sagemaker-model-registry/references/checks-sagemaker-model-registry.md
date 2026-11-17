# Checks — SageMaker Model Registry / lineage / approval (LLM-SM-REG-*)

Covers SageMaker Model Registry governance of customized GenAI / LLM artifacts — registration, approval status, lineage, and package-group policy/encryption.

Each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation`

Family code: **SM** = SageMaker for LLMs. Family prefix: `LLM-SM-`; the `LLM-SM-REG-*` sub-family covers model registry / lineage.

Severity scale: CRITICAL > HIGH > MEDIUM > LOW > INFO. A *tuning or right-sizing judgment* with no AWS-published number is marked `workload-specific` at severity INFO; a *binary present/absent/failed* state (a job FAILED, no checkpoint produced, access denied) keeps its catalog severity even when AWS publishes no number.

## Model Registry / lineage / approval for customized artifacts (LLM-SM-REG-*)

Lineage and approval governance for **customized** LLM artifacts (the output of LLM-SM-TRAIN). Distinct from the preserved LLM-SM-011, which flags a *deployed endpoint* lacking registry lineage; REG-* governs the registered package itself.

| check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation |
|---|---|---|---|---|---|
| LLM-SM-REG-001 | Operational Excellence | MEDIUM | A customized/fine-tuned model artifact from an LLM-SM-TRAIN job was **never registered** in the SageMaker Model Registry (`ListModelPackages` has no package for it) — the artifact has no governed version or lineage. | Register the customized artifact as a versioned model package in a model package group so it has lineage back to the training job and dataset. | https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html |
| LLM-SM-REG-002 | Operational Excellence | HIGH | A model package deployed (or staged for deploy) has `ModelApprovalStatus` = `PendingManualApproval` or `Rejected` — an unapproved customized model is being served or promoted. | Route the package through the approval step; deploy only `Approved` versions. If a rejected/pending version is live, investigate how it was promoted. | https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html |
| LLM-SM-REG-003 | Operational Excellence | LOW | A registered customized model package has no lineage association back to its training job / input dataset (`ListModelPackages`/lineage query returns no upstream link) — provenance of the fine-tuned model is untraceable. Threshold `workload-specific`. | Record lineage (training job, recipe, and dataset) on the model package via SageMaker Lineage / package metadata so the customized model is reproducible and auditable. | https://docs.aws.amazon.com/sagemaker/latest/dg/lineage-tracking.html |
| LLM-SM-REG-004 | Security | MEDIUM | The model package group has no resource policy / overly broad cross-account access, or the artifact S3 location is not CMK-encrypted — a governed artifact with an ungoverned boundary. Threshold `workload-specific` for the access breadth. | Scope the model package group resource policy to least privilege and set a CMK on the artifact S3 location; report principals by name/ARN with the account segment masked. | https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html |
