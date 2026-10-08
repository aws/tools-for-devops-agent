# Changelog

## [1.2.3] - 2026-09-21
### Changed
- `SKILL.md`: set `metadata.author` to a resolvable GitHub login (`midakin`) so the generated docs-catalog profile link points to a valid account.
### Added
- Root `llms.txt` catalog entry for the skill.
- `.skilleval.yaml` pinning the intentional `STR-016` audit info finding (README alongside SKILL.md).

## [1.2.2] - 2026-09-10
### Changed
- `references/tgw-routing-patterns.md`: clarified that the VPN-preferred-over-DX behavior applies specifically to a **static** VPN (dynamic VPN behaves differently).
- `references/dx-routing-patterns.md`: replaced the specific internal LOCAL_PREF values (3000/2500) with generic "Higher"/"Lower", since the exact values are internal and not publicly documented; the DX-over-peering preference is still stated.

## [1.2.1] - 2026-09-10
### Changed
- `references/cloudwan-dx-routing-patterns.md`: added the "every route table does its own independent lookup" mental model and the DXGW-then-CNE two-lookup framing; corrected the AS-path prepending pitfall (local-region LP is evaluated before AS-path at the DXGW, so prepending a local VIF is not a cross-region steering lever — it only breaks the LP-equal tiebreak among remote advertisements); added a worked per-region example and remapped directional control and cleanup guidance to the two lookups.
- `SKILL.md`: set `metadata.version` to `1.2.1` to match the changelog.

## [1.2.0] - 2026-08-25
### Added
- Two functional eval scenarios covering the corrected knowledge: TGW→VPN summarization (keep propagation + static summary + limit-hit selection order) and overlapping DX supernet into Cloud WAN (Routing Policies drop/suppress on DX; no BGP communities on DX attachments).
- Matching positive trigger queries for the two new scenarios.
### Changed
- `references/tgw-routing-patterns.md`: clarified the limit-hit advertisement-selection order (static over propagated, then least-specific), labeled as field knowledge.
- `references/cloudwan-dx-routing-patterns.md`: added that Cloud WAN Routing Policies support prefix filtering (drop/summarize) inbound/outbound on Direct Connect attachments (distinct from the legacy allowed-prefixes list); DX attachments cannot match/set BGP communities.

## [1.1.0] - 2026-08-18
### Changed
- Refined the `description` for better activation: added symptom-based trigger phrasings and explicit
  service/keyword coverage.
### Added
- Expanded functional evals (DX location preference, TGW ECMP, DX+VPN redundancy, verification of
  unknown sources) — 7 scenarios total.
- Expanded trigger tests with more positive routing prompts and additional negative (non-routing)
  prompts.

## [1.0.0] - 2026-08-18
### Added
- Initial release of the `aws-routing` skill, adapted from the AWS Routing custom agent.
- Route-evaluation guidance for Cloud WAN CNEs, Direct Connect Gateway path selection, Transit
  Gateway route tables, and VPC route tables.
- BGP traffic-engineering guidance: LP communities (`7224:7100/7200/7300`), AS-path prepending
  (within-region only), MED (low-priority tiebreaker), and longest-prefix-match behavior.
- DX + VPN redundancy, active/active vs active/passive, and failover analysis.
- Reference knowledge base under `references/`.
- Verification / anti-hallucination directives built into the skill instructions.
