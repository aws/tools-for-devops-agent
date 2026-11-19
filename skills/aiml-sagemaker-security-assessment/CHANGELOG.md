# Changelog

All notable changes to the `aiml-sagemaker-security-assessment` skill are
documented here. This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0]

### Added
- Initial release. Read-only Amazon SageMaker AI security posture assessment as an
  AWS DevOps Agent skill — the SageMaker domain of a per-domain AI/ML security
  posture family.
- **25 read-only SageMaker checks (`SM-01`..`SM-25`)** covering notebook/domain
  internet exposure and VPC deployment, notebook root access, KMS encryption at
  rest (notebooks, models, Feature Store offline store, processing/transform/
  hyperparameter-tuning/compilation/AutoML volumes and output), model network
  isolation, container-repository access mode, endpoint high-availability, Model
  Monitor and drift detection, GuardDuty coverage, and MLOps governance (Model
  Registry, approval workflow, lineage).
- **Verify-vs-prescribe determinism contract:** each check is classified
  `Verifiable` (17) or `Heuristic` (8). The report never marks an unread or
  access-denied control as `Passed`. `SM-02` carries Prescribe-only sub-aspects
  (stale access, IAM Identity Center) that are always reported `N/A`.
- **Owns-vs-defers boundary** against `aiml-access-diagnostics` (reactive
  access-denial diagnosis). Security Hub controls (SageMaker.1–25) cited as
  cross-references only; no `securityhub:*` calls.
- Handling for service-availability and instance-type constraints: no `Failed`
  for absence of Model Monitor/Clarify (closed to new customers), and locally
  encrypted instance types (for example `ml.g4dn`, `ml.g5`) count as encrypted.
- Job-scan guardrails (90-day window, 50-job cap per check per region).
- Uses the managed `AIDevOpsAgentAccessPolicy`; no extra IAM policy required.
- Multi-region and multi-account support via AWS DevOps Agent account associations.
