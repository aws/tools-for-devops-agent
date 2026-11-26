# Changelog

## 1.0.2

- Multi-account execution: the `start-automation-execution` example now pins `--document-version <version>`, as the single-account examples in `execution.md` do, so a change to the runbook's default version doesn't change what runs in every target account (#308).

## 1.0.1

- Added a Demo videos subsection to the README's "How to Use This Skill" section, linking two demo recordings hosted as GitHub attachments. Only README text changes; the published skill package gains no files.

## 1.0.0

- Initial version: one Systems Manager skill with a routing table, a shared safety contract and task chapters loaded on demand.
- Automation chapters: runbook discovery (catalog of 485 AWS-owned runbooks published 2026-11-04 by symptom category and target resource type, with descriptions, required parameters and risk tiers; Region confirmation with `DescribeDocument`; fallback search of account-owned runbooks), execution (rate-controlled, alarm-protected start commands for a person to run; monitoring and diagnosis from step status; worked examples from real executions), and hardening (static review with checks backed by public Systems Manager and IAM documentation, and a hardened document).
- Review round 1: corrected risk tiers — a script in an attachment or embedded in an `aws:createStack` template is now analysed or treated as not inspectable (at least `mutating-reversible`), fixing 49 catalog entries; added the `Resume` signal for `aws:pause` steps; the review agent detects multi-account runs from `AutomationType: CrossAccount` and compares absolute `MaxConcurrency` against the resolved target count.
- Review round 3: tier corrections for `AWSSupport-RequestSageMakerLimitIncrease` (destructive; an approved quota increase cannot be reversed) and `AWSSupport-TroubleshootMSKClusterConnection` (mutating-reversible; it deletes only resources its own temporary stack created).
- Review round 4: the trigger boundary stays with the maintainers' scope — general service symptoms require Automation or runbook intent, Systems Manager-specific symptoms trigger directly; eval results regenerated on this version.
