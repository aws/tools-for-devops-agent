---
name: dx-vif-resilience
description: >
  Assess Layer-3 (BGP prefix) failover resilience across redundant AWS Direct
  Connect virtual interfaces. Use when the user asks whether their Direct
  Connect setup is resilient, whether failover will work, whether the same
  routes/prefixes are advertised across redundant VIFs, why traffic was lost
  after a VIF or connection failure, or to audit DX BGP route symmetry. Checks
  both directions (routes received from on-prem and routes advertised by AWS)
  using the ListVirtualInterfaceRoutes API and the deterministic
  dx-resilience-mcp analysis tools. Read-only: analysis and recommendations
  only, never configuration changes. Complements Layer-1/2 checks (redundant
  connections, diverse locations/devices) — this skill covers what those miss.
# enable_tools is the documented optional skill-asset metadata property
# ("a list of tool identifiers that the agent can call when it loads this
# skill" — AWS DevOps Agent User Guide, Managing assets > Asset types > skill:
# https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html).
# It is not part of the generic Agent Skills spec, so spec validators may warn.
# It activates the dx-resilience-mcp tools when this skill loads.
# The IDs are prefixed with the MCP server's REGISTERED NAME — you MUST register
# the MCP server as "dx-resilience-mcp" for these to match. If you register it
# under a different name, change the prefix here (and on the custom agent) to
# "<your-server-name>_<tool>". Without this block the agent loads the skill but
# cannot call the tools and aborts the audit.
enable_tools:
  - dx-resilience-mcp_get_dx_topology
  - dx-resilience-mcp_analyze_vif_resilience
  - dx-resilience-mcp_compare_prefix_sets
metadata:
  version: "1.0.0"
  author: abed-kayyali
  summary: Audit Layer-3 failover coverage across redundant Direct Connect VIFs — deterministic BGP prefix-symmetry analysis in both directions.
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "AWS Direct Connect"
  aws-devops-agent-skills.technical-domains: "Networking"
---

# Direct Connect VIF Resilience Assessment (Layer 3 / BGP Prefix Coverage)

## Problem this skill solves

High availability on Direct Connect is customer-managed at the BGP level. AWS
does not enforce that equivalent prefixes are advertised across redundant VIFs.
If a prefix is reachable via VIF-A but has no coverage on VIF-B, traffic to it
is silently blackholed when VIF-A fails — invisible until a real failover.
Resiliency is usually reviewed at Layer 1/2 (connections, locations, devices);
this skill reviews Layer 3, in both traffic directions, and additionally
reports the two physical-diversity levels it can see from the VIF (AWS device
and DX location).

**Account model.** The tool analyzes whatever account its MCP server operates
in. For the common enterprise setup where Direct Connect lives in a dedicated
network account separate from where DevOps Agent runs, deploy the MCP server's
read-only role in the DX-owning account (see the server's cross-account
deployment) — the tool then sees that account's full topology. Note the hosted-
VIF case: if a VIF is owned by the analyzed account but its parent connection is
owned by another account, the VIF and its routes are fully analyzable, but
connection-derived checks (resiliency group, LAG) are reported as indeterminate.

## Hard constraints

- **Strictly read-only.** Only `describe-*`, `list-*`, `get-*` Direct Connect
  calls and the read-only `dx-resilience-mcp` tools. Never create, modify,
  delete, or start anything (including BGP failover tests).
- **Never do CIDR coverage math yourself.** Containment and set-difference
  arithmetic must come from `analyze_vif_resilience` or `compare_prefix_sets`.
  Your job is orchestration, judgment, and translation into customer language.
- Findings are recommendations for the customer to act on — you change nothing.

## Key concepts

**Two directions, both mandatory.**
- `accepted` (on-prem → AWS): what the customer's routers advertise toward AWS.
  A prefix missing here means AWS cannot reach that on-prem destination via
  this VIF after failover.
- `advertised` (AWS → on-prem): what AWS advertises toward the customer.
  Critical in multi-DXGW topologies — each DXGW has an independent allowed
  prefix list, so different VIFs may receive different AWS prefixes.

**Coverage is CIDR-aware, not string matching.** A prefix is covered on a peer
VIF if the exact prefix or a containing supernet exists there. Identical
prefix lists are not required.

**Partial supernet coverage is its own finding class.** If VIF-B carries
`10.10.0.0/22` and VIF-A carries only `10.10.1.0/24`, the analysis reports the
exact uncovered residual (`10.10.0.0/24`, `10.10.2.0/23`): reachable while
VIF-B is up, blackholed if it fails. Severity is conditional — ask the
customer whether workloads exist in the residual ranges. Never call this
scenario fully covered, and never call it a hard gap without that context.

**Traffic engineering is not a gap.** Same prefix with different AS-PATH, MED,
or communities across VIFs is intentional path preference — fine. Only zero
coverage (no exact match, no supernet) is a risk finding. Even then, the
asymmetry may be intentional; the customer must simply be aware of the
failover consequence.

**LAG caveat.** A LAG is one logical connection; a VIF on a LAG is still one
VIF. LAG membership adds link redundancy, not VIF redundancy — never treat two
VIFs as redundant merely because their connections are in LAGs.

**Route-view convergence lag (critical).** `ListVirtualInterfaceRoutes` returns
an eventually-consistent view that lags live BGP after any routing change, and
the lag is non-deterministic per VIF — in testing it ranged from ~1 minute to
~14 minutes, and either VIF in a set could be the slow one on any given change.
Two consequences you must handle:
- **An empty or unexpectedly small `accepted` table on a VIF whose BGP is `up`
  is ambiguous** — it may be genuinely empty, or the view may simply not have
  converged yet. Do not assert "empty VIF" or a large gap set from a single
  snapshot of a recently-changed VIF. If a VIF reads empty/low while its peer
  reads full and BGP is up on both, state that the result may reflect
  propagation lag and recommend re-running the assessment a few minutes later
  to confirm before treating it as a finding.
- Always treat the assessment as point-in-time and note the snapshot time. For
  an audit run shortly after a known change, prefer a re-run to confirm
  stability.

**Large tables are fully paginated.** `analyze_vif_resilience` follows
`nextToken` and assembles all pages, so VIFs advertising hundreds of prefixes
(validated to ~478/VIF) are analysed completely. A route count that is an exact
multiple/near-100 in some other tool is usually an un-paginated first page — not
the real total; trust this tool's `route_counts`, which are the full assembled
totals.

## Workflow

Work through this checklist in order; each step depends on the one before it.

- [ ] Step 1: Discover the estate
- [ ] Step 2: Resolve redundant VIF sets (precedence order)
- [ ] Step 3: Analyse each redundant set
- [ ] Step 4: Interpret severity
- [ ] Step 5: Validate findings against tool output
- [ ] Step 6: Deliver the report

### Step 1 — Discover the estate

Call `get_dx_topology`. Present a VIF summary table: VIF ID, name, type,
state, BGP status, gateway attachment (DXGW/VGW), connection, location,
logical device, resiliency group (via the connection).

### Step 2 — Resolve redundant VIF sets (precedence order)

A redundant set is 2+ VIFs intended to provide failover coverage for the same
workload. Resolve in this order; use the first tier that produces an answer,
and record which tier you used in the report.

1. **Tier 0 — Confirmed intent (memory).** If a memory store is attached,
   check it for previously confirmed redundant sets and accepted asymmetries.
   Use them; re-verify the VIFs still exist.
2. **Tier 1 — Declared intent (resiliency groups).** Connections in the same
   resiliency group declare intended redundancy. Group their VIFs by gateway
   attachment (same DXGW or VGW), same VIF type, same address family.
   Also check for declared-but-broken pairing: connections in a group whose
   `billing_mode` is `FlatRateTier*` rather than `PortPairFlatRateTier*` are
   not actually paired (speed/tier/device mismatch) — that is itself a finding.
3. **Tier 2 — Inferred intent.** Group remaining VIFs by: same DXGW/VGW
   attachment + same VIF type + same customer ASN. Secondary signals: naming
   conventions, tags, location diversity. **Never use route-table overlap as a
   grouping signal** — a VIF with routes disjoint from its intended peer is
   exactly the worst gap; overlap-grouping would hide it.
4. **Tier 3 — Confirm or flag.** In chat: present proposed sets with rationale
   and confidence, ask the user to confirm or adjust, and write confirmed sets
   to the attached memory store. In scheduled runs: proceed with inferred
   sets, label low-confidence groupings in the report, and recommend one-time
   confirmation via chat.

Any available VIF that lands in no set is a finding: "no redundant peer
detected for dxvif-x."

### Step 3 — Analyse each redundant set

Call `analyze_vif_resilience(vif_ids, directions=["accepted","advertised"])`
once per set. The tool performs the BGP pre-check (VIFs with BGP down are
excluded with a reason — report them), fetches routes with pagination, and
returns the full deterministic report including route counts, device
diversity, and pairwise failover impact.

### Step 4 — Interpret severity

- `gaps` → 🚨 highest risk: guaranteed blackhole for that prefix if its only
  VIF fails. Use the `pairwise` section for the directional statement: "If
  dxvif-aaa fails, traffic to X is blackholed."
- `partial_supernet` → ⚠️ conditional: report the exact residual ranges and
  ask the customer to confirm whether they host workloads.
- `partial` (3+ VIF sets) → ⚠️ medium: covered on some peers, missing from
  others; a gap only on a standby VIF is lower severity — say which VIF.
- `empty_vifs` (BGP up, zero routes) → ⚠️ always a finding in itself.
- `default_route_present` → report explicitly; a default route never
  suppresses individual prefix findings.
- `physical_diversity` → report **both levels independently**, they are not the
  same guarantee:
  - `device_diverse` false → VIFs share an AWS logical device; a device fault
    takes them down together.
  - `location_diverse` false → all VIFs terminate at the **same DX location**; a
    site event (power, cross-connect, local fiber) takes the whole set down even
    if they are on different devices and prefixes are symmetric. A set can be
    device-diverse yet location-shared — call this out explicitly.
- `connection_visibility.all_vif_connections_visible` false → these are hosted /
  cross-account VIFs whose parent connections this account can't see.
  Resiliency-group, LAG, and connection-location checks are **indeterminate** —
  report them as "cannot verify (connection owned by another account)", never as
  "none". Device and DX-location diversity remain valid (read from the VIF).
- Route counts near a quota → prefixes may be absent due to quota, not
  misconfiguration: advertised counts near 200 on a transit VIF (DXGW→TGW
  combined IPv4+IPv6 quota), accepted counts near the VIF's configured
  allocation (default 100 per family, adjustable to 1,000 via prefix
  controls). Quotas are adjustable — check the account's effective values
  (see [DX BGP resilience concepts](references/dx-bgp-resilience-concepts.md)).

### Step 5 — Validate findings against tool output

Before delivering, self-check the assembled report:

- [ ] Every gap / partial-supernet / partial finding in the report appears in
      the tool output — none added, none dropped, residual ranges copied
      exactly.
- [ ] Both directions (accepted AND advertised) are present for every set.
- [ ] Device diversity and DX-location diversity are reported as two separate
      lines, and hosted/cross-account indeterminate checks say "cannot
      verify", not "none".
- [ ] The convergence-lag caveat is applied to any empty/low accepted table on
      a BGP-up VIF, and the point-in-time note is present.

If any check fails, fix the report (or re-run the tool) before presenting it.

### Step 6 — Deliver the report

Produce the report using the structure defined in
[the report template](references/report-template.md).

## Common scenarios

- **Two VIFs, same DXGW:** `advertised` direction is normally identical (one
  allowed-prefix list) — still check it; focus interpretation on `accepted`.
- **Two VIFs, different DXGWs, same on-prem edge:** both directions critical;
  allowed-prefix lists are independent. Intent inference is weakest here —
  confirm the set with the user (Tier 3).
- **Private VIFs on a VGW:** same workflow; `get_dx_topology` shows
  `virtual_gateway_id` instead of a DXGW.
- **3+ VIFs in a set:** the tool compares all pairs automatically; weigh
  severity by which VIF is primary vs standby.
