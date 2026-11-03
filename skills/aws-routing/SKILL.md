---
name: aws-routing
description: 'Use this skill when the user wants to know which path AWS will pick for their traffic, why traffic took an unexpected route, or how to make AWS prefer a path. Covers Cloud WAN CNE route evaluation, Direct Connect Gateway local vs remote region preference, Transit Gateway route tables, ECMP and peering, VPC longest-prefix-match, BGP traffic engineering (LP communities 7224:7100/7200/7300, AS-path prepending, MED), DX + VPN redundancy and failover, and asymmetric routing. Use it even when the user only describes a symptom, such as "traffic is leaving the region", "not using my local Direct Connect", "routing to the wrong VIF/location", or "path is asymmetric". Read-only: analysis, recommendations, and describe/get/list validation commands grounded in public AWS docs.'
metadata:
  version: "1.2.6"
  author: midakin
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
---

## Overview

This skill provides routing-first analysis for AWS networking. It reasons about the full traffic
path, applies the documented route-evaluation logic for each service, and grounds recommendations
in public AWS documentation. It is **read-only**: it produces analysis, recommendations, and
read-only validation commands (`describe-*`, `get-*`, `list-*`) - never mutating actions.

## Verification & Anti-Hallucination Directives (Mandatory)

- Do not generate any fact, citation, or source that is not fully verifiable. If you lack a verified
  source, state "I cannot verify this" rather than inventing details.
- State assumptions explicitly before answering.
- Cross-check each claim against public AWS documentation or the `references/` files. Omit claims you
  cannot confirm.
- Only cite AWS documentation URLs you have actually retrieved or confirmed. Do not fabricate links.

## When to use this skill

Activate when the user asks about:
- Cloud WAN route evaluation / Core Network Edge (CNE) path selection
- Direct Connect Gateway path selection, local-region preference, or LP communities
- Transit Gateway route evaluation, ECMP, or peering routing
- VPC route tables and longest-prefix-match behavior
- BGP traffic engineering (communities, AS-path prepending, MED)
- DX + VPN redundancy, active/active vs active/passive, or failover design
- Why traffic is taking an unexpected path

## What this skill does NOT do

This skill is **read-only and advisory**. It will not:
- **Design or apply infrastructure changes.** It does not create, modify, or delete AWS resources,
  and it does not run mutating CLI/API calls (`create-*`, `modify-*`, `associate-*`, `delete-*`,
  `put-*`, `update-*`) or write Infrastructure-as-Code to be deployed. Any change it describes is a
  *recommendation* for you to review and implement yourself.
- **Configure BGP or push routing policy.** It explains which communities, AS-path, or MED settings
  to use, but it does not apply them to VIFs, route tables, or Cloud WAN policy documents.
- **Execute anything against a live account beyond read-only validation.** Commands it provides are
  limited to `describe-*`, `get-*`, and `list-*` for confirming state.
- **Guarantee production outcomes.** It recommends non-production testing and blue/green rollout;
  it does not perform the cutover or validate the result for you.
- **Provide compliance, security, or contractual sign-off**, or make claims it cannot ground in
  public AWS documentation or the `references/` files.

For designing and applying changes, hand the recommendation to a change-capable workflow (with
appropriate review, approvals, and testing).

## How to analyze a routing problem

Work through this checklist in order; each step depends on the one before it.

- [ ] **1. Establish the path.** Identify source, destination, and every routing construct in
  between (VPC route table → TGW/Cloud WAN CNE → DXGW → VIF → on-prem, or the relevant subset).
- [ ] **2. Name the route table.** Be explicit about which table makes each decision (VPC RT, TGW RT,
  CNE RT, DXGW internal selection).
- [ ] **3. Apply the evaluation order for that construct** (see below).
- [ ] **4. Identify the deciding attribute** (longest prefix, local preference, AS-path, MED, source
  type).
- [ ] **5. Flag non-determinism** (e.g., ECMP or "deterministically random" tiebreakers) and
  recommend a deterministic alternative.
- [ ] **6. Cite the AWS documentation** that supports the behavior.
- [ ] **7. Provide read-only validation commands** the user can run to confirm.
- [ ] **8. Self-check before answering.** Re-read the answer against steps 1-7: every route table is
  named, the evaluation order matches the construct, each cited URL was actually retrieved, and every
  command is read-only. Fix any gap before presenting.

## Key evaluation rules

### Every route table does its own lookup
Each construct that owns a route table makes its own decision. The DXGW is a distributed set of BGP
route reflectors outside the data path: it selects the best VIF per prefix and reflects it, so a TGW
or Cloud WAN CNE sees the DXGW as (usually) a single next hop and traffic goes straight to that VIF.
There is no second packet lookup at the DXGW.

### ECMP is an outcome, not a step
Longest prefix match comes first (a route lookup, not a BGP attribute). Then BGP attributes are
compared in order and selection stops at the first attribute that differs. If all of them are equal,
the result is ECMP.

### Cloud WAN (per CNE)
Longest prefix match first; then static → system routes (1:1 NAT) → VPC-propagated (same region) →
unequal AS-path/MED (shortest AS-path, then lowest MED) → equal AS-path & MED source preference:
DXGW-propagated → Cloud WAN Connect → S2S VPN → other (TGW peering, remote CNEs; identical from 2+
sources = deterministically random, chosen per segment / network function group).

### Direct Connect (private/transit VIF, outbound AWS→on-prem)
Longest prefix match first; then local preference → AS_PATH length → MED, stopping at the first
difference. If all are equal, the result is ECMP across the VIFs. LP communities `7224:7300/7200/7100`
(High/Medium/Low) set local preference and are evaluated before AS-path. These BGP attributes are
set at the VIF level on the on-prem router's advertisements and evaluated by the DXGW. DXGW prefers
the local associated-region DX by default.

### Transit Gateway with Direct Connect
Use one DXGW with multiple transit VIFs for ECMP. BGP attributes stay on the VIFs and do not pass to
the TGW. Use multiple DXGWs only for traffic isolation or multiple primary paths. For ECMP across
DXGW attachments, LP communities and failover timing, load
[Transit Gateway routing patterns](references/tgw-routing-patterns.md).

### Direction & tooling guidance
- **AWS → on-prem (egress):** control with DX LP communities.
- **On-prem → AWS (ingress):** control with the customer router's local-pref/weight/MED.
- **AS-path prepending:** within a region only - unreliable across regions because DXGW local-region
  LP overrides it. **LP communities:** work within-region and cross-region.

## Reference material

Detailed mechanics, patterns, and caveats are in `references/`. Load only the file that matches the
construct deciding the path:
- [Cloud WAN + DX routing patterns](references/cloudwan-dx-routing-patterns.md) - load when the path
  crosses a Cloud WAN CNE: CNE route evaluation, DXGW path selection into Cloud WAN, community
  traffic-engineering patterns, regional inspection, multi-region egress.
- [Direct Connect routing patterns](references/dx-routing-patterns.md) - load when the question is
  about a DX VIF or DXGW without Cloud WAN: BGP mechanics, BFD, MED, ASN ranges, VIF considerations,
  CloudHub, when VIFs can talk, active/active vs active/passive.
- [Transit Gateway routing patterns](references/tgw-routing-patterns.md) - load when a TGW route
  table makes the decision: TGW route evaluation, ECMP limits, DXGW-to-TGW behavior, DX/VPN caveats,
  failover, peering.
- [VPN + DX redundancy patterns](references/vpn-dx-redundancy-patterns.md) - load when VPN backs up
  or runs alongside DX: route preference between them, ECMP limits, asymmetric return paths.
- [Networking strategic questions](references/networking-strategic-questions.md) - load when key
  facts are missing (regions, attachments, ASNs, communities) and you need discovery questions to ask
  before analyzing.

## Output expectations

- Explain the route-evaluation logic step by step.
- Name the specific route table involved.
- Give the end-to-end traffic path.
- Compare options with tradeoffs (determinism, complexity, failover) when multiple solutions exist.
- Include read-only AWS CLI validation commands.
- Recommend testing in a non-production environment and blue/green for migrations.
