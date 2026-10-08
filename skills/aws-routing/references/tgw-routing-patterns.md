---
inclusion: manual
---

# Transit Gateway Routing Patterns & Considerations

This document captures key routing mechanics, ECMP behavior, failover characteristics, and operational considerations for Transit Gateway architectures. Use this knowledge when advising on TGW route evaluation, multi-attachment designs, inter-region peering, and DX/VPN integration.

## Reference Documentation

- [Transit Gateway Route Evaluation Order](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html#tgw-route-table-evaluation)
- [Transit Gateway VPN ECMP](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-share.html)
- [Direct Connect + Transit Gateway](https://docs.aws.amazon.com/directconnect/latest/UserGuide/direct-connect-transit-gateways.html)

## Route Evaluation & Priority

### Static VPN Has Higher Priority Than DX

- Static VPN routes have a **higher routing priority** at the TGW than Direct Connect routes
- Always refer to the TGW Route evaluation order when determining which attachment path will win for a given prefix
- This can cause unexpected behavior if a customer has both a static VPN and DX advertising the same prefix — the static VPN will be preferred

## ECMP Behavior

### Supported ECMP Scenarios

- **VPN attachments**: TGW supports ECMP across VPN attachments. A TGW-level toggle ("VPN ECMP support") must be enabled.
- **Multiple DX-GW attachments** (within the same DX-GW): TGW will ECMP across matching prefixes
- **Multiple different DX-GWs**: TGW will ECMP across matching prefixes received from different DX Gateways
- **Multiple TGW Connect attachments**: TGW will ECMP across matching prefixes

### NOT Supported

- **ECMP across different attachment types** — TGW does NOT ECMP between, for example, a DX-GW attachment and a VPN attachment for the same prefix. Instead, the Route evaluation order determines the winner.
- **Multipath AS-path relaxed** — ECMP for paths with different AS-paths is NOT supported. If matching prefixes are received with different AS-paths, only the **oldest route is installed** (not load-balanced).
- If prefixes match but ECMP conditions aren't met, the **oldest route** is installed.

## Direct Connect + TGW Considerations

### LP Communities Not Honored Across Multiple DX-GW Attachments

- Direct Connect Local Preference BGP communities (`7224:7300/7200/7100`) are **NOT honored** across multiple DX Gateway attachments on TGW
- This differs from Cloud WAN where communities influence DXGW path selection
- For TGW with multiple DX-GW attachments advertising the same prefix, ECMP or oldest-route logic applies — NOT community-based preference

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

### TGW-to-VPN 5,000 Route Advertisement Limit

- The limit of **5,000 routes advertised from TGW to VPN** (toward the customer gateway) is **not adjustable**
- The TGW route table itself supports **10,000 routes** — it can hold more than the VPN advertisement limit
- **Advertisement-selection order when the attachment's advertised-route limit is exceeded** (e.g., TGW→VPN at 5,000): the routes that get advertised are chosen by (1) **static takes precedence over propagated**, then (2) among routes of the **same type** (both static or both propagated), the **least-specific** is advertised first. This is what lets a static summary survive the cap while the propagated specifics it covers are the ones dropped.
  - **[Field knowledge]** This limit-hit advertisement-selection order (static-over-propagated, then least-specific-first) is field-proven behavior and is **not stated on the public AWS TGW route-evaluation page** (which documents most-specific-first forwarding and static-over-propagated for same-CIDR). Treat as operational guidance; validate in-account.

### Correct Summarization Approach

**Do NOT remove VPC propagation** — propagated routes are needed for the return path (VPN → individual VPCs via longest prefix match within the TGW data plane).

**How it works:**
1. **Keep VPC propagation enabled** — individual VPC routes (/16s, /24s) remain in the TGW route table for return path forwarding
2. **Add static summary routes** covering the VPC CIDR ranges (e.g., 10.0.0.0/14 covering 10.0-10.3.x.x)
3. **Advertisement-selection under the cap** favors the static summary — static beats propagated, and among same-type routes the least-specific (the summary) is advertised first
4. Once the advertised-route limit is reached, remaining propagated specifics are cut off — but the summary already covers them, so reachability is preserved
5. **Return traffic** from VPN to individual VPCs still works because TGW uses longest prefix match internally — the more-specific propagated /16 routes win over the /14 summary for data plane forwarding

**Key points:**
- TGW route table holds BOTH the static summary AND the propagated specifics (up to 10,000 total)
- The static summary consumes 1 route in the 5,000 VPN advertisement budget (instead of hundreds of individual VPC routes)
- VPC propagation is NOT removed — it provides the granular return path
- This pattern leverages the difference between the advertisement limit (5,000) and the route table capacity (10,000)
- **Static summary routes must point to a valid attachment** — if the attachment is deleted, the route becomes blackholed, and blackholed routes are NOT propagated/advertised. Point summaries to a persistent attachment:
  - A **shared-services or firewall VPC** (recommended — already exists, won't be deleted)
  - A **dedicated "dummy" VPC** — a minimal VPC created specifically to anchor static summary routes. Disable propagation on this VPC (no traffic originates from it), label it clearly as non-deletable, and tag it for operational protection. This ensures summary routes remain active even if workload VPCs are added/removed.

### Alternatives When Summarization Isn't Sufficient

- **TGW Connect (GRE+BGP):** Each Connect peer has its own 5,000-route advertisement quota. With 4 peers per attachment, scales horizontally.
- **Multiple VPN connections:** Segment route tables per VPN so each stays under 5,000 advertised. Adds on-prem complexity.
- **Cloud WAN:** Native outbound route summarization via routing policies.

## Failover & Convergence

### On-Prem → AWS Convergence

- Route table updates for **propagated routes from BGP peers** can take **up to 60 seconds** to take effect within TGW between attachment paths
- Customers needing faster failover should:
  - Route traffic over the **same/single attachment** (avoid cross-attachment failover dependency)
  - Consider **bypassing TGW** for high-priority workloads that cannot tolerate 60s convergence

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

- TGW Inter-Region Peering (across regions) is **not yet supported in all regions**
- **BGP dynamic route propagation across TGW peering is not yet supported** — routes must be statically configured on peered TGW route tables
- This limitation does NOT apply to Cloud WAN dynamic peering

### Intra-Region Peering

- TGW Intra-Region Peering (within a region) **is supported**

### Alternative to Multiple TGWs

- Instead of deploying multiple TGWs, customers can use **Route Tables within a single TGW** to segregate traffic between different domains/environments
- This simplifies management and avoids peering complexity

## Multi-Region Traffic & AZ Awareness

### Gray Failure Risk with Static TGW Peering

- Traffic between peered TGWs **does not have AZ awareness**
- When traffic arrives from a remote region over **static TGW peering**, it could first land in an AZ different from the destination AZ before being routed to its final destination
- During **gray failures** (partial AZ degradation): packet loss can be observed even though the destination AZ is not impacted — because traffic may transit the degraded AZ
- **This limitation only applies to static TGW Peerings**
- It will NOT exist once BGP dynamic route propagation across TGW peering becomes available
- It does NOT apply to **Cloud WAN dynamic peering** (which has AZ awareness)
