---
inclusion: manual
---

# Cloud WAN + Direct Connect Routing Patterns & Considerations

This document captures key routing mechanics and traffic engineering patterns for Cloud WAN architectures with Direct Connect egress. Use this knowledge when advising on Cloud WAN route evaluation, DX Gateway behavior, BGP community usage, and regional failover design.

## Reference Documentation

- [Cloud WAN Route Evaluation](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-route-evaluation.html)
- [Cloud WAN Routing Policies](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-routing-policies.html)
- [Direct Connect Routing Policies and BGP Communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)

## Cloud WAN Route Evaluation Order (Per CNE)

At each Core Network Edge, Cloud WAN evaluates routes in this order:

1. **Most specific route** (longest prefix match) — absolute, wins before everything
2. For same-destination routes with different targets:
   1. Static routes
   2. VPC-propagated routes (same region)
   3. **Unequal AS-path length and/or MED** — shortest wins
   4. **Equal AS-path and MED** — preference order:
      1. Direct Connect Gateway-propagated routes
      2. Cloud WAN Connect (same region)
      3. Site-to-Site VPN (same region)
      4. Other sources (TGW peering, CNEs in other regions) — if identical from 2+ sources: **deterministically random**

## DX Gateway Path Selection Mechanics

### Key Behaviors

1. **DXGW propagates only ONE path per prefix to each CNE route table** — it performs internal path selection and sends only the winner. CNEs do not see all available DX paths.

2. **DXGW uses Local Preference to prefer local-region DX over remote regions** — if a DX VIF exists in the same associated AWS region as the target CNE, DXGW prefers it regardless of AS-path length.

   **⚠️ Always verify the Associated Region for each DX location** — some DX locations can associate to different regions than expected based on geography. For example, London-area locations associate to different regions:
   - Equinix LD5 (Slough) → **eu-west-1** (Ireland)
   - Digital Realty LHR20 (London) → **eu-west-1** (Ireland)
   - Telehouse (London Docklands) → **eu-west-2** (London)
   - Equinix MA3 (Manchester) → **eu-west-2** (London)
   
   The associated region determines which CNE/TGW considers the DX "local" for LP preference. Verify a location's associated region with the `DescribeLocations` API/CLI (`aws directconnect describe-locations`) or the official AWS Direct Connect locations reference: https://aws.amazon.com/directconnect/locations/

3. **Explicit LP communities override DXGW's default local-region preference** — applying `7224:7300/7200/7100` on advertised prefixes forces DXGW to honor the explicit LP before applying its local-vs-remote default.

4. **LP communities are evaluated before AS-path** — per DX documentation: "Local preference BGP community tags are evaluated before any AS_PATH attribute." This applies at the DXGW path selection stage.

5. **LP communities from DX VIFs are NOT visible as community tags in Cloud WAN** — the community tags themselves don't propagate into Cloud WAN routing policies. However, the LP value they set at the DXGW level influences which path gets propagated to the CNE route table.

6. **DXGW ECMPs across equal remote paths** — when the local-region DX fails and multiple remote DX locations have equal attributes (same LP, same AS-path), DXGW will **ECMP across them** rather than picking one non-deterministically. This provides load-balanced failover across all remaining DX locations.

7. **Route filtering on the native Cloud WAN DXGW attachment (Routing Policies)** — Cloud WAN Routing Policies support **prefix-based route filtering (drop) and summarization, inbound and outbound, on Direct Connect attachments**. This is a **separate, supported feature** from the (unsupported) DXGW allowed-prefixes list. Use it to drop an overlapping inbound supernet or to suppress specific VPC prefixes advertised outbound to on-prem.
   - Match prefixes via `prefix-in-cidr` or `prefix-in-prefix-list`; actions are `allow`/`drop`; `routing-policy-direction` is `inbound` or `outbound`.
   - **DX caveat:** BGP communities **cannot** be matched or set on Direct Connect attachments in Cloud WAN — prefix/CIDR matching only (consistent with point 5). Community-based routing policies work on other attachment types but not DX.
   - Source: [Cloud WAN Routing Policies](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-routing-policies.html); the DXGW-attachment "no allowed-prefixes list" limitation ([DX gateway attachments in Cloud WAN](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-dxattach-about.html)) refers to the legacy allowed-prefixes construct, not routing-policy filtering.

**Important distinction — path selection behavior by service:**
- **DXGW:** ECMPs across equal remote paths (load-balanced failover)
- **TGW:** Deterministic — selects oldest route for equal paths. Consistent but not customer-controllable.
- **Cloud WAN CNE:** Deterministic — "deterministically random" at Step 2.4.4 for equal remote CNE paths. Consistent but not customer-controllable.

### Common Pitfall: AS-Path Prepending Does Not Override Local-Region LP at the DXGW

**The mistaken assumption:** "If I prepend a DX VIF's prefix enough, I can steer that region's traffic away from (or toward) it across regions."

**Why it's wrong:** DX egress selection happens at the **DXGW lookup** (see "Two Route Lookups" below), where **local-region Local Preference is evaluated before AS-path**. For a region that has a **local** DX advertisement, the DXGW picks that local path on LP — AS-path (and therefore any prepend) is never consulted. So prepending a local VIF does **not** move that region's traffic off its local DX.

**Where prepending actually acts:** only as the **tiebreaker among remote advertisements** for regions that have **no local** advertisement for the prefix. There, all candidates are remote (LP equal), so the DXGW falls through to AS-path length and the shortest remote advertisement wins. Prepending shapes *which remote DX* those regions use — nothing more.

**Consequence:** Over-prepending a local VIF is not a cross-region steering lever; it only changes that location's standing in the remote-tiebreak for *other* regions. To steer cross-region DX preference, use LP communities (which are evaluated before AS-path at the DXGW), not prepending. Confirm the installed per-region result with `get-network-routes` and the advertised paths with `list-virtual-interface-routes`.

### Foundational Principle: Every Route Table Does Its Own Independent Lookup

The single most important mental model for reasoning about AWS routing: **every construct that has its own route table performs its own independent route lookup**, and a packet is evaluated **hop-by-hop** — each route table it traverses makes a fresh, local forwarding decision using only the routes present in *that* table. There is no single end-to-end path calculation; the path is the concatenation of per-table decisions.

Route-table-owning constructs each do this independently, including:
- **VPC route tables** (subnet → destination: local, IGW, NAT, ENI, TGW/VGW/CWAN attachment, peering, endpoint)
- **Transit Gateway route tables** (per-attachment association/propagation; oldest-route tiebreak on equal paths)
- **DX Gateway** (its own BGP path selection; installs one winning path per prefix into each attached CNE/VGW)
- **Cloud WAN Core Network Edge (CNE) route tables** (the CNE evaluation order over propagated routes)
- **On-prem / customer routers** (their own BGP/IGP tables)

The routing "outcome" is what you get when you chain these together. Each table's chosen next-hop simply hands the packet to the next construct, which then runs *its own* lookup. So to predict or debug a path, walk it table by table: at each hop, ask "what does *this* route table select for this destination, given only the routes it has?" The output (installed route) of one table's lookup becomes an input (a propagated/attached route) to the next.

**Common analysis error:** treating an end-to-end path as one decision, or assuming an attribute (like a DX BGP community or a local preference) that decided at one table still applies at the next. It does not automatically — each table applies only its own selection rules over its own routes. (Example: DX LP communities decide at the DXGW's table but are not visible inside the Cloud WAN CNE table.)

### Applying the Principle: DXGW Lookup then CNE Lookup

In a DX → Cloud WAN egress path, two of these independent lookups sit back-to-back, for the two directions. The DXGW's lookup output is the CNE's lookup input.

**Lookup 1 — DXGW path selection (on-prem → AWS; decides what is INSTALLED into each CNE).**
The DXGW performs its own selection for a prefix and **installs one winning path into each CNE's route table**. Its selection order is:
1. **Local-region Local Preference first** — if a DX VIF advertising the prefix is in the same associated region as the CNE, the DXGW prefers it **regardless of AS-path**. That local copy is installed into that region's CNE.
2. **If no local advertisement exists for that CNE**, every candidate is remote, so they share the **same (remote) LP** — LP is equal. The DXGW then falls through to **AS-path length**, and the **shortest AS-path wins** and is installed into that CNE.

**Lookup 2 — Cloud WAN CNE route lookup (AWS → on-prem return path).**
For return traffic, each CNE runs its own lookup over the routes **propagated into its table** (what Lookup 1 installed, plus routes propagated from other CNEs). This is where the CNE evaluation order (longest-prefix → AS-path → source preference) applies, operating on the already-propagated entries.

### Worked Example (from the field diagram)

Only **FR5/Frankfurt (eu-central-1)** and **LD5/London (eu-west-1)** advertise `11.0.0.0/8`. Applying **Lookup 1 (DXGW)** per region:

| CNE region | Has local `/8` advertisement? | DXGW decision | Installed `/8` path |
|---|---|---|---|
| eu-central-1 (FR5) | Yes (FR5 local) | Local-region LP wins — AS-path not consulted | **FR5 (local DX)** |
| eu-west-1 (LD5) | Yes (LD5 local) | Local-region LP wins — AS-path not consulted | **LD5 (local DX)** |
| ap-southeast-1 | No | FR5 and LD5 **both remote → LP equal** → fall through to AS-path → **FR5 shortest wins** | **FR5** |
| us-east-1 | No | both remote → LP equal → AS-path → **FR5 shortest** | **FR5** |
| us-east-2 | No | both remote → LP equal → AS-path → **FR5 shortest** | **FR5** |

**Why the non-LD5 regions use FR5's advertisement:** they have no local `/8`, so at the DXGW both FR5 and LD5 are **remote** and carry the **same (remote) LP** — LP is equal. The DXGW therefore falls to the next attribute, **AS-path length**, where **FR5 is shorter than the (heavily prepended) LD5 advertisement**, so FR5 wins and is installed. This is a straightforward DXGW LP-then-AS-path decision — **not** a CNE-to-CNE backbone comparison.

**Role of the AS-path prepends:** the prepends matter at **Lookup 1 (DXGW)**, specifically as the **tiebreaker when LP is equal** (i.e., only for regions with no local advertisement). They set which remote advertisement (FR5 vs LD5) wins for those regions. They do **not** override the local-region LP for regions that *do* have a local advertisement — eu-central-1 and eu-west-1 pick their local DX on LP before AS-path is ever considered. So over-prepending LD5 does not stop eu-west-1 from choosing LD5 locally; it affects LD5's standing in the **AS-path tiebreak for the other regions**, where FR5's shorter path beats it.

**Rule of thumb:** Because local-region LP is evaluated before AS-path at the DXGW, a region with a local `/8` advertisement egresses locally regardless of prepends. Use AS-path prepending only to shape which **remote** advertisement wins for regions that have **no local** advertisement (the LP-equal tiebreak). Verify the installed per-region result with `get-network-routes` (Lookup 2's table) and the per-VIF advertised paths with `list-virtual-interface-routes` (Lookup 1's inputs).

### Common Pitfall: Confusing Prepend Count with Total AS-Path Length (Origination vs. Transit)

When comparing AS-path lengths at a CNE (Step 2.3), the number that matters is the **total AS-path AWS receives on the VIF**, not the prepend count configured on a site. These are only the same when the advertising site is the **originator** of the prefix.

**The distinction:**
- **Originating site** — the site owns/aggregates the prefix (e.g., `aggregate-address 11.0.0.0/8`). The AS-path AWS sees is just that site's ASN, repeated by its prepend count. A `prepend 60208 2` on an originated route → AS-path `60208 60208 60208` (length 3).
- **Transiting site** — the site does NOT originate the prefix; it **learns it from another site over the on-prem WAN** and re-advertises it to its DX. The AS-path already contains the origin's ASN, so the transiting site's ASN and prepends stack **on top of** the origin ASN. A `prepend 60208 2` applied to a `/8` learned from origin AS 56608 → AS-path `60208 60208 60208 56608` (length **4**, not 3).

**Config signature to tell them apart:** A site that **matches-and-prepends** a prefix in a route-policy but has **no `aggregate-address`/origination** for it is almost certainly **transiting** a route learned from elsewhere. Do not assume it originates the prefix just because the prefix appears in its outbound policy.

**Why this matters for path selection:** Step 2.3 compares total path length. If you model a transiting site's length as "prepend count + 1" (treating it as an originator) you will miscompute which copy wins — often flipping the predicted winner and the failover order. Example: three sites advertise a `/8` that **originates at only one** of them; the two that transit-and-prepend it are longer than a naive prepend-count model suggests, and can tie with the origin.

**How to get the ground truth:** Never infer AS-path length from prepend config alone when a prefix may be transited. Read the literal path AWS receives per VIF:
```
aws directconnect list-virtual-interface-routes --virtual-interface-id <vif-id>
```
This shows the exact AS-path (and communities) AWS accepted, settling origination-vs-transit and the true length used at Step 2.3.

## DX Routing Selection — General Best Practice

- **Always use LP communities (`7224:7300/7200/7100`) for expected egress routing** — High Preference BGP communities are the recommended mechanism to achieve predictable DX egress behavior.
- **AS-path prepending: within a region ONLY** — AS-path prepending can be used to influence egress traffic between DX connections belonging to the **same associated AWS region** (e.g., two DX locations both in the same region). It should NOT be used to influence traffic across regions — DXGW's local-region LP behavior makes cross-region AS-path prepending unreliable.
- **BGP communities: within region OR across regions** — LP communities work for both intra-region path selection (between VIFs in the same region) and cross-region preference (overriding DXGW's default local-region LP to prefer a remote DX location globally).

| Scope | Recommended Mechanism | Why |
|---|---|---|
| Cross-region DX preference | LP Communities (`7224:7300/7200/7100`) | Overrides DXGW local-region LP; evaluated before AS-path |
| Within-region DX preference (same associated region) | AS-path prepending OR LP communities | Both work; AS-path provides granular control between same-region VIFs |
| Never use for cross-region | AS-path prepending alone | DXGW local-region LP overrides AS-path at the DXGW level, making prepending unreliable across regions |

## Traffic Engineering Patterns

### Pattern 1: Global DX Preference (Single Primary)

**Use case:** One DX location should be globally preferred for a prefix, with another as backup.

**Solution:** Apply tiered LP communities from on-premises routers:

| DX Location | Community | Role |
|---|---|---|
| Primary DX location | `7224:7300` | HIGH — globally preferred |
| Secondary DX location | `7224:7200` | MEDIUM — failover |
| All other DX locations | `7224:7100` | LOW — last resort |

**Result:** DXGW selects the primary for ALL CNEs (overriding local-region preference). If the primary fails, the medium-priority location (`7224:7200`) takes over automatically. (Note: "medium" here refers to the medium local-preference community, not the BGP MED attribute.)

**Tradeoff:** Regions with a local DX that isn't the primary will cross the AWS backbone to reach the preferred DX. Traffic still traverses the local-region firewall (service insertion happens at segment level, before the CNE egress decision).

### Pattern 2: Per-Region DX Preference (Split DXGW)

**Use case:** Different regions need different primary DX locations (e.g., one region group prefers DX-A, another region group prefers DX-B).

**Problem:** Communities from a single DXGW are global — cannot provide per-region preferences.

**Solution:** Create separate DXGWs per region group, each with their own VIFs:
- DXGW-A: Region-A DX locations (primary `7224:7300`, secondary `7224:7200`)
- DXGW-B: Region-B DX locations (`7224:7300`)

Both DXGWs propagate their path to all CNEs. The CNE route table evaluates them at Step 2.3 (AS-path length). Control which DXGW wins per region by differentiating AS-path length on the VIFs between the two DXGWs.

Use communities within each DXGW for internal failover. No Cloud WAN Routing Policies needed — VIF-level BGP attributes provide per-region control at the CNE route table.

### Pattern 3: Per-Region Control via More Specific Routes

**Use case:** On-prem address space is regionally segmented.

**Solution:** Advertise more-specific prefixes from the corresponding DX location:
- DX location A advertises a more-specific covering Region-A on-prem hosts
- DX location B advertises a more-specific covering Region-B on-prem hosts
- All locations advertise the aggregate as a failover catch-all

**Result:** Step 1 (longest prefix match) is absolute — each CNE route table forwards to the correct DX based on destination address.

**Requirement:** Only works if on-prem address space is subdivided into regional ranges. Does NOT work for flat supernets.

## Multi-Region Centralized Internet Egress

### Non-Local Exit Point Selection

In architectures where internet egress is centralized (e.g., a single region hosts the NAT/internet gateway or firewall for outbound traffic), Cloud WAN must route traffic from remote regions to the centralized exit point. Understanding how non-local exit points are selected is critical:

- Each CNE evaluates routes per the standard route evaluation order
- If the default route (0.0.0.0/0) or internet-bound prefix is only advertised from the centralized region's attachment (e.g., via TGW Connect or VPN), all CNEs will install that path
- Remote CNEs forward internet-bound traffic across the AWS backbone to the centralized region's CNE

### AS-Path Prepending for Deterministic Exit (via TGW/VPN)

When routes are propagated from DX or VPN **via TGW** to Cloud WAN (TGW peering attachment), AS-path length information is preserved. This means:

- **AS-path prepending can define a deterministic exit path** — if multiple regions advertise the same prefix via TGW attachments to Cloud WAN, prepending on less-preferred paths ensures remote CNEs choose the shorter AS-path (preferred exit)
- **More-specific routing also applies** — advertising a more-specific prefix from the preferred exit region wins at Step 1 (longest prefix match) regardless of AS-path

**Note:** This behavior differs from DX-attached prefixes where DXGW's local-region LP can override AS-path. When routes come via TGW attachments to Cloud WAN, AS-path evaluation at the CNE operates without DXGW LP interference — making prepending a valid and effective traffic engineering tool in this context.

### Example: Centralized Internet Egress

- Region-A TGW advertises `0.0.0.0/0` to Cloud WAN via TGW peering (short AS-path)
- Region-B TGW also advertises `0.0.0.0/0` but with prepending (longer AS-path)
- All CNEs prefer Region-A as the internet exit (Step 2.3: shorter AS-path wins)
- If Region-A fails, Region-B's longer path takes over as backup

## Regional Firewall Inspection

- Cloud WAN segment policy / service insertion routes traffic through the **same-region firewall** before it reaches the CNE
- Traffic flow: VPC → local firewall (service insertion) → returns to local CNE → CNE route table → DXGW → DX
- With a local DX advertisement present, the DXGW installs the local path into the local CNE (local-region LP, Lookup 1) — traffic stays at the local CNE for egress, preserving the local inspection chain
- If the region has no local DX advertisement (or a community forces a remote DX to win), the installed path points out of region, and traffic leaves the local region for egress — potentially bypassing local firewall inspection
- **Requirement:** Firewall VPCs must exist in every region with workloads

## Directional Control (Mapped to the Two Lookups)

The two route lookups map to the two directions. Keep these straight — they are governed by different services and different mechanisms.

| Direction | Governing lookup | Controlled by | Mechanism |
|---|---|---|---|
| **On-prem → AWS** (which DX path is INSTALLED into each CNE) | **Lookup 1 — DXGW path selection** | On-prem BGP attributes the DXGW sees: DX LP communities (`7224:7300/7200/7100`), then AS-path as the LP-equal tiebreak | DXGW evaluates local-region LP first, then AS-path; installs one winning path per prefix into each CNE |
| **AWS → On-prem** (return path from each CNE) | **Lookup 2 — Cloud WAN CNE route lookup** | The routes propagated into the CNE table (from Lookup 1 + other CNEs), evaluated by the CNE order | CNE evaluation: longest-prefix → AS-path → source preference, over already-propagated routes |

Notes:
- DX LP communities set the LP the **DXGW** uses in Lookup 1 — they are the recommended lever for steering which DX path is installed. They are **not visible inside Cloud WAN** and do not act at Lookup 2.
- If on-prem AS-path prepending was being used to influence selection, prefer LP communities at the DXGW (Lookup 1); over-prepending a local VIF does not achieve cross-region steering (see the AS-Path Prepending pitfall above).

## Cleanup Recommendations

- **Prefer LP communities over prepending for DX egress steering.** Communities set the LP the DXGW uses in Lookup 1 and are evaluated before AS-path; they can steer cross-region preference, which prepending cannot (local-region LP overrides AS-path for any region with a local advertisement).
- **Do not use prepending on a local VIF as a cross-region lever.** At the DXGW, a region with a local advertisement selects it on LP regardless of prepends. Prepending only affects the AS-path tiebreak among **remote** advertisements for regions that have no local advertisement — so its only legitimate use here is choosing which remote DX those regions fall to.
- **Once communities are in place, remove leftover prepends** as a cleanup step, keeping only any within-region or remote-tiebreak prepends that serve a confirmed purpose.
- Always confirm the actual outcome with `get-network-routes` (installed per-CNE result) and `list-virtual-interface-routes` (the AS-path/communities the DXGW actually received) rather than reasoning from configured prepend counts alone.
