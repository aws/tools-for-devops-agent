# Changelog

## [1.2.6] - 2026-11-03
### Changed
- All files: adopted the two-lookup model. Every construct that owns a route table does its own lookup; the DXGW is a distributed set of BGP route reflectors outside the data path, so the TGW/CNE sees it as (usually) one next hop and traffic goes straight to the selected VIF.
- All files: path selection is now written as longest prefix match first (a route lookup), then local preference → AS_PATH length → MED, stopping at the first difference. ECMP is described as the result when all are equal, never as a step.
- All files: BGP attributes (LP communities, AS_PATH prepends, MED) are described as **VIF-level**, set on the on-prem router's advertisements and evaluated by the DXGW / Direct Connect side. Across multiple DXGWs on one TGW, Direct Connect compares the VIF advertisements and the TGW installs the result; the attributes do not pass to the TGW and the TGW does not compare them (SME-confirmed field knowledge).
- All files: removed every statement that the TGW picks among equal routes by route age. Replaced with: Direct Connect compares the VIF advertisements across DXGWs using all BGP attributes; when they all match, the TGW installs every DXGW attachment as an ECMP next hop, otherwise a single attachment is installed (one picked by a hash of the prefix metadata when no attribute separates them; field knowledge), plus the documented note that AWS can't guarantee a consistent order for exact ties.
- `references/tgw-routing-patterns.md`: corrected the 1.2.5 DXGW claims. Removed "DXGW Advertises Only ONE Best Path Per Prefix to TGW" (redundant VIFs on one DXGW being active/passive at the TGW, and multiple DXGWs being needed for multiple active paths); one DXGW with multiple transit VIFs is now the documented ECMP recommendation. Replaced "Same-ASN Requirement for TGW ECMP Across DXGWs" with the documented condition (prefix, prefix length and AS_PATH exactly the same; no AS-Path Relax) plus field knowledge (equal MED, same ASNs), the decision made on the Direct Connect side, and the `search-transit-gateway-routes` check (two attachments listed = ECMP). The DXGW Amazon-side ASN is kept as the only open question.
- `references/tgw-routing-patterns.md` and `references/dx-routing-patterns.md`: **reversed** "LP Communities Not Honored Across Multiple DX-GW Attachments". Per SME-confirmed field knowledge, the cross-DXGW comparison uses local preference (LP communities and the local-Region default) before AS_PATH and MED, so LP communities are the preferred lever for steering between DXGWs.
- `references/tgw-routing-patterns.md`: added "When to Use Multiple DXGWs". Default is one DXGW (AWS recommends a single DXGW for ECMP and states high availability is built in). The only reasons for multiple DXGWs are traffic isolation (between on-prem networks/sites or between attachments) and architectures that need multiple primary paths (cross-references Cloud WAN Pattern 2). Added deterministic steering levers, failover/failback behavior and the stateful-firewall asymmetry risk (field knowledge), and up-to-60-second convergence between attachments of any type.
- `references/tgw-routing-patterns.md`: replaced the 5,000-route section with a quotas table (5,000 VPN advertisement cap not adjustable; 1,000 inbound; 10,000 is TGW-wide across all route tables, not per table; Connect peer 5,000), an escalation note, and the cap selection order (SME-confirmed field knowledge). TGW peering: static routes only, no announced timeline for route propagation, Region support via the FAQ.
- `references/dx-routing-patterns.md`: added the route-reflector description; BGP route visibility now lists the China Regions; dropped the unverified CloudWatch metrics date; replaced the VPC-to-VPC "Regression" section with the documented DXGW behavior and mitigations; added the one-DXGW guidance to Active/Active; the DX site-to-site transit row is marked as a capability statement, not a reason to add a DXGW.
- `references/dx-routing-patterns.md` and `references/cloudwan-dx-routing-patterns.md`: corrected the associated-Region examples. The associated Region belongs to the Direct Connect **device**, and one location can host devices for several Regions. Equinix LD5 and Digital Realty LHR20 are now listed as **eu-west-1 and eu-west-2**; Telehouse West and Equinix MA3 stay eu-west-2 only. Added the documented default-LP rule (same associated Region = `7224:7200` medium, others lower, unless communities are tagged) and guidance to confirm a connection's Region with `describe-connections`. The associated-Region note now has its own heading instead of a duplicated "BFD" heading.
- `references/cloudwan-dx-routing-patterns.md`: added the system routes (1:1 NAT) step and per-segment deterministic choice to the route evaluation order (step numbers shifted by one); reframed DXGW point 1 with the two-lookup model; local-region LP and remote-ECMP marked as SME-confirmed field knowledge; corrected the Lookup 1 / Lookup 2 text and the directional-control table so both lookups govern AWS → on-prem traffic; Pattern 2 now states that LP communities on the VIFs of a single DXGW apply globally.
- `references/vpn-dx-redundancy-patterns.md`: scoped "no ECMP" to VPN on a VGW; TGW and Cloud WAN support VPN ECMP (dynamic routing required on TGW). Labeled the same-DX-location flow-hash rule as field knowledge. Added that DX local-preference communities (`7224:7300/7200/7100`) on private VIFs attached directly to a VGW steer AWS → on-prem traffic and are evaluated before AS_PATH, then MED (SME-confirmed field knowledge).
- `SKILL.md`: added "Every route table does its own lookup", "ECMP is an outcome, not a step" and "Transit Gateway with Direct Connect" to the key evaluation rules; updated the Cloud WAN and Direct Connect rules. Set `metadata.version` to `1.2.6`.
- `evals/evals.json`: functional expected outputs and assertions updated to the corrected guidance (two-lookup model and local-region LP before AS-path, ECMP as an outcome, one DXGW for ECMP, LP communities honored across DXGWs, no route-age selection). Eval results re-generated.

## [1.2.5] - 2026-10-27
### Added
- `references/tgw-routing-patterns.md`: new "DXGW Advertises Only ONE Best Path Per Prefix to TGW" subsection. A single DXGW propagates one winner per prefix to the TGW, so redundant VIFs on one DXGW are active/passive at the TGW; multiple paths per prefix at the TGW require multiple DXGW attachments. Marked `[Field knowledge]`.
### Changed
- `references/tgw-routing-patterns.md`: removed the "multiple DX-GW attachments (within the same DX-GW)" ECMP line, which contradicted the one-path-per-prefix behavior. Clarified that TGW ECMP across separate DXGWs needs identical AS-paths (same ASNs, not just equal length) because TGW does not support AS-path relax, and contrasted this with DX-side ECMP, where AS_PATH ASNs do not need to match.
- `SKILL.md`: `description` rewritten to open with "Use this skill when..." and focus on user intent, keeping the same scope and symptom triggers (BP-01).
- `SKILL.md`: reference files are now markdown links, each with a condition for when to load it; the routing-analysis steps are a checklist with a final self-check step. No technical guidance changed. Driven by skill evaluation tool best-practices findings (BP-04, BP-05, BP-16, BP-17).
- `evals/evals.json`: converted to the skill evaluation tool's functional schema (`skill_name`, `task_type`, `should_trigger`), keeping the nine existing evals unchanged and adding two negative evals.
## [1.2.4] - 2026-10-21
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## [1.2.3] - 2026-09-21
### Changed
- `SKILL.md`: set `metadata.author` to a resolvable GitHub login (`midakin`) so the generated docs-catalog profile link points to a valid account.
### Added
- Root `llms.txt` catalog entry for the skill.
- `.skilleval.yaml` pinning the intentional `STR-016` audit info finding (README alongside SKILL.md).

## [1.2.2] - 2026-09-10
### Changed
- `references/tgw-routing-patterns.md`: clarified that the VPN-preferred-over-DX behavior applies specifically to a **static** VPN (dynamic VPN behaves differently).
- `references/dx-routing-patterns.md`: replaced the specific internal LOCAL_PREF values with generic "Higher"/"Lower", since the exact values are internal and not publicly documented; the DX-over-peering preference is still stated.

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
