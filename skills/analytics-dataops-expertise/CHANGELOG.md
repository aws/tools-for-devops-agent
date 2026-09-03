# Changelog

All notable changes to the `analytics-dataops-expertise` skill are documented here.

## [1.1.0] - 2026-08-28
### Added
- Optional downloadable **HTML report**: a self-contained, styled template at
  `assets/templates/dataops-maturity-report.html` (executive score-card tiles, per-dimension
  cards with RAG summary, per-question expandable detail blocks with confidence badges,
  observed-metric tiles, and ⚠️/💬 callouts, the 26-row score matrix, and a self-download
  button) that the agent fills with live data and saves as a chat artifact. Follows the
  static-template pattern used by the redshift-support-specialist skill — no scripts, no
  renderer; the agent substitutes values into the template.
- Companion Markdown template `assets/templates/dataops-maturity-report.md` (the always-on
  in-chat output) mirroring the HTML structure section-for-section.
- SKILL.md rules for the HTML path: always produce the Markdown; generate HTML only on
  request; HTML-escape all substituted values; template is structure-only, never a data
  source; identical data across both outputs.

## [1.0.3] - 2026-08-28
### Added
- Richer report format mirroring the reference pre-assessment layout: an Executive
  Summary with an overall + per-dimension score-card row and a maturity tier; a
  scoring-caveat banner listing any unavailable signal APIs; per-dimension RAG summary
  bands (Strengths ≥3.0 / Watch 2.0–2.9 / Gaps <2.0); and a per-question detail block
  for all 26 questions with a HIGH/MEDIUM confidence badge, a one-line rationale,
  real observed metrics, an optional ⚠️ warning callout, and 💬 discussion-ask prompts
  to drive the customer conversation. Added a Confidence column to the score matrix.
### Changed
- Output remains 100% markdown (no scripts, no HTML renderer) so the skill stays
  within the DevOps Agent no-executable-content constraint; added a guard prohibiting
  raw structure/dict/JSON dumps in observed-metric values (summarize in words instead).

## [1.0.2] - 2026-08-28
### Fixed
- Dimension fidelity: pinned the scorecard to EXACTLY five dimensions (Architecture;
  Security & Governance; Incident Management & Observability; Automation & Testing; Cost)
  with fixed per-question membership, and aligned the frontmatter description to those five.
  Fixes an observed run where the agent reported "7 dimensions" by promoting Architecture
  questions (Real-time Processing Q4, Resilience Q7/Q8) into standalone top-level dimensions.

## [1.0.1] - 2026-08-28
### Fixed
- Report rendering: added a LITERAL-CONTENT RULE and an incremental RENDERING METHOD
  to the Output Format so the agent writes every section and all 26 score-matrix rows
  with real computed values. Fixes an observed failure in DevOps Agent where a saved
  artifact contained placeholder labels ("full 3-tier content…", `{"q":"Q3"}` rows with
  empty columns) instead of the actual report. Reinforced the same requirement in
  Execution Flow step 6.

## [1.0.0] - 2026-08-27
### Added
- Initial release: 26 read-only control-plane maturity questions across five dimensions
  (Architecture; Security & Governance; Incident Management & Observability;
  Automation & Testing; Cost), each scored on a 1-5 maturity scale.
- Per-question checks that name the AWS API(s), the field(s) to read, and the signal-to-rating
  mapping — 100% control-plane / API-driven with no data-plane access and no AWS-internal
  data sources.
- Auto-score ceilings: questions that cannot be fully confirmed from control-plane signals
  alone (Q6, Q8, Q11, Q13, Q14, Q19, Q20, Q23, Q24, Q26, Q30, Q37, Q38, Q39) are capped at 3;
  the report states when a higher score requires conversational confirmation.
- Remediation Reference: a 26-entry verbatim dictionary (why-it-matters, resolution steps,
  and verified official AWS documentation links) in `references/remediation-reference.md`,
  loaded on demand via `read_skill_resource`. Every question scored ≤ 3 pulls its entry
  verbatim; documentation links come only from the dictionary, eliminating URL hallucination.
- Structured scorecard output: per-section and overall averages, tiered findings, prioritized
  recommendations, a raw-data reference, and a mandatory 26-row score matrix with a self-count
  check.
- Error handling: missing services and region-unavailable APIs are treated as score-1 signals,
  not blockers; a question is only SKIPPED when every API it needs is denied by IAM. Cost
  Explorer must be enabled and is called in `us-east-1`.
