# Changelog
## [1.0.0] - 2026-11-19
- Initial release. Merges llmops-quality-evaluation 1.0.0, llmops-sagemaker-evaluation 1.0.0 into one skill.
- Bedrock evaluation: model evaluation (`CreateEvaluationJob`, automated or human), Bedrock RAG evaluation jobs on a knowledge base, quality gates, regression detection and A/B comparison (LLM-EVAL-001..011).
- Finish-reason drift from Bedrock invocation logs (LLM-EVAL-012..014).
- SageMaker-side evaluation: Nova evaluation recipes and LLM-as-judge jobs run as SageMaker training jobs (LLM-SM-EVAL-001..004). LLM-SM-EVAL-004 now marks the switch to this skill's Bedrock path instead of a hand-off.
- Inside a live incident the skill still produces its own findings; the fault locus belongs to live-failure triage when available, and otherwise the answer says the locus was not determined.
- Check-ids and severities unchanged; other families' ids removed from the shared references.
- Routes to other skills replaced by an optional Related skills section.
- The two catalogs are merged into `references/checks-evaluation.md` with one section per family; each section keeps its own severity-scale sentence.
- `api-quirks.md` keeps the quality skill's traps §1–§14 (other families' ids replaced by area names), folds the SageMaker "no datapoints" sentence into §10, and adds §15 (which service ran the eval).
- `collection-reference.md` adds the SageMaker-side evaluation rows and a Bedrock RAG evaluation row (`applicationType`, `inferenceConfig`, `failureMessages`); `metrics-and-logs.md` adds §7 SageMaker-side evaluation job signals.
- Finish-reason filter drift: the telemetry-family id that described an absent `stopReason` metric filter is dropped; LLM-EVAL-013 is the id this skill runs for that condition.
- Severity table: kept the quality skill's SLAs (same day / days / next sprint / backlog) and added LLM-SM-EVAL examples; the SageMaker table's SLAs (24–48 h / 1 week / 30 days / when convenient) are not used. Neither is AWS-published.
- Recommended custom metric namespaces renamed to `OpsAI/Evaluation` and `OpsAI/FinishReason/MaxTokens`; dashboards or alarms built on the previous prefix need re-pointing.
- The SageMaker report template is renamed `assets/sagemaker-evaluation-report-template.md`; the report template and delegation payload use an `Owning area` column instead of a skill name.
- Old evals results (structure, best-practices, functional) not carried over; best-practices and functional must be re-run.
