# Changelog

All notable changes to the `lambda-operational-review` skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-05

### Added
- Initial release.
- Read-only Lambda operational review across seven dimensions: Configuration &
  Runtime, Reliability, Performance, Concurrency & Throttling, Security, Cost,
  and Observability.
- Incident-investigation mode with decision-tree runbooks
  (`references/troubleshooting-runbooks.md`) for elevated errors, throttling,
  timeouts, VPC/networking errors, cold-start latency, and stream consumer lag.
- Discovery of function configuration, event source mappings, concurrency
  settings, function URLs, resource policies, and execution roles.
- 14-day CloudWatch metrics analysis with severity thresholds
  (`references/metrics-thresholds.md`) and a memory-vs-duration right-sizing
  heuristic.
- Best-practices checklist (`references/best-practices-checklist.md`) covering
  deprecated runtimes, DLQ/destinations, cold starts, reserved/provisioned
  concurrency, execution-role least privilege, function URL auth, arm64
  candidacy, and log retention.
- Per-function report artifact named `lambda-review-<function-or-scope>-<YYYY-MM-DD>.md`.
