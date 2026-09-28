# Changelog

## [1.1.0] - 2026-09-28
### Changed
- Rewrote §4.5/§4.6 to be prescriptive about conformance-pack overlap. Overlapping packs (e.g. PCI DSS and NIST 800-53) are treated as intentional dual-attestation, not waste, since AWS Config tracks compliance per pack and maps shared rules to different framework controls. Consolidation/merge is now recommended only when the customer confirms separate per-framework reporting is not required; otherwise the overlap is reported as INFO with a cost ceiling.
- Tightened the standalone-vs-pack duplicate-rule check to require matching source identifier and parameters, and to flag stricter-threshold standalone rules as distinct requirements rather than duplicates.
### Added
- Safety boundary and Known Quirk: never collapse compliance frameworks to save evaluation cost; the lost per-framework attestation is not recoverable.

## [1.0.0] - 2026-09-24
### Added
- Initial release of the AWS Config cost optimization skill for AWS DevOps Agent
- Read-only inventory of configuration recorders, recording mode (continuous/daily and per-resource-type overrides), delivery channels, rules, conformance packs, and aggregators
- Cost optimization checks across eight areas: continuous-vs-daily recording frequency mismatch, over-broad `allSupported` recording, duplicate global-resource recording across Regions, high-churn configuration-item drivers, redundant/unnecessary rules, conformance pack efficiency, S3 delivery-bucket lifecycle hygiene, and recorders running with no downstream consumer
- Configuration-item driver attribution via Cost Explorer usage types, Athena-based analysis, or resource-count signals, with estimated monthly savings
- Severity-ranked findings (CRITICAL, HIGH, MEDIUM, LOW, INFO) and a shareable Markdown report artifact named `config-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
- Compliance-aware, read-only guidance — no recorder, rule, or conformance-pack mutations
- Evaluation test cases (5 functional evals, 6 trigger queries)
