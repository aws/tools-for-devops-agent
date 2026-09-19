# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-09-01

### Added

- Fixed four report-quality defects a full-account live run exposed (21 Regions, 53
  resources, 5 subagents — the same scale that previously collapsed, now rendering a
  complete report). (1) Extended the single-source-of-truth rule to the **vault and
  backup-plan counts**: a run showed Scope "Vaults 6" while findings and checks said
  "7 vaults" — the counts are now computed once and quoted everywhere. (2) Forbade
  **reasoning, self-corrections, and planning preamble in the rendered report** after
  a finding cell contained a literal "…×3, ap-south-1 ×3… wait, 3+1+3=7 — see Check
  Coverage Matrix for exact count"; the report begins at the title and carries only
  settled values. (3) Clarified that the **Permissions Notice and Tooling Availability
  Notice are distinct and never merged** — `AccessDenied` (a real IAM gap) goes in the
  Permissions Notice, a guardrail cancellation goes in the Tooling Availability Notice
  as `ToolingFailure`, and a run with both renders both; a run had merged guardrail
  cancellations under a "Permissions Notice" heading. (4) Stated that a **passing (`✅`)
  check has no Findings row** — `✅ (pass)` is not a severity — after check 5.3 appeared
  in the Findings table "for completeness".

- Hardened the skill against a context-loss failure that a live run
  exposed: a 41-minute, ~1,100-tool-call sweep (21 Regions, direct enumeration
  because the account's Config recorder was stopped, six subagents with overlapping
  Region groups) produced a 4,428-byte report with 3 of the required sections, 0 of
  the 23 check rows, and no Coverage Matrix. The template and the per-resource
  inventory had both fallen out of context by render time and been reconstructed from
  a remembered outline. Four changes address the mechanism rather than the symptom:
  (1) Step 8 now requires **re-loading `assets/report-format.md` immediately before
  rendering** — a read from earlier in the run no longer counts; (2) Steps 5 and 6
  now require **persisting the per-resource rows and all 23 check verdicts to a
  working file** and rendering the Coverage Matrix, Check Coverage Matrix and Findings
  from that file rather than from context; (3) the subagent delegation contract now
  **bounds each subagent to a compact structured return** (data only, no prose, no
  rendered report) over **non-overlapping Region groups**, since a free-text return
  forces a distillation pass that drops per-resource detail; and (4) a subagent that
  **returns nothing — refusal, empty, or cancelled — is now `ToolingFailure`** for the
  types it covered, never "zero resources." Also added a README limitation making the
  guardrail-cancellation behaviour explicit: `backup:ListRestoreTestingPlans` and
  `storagegateway:ListGateways` are read-only and IAM-grantable yet cancelled by the
  DevOps Agent permission guardrail as mutative, so the resulting `ToolingFailure`
  line is expected and no policy change fixes it.

- Documented that the IAM action prefix is the service name, not the SDK client name.
  Live testing showed the agent calling `timestream-write:ListDatabases` — the boto3
  client is `timestream-write`, but the IAM action is `timestream:ListDatabases` — and
  recording the resulting `AccessDenied` as a permissions gap. Verified on the test
  role: `timestream:ListDatabases` is `allowed` while `timestream-write:ListDatabases`
  is `implicitDeny`, so no policy could have granted it; the action does not exist. The
  effect was that Timestream was dropped from the coverage denominator over a naming
  error rather than a real permission boundary, understating the inventory the report
  claimed to have swept. Added a prefix table alongside the existing exact-operation-name
  note, and a rule to check a denied action against the allowlist before recording
  `AccessDenied`.

- Fixed a false negative in the functional eval assertions: the four section-order
  regexes matched `## Coverage Matrix` as a substring of
  `### Coverage Matrix — Account-Wide by Resource Type`, so a report that nested a
  required section under another passed the structural check. Anchored all four to line
  start with `(?sm)` and `^##`. Verified against a real report artifact that nested the
  section: the old pattern passed it, the new pattern fails it, and correct reports
  still pass. Also added an assertion requiring a resource type whose enumeration
  returned `AccessDenied` or was cancelled to be reported with that status rather than
  as zero resources, and rewrote the `SelectedNotProtected` assertion in the
  single-resource-type scenario, which asserted a condition the test account does not
  contain and so could never pass.

- Narrowed the delivery contract to permit a grounded slice on a same-session
  follow-up. Live chat testing showed the agent answering "are my EBS volumes
  protected in us-east-1?" as a short table rather than a report — but only because it
  had rendered the full report for that scope moments earlier in the same
  conversation, and said so. The contract as written ("the report is the deliverable
  at every scope") made that non-compliant, which was the contract being wrong rather
  than the agent: re-rendering an identical report minutes later serves nobody. Added
  a **Follow-up questions in the same conversation** subsection allowing a direct
  answer under three conditions — the earlier report already swept the scope asked
  about, the answer agrees with it, and no new API call is needed — and requiring the
  response to name the review it draws from. The exception explicitly never applies to
  the first coverage-related response in a conversation, which is where the original
  cold-start defect lived. Note that the functional evals cannot cover this case:
  each eval prompt runs in a freshly provisioned agent space with no prior turn, so
  same-session behaviour is reachable only by manual testing.

- Fixed a false-finding defect that live Agent Space testing exposed. The agent's
  tool policy cancels `backup:ListRestoreTestingPlans` and
  `storagegateway:ListGateways` as mutative operations even though both are
  read-only and IAM-permitted, returning `Cancelled mutative operation: … requires
  an operator approval`. Check 5.1's verdict was "Fail on zero restore testing
  plans", so a cancelled call — which returns nothing — would have been read as zero
  and reported as "no restore testing plan is configured": a HIGH finding asserting
  something false about the customer's account. Generalised the existing
  CloudTrail-specific note into a **Guardrail cancellations** section mapping any
  cancellation of an allowlisted read to `ToolingFailure`, which caps the rating at
  Medium and is never scored as a gap, and added a matching precondition to check
  5.1. The cancellation is a platform classification, not a permissions problem, and
  cannot be fixed by granting IAM actions.

- Stated the exact operation names for two calls the agent improvised in live
  testing. It called `backup:ListBackupFrameworks`, which does not exist and fails
  with `Invalid AWS operation` — the real operation is `ListFrameworks`, which the
  skill already documented — and `backup:ListCopyJobs`, which is not in the
  allowlist at all; cross-Region copy configuration is read from the backup plan via
  `GetBackupPlan`, not from job history.

- Closed a delivery-contract gap that functional testing exposed: a scope-narrowing
  question ("are my EBS volumes protected in us-east-1?") caused the skill to load and
  then deliberately opt out of the report, reasoning that "a scoped question" deserved
  "a direct, bounded lookup instead of invoking the full skill machinery." The contract
  already forbade condensed output for casually *phrased* requests but said nothing
  about narrowly *scoped* ones, so the model treated scope as a third, unaddressed
  case. Added a **Scoped requests** subsection separating the two axes — a named Region
  or resource type narrows what is swept, never what is rendered — and a third Output
  Contract failure mode that names the rationalization directly. Also forbade offering
  the full review as a follow-up, which was how the truncated answer ended.

- Rewrote the functional evals in `evals/evals.json` as report-generating chat prompts
  in place of quiz-style questions about the skill, and rewrote the assertions the
  eval tool flagged as non-discriminating. Assertions asserting backup *reasoning*
  (recovery points prove protection, permission gaps are not coverage gaps) passed
  without the skill too, because the base model already reasons that way; the skill's
  measurable contribution is structural, so those assertions now target the report's
  section headings, the 23-row Check Coverage Matrix, the defined coverage-state and
  status vocabulary, and SLA bucketing. One assertion — "the response is the full
  report rather than a one-line yes/no" — was passing on a technicality, since any
  multi-sentence answer clears "not a one-liner"; it now requires the named headings.

- Moved `report-format.md` from `references/` to a new `assets/` directory, following
  the Agent Skills spec convention that output templates live in `assets/` while
  `references/` holds background material. `report-format.md` was the only file of the
  four that is a fill-in template rather than a reference; the other three
  (data collection, coverage logic, backup best practices) stay in `references/`.
  Skill-root-relative paths *inside* `report-format.md` are unchanged, since file
  references resolve from the skill root rather than from the containing file.

- Converted every file citation in `SKILL.md` from a backtick code span to a real
  markdown link, and stated the loading trigger at each site (`Load it at Step 8,
  before rendering the report`). The reference and asset link checks require the
  `[text](path)` pattern specifically and require the link to say *when* to load —
  code spans were passing only on judge leniency, leaving a gating check one run away
  from flipping.

- Converted the `## Execution Flow` numbered list to a `- [ ] **Step N — …**` checkbox
  checklist, per the spec's guidance for multi-step workflows. The `### Delivery` list
  stays a plain numbered list — its items are a single step's sub-parts, not the
  top-level procedure.

- Corrected "five coverage states" to "six" in `SKILL.md`; the coverage model has
  defined six states since restore-point orphan detection was added.

- Moved the report skeleton and the error-handling table out of `SKILL.md` into
  `references/`, following progressive disclosure. The skeleton was inlined earlier as
  insurance against `references/` not loading; `assets/report-format.md` is now the
  authoritative report structure, loaded at Step 8, so the inlined skeleton was
  redundant. `SKILL.md` is back under the 5,000-token
  guidance. The API quirks table stays in the body deliberately — it prevents a silent
  failure where reading the wrong `ListBackupSelections` response key makes every
  resource appear unprotected, and that is worth keeping where it cannot be missed.

- Monitoring and observability checks in D5, following TFC domain review feedback:
  **5.4** verifies an AWS Backup Audit Manager report plan is scheduled in each Region
  with backup activity — report plans are per Region, so one does not cover the
  others — and **5.5** verifies an Audit Manager framework is configured where
  protected resources exist, since a report plan alone reports job activity without
  evaluating control compliance. Both consume `ListReportPlans` and `ListFrameworks`,
  which the data collection phase already gathered but no check previously used.
  Coverage is a point-in-time state; these two ask whether a decline in it would be
  noticed.

- Initial release for AWS DevOps Agent.
- Read-only AWS Backup coverage and posture review across all enabled Regions of a
  single account.
- Five-state coverage model (`Protected`, `Stale`, `SelectedNotProtected`,
  `Unprotected`, `OptInBlocked`) that distinguishes backup plan membership from
  actual protection.
- 23 fixed, numbered checks across 5 dimensions: service enablement, coverage,
  plan quality, vault posture, and coverage integrity. Thresholds match the AWS
  Backup Audit Manager control defaults so results are comparable with Audit
  Manager output.
- Independent resource inventory with an AWS Config fast path
  (`config:SelectResourceConfig`) and a direct per-service enumeration fallback, so
  the review works in accounts where AWS Config is not recording.
- Per-Region resource type opt-in detection, covering the case where a backup plan
  and selection appear correct in the console but AWS Backup will never protect the
  resource.
- Selection breadth check that flags ARN-only backup selections, which cannot match
  resources created after the selection was written.
- Four-state status enum (`OK`, `NotConfigured`, `AccessDenied`, `ToolingFailure`)
  plus `NotEnumerated`, with the rule that permission gaps cap the Coverage Rating
  at Medium rather than being scored as coverage gaps.
- Coverage Rating roll-up (High / Medium / Low / Indeterminate) with deterministic
  criteria.
- Report format with a Coverage Matrix, a mandatory 23-row Check Coverage Matrix,
  severity-ranked findings, SLA-bucketed next steps, and 11 pre-render validation
  checks.
- Final Delivery Contract so the full report is returned verbatim regardless of how
  the request is phrased.
- Reference documents for data collection, coverage logic, report format, and
  best-practices remediation with a canonical AWS documentation URL list.
- Minimum report skeleton inlined into `SKILL.md` so the report structure survives
  when `references/` is not loaded — for example when the account sweep is
  delegated to a research subagent, which returns data but must never render the
  final answer.
- Region sweep discipline: every enabled Region is swept unless the user narrows
  scope, and any unswept Region is disclosed in the Scope table and caps the
  Coverage Rating at Medium, since the denominator is incomplete.
- Per-Region S3 evaluation: buckets are resolved to their own Region with
  `GetBucketLocation` and judged against that Region's opt-in setting, because S3
  can be opted in for one Region and out for another in the same account.
- Dangling-ARN sub-check on backup selections, escalating an ARN-only selection to
  CRITICAL when the referenced resource no longer exists.
- `OrphanedRecoveryPoint` coverage state for resources that still appear in
  `ListProtectedResources` after deletion. Excluded from the numerator, the
  denominator, and from `Stale`, since a deleted resource can be neither covered nor
  uncovered.
- Output Contract at the top of `SKILL.md` plus a countable self-check, after live
  testing showed the report being replaced by a conversational summary when the
  account sweep was delegated to a research subagent.
- Single-source-of-truth counting: aggregate counts are computed once in the
  account-wide by-resource-type table and quoted everywhere else. Per-Region totals
  and percentages were removed after they repeatedly disagreed with the account
  total.
- Precision discipline: the coverage percentage is presented as indicative, bulk
  resource-type counts must state their provenance or be marked `Unconfirmed` rather
  than estimated, and coverage totals may never be used to justify a severity.
- Pre-render validation expanded from 11 to 18 checks, adding arithmetic
  reconciliation, a prohibition on duplicate findings, and a prohibition on invented
  or blended severities.
- Documented that `AIDevOpsAgentAccessPolicy` already covers 43 of the 49 actions
  used, with only five needing to be added, and that each Agent Space has its own
  IAM role requiring the policy separately.
