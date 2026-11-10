# Changelog

## [1.0.0] - 2026-11-09
### Added
- Initial release. Adapted from the business-context MCP prototype
  (Lambda + API Gateway, synthetic example data) in the Aurora MySQL
  Incident Investigation demo in `aws-samples/sample-aws-genai-ops-demos`.
- Four evidence categories: dependent services/criticality, cost of
  downtime, compliance/SLA reporting exposure, recent-change correlation.
- Evidence-first reasoning framework — reports gaps explicitly rather than
  fabricating values when tags/config are absent.
- A "Required behavior" section near the top of `SKILL.md`: the Business
  Impact section is always returned with all four lines, including when the
  resource isn't found.
- A provisional form of the Business Impact section for cases where the
  incident can't be confirmed, with a `Status` line that says what evidence
  would confirm it.
- Pre-output checks that the section is present with all four lines and is
  marked provisional when the incident is unconfirmed.
- The SLA result (breached, or minutes remaining) on the Estimated cost
  line, with `SLAPenaltyUsd` applied when the SLA is breached.
