# Changelog

All notable changes to the `bedrock-kb-diagnosis` skill.

## [1.0.0] - 2026-11-11

Initial release.

- Reactive, read-only diagnosis of a deployed Amazon Bedrock Knowledge Base.
- Two-pass method: always-on cheap pass (`ListKnowledgeBases`/`GetKnowledgeBase`,
  `ListDataSources`/`GetDataSource`, `ListIngestionJobs` statistics) plus a targeted pass per
  symptom branch.
- Symptom map covering: no sources, stale answers, removed content still cited, failed/partial
  sync, a document that never indexed, indexing failures, throttled ingestion, stuck
  resources, and query-layer "fewer results than expected".
- Verdict vocabulary: Root cause / Contributing / Inspect / Ruled out / Not checked.
- Store-scoped checks for OpenSearch Serverless and Aurora; third-party and S3 Vectors stores
  disclosed as Not checked; Kendra GenAI / structured / graph KBs deferred.
- Handoffs to `aiml-access-diagnostics` (IAM), `bedrock-operation-review` (posture), and
  `service-quota-check` (embedding throttles).
- IAM: core reads covered by `AIDevOpsAgentAccessPolicy` v15; source-bucket reads
  (`s3:ListBucket`/`s3:GetBucketLocation`) and `bedrock:GetIngestionJob` ship as one opt-in
  CloudFormation parameter, required to name files dropped at intake.
