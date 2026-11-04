---
inclusion: manual
---

# Transit Gateway Routing Patterns & Considerations

This document captures key routing mechanics, ECMP behavior, failover characteristics, and operational considerations for Transit Gateway architectures. Use this knowledge when advising on TGW route evaluation, multi-attachment designs, inter-region peering, and DX/VPN integration.

## Reference Documentation

- [How transit gateways work (route evaluation order)](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)
- [Transit Gateway quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html)
- [Site-to-Site VPN quotas](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-limits.html)
- [Transit gateway peering attachments](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-peering.html)
- [Transit Gateway FAQs](https://aws.amazon.com/transit-gateway/faqs/)
- [Direct Connect gateways](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-gateways-intro.html)
- [Direct Connect routing policies and BGP communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)
- [Transit Gateway VPN ECMP](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-share.html)
- [Direct Connect + Transit Gateway](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-transit-gateways.html)

## Route Evaluation & Priority

### Static VPN Has Higher Priority Than DX

- Static VPN routes have a **higher routing priority** at the TGW than Direct Connect routes
- Always refer to the TGW Route evaluation order when determining which attachment path will win for a given prefix
- This can cause unexpected behavior if a customer has both a static VPN and DX advertising the same prefix — the static VPN will be preferred

### Path Selection Wording: ECMP Is an Outcome, Not a Step

- **Longest prefix match comes first.** It is a route lookup, not a BGP attribute.
- For routes with the same prefix, the BGP attributes are compared in order and **selection stops at the first attribute that differs**. For routes of the same attachment type at the TGW, the documented tiebreakers are shorter AS_PATH, then lower MED, then eBGP over iBGP ([route evaluation order](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)).
- If every compared attribute is equal and the ECMP conditions below are met, the **result** is ECMP. ECMP is never an attribute or a step in the order.
- **Routes from DXGW attachments are a special case:** **[Field knowledge, SME-confirmed]** the BGP attributes (LP communities, AS_PATH prepends, MED) are set at the **VIF level**, on the advertisements the on-prem router sends over each VIF, and are evaluated by the DXGW / Direct Connect side. They do not pass to the TGW, and the TGW does not compare them. Direct Connect compares the VIF advertisements across the DXGWs and the TGW installs the result (see "ECMP Across Multiple DXGW Attachments" below).

## ECMP Behavior

### How the TGW Sees a Direct Connect Gateway (Two-Lookup Model)

Every construct that owns a route table does its own route lookup. The DXGW is not a forwarding hop: AWS describes it as "a distributed set of BGP route reflectors" that "operates outside the data traffic path" ([Direct Connect gateways](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-gateways-intro.html)).

- **Lookup 1, at the DXGW (control plane):** the DXGW receives on-prem prefixes over its transit VIFs, evaluates the BGP attributes on each VIF's advertisements (set by the on-prem router per VIF) using the DX rules (longest prefix match, then local preference → AS_PATH length → MED), and reflects the result to the TGW. If the attributes are equal across VIFs, the result of this selection is ECMP across those VIFs.
- **Lookup 2, at the TGW route table:** for on-prem prefixes the TGW sees the DXGW attachment as (usually) a single next hop. The TGW route table shows **one entry per prefix per DXGW attachment** (when two DXGW attachments qualify for ECMP, both appear as next hops for the prefix; see below).
- **Data path:** traffic forwarded by the TGW goes straight to the VIF(s) the DXGW selected. Packets do not go through a second lookup at the DXGW.

Consequences:
- One TGW route-table entry per DXGW attachment does **not** mean one active VIF. VIF load sharing happens inside the DXGW's own selection. The TGW docs state that "A single Direct Connect gateway supports ECMP across multiple transit virtual interfaces," and AWS recommends using a single Direct Connect gateway rather than multiple gateways to take advantage of ECMP ([route evaluation order](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)).
- You do not need multiple DXGWs to get multiple active DX paths. Use **one DXGW with multiple transit VIFs** for ECMP.

### Supported ECMP Scenarios

- **VPN attachments**: TGW supports ECMP across VPN attachments when "VPN ECMP support" is enabled on the TGW. To use ECMP the VPN connection must use **dynamic (BGP) routing**; ECMP is not supported on static VPN connections ([VPN quotas](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-limits.html), [TGW quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html)).
- **Multiple transit VIFs on one DXGW (recommended)**: ECMP is the result of the DXGW's own selection when the BGP attributes on the VIF advertisements are equal. The TGW still shows one entry for that DXGW attachment.
- **Multiple DXGW attachments**: see the next section.
- **Multiple TGW Connect attachments**: TGW will ECMP across matching prefixes

### ECMP Across Multiple DXGW Attachments

- **Documented condition:** the prefix, prefix length and AS_PATH must be **exactly the same**. BGP Multipath AS-Path Relax is not supported, so there is no ECMP across different ASNs ([route evaluation order](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)).
- **[Field knowledge, lab-validated]** The routes also need **equal MED** and AS_PATHs that contain **exactly the same ASNs** (equal length alone is not enough).
- **[Field knowledge, SME-confirmed]** The DXGWs' **Amazon-side ASNs must match** (see "DXGW Amazon-Side ASNs Must Match for ECMP" below).
- **TGW-specific:** this Direct Connect-side cross-DXGW decision applies to a TGW. Cloud WAN works differently: the CNE learns the route from each DXGW attachment and runs its own route evaluation, steered by Cloud WAN routing policies (see "Multiple DXGWs on Cloud WAN" in cloudwan-dx-routing-patterns.md).
- **[Field knowledge, SME-confirmed] Where the decision is made:** the ECMP decision is made on the **Direct Connect side**, not by the TGW comparing attributes. The BGP attributes are VIF-level (set on the on-prem router's advertisements over each VIF) and do not pass to the TGW. Direct Connect compares the VIF BGP advertisements across the DXGWs using **all** the BGP attributes, in this order:
  1. Longest prefix match (a route lookup, not a BGP attribute)
  2. Local preference — LP communities (`7224:7300/7200/7100`) and the local-Region default
  3. AS_PATH length
  4. MED

  Selection stops at the first attribute that differs.
  - If all of them match, Direct Connect sends all of those DXGW attachments to the TGW and the TGW installs them as **ECMP next hops**. The TGW route table lists **every** qualifying DXGW attachment for the prefix, the same way it lists multiple VPN connections for VPN ECMP.
  - If they do not match, only a **single** DXGW attachment (the winner) is installed for the prefix.
- **In-account check:** `aws ec2 search-transit-gateway-routes` for the prefix. **Two (or more) DXGW attachments listed = ECMP. One attachment listed = a single path.**

### NOT Supported

- **ECMP across different attachment types** — TGW does NOT ECMP between, for example, a DX-GW attachment and a VPN attachment for the same prefix. Instead, the Route evaluation order determines the winner.
- **Multipath AS-Path Relax** — ECMP for paths with different AS_PATHs (including different ASNs) is NOT supported.

### When Routes From Multiple DXGW Attachments Do Not Qualify for ECMP

- If one route wins on an attribute (local preference, AS_PATH length, MED), only that DXGW attachment is installed.
- **[Field knowledge]** If no attribute separates them but they still do not qualify for ECMP (for example, equal AS_PATH length but different ASNs), one attachment is picked deterministically using a hash of the prefix metadata, and only that attachment is installed in the TGW route table. The choice is consistent but not customer-controllable.
- Documented: for routes with the same CIDR, attachment type and BGP attributes, AWS "can't guarantee a consistent route prioritization order" ([route evaluation order](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)). Do not design around which attachment wins an exact tie.

### DXGW Amazon-Side ASNs Must Match for ECMP

**[Field knowledge, SME-confirmed]** For TGW ECMP across multiple DXGW attachments, the DXGWs' **Amazon-side ASNs must match**. The AS_PATH compared across DXGWs must be exactly the same, and AS-Path Relax is not supported, so DXGWs with different Amazon-side ASNs do not qualify for ECMP; a single attachment is installed instead. Verify in-account with the route-table check:
- `aws ec2 search-transit-gateway-routes` — two DXGW attachments listed as next hops for the prefix = ECMP; one attachment = single path
- `aws directconnect list-virtual-interface-routes` — the AS_PATH and communities each VIF received
- `aws directconnect describe-direct-connect-gateways` — the `amazonSideAsn` of each DXGW

### Recommendation

- **Use ONE DXGW, with multiple transit VIFs for ECMP.** This is the documented recommendation.
- Add more DXGWs **only** for the two reasons in "When to Use Multiple DXGWs" below, never to get ECMP or redundancy.

## Direct Connect + TGW Considerations

### When to Use Multiple DXGWs

**In general there is no reason to have multiple DXGWs; use one.** AWS recommends a single Direct Connect gateway to take advantage of ECMP ([route evaluation order](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)), and states that high availability is inherently built into the DXGW design, "eliminating the need for multiple Direct Connect gateways" ([Direct Connect gateways](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-gateways-intro.html)).

**[Field knowledge, SME-confirmed]** The only reasons to use multiple DXGWs are:

1. **Traffic isolation**, either between on-prem networks/sites or between attachments. Examples:
   - **Attachment isolation (on-prem firewall hairpin):** separate allowed-prefix lists and separate TGW route-table associations per DXGW, so traffic between VPCs is sent through an on-prem firewall and back ([re:Post: route VPC traffic through an on-prem firewall over a transit VIF](https://repost.aws/knowledge-center/route-vpc-traffic-with-dc-transit-vif)).
   - **VPC isolation:** the DXGW docs list provisioning a separate DXGW per VPC as a mitigation to block VPC-to-VPC communication through a shared DXGW ([Direct Connect gateways](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-gateways-intro.html); see "VPC-to-VPC Traffic via a DXGW" in dx-routing-patterns.md).
2. **Architectures that need multiple primary paths**, for example Asia needs a different primary DX location than North America. LP communities on the VIFs of a single DXGW apply globally, so one DXGW gives one primary path for everyone. Per-region primaries need a DXGW per region group. See "Pattern 2: Per-Region DX Preference (Split DXGW)" in cloudwan-dx-routing-patterns.md.

ECMP and redundancy are not reasons for multiple DXGWs. The DX site-to-site transit design (CGW1–DXGW1–TGW–DXGW2–CGW2) in dx-routing-patterns.md is a capability statement, not a recommended reason to add a DXGW.

If two DXGWs on a TGW carry the same prefix, **make the outcome deterministic** instead of relying on an exact tie. (On Cloud WAN, use routing policies on the DXGW attachments instead; see cloudwan-dx-routing-patterns.md.) All of these work on a TGW because the BGP attributes are set on the VIF advertisements, Direct Connect compares those VIF advertisements across the DXGWs, and the TGW installs the winning DXGW attachment:
- **LP communities (preferred)** — tag `7224:7300/7200/7100` on the advertisements sent over the preferred DXGW's VIFs so that path has the higher local preference. **[Field knowledge, SME-confirmed]**
- **Longest prefix match** — advertise a more-specific prefix over the preferred DXGW
- **AS_PATH prepending** — the shorter AS_PATH wins when local preference is equal
- **MED** — lower MED wins when local preference and AS_PATH are equal
- **Separate TGW route tables** — associate different attachments with different route tables so each table has only one candidate
- Do **not** rely on an exact tie

### LP Communities Across Multiple DXGW Attachments

- **[Field knowledge, SME-confirmed]** LP communities **are honored** across multiple DXGW attachments on a TGW. The communities are tagged at the VIF level, on the on-prem router's advertisements. Direct Connect's cross-DXGW comparison of those VIF advertisements uses all the BGP attributes, and local preference (LP communities and the local-Region default) is compared before AS_PATH and MED. The TGW does not compare the attributes; it installs the result.
- **Local-Region default across DXGWs [Field knowledge, SME-confirmed]:** with **no** LP community tagged and equal AS_PATH and MED, if one DXGW's VIF is at a DX location whose associated Region matches the TGW's Region and the other DXGW's VIF is at a location associated with a remote Region, the **local one wins on local preference** (AWS prefers local over remote Regions); they do not ECMP. Check each connection's associated Region on the [Direct Connect locations page](https://aws.amazon.com/directconnect/locations/) and the [Associated Region](https://docs.aws.amazon.com/directconnect/latest/UserGuide/remote_regions.html#associated-region) table; some locations serve more than one Region depending on port speed, so confirm the connection itself with `aws directconnect describe-connections`.
- Inside each DXGW, the same communities set local preference for the DXGW's own VIF selection, as documented ([DX routing policies](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)).
- LP communities are the preferred lever for steering between DXGWs, alongside more-specific prefixes, AS_PATH prepending and MED.
- Verify in-account: `search-transit-gateway-routes` (which DXGW attachment(s) the TGW installed per prefix) and `list-virtual-interface-routes` (communities each VIF received).

### IPv6 Addressing Limitation

- When attaching VPCs with **AWS-assigned IPv6** addresses to a TGW, these IPv6 CIDRs are discontinuous by default and **cannot be aggregated** for use with Direct Connect
- This leads to DX prefix quota limitations
- **Workarounds:**
  - Use Amazon-provided **contiguous** IPv6 CIDR blocks
  - Use **EC2 BYOIP** (Bring Your Own IP) for aggregatable address space

### Allowed Prefixes Update Behavior (AWS → On-Prem)

- Updates (Add and Remove) to the "Allowed prefixes" in the TGW ↔ DX-GW association are **executed at the same time** on the AWS side
- However, from an **on-premises perspective**, it appears as prefixes added first, then removed later
- This is because on-prem learns the new route once added to the first device, and only loses the old route once withdrawn from all devices
- Transition window: typically **1 to 6 minutes**

## Route Advertisement Limits & Summarization

### Relevant Quotas

| Quota | Value | Adjustable | Source |
|---|---|---|---|
| Routes advertised from a Site-to-Site VPN connection on a transit gateway to a customer gateway device | 5,000 | **No** | [VPN quotas](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-limits.html) |
| Dynamic routes advertised from a customer gateway device to a Site-to-Site VPN connection on a transit gateway (inbound) | 1,000 | **No** | [VPN quotas](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-limits.html) |
| Total combined routes (dynamic and static) across all route tables for a single transit gateway | 10,000 | Contact your SA or TAM | [TGW quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html) |
| Routes advertised from a Connect peer on a transit gateway to a virtual router appliance | 5,000 | No | [TGW quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html) |

Notes:
- The routes a VPN attachment advertises come from the **TGW route table associated with that VPN attachment**.
- The 10,000 figure is **TGW-wide** (all route tables combined), **not per route table**.
- **Escalation path:** hard (non-adjustable) limits go to the service team after SME review. Quotas marked "Contact your SA or TAM" go through the account team.

### Advertisement Selection When the 5,000 VPN Cap Is Hit

- When the routes in the associated route table exceed the advertised-route cap, the routes that get advertised are chosen by (1) **static before propagated**, then (2) among routes of the **same type**, the **least-specific first**. This lets a static summary survive the cap while the propagated specifics it covers are the ones dropped.
- **[Field knowledge, SME-confirmed]** This selection order is not stated on the public TGW route-evaluation page (which documents most-specific-first forwarding and static-over-propagated for the same CIDR). Validate in-account.

### Correct Summarization Approach

**Do NOT remove VPC propagation** — propagated routes are needed for the return path (VPN → individual VPCs via longest prefix match within the TGW data plane).

**How it works:**
1. **Keep VPC propagation enabled** — individual VPC routes (/16s, /24s) remain in the TGW route table for return path forwarding
2. **Add static summary routes** covering the VPC CIDR ranges (e.g., 10.0.0.0/14 covering 10.0-10.3.x.x)
3. **Advertisement-selection under the cap** favors the static summary — static before propagated, and among same-type routes the least-specific (the summary) is advertised first
4. Once the advertised-route limit is reached, remaining propagated specifics are cut off — but the summary already covers them, so reachability is preserved
5. **Return traffic** from VPN to individual VPCs still works because TGW uses longest prefix match internally — the more-specific propagated /16 routes win over the /14 summary for data plane forwarding

**Key points:**
- The TGW route table holds BOTH the static summary AND the propagated specifics. All route tables on the TGW together count against the TGW-wide quota of 10,000 total combined routes.
- The static summary consumes 1 route in the 5,000 VPN advertisement budget (instead of hundreds of individual VPC routes)
- VPC propagation is NOT removed — it provides the granular return path
- This pattern works because the TGW can hold more routes (10,000 TGW-wide) than a VPN attachment can advertise (5,000)
- **Static summary routes must point to a valid attachment** — if the attachment is deleted, the route becomes blackholed, and blackholed routes are NOT propagated/advertised. Point summaries to a persistent attachment:
  - A **shared-services or firewall VPC** (recommended — already exists, won't be deleted)
  - A **dedicated "dummy" VPC** — a minimal VPC created specifically to anchor static summary routes. Disable propagation on this VPC (no traffic originates from it), label it clearly as non-deletable, and tag it for operational protection. This ensures summary routes remain active even if workload VPCs are added/removed.

### Alternatives When Summarization Isn't Sufficient

- **TGW Connect (GRE+BGP):** Each Connect peer has its own 5,000-route advertisement quota (not adjustable). With 4 peers per attachment, scales horizontally.
- **Multiple VPN connections:** Segment route tables per VPN so each stays under 5,000 advertised. Adds on-prem complexity.
- **Cloud WAN:** Native outbound route summarization via routing policies.

## Failover & Convergence

### Convergence Between Attachments

- **[Field knowledge, SME-confirmed]** TGW failover between attachments of **any type** — including between multiple DXGW attachments — can take **up to 60 seconds** to take effect.
- Customers needing faster failover should:
  - Route traffic over the **same/single attachment** (for DX, one DXGW with multiple transit VIFs, so VIF failover happens inside the DXGW's selection)
  - Consider **bypassing TGW** for high-priority workloads that cannot tolerate up to 60 seconds of convergence

### Failover Across Multiple DXGW Attachments

- **[Field knowledge]** When the selected DXGW attachment's route is withdrawn or deprioritized, the remaining routes are rehashed, one attachment is picked deterministically, and the TGW installs it.
- **[Field knowledge]** Direct Connect sees the BGP update immediately, but the TGW lags behind. In designs with a **separate stateful firewall per DXGW path**, that window can cause asymmetric routing and dropped flows.

### Failback Across Multiple DXGW Attachments

- **[Field knowledge]** When the route returns, Direct Connect compares the returning VIF advertisement against the existing ones and the TGW installs the result:
  - If all attributes match (and the ECMP conditions above are met), the result is ECMP and both attachments are installed.
  - If attributes differ, a single attachment stays installed. If the returning route has a **higher hash priority**, traffic switches back to it automatically.
- This switch-back is **not customer-controllable**. A flapping route can move traffic back and forth; use the deterministic levers above (LP communities, longest prefix, AS_PATH, MED, separate route tables) if that is a risk.

## TGW Peering

### Policy-Based Routing (PBR) — Transit Gateway Policy Tables

TGW now supports **Policy-Based Routing** via policy tables, enabling forwarding decisions based on packet attributes beyond just destination IP:

- Forwarding decisions can be based on: **source IP, destination IP, source port, destination port, and protocol**
- Configured through **policy tables** — ordered lists of rules that classify traffic and direct matching packets to a specified TGW route table
- A policy table is associated with a TGW attachment — it **replaces** the standard route table on that attachment (attachment can have either a policy table OR a route table, not both)
- Available in all regions at no additional charge beyond standard TGW fees

**Use cases:**
- Steer traffic selectively to security appliances or inspection services based on source, port, or protocol
- Route traffic from different applications or user populations over different network paths
- Isolate network traffic into separate routing domains for security segmentation

**Reference:** [Transit Gateway Policy Tables](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-policy-tables.html)

### Inter-Region Peering

- For Region support of inter-Region peering, check the [Transit Gateway FAQs](https://aws.amazon.com/transit-gateway/faqs/).
- **Static routes only:** routes over a TGW peering attachment must be added as static routes in the peered TGW route tables; BGP route propagation over TGW peering is not available ([TGW peering](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-peering.html)).
- **No announced timeline** for BGP route propagation over TGW peering. The peering doc advises using unique ASNs for each peered transit gateway "to take advantage of future route propagation capabilities" ([TGW peering](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-peering.html)).
- This limitation does NOT apply to Cloud WAN dynamic peering

### Intra-Region Peering

- TGW Intra-Region Peering (within a region) **is supported**

### Alternative to Multiple TGWs

- Instead of deploying multiple TGWs, customers can use **Route Tables within a single TGW** to segregate traffic between different domains/environments
- This simplifies management and avoids peering complexity

## Multi-Region Traffic & AZ Awareness

### Gray Failure Risk with Static TGW Peering

- **[Field knowledge, SME-confirmed]** Traffic between peered TGWs **does not have AZ awareness**
- When traffic arrives from a remote region over **static TGW peering**, it could first land in an AZ different from the destination AZ before being routed to its final destination
- During **gray failures** (partial AZ degradation): packet loss can be observed even though the destination AZ is not impacted — because traffic may transit the degraded AZ
- **This limitation only applies to static TGW Peerings**
- It is expected to go away once BGP route propagation over TGW peering is available. There is **no announced timeline** for that capability.
- **[Field knowledge, SME-confirmed]** It does NOT apply to **Cloud WAN dynamic peering** (which has AZ awareness)
