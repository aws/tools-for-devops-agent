---
inclusion: manual
---

# Cloud WAN + Direct Connect Routing Patterns & Considerations

This document captures key routing mechanics and traffic engineering patterns for Cloud WAN architectures with Direct Connect egress. Use this knowledge when advising on Cloud WAN route evaluation, DX Gateway behavior, BGP community usage, and regional failover design.

## Reference Documentation

- [Cloud WAN Route Evaluation](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-route-evaluation.html)
- [Cloud WAN Routing Policies](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-routing-policies.html)
- [Cloud WAN Routing Policy, Part 1: fine-grained controls](https://aws.amazon.com/blogs/networking-and-content-delivery/aws-cloud-wan-routing-policy-fine-grained-controls-for-your-global-network-part-1/)
- [Cloud WAN Routing Policy, Part 2: real-world scenarios](https://aws.amazon.com/blogs/networking-and-content-delivery/aws-cloud-wan-routing-policy-real-world-global-network-scenarios-part-2/)
- [Direct Connect locations](https://aws.amazon.com/directconnect/locations/)
- [Direct Connect Associated Region](https://docs.aws.amazon.com/directconnect/latest/UserGuide/remote_regions.html#associated-region)
- [Direct Connect Routing Policies and BGP Communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)
- [Direct Connect gateways](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-gateways-intro.html)

## Cloud WAN Route Evaluation Order (Per CNE)

At each Core Network Edge, Cloud WAN evaluates routes in this order ([Cloud WAN route evaluation](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-route-evaluation.html)):

1. **Most specific route** (longest prefix match) — absolute, wins before everything. This is a route lookup, not a BGP attribute.
2. For same-destination routes with different targets:
   1. Static routes
   2. System routes (1:1 NAT)
   3. VPC-propagated routes (same region)
   4. **Unequal AS-path length and/or MED** — shortest AS-path wins, then lowest MED
   5. **Equal AS-path and MED** — preference order:
      1. Direct Connect Gateway-propagated routes
      2. Cloud WAN Connect (same region)
      3. Site-to-Site VPN (same region)
      4. Other sources (TGW peering, CNEs in other regions) — if identical from 2+ sources: **deterministically random**

The deterministically random choice is made **per segment / network function group**, so the same route can resolve to a different next hop in different segments.

## DX Gateway Path Selection Mechanics

### Key Behaviors

1. **Two lookups: the DXGW reflects, the CNE forwards.** The DXGW is "a distributed set of BGP route reflectors" that "operates outside the data traffic path" ([Direct Connect gateways](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-gateways-intro.html)). For each prefix, the DXGW does its own selection across its VIFs for each CNE, evaluating the BGP attributes on each VIF's advertisements (set per VIF by the on-prem router), and reflects the result, so the CNE sees the DXGW as (usually) a single next hop. The CNE then does its own lookup over that route and the routes from other sources. Traffic leaving the CNE goes straight to the VIF the DXGW selected; packets do not go through a second lookup at the DXGW. CNEs do not see every available DX path, only the DXGW's result.

2. **Local-region preference is applied as local preference** — **[Field knowledge, SME-confirmed]** for AWS → on-prem traffic, AWS applies a higher local preference to the path through a DX VIF in the same associated Region as the CNE. Local preference is compared before AS_PATH, and BGP stops at the first attribute that differs, so AS-path prepending cannot override it.

   **⚠️ Always check the associated Region of the specific DX *connection*; do not assume one Region per location.** Source the location name and associated Region(s) from the [Direct Connect locations page](https://aws.amazon.com/directconnect/locations/) and the [Associated Region](https://docs.aws.amazon.com/directconnect/latest/UserGuide/remote_regions.html#associated-region) table. Some locations serve **more than one Region, depending on port speed**, and a connection takes the Region of the device it terminates on.
   - Dual-Region example: **Equinix LD5 (Slough, GBR)** is listed as Europe (Ireland) for 1G and 10G, and Europe (London) for 1G, 10G and 100G, so a 1G or 10G connection at LD5 can be associated with either Region. Digital Realty LHR20 (London), Digital Realty STO1 (Stockholm) and Telehouse Voltaire (Paris) are also listed with two Regions.
   - Single-Region examples from the same table: Equinix MA3 (Manchester) and Telehouse West (London) → Europe (London); Equinix FR5 (Frankfurt) → Europe (Frankfurt). Re-check the table, as it changes over time.
   
   The connection's associated Region determines which CNE/TGW considers the DX "local" for LP preference. AWS sets the default LP per Region to prefer same-associated-Region DX (`7224:7200` medium) and sets it lower for others, unless LP communities are tagged. Confirm the actual connection's Region with `aws directconnect describe-connections` (`describe-locations` lists the locations available in a Region). References: [Associated Region](https://docs.aws.amazon.com/directconnect/latest/UserGuide/remote_regions.html#associated-region), [Locations and their associated Regions](https://docs.aws.amazon.com/directconnect/latest/UserGuide/remote_regions.html#locations-and-associated-regions), [Routing policies and BGP communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html).

3. **Explicit LP communities override DXGW's default local-region preference** — applying `7224:7300/7200/7100` on advertised prefixes forces DXGW to honor the explicit LP before applying its local-vs-remote default.

4. **LP communities are evaluated before AS-path** — per DX documentation: "Local preference BGP community tags are evaluated before any AS_PATH attribute." This applies at the DXGW path selection stage.

5. **LP communities from DX VIFs are NOT visible as community tags in Cloud WAN** — the community tags themselves don't propagate into Cloud WAN routing policies. However, the LP value they set on the VIF advertisements, which the DXGW evaluates, influences which path the DXGW reflects to the CNE.

6. **DXGW ECMPs across equal remote paths** — **[Field knowledge, SME-confirmed]** when the local-region DX fails and multiple remote DX locations have equal attributes (same LP, same AS-path), DXGW will **ECMP across them** rather than picking one non-deterministically. This provides load-balanced failover across all remaining DX locations. Source of truth for which Region is local: the [Direct Connect locations page](https://aws.amazon.com/directconnect/locations/) and `aws directconnect describe-locations`.

7. **Routing policies on the native Cloud WAN DXGW attachment (filtering, summarization, path preferences)** — Cloud WAN Routing Policies (core network policy version **2025.11 or later**) support, on Direct Connect attachments: **prefix-based route filtering** (allow/drop, inbound and outbound), **summarization** (outbound only), and **path preferences** — setting **local preference, AS_PATH or MED** on inbound and outbound route propagations. This is a **separate, supported feature** from the (unsupported) DXGW allowed-prefixes list. Use filtering to drop an overlapping inbound supernet or to suppress specific VPC prefixes advertised outbound to on-prem; use inbound path preferences to steer between multiple DXGW attachments (see "Multiple DXGWs on Cloud WAN" below).
   - Match prefixes via `prefix-in-cidr` or `prefix-in-prefix-list`; actions include `allow`/`drop` (terminal), `set-local-preference` and `set-med` (non-terminal), and `summarize`; `routing-policy-direction` is `inbound` or `outbound`. A higher local preference is preferred; the default is 0.
   - **DX caveat:** BGP communities **cannot** be matched or set on Direct Connect attachments in Cloud WAN — prefix/CIDR matching only (consistent with point 5). Community-based routing policies work on other attachment types but not DX.
   - **Visibility:** the **Route information base** tab (and `list-core-network-routing-information`) shows routes **before** routing policies are applied; the **Routes** tab shows the route Cloud WAN installed after policy evaluation.
   - Sources: [Cloud WAN Routing Policies](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-routing-policies.html), [Cloud WAN Routing Policy Part 1](https://aws.amazon.com/blogs/networking-and-content-delivery/aws-cloud-wan-routing-policy-fine-grained-controls-for-your-global-network-part-1/) (policy version 2025.11, Route information base vs Routes tab); the DXGW-attachment "no allowed-prefixes list" limitation ([DX gateway attachments in Cloud WAN](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-dxattach-about.html)) refers to the legacy allowed-prefixes construct, not routing-policy filtering.

### Multiple DXGWs on Cloud WAN (Differs From TGW)

Cloud WAN does **not** use the TGW model for multiple DXGWs. On a TGW, the Direct Connect side compares the VIF attributes across the DXGWs and the TGW installs the result (ECMP or one attachment; see tgw-routing-patterns.md). On Cloud WAN:
- **Inside each DXGW**, the DXGW still selects its own VIF per prefix (VIF LP communities `7224:7300/7200/7100`, local-region default, AS_PATH, MED) and reflects that result.
- **Between DXGWs**, the **CNE itself** learns the route from each DXGW attachment and runs its own Cloud WAN route evaluation over them.
- **To steer between DXGWs, use Cloud WAN routing policies** (policy version 2025.11 or later): an **inbound** policy on each DXGW attachment sets local preference, AS_PATH or MED for matching prefixes, giving a deterministic primary/secondary/tertiary order.
- **Without a routing policy**, identical routes from multiple DXGWs give **non-deterministic path selection**; prefixes that match no rule fall into the same case, so keep the prefix lists current.
- BGP communities cannot be matched or set on Direct Connect attachments in Cloud WAN, so the routing policy matches on prefixes or prefix lists.
- Verify with the **Route information base** tab (routes before policies) against the **Routes** tab (installed route).

**Published example** ([Part 2, Scenario 2](https://aws.amazon.com/blogs/networking-and-content-delivery/aws-cloud-wan-routing-policy-real-world-global-network-scenarios-part-2/)): three data centers each connect through their own DXGW (ASNs 65010, 65011, 65012) and all advertise all three DC prefixes. Inbound routing policies on each DXGW attachment set local preference 300/200/100 per prefix list, so each prefix prefers the DXGW of the DC that owns it, with deterministic failover. Inside each DXGW, VIF communities `7224:7300` (primary) and `7224:7100` (secondary) choose the VIF, or `7224:7200` on both VIFs gives active-active ECMP.

**Important distinction — path selection behavior by service:**
- **DXGW:** ECMPs across equal remote paths (load-balanced failover)
- **TGW with multiple DXGW attachments (TGW-specific):** **[Field knowledge, SME-confirmed]** the BGP attributes are set at the VIF level on the on-prem advertisements. Direct Connect compares those VIF advertisements across the DXGWs using all BGP attributes (longest prefix, then local preference, AS_PATH, MED); the attributes do not pass to the TGW and the TGW does not compare them. If they all match, every qualifying DXGW attachment is installed in the TGW as an ECMP next hop; if one wins on an attribute, only that attachment is installed. **[Field knowledge]** If no attribute separates them but they still do not qualify (for example, different ASNs), one attachment is picked deterministically using a hash of the prefix metadata; not customer-controllable. Documented: for routes with the same CIDR, attachment type and BGP attributes, AWS "can't guarantee a consistent route prioritization order" ([TGW route evaluation](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)). TGW ECMP across DXGWs also needs matching DXGW Amazon-side ASNs **[Field knowledge, SME-confirmed]**.
- **Cloud WAN CNE with multiple DXGW attachments:** the CNE learns the route from each DXGW attachment and runs its own route evaluation; steer with inbound routing policies (local preference, AS_PATH, MED) on the DXGW attachments. Without a policy, identical routes from multiple DXGWs give non-deterministic path selection (see "Multiple DXGWs on Cloud WAN" above).
- **Cloud WAN CNE (equal routes from other sources):** Deterministic — "deterministically random" at Step 2.5.4 for equal remote CNE paths, chosen per segment / network function group. Consistent but not customer-controllable.

### Common Pitfall: AS-Path Prepending Does Not Override Local-Region LP at the DXGW

**The mistaken assumption:** "If I prepend a DX VIF's prefix enough, I can steer that region's traffic away from (or toward) it across regions."

**Why it's wrong:** DX egress selection happens at the **DXGW lookup** (see "Two Route Lookups" below), where **local-region Local Preference is evaluated before AS-path**. For a region that has a **local** DX advertisement, the DXGW picks that local path on LP — AS-path (and therefore any prepend) is never consulted. So prepending a local VIF does **not** move that region's traffic off its local DX.

**Where prepending actually acts:** only as the **tiebreaker among remote advertisements** for regions that have **no local** advertisement for the prefix. There, all candidates are remote (LP equal), so the DXGW falls through to AS-path length and the shortest remote advertisement wins. Prepending shapes *which remote DX* those regions use — nothing more.

**Consequence:** Over-prepending a local VIF is not a cross-region steering lever; it only changes that location's standing in the remote-tiebreak for *other* regions. To steer cross-region DX preference, use LP communities (which are evaluated before AS-path at the DXGW), not prepending. Confirm the installed per-region result with `get-network-routes` and the advertised paths with `list-virtual-interface-routes`.

### Foundational Principle: Every Route Table Does Its Own Independent Lookup

The single most important mental model for reasoning about AWS routing: **every construct that has its own route table performs its own independent route lookup**. Each route table makes its decision using only the routes present in *that* table. There is no single end-to-end path calculation; the path is the concatenation of per-table decisions.

Route-table-owning constructs each do this independently, including:
- **VPC route tables** (subnet → destination: local, IGW, NAT, ENI, TGW/VGW/CWAN attachment, peering, endpoint)
- **Transit Gateway route tables** (per-attachment association/propagation; ECMP or a hash-selected single attachment when multiple DXGW attachments carry the same prefix — see tgw-routing-patterns.md)
- **DX Gateway** (a set of BGP route reflectors outside the data path: it does its own BGP selection across VIFs and reflects the result per prefix to each attached CNE/TGW/VGW)
- **Cloud WAN Core Network Edge (CNE) route tables** (the CNE evaluation order over propagated routes)
- **On-prem / customer routers** (their own BGP/IGP tables)

The routing "outcome" is what you get when you chain these together. To predict or debug a path, walk it table by table: at each table, ask "what does *this* route table select for this destination, given only the routes it has?" The output of one table's selection becomes an input (a propagated or reflected route) to the next.

**DXGW special case:** the DXGW's selection is a control-plane decision. It decides which VIF a CNE's or TGW's route points to; the packet then goes from the CNE/TGW straight to that VIF, without a second packet lookup at the DXGW.

**Common analysis error:** treating an end-to-end path as one decision, or assuming an attribute (like a DX BGP community or a local preference) that decided at one table still applies at the next. It does not automatically — each table applies only its own selection rules over its own routes. (Example: DX LP communities decide at the DXGW's selection but are not visible inside the Cloud WAN CNE table.)

### Applying the Principle: DXGW Lookup then CNE Lookup

For AWS → on-prem traffic in a DX + Cloud WAN design, two independent lookups decide the path. Both act on routes that on-prem advertised into AWS. The DXGW's result is the CNE's input.

**Lookup 1 — DXGW selection (control plane; decides which VIF each CNE's DXGW route points to).**
The DXGW performs its own selection for a prefix and **reflects one result per prefix to each CNE**. Its selection order is:
1. **Local-region Local Preference first** — if a DX VIF advertising the prefix is in the same associated region as the CNE, the DXGW prefers it **regardless of AS-path**. That local path is what the DXGW reflects to that region's CNE.
2. **If no local advertisement exists for that CNE**, every candidate is remote, so they share the **same (remote) LP** — LP is equal. The DXGW then falls through to **AS-path length**, and the **shortest AS-path wins** (if all attributes are equal, the result is ECMP across those VIFs).

**Lookup 2 — Cloud WAN CNE route lookup.**
Each CNE runs its own lookup over the routes **in its table** (the DXGW route from Lookup 1, plus routes propagated from other CNEs and other attachments). This is where the CNE evaluation order (longest prefix → static → system → VPC-propagated → AS-path/MED → source preference) applies. If the DXGW route wins, traffic goes straight to the VIF the DXGW selected.

### Worked Example (from the field diagram)

Only **FR5/Frankfurt (eu-central-1)** and **LD5/Slough** advertise `11.0.0.0/8`. In this example the LD5 connection is on a device associated with **eu-west-1 (Ireland)**; LD5 also has eu-west-2 (London) devices, so check the actual connection. Applying **Lookup 1 (DXGW)** per region:

| CNE region | Has local `/8` advertisement? | DXGW decision | Path reflected to the CNE |
|---|---|---|---|
| eu-central-1 (FR5) | Yes (FR5 local) | Local-region LP wins — AS-path not consulted | **FR5 (local DX)** |
| eu-west-1 (LD5) | Yes (LD5 local) | Local-region LP wins — AS-path not consulted | **LD5 (local DX)** |
| ap-southeast-1 | No | FR5 and LD5 **both remote → LP equal** → fall through to AS-path → **FR5 shortest wins** | **FR5** |
| us-east-1 | No | both remote → LP equal → AS-path → **FR5 shortest** | **FR5** |
| us-east-2 | No | both remote → LP equal → AS-path → **FR5 shortest** | **FR5** |

**Why the non-LD5 regions use FR5's advertisement:** they have no local `/8`, so at the DXGW both FR5 and LD5 are **remote** and carry the **same (remote) LP** — LP is equal. The DXGW therefore falls to the next attribute, **AS-path length**, where **FR5 is shorter than the (heavily prepended) LD5 advertisement**, so FR5 wins. This is a straightforward DXGW LP-then-AS-path decision — **not** a CNE-to-CNE backbone comparison.

**Role of the AS-path prepends:** the prepends matter at **Lookup 1 (DXGW)**, specifically as the **tiebreaker when LP is equal** (i.e., only for regions with no local advertisement). They set which remote advertisement (FR5 vs LD5) wins for those regions. They do **not** override the local-region LP for regions that *do* have a local advertisement — eu-central-1 and eu-west-1 pick their local DX on LP before AS-path is ever considered. So over-prepending LD5 does not stop eu-west-1 from choosing LD5 locally; it affects LD5's standing in the **AS-path tiebreak for the other regions**, where FR5's shorter path beats it.

**Rule of thumb:** Because local-region LP is evaluated before AS-path at the DXGW, a region with a local `/8` advertisement egresses locally regardless of prepends. Use AS-path prepending only to shape which **remote** advertisement wins for regions that have **no local** advertisement (the LP-equal tiebreak). Verify the installed per-region result with `get-network-routes` (Lookup 2's table) and the per-VIF advertised paths with `list-virtual-interface-routes` (Lookup 1's inputs).

### Common Pitfall: Confusing Prepend Count with Total AS-Path Length (Origination vs. Transit)

When comparing AS-path lengths (at the DXGW, or at a CNE in Step 2.4), the number that matters is the **total AS-path AWS receives on the VIF**, not the prepend count configured on a site. These are only the same when the advertising site is the **originator** of the prefix.

**The distinction:**
- **Originating site** — the site owns/aggregates the prefix (e.g., `aggregate-address 11.0.0.0/8`). The AS-path AWS sees is just that site's ASN, repeated by its prepend count. A `prepend 60208 2` on an originated route → AS-path `60208 60208 60208` (length 3).
- **Transiting site** — the site does NOT originate the prefix; it **learns it from another site over the on-prem WAN** and re-advertises it to its DX. The AS-path already contains the origin's ASN, so the transiting site's ASN and prepends stack **on top of** the origin ASN. A `prepend 60208 2` applied to a `/8` learned from origin AS 56608 → AS-path `60208 60208 60208 56608` (length **4**, not 3).

**Config signature to tell them apart:** A site that **matches-and-prepends** a prefix in a route-policy but has **no `aggregate-address`/origination** for it is almost certainly **transiting** a route learned from elsewhere. Do not assume it originates the prefix just because the prefix appears in its outbound policy.

**Why this matters for path selection:** AS-path selection compares total path length. If you model a transiting site's length as "prepend count + 1" (treating it as an originator) you will miscompute which copy wins — often flipping the predicted winner and the failover order. Example: three sites advertise a `/8` that **originates at only one** of them; the two that transit-and-prepend it are longer than a naive prepend-count model suggests, and can tie with the origin.

**How to get the ground truth:** Never infer AS-path length from prepend config alone when a prefix may be transited. Read the literal path AWS receives per VIF:
```
aws directconnect list-virtual-interface-routes --virtual-interface-id <vif-id>
```
This shows the exact AS-path (and communities) AWS accepted, settling origination-vs-transit and the true length used in AS-path comparison.

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

**Problem:** LP communities tagged on the VIFs of a single DXGW apply globally, so one DXGW gives one primary path for every region and cannot provide per-region preferences.

This is one of the only two reasons to use multiple DXGWs (the other is traffic isolation); otherwise use a single DXGW. See "When to Use Multiple DXGWs" in tgw-routing-patterns.md.

**Solution:** Create separate DXGWs per region group, each with their own VIFs:
- DXGW-A: Region-A DX locations (primary `7224:7300`, secondary `7224:7200`)
- DXGW-B: Region-B DX locations (`7224:7300`)

Both DXGWs reflect their selected path to all CNEs, and each CNE learns the route from both DXGW attachments and runs its own Cloud WAN route evaluation. The Direct Connect-side cross-DXGW comparison used with a TGW does not apply here (see "Multiple DXGWs on Cloud WAN" above).

**Primary lever — Cloud WAN routing policies** (policy version 2025.11 or later): apply an **inbound** routing policy to each DXGW attachment that sets **local preference** (or AS_PATH / MED) for the matching prefixes or prefix lists, so each CNE or region group prefers the intended DXGW with a deterministic failover order. Apply them per attachment, or per segment / CNE-to-CNE where the preference must differ by region. Without a policy, identical routes from the two DXGWs give non-deterministic path selection. See [Cloud WAN routing policies](https://docs.aws.amazon.com/network-manager/latest/cloudwan/cloudwan-routing-policies.html) and [Part 2, Scenario 2](https://aws.amazon.com/blogs/networking-and-content-delivery/aws-cloud-wan-routing-policy-real-world-global-network-scenarios-part-2/).

**Alternative — AS_PATH differentiation on the VIFs:** make the AS_PATH length on the VIF advertisements differ between the two DXGWs so the CNE prefers the shorter one at Step 2.4 (AS-path length). This works without routing policies but is coarser and harder to vary per region.

Use VIF LP communities within each DXGW for internal VIF failover (communities cannot be matched or set by Cloud WAN routing policies on Direct Connect attachments). Confirm the result on the **Routes** tab; the **Route information base** tab shows routes before policies are applied.

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
- All CNEs prefer Region-A as the internet exit (Step 2.4: shorter AS-path wins)
- If Region-A fails, Region-B's longer path takes over as backup

## Regional Firewall Inspection

- Cloud WAN segment policy / service insertion routes traffic through the **same-region firewall** before it reaches the CNE
- Traffic flow: VPC → local firewall (service insertion) → returns to local CNE → CNE route table → DX VIF selected by the DXGW
- With a local DX advertisement present, the DXGW reflects the local path to the local CNE (local-region LP, Lookup 1) — traffic stays at the local CNE for egress, preserving the local inspection chain
- If the region has no local DX advertisement (or a community forces a remote DX to win), the selected path points out of region, and traffic leaves the local region for egress — potentially bypassing local firewall inspection
- **Requirement:** Firewall VPCs must exist in every region with workloads

## Directional Control (Mapped to the Two Lookups)

Keep the two traffic directions straight — they are governed by different devices and different mechanisms.

| Traffic direction | Deciding lookup(s) | Controlled by | Mechanism |
|---|---|---|---|
| **AWS → On-prem** (egress from each CNE) | **Lookup 1 — DXGW selection**, then **Lookup 2 — CNE route lookup** | The BGP attributes on-prem advertises to AWS: DX LP communities (`7224:7300/7200/7100`) first, then AS-path as the LP-equal tiebreak; plus the competing routes in each CNE table | The DXGW selects the VIF per prefix per CNE (local-region LP first, then AS-path) and reflects it; each CNE then applies its own evaluation order |
| **On-prem → AWS** (ingress) | On-prem router lookup | Customer router policies | Local-pref, weight, MED on on-prem routers — independent of Cloud WAN |

Notes:
- DX LP communities set the LP the **DXGW** uses in Lookup 1 — they are the recommended lever for steering which VIF each DXGW selects. They are **not visible inside Cloud WAN** and do not act at Lookup 2.
- With **multiple DXGWs**, the choice between them is made at Lookup 2 by the CNE. Steer it with Cloud WAN inbound routing policies on the DXGW attachments (local preference, AS_PATH or MED), not with VIF communities.
- Communities do NOT affect the on-prem → AWS direction. If on-prem AS-path prepending was being used to influence selection, prefer LP communities at the DXGW (Lookup 1); over-prepending a local VIF does not achieve cross-region steering (see the AS-Path Prepending pitfall above). If prepending was also used for on-prem path selection, replace that with router-side local-pref/weight before removing prepends.

## Cleanup Recommendations

- **Prefer LP communities over prepending for DX egress steering.** Communities set the LP the DXGW uses in Lookup 1 and are evaluated before AS-path; they can steer cross-region preference, which prepending cannot (local-region LP overrides AS-path for any region with a local advertisement).
- **Do not use prepending on a local VIF as a cross-region lever.** At the DXGW, a region with a local advertisement selects it on LP regardless of prepends. Prepending only affects the AS-path tiebreak among **remote** advertisements for regions that have no local advertisement — so its only legitimate use here is choosing which remote DX those regions fall to.
- **Once communities are in place, remove leftover prepends** as a cleanup step, keeping only any within-region or remote-tiebreak prepends that serve a confirmed purpose.
- Always confirm the actual outcome with `get-network-routes` (installed per-CNE result) and `list-virtual-interface-routes` (the AS-path/communities the DXGW actually received) rather than reasoning from configured prepend counts alone.
