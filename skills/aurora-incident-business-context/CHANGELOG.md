# Changelog

## [1.0.0] - 2026-10-29
### Added
- Initial release. Adapted from the business-context MCP prototype
  (Lambda + API Gateway, synthetic example data) in the Aurora MySQL
  Incident Investigation demo in `aws-samples/sample-aws-genai-ops-demos`.
- Four evidence categories: dependent services/criticality, cost of
  downtime, compliance/SLA reporting exposure, recent-change correlation.
- Evidence-first reasoning framework — reports gaps explicitly rather than
  fabricating values when tags/config are absent.
