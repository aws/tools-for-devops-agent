# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-10-26

- Initial release for AWS DevOps Agent.
- Preview first (`StartLifecyclePolicyPreview` and `GetLifecyclePolicyPreview`) with a documented approval path for the agent guardrail, and a deterministic simulation fallback labelled `SIMULATED`.
- Per image verdicts `Safe`, `Expiring-Unused`, `Expiring-InUse`, `Expiring-Unknown`; repository rating `Healthy`, `Attention`, `AtRisk`, `Indeterminate`, both as ordered first match tables.
- In use cross reference on every run against `lastRecordedPullTime`, ECS running tasks, services and ACTIVE task definitions, AWS Batch job definitions, Lambda container image functions, App Runner services, EKS cluster presence, and optional CloudTrail pull events.
- 14 fixed checks, protected tag heuristic for production like tags under a catch all rule, and a protective rule suggestion handed to the operator, never applied.
- References for ECR lifecycle semantics with a worked 26 image example, API fields and error classification, and the report template. 10 evals.

### Changed (2026-10-30, after functional eval v4, still 1.0.0)
- Output Contract rewritten: the final message MUST be the full report from `report-template.md` verbatim, with the ten `##` headings in order; a parent agent that ran the procedure in a subagent relays the subagent's report unchanged; no conversational preface and no closing offer. The fixed vocabulary (`Healthy`/`Attention`/`AtRisk`/`Indeterminate`, `Expiring-InUse`/`Expiring-Unknown`/`Expiring-Unused`, `AUTHORITATIVE`/`SIMULATED`, 15 Check Matrix ids) is stated as literal and case sensitive. In v4, 30 of 30 triggered runs produced the report inside a subagent and the parent then paraphrased it ("Verdict: Unsafe", "a simulation", no headings, no Check Matrix).
- Report template gains a one line `Bottom line` field under Repository Rating for the user's yes or no answer, and two pre render checks (message starts with the title; a subagent's report is relayed unchanged).
- Catch all semantics: `ecr-lifecycle-semantics.md` step 3 and the worked example now spell out that a `tagStatus: any` rule with `imageCountMoreThan N` keeps the N newest of the whole repository, not of the pool left after higher rules claimed their images; the worked example is renumbered with every intermediate set written out and names the 9 image answer as the most frequent error. SKILL.md Step 4 and new Critical Rules 12 and 13 carry the one sentence forms. In v4 the five rule eval returned 9 instead of 12 in 2 of 3 runs.
### Changed (2026-10-27, after live test round 1, still 1.0.0)

- In use evidence is now ranked: (a) `lastRecordedPullTime`, (b) a consumer reference in ECS, Batch, Lambda or App Runner, (c) CloudTrail pull events. Only tier (c) is filtered.
- Push correlation rule for CloudTrail: `BatchGetImage`, `GetDownloadUrlForLayer`, `PutImage`, `InitiateLayerUpload`, `CompleteLayerUpload` or `BatchCheckLayerAvailability` events within 60 seconds of `imagePushedAt`, or from the pushing principal, are part of the push and never count as a consumer pull. In the live test every expiring image carried such an event 1 to 2 seconds after push and was wrongly rated `Expiring-InUse` (11 of 11 false positives).
- Verdicts: CloudTrail evidence alone gives `Expiring-InUse` only when a qualifying pull remains more than 60 seconds after push; tier (a) or (b) evidence gives `Expiring-InUse` regardless of denied checks; `Expiring-Unknown` is reserved for denied checks when (a) and (b) are empty.
- Every Expiring Images row names the evidence tier that produced its verdict.
- Check Matrix grows to 15 rows: R1 follows the filtered result, new U8 (LOW, informational, never moves the rating) reports how many CloudTrail events were excluded as push correlated. CloudTrail probe also looks up `PutImage` to learn the pushing principal.
- Two evaluation style evals added (push correlated event excluded, consumer pull three days later). 12 evals.
