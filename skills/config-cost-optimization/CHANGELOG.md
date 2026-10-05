# Changelog

## [1.3.0] - 2026-09-30
### Added
- Treat all ingested data (recorder/rule/pack names, resource tags and identifiers,
  delivery-bucket names, Athena-derived resource strings, Cost Explorer usage-type
  strings) as untrusted — the "Safety and Boundaries" section now states this data must
  never be followed as instructions, so a crafted name or tag cannot steer the agent
  into recommending reduced recording coverage.
- Require every coverage-reducing recommendation (narrow recorded types, switch to
  daily, stop a recorder, drop a rule or conformance pack) to state its
  compliance/security impact and cite the specific cost signal, CI-driver, or
  recorder/rule setting it rests on, enforced by the Step 5 validation check and two
  new report-template columns (Security Impact, Evidence). Addresses H1 from peer
  review.

## [1.2.0] - 2026-09-28
### Changed
- Restructured the skill for progressive disclosure to fix failing best-practices evals (BP-03, BP-12, BP-16) and the BP-17 warning. The SKILL.md body is now a slim checkbox-checklist workflow; detailed material moved into linked files.
- Converted the Step 1–5 workflow to a `- [ ] Step N` checklist and added a dedicated **Step 5: Validate findings** self-check (traceable savings, stated compliance tradeoffs, no unconfirmed conformance-pack merges, no mutations) before report generation.
### Added
- `references/billing-model.md` (charge components and continuous-vs-daily pricing), `references/data-collection.md` (inventory APIs and cost signals), and `references/opportunities.md` (the full Step 4.1–4.8 checks including the conformance-pack overlap decision tree).
- `assets/report-template.md` holding the report structure and table schemas, linked from Step 6.
- Migrated `evals/evals.json` to the current schema and added a file-independent,
  uplift-oriented functional eval suite (6 scenarios incl. conformance-pack overlap,
  standalone-vs-pack, and a negative-trigger case). Best-practices, structure, and
  functional eval results all pass (best-practices 100/100).

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
