# Changelog

## [1.0.0] - 2026-10-20
### Added
- Initial release. Read-only Amazon CloudFront operational review across Security, Reliability, Performance Efficiency, Operational Excellence, and Cost Optimization.
- Two-pass design: account-level reads score and rank every distribution; per-distribution reads (metrics, WAF, ACM, policy detail, tags) run on all distributions when there are fewer than 10, otherwise on the 10 worst-ranked plus any the user named.
- Origin classification before origin-access findings, so origin access control is only recommended for eligible origins.
- Three-state Pass / Inspect / Fail verdicts; default origin timeouts, geo restriction and field-level encryption are Inspect.
- Origin classification and severity / scoring rules in `references/`, loaded on demand, with in-body fallbacks.
- Self-check of findings, scores and visibility limits before the report is delivered.
- Detection of opt-in additional metrics via the monitoring subscription, and of standard logging (v2) via CloudWatch Logs deliveries.
- Readiness score that LOW findings do not reduce; Cost Explorer findings degrade gracefully in linked accounts.
