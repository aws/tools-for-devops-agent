# Changelog
## [1.0.0] - 2026-11-19
- Initial release. Merges llmops-sagemaker-training 1.0.0, llmops-sagemaker-model-registry 1.0.0 into one skill.
- Training / customization: Nova and JumpStart fine-tuning job failures, capacity vs quota, Pending-on-capacity, missing checkpoints, billed GPU cost (LLM-SM-TRAIN-001..008).
- Model Registry: registration, approval gating, lineage, package-group boundary and CMK encryption (LLM-SM-REG-001..004).
- Check-ids and severities unchanged; other families' ids removed from the shared references.
- Routes to other skills replaced by an optional Related skills section.
- `api-quirks.md` renumbered to traps §1–§7 (training §1–§5, registry "no datapoints" §6, `Approved` ≠ deployed §7); the "no datapoints" trap now states that the registry publishes no metric namespace.
- `known-causes.md` merged into one file: training §1–§7, Model Registry §8–§14.
- The registry catalog intro and report template no longer name the endpoint check-id for a deployed endpoint lacking lineage; they name the SageMaker endpoint area instead.
- Old evals results (structure, best-practices, functional) not carried over; best-practices and functional must be re-run.
