# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-11-03

- Boundary with `cloudtrail-cost-optimization` made explicit after the SME's overlap review. README and SKILL.md name the cost skill and `unified-security-cost-optimizer` with a one sentence boundary each and a hand off rule for cost, duplicate trail waste and data event charge questions; the description's negative trigger names them.
- L1 reworded as a coverage question: a stopped trail is CRITICAL or HIGH only when it was the only source of some coverage, INFO when another logging trail records the same events. M2 fires only when a KMS or RDS source is excluded on every management trail; an exclusion covered elsewhere is INFO. T1 evidence and the Resource Coverage selector note state "recorded by N trails" as a fact, never a finding, with no saving estimate. M1 is evaluated across trails that record management events. D4's operator change is "widen, or record that the audit accepts the exclusion".
- permissions.md: dropped unused `s3:GetBucketPolicy`; `sqs:ListQueues` and `sqs:GetQueueAttributes` confirmed in `AIDevOpsAgentAccessPolicy` v12 (`sqs:List*`, explicit), caveat removed.

## [1.0.0] - 2026-11-02

- Initial release for AWS DevOps Agent. Draft pending SME review.
- Read only CloudTrail coverage audit for one account: trail and event data store inventory across every enabled Region with shadow trails de duplicated by ARN, trail status, event selectors and Insights selectors, and a resource inventory of S3 buckets, Lambda functions and DynamoDB tables.
- Five coverage states per resource as an ordered first match list: `NotApplicable`, `Unknown`, `Covered`, `CoveredByOrgTrail-Unverified`, `Uncovered`; basic and advanced event selector semantics with sources, including the multipart upload and `DeleteObjects` gap in `eventName` allowlists.
- Organization trail status, configuration and selectors are always read with the full trail ARN from a member account; `CoveredByOrgTrail-Unverified` only after that call fails.
- Fixed 20 check matrix (T1, T2, M1 to M3, D1 to D4, I1, L1 to L4, E1, E2, O1, O2, N1, N2) with severities and a rating roll up `Healthy`, `Attention`, `AtRisk`, `Indeterminate`; Event history and automated system attribution notes render on every run.
- Baseline mode and required list mode; inline data mode for pasted `DescribeTrails`, `GetEventSelectors` or `GetTrailStatus` output labelled `SUPPLIED DATA`.
- Output contract: the final message is the full report with a one line Bottom line under the rating and no closing offer to change anything.
- References: coverage model, check matrix, API reference with error classification and quirks, permissions (all actions in `AIDevOpsAgentAccessPolicy` v12), report template. 12 evals (6 live account, 4 inline data, 2 negative) graded on substance.
