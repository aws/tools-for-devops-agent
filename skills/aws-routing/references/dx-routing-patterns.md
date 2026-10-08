---
inclusion: manual
---

# Direct Connect Routing Patterns & Considerations

This document captures key BGP routing mechanics, path selection behavior, VIF-specific considerations, and operational caveats for AWS Direct Connect architectures. Use this knowledge when advising on DX design (active/active, active/passive), BGP community behavior, BFD configuration, and public/private/transit VIF routing.

## Reference Documentation

- [Direct Connect Routing Policies and BGP Communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)
- [Direct Connect Path Selection (routing policies for private/transit VIFs)](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)
- [Direct Connect Virtual Interfaces](https://docs.aws.amazon.com/directconnect/latest/UserGuide/WorkingWithVirtualInterfaces.html)

## BGP & Routing

### BGP Route Visibility (ListVirtualInterfaceRoutes)

As of July 2026, DX supports **BGP route visibility** on virtual interfaces via the `ListVirtualInterfaceRoutes` API and the DX console:

- **Accepted routes:** Routes AWS received from your on-prem router
- **Advertised routes:** Routes AWS is sending to your on-prem router
- Each route shows: prefix, address family, AS-path, community values, installation timestamp
- Can filter by: prefix, AS-path, community, or address family
- Available on: private, transit, and public VIFs
- Available in: all AWS commercial regions

**Use for troubleshooting:**
- Verify route propagation between on-prem and AWS
- Validate BGP policy configurations (communities, AS-path prepending)
- Diagnose unexpected traffic patterns or asymmetric routing
- Confirm which routes DXGW is accepting vs. advertising
- Validate LP community tags are being received correctly

**Reference:** [AWS Direct Connect BGP Route Visibility announcement](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-direct-connect-bgp-visibility/)

### CloudWatch BGP Metrics for DX Virtual Interfaces

As of March 2026, DX publishes **3 BGP metrics** to CloudWatch for all VIF types (private, transit, public):

| Metric | What It Reports |
|---|---|
| `VirtualInterfaceBgpStatus` | BGP session state: 1 = up, 0 = down |
| `VirtualInterfaceBgpPrefixesAccepted` | Number of prefixes AWS accepted from on-prem |
| `VirtualInterfaceBgpPrefixesAdvertised` | Number of prefixes AWS advertises to on-prem |

**Key details:**
- Updated every 5 minutes (BGP flaps between intervals may not be captured)
- Published at no extra cost in the region where the DX location is associated
- Available via CloudWatch MCP server (`get_metric_data`) for programmatic access

**Use cases:**
- **BGP session monitoring:** Alarm on `VirtualInterfaceBgpStatus < 1` to detect session failures without API polling
- **Prefix limit protection:** Alarm when `PrefixesAccepted` approaches VIF quota to prevent session idle state
- **Silent route withdrawal detection:** BGP session stays UP but prefix count drops → indicates routes withdrawn without session going down
- **DR/failover validation:** Compare prefix counts between primary and standby VIFs — a standby with fewer prefixes indicates a broken failover path
- **Route change correlation:** Sudden drop in accepted/advertised prefixes correlates with traffic impact events

**Alarm examples:**
- `VirtualInterfaceBgpStatus` — Statistic: Minimum, Period: 5min, Threshold: Lower than 1
- `VirtualInterfaceBgpPrefixesAccepted` — Statistic: Maximum, Period: 5min, Threshold: Greater/Equal to (near quota limit)
- `VirtualInterfaceBgpPrefixesAccepted` — Statistic: Maximum, Period: 5min, Threshold: Lower/Equal to (below expected minimum)

**Reference:** [CloudWatch Metrics for DX VIF BGP Health and Prefix Count](https://aws.amazon.com/blogs/networking-and-content-delivery/introducing-cloudwatch-metrics-for-aws-direct-connect-virtual-interface-bgp-health-and-prefix-count/)

### General Routing Behavior

- When designing active/active or active/passive DX (within or across DX locations), apply the documented **Private/Transit VIF outbound path-selection order**: longest prefix match → local preference → AS_PATH length → MED → ECMP (equal AS_PATH length and BGP attributes). See [Direct Connect routing policies and BGP communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html).
- Consider recommendations for **migrating from DX + VGW/Private VIF to DX + TGW/Transit VIF** when customers are modernizing their architecture

### MED Support

- DX **supports Multi-Exit Discriminator (MED) on Private and Transit VIFs** — MED can influence the outbound (AWS → on-prem) routing path, but only as a **tiebreaker after prefix length, local preference, and AS_PATH are equal**. AWS explicitly **does not recommend relying on MED** given its lower priority in the evaluation order.
- For **Public VIFs**, the documented outbound routing policy uses **AS_PATH and longest prefix match** — MED is not listed among the supported public VIF path-selection attributes.
- **Outbound (AWS → on-prem) path selection order for Private/Transit VIF:** longest prefix match → local preference → AS_PATH length → MED → ECMP (equal AS_PATH length and BGP attributes).

**Reference:** [Direct Connect routing policies and BGP communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)

### BFD (Bidirectional Forwarding Detection)

**⚠️ Always verify the Associated Region for each DX location** — some DX locations can associate to different AWS regions than expected based on their physical geography. For example:
- Equinix LD5 (Slough, UK) → **eu-west-1** (Ireland)
- Telehouse (London Docklands, UK) → **eu-west-2** (London)
- Equinix MA3 (Manchester, UK) → **eu-west-2** (London)

The associated region determines which TGW/DXGW considers the DX "local" for LP preference and routing behavior. Verify a location's associated region with the `DescribeLocations` API/CLI (`aws directconnect describe-locations`) or the official AWS Direct Connect locations reference: https://aws.amazon.com/directconnect/locations/

### BFD (Bidirectional Forwarding Detection)

- **Asynchronous BFD is automatically enabled** on the AWS side for all DX virtual interfaces
- Customer must configure asynchronous BFD on their router (refer to vendor documentation)
- BFD provides fast link failure detection — ensures BGP neighbor relationship is torn down quickly for faster failover
- **Do NOT configure both BFD for BGP and BGP Graceful Restart simultaneously** — this results in sub-optimal routing performance (conflicting goals: BFD wants fast teardown, Graceful Restart wants to preserve routes during failure)

### ASN Support

| Context | Supported ASN Range |
|---|---|
| AWS side via DX-GW | Full 32-bit: 4,200,000,000 to 4,294,967,294 (private) |
| AWS side via VGW | 32-bit: 1 to 2,147,483,647 only |
| Customer side (Private/Public/Transit VIF) | 32-bit: 1 to 2,147,483,647 only |

- Customers can request a Private/Transit VIF ASN from the 4,200,000,000–4,294,967,294 range via a support case (non-standard, requires internal approval)

### SiteLink & BGP Communities

- SiteLink **maintains BGP community tags** — tags are passed through from one connected peer to another
- This means communities set on one DX location will be visible at another DX location connected via SiteLink

## VIF-Specific Considerations

### Public VIF

- **Reverse-path forwarding (RPF) strict mode is enforced** — validates that the source of traffic originated from the customer's advertised prefix (prevents address spoofing)
- **Do NOT use EC2 EIPs for Public VIF BGP peering** — can cause routing issues. Customers should use:
  - Public IPs they own, OR
  - IPs assigned by their provider/AWS support
- **EC2 BYOIP CIDRs are NOT in ip-ranges.json** (not part of Amazon address space), but they ARE advertised over DX Public VIF to customers
- **S3-only Public VIF**: BGP prefix lists are available (GitHub repository) for filtering S3 traffic over DX Public VIF — allows routing only S3 traffic through DX while sending other AWS traffic over internet to reduce costs

### Private / Transit VIF

- For Private/Transit VIFs, customers can use any IPv4 address (if not using AWS auto-generated IPs), but must ensure those IPs **do not conflict** with on-prem and/or VPC networks
- When attaching VPCs with **AWS-assigned IPv6** to a TGW, these are discontinuous by default and **cannot be aggregated** for Direct Connect — leads to DX prefix quota limitations
  - **Workarounds:** Use Amazon-provided contiguous IPv6 CIDR blocks, or EC2 BYOIP

### VPC-to-VPC Routing via DXGW (Regression)

- As of November 2021, **VPC-to-VPC routing** connected to the same DXGW via VGW/TGW which are also connected over Private/Transit VIF **is possible due to a regression**
- This was previously blocked — be aware of this change
- Workarounds exist to block this unintended traffic flow if isolation is required

### DX VIFs and VGW — CloudHub Behavior

- **VPN CloudHub is a Site-to-Site VPN feature**: multiple VPN connections terminating on the same VGW can exchange routes with each other, letting remote sites communicate through AWS. See [AWS VPN CloudHub](https://docs.aws.amazon.com/vpc/latest/userguide/vpn-connections.html).
- **DX can participate in a CloudHub with VPN**: when a DX private VIF and one or more VPN connections share the same VGW, prefixes learned from a VPN customer gateway are advertised to the DX customer gateway and vice versa — so a DX site and VPN site(s) on the same VGW can reach each other.
- **DX-to-DX does NOT hub through a VGW**: if two DX VIFs from different on-prem sites terminate on the same VGW (or DX Gateway), AWS does not re-advertise one site's on-prem prefixes to the other. AWS advertises only the VPC CIDR(s) toward each VIF, so the two on-prem sites cannot reach each other through AWS. Site-to-site transit requires the customer's own router (hairpin) or a design that isn't a single shared gateway.
- **DX Gateway (VGW association) advertises only VPC CIDRs to on-prem** — it does not provide CloudHub between gateway associations; associations on the same DXGW cannot send traffic to each other.
- **Floating VGW (VGW not attached to a VPC):**
  - *With VPN* — a floating VGW can still act as a VPN CloudHub: multiple VPN connections on it exchange routes, so remote sites reach each other through AWS with no VPC involved.
  - *With DXGW* — not a usable scenario. A DXGW advertises associated VPC CIDRs to on-prem; a floating VGW has no VPC, so there is nothing to advertise. DXGW-over-VGW is only meaningful when the VGW is attached to a VPC.

**Note:** This corrects an earlier claim that DX VIFs on a shared VGW form a DX-to-DX hub-and-spoke mesh. Route sharing between on-prem sites on a shared gateway is a VPN CloudHub behavior (VPN connections), not a DX-to-DX behavior. Validate specific flows in a lab before relying on them.

### When Can VIFs Talk to Each Other? (Site-to-Site via AWS)

**Governing principle:** AWS does not act as a transit hub between VIFs by default. Over a VGW or a single DXGW, AWS advertises only the **VPC CIDRs** toward each VIF, so two on-prem sites (each on its own VIF) do not learn each other's prefixes unless something explicitly enables it.

**Supported — VIFs (sites) CAN reach each other:**

| Scenario | How it works |
|---|---|
| VPN CloudHub on a VGW | Multiple VPN connections on the same VGW exchange routes; remote sites reach each other. See [AWS VPN CloudHub](https://docs.aws.amazon.com/vpc/latest/userguide/vpn-connections.html). |
| DX + VPN on the same VGW | A DX private VIF sharing a VGW with VPN connection(s) can talk to the VPN site(s) — DX ↔ VPN. |
| TGW + Allowed Prefix List | The DXGW→TGW attachment advertises whatever is in the Allowed Prefix List (no VPC-CIDR-only restriction), so remote-site prefixes can be advertised intentionally. Enables DX ↔ VPN CloudHub via TGW. |
| DX ↔ DX via two DXGWs into one TGW | Two DXGWs attached to the same TGW (CGW1–DXGW1–TGW–DXGW2–CGW2) allows DX site-to-site. |
| Customer-side hairpin | Always available: advertise a supernet/default from on-prem and let the customer router be the hub. AWS is not the transit point. |

**Not supported — sites CANNOT reach each other through AWS:**

| Scenario | Why |
|---|---|
| Two DX VIFs on the same VGW | AWS advertises only VPC CIDRs to each VIF; no site-to-site. |
| Two DX VIFs on the same single DXGW | Gateway associations on one DXGW cannot send traffic to each other. |
| Inter-site over a single DXGW with transit VIFs | Routes may install but the flow loops; not supported. Use two DXGWs. |
| Inter-site via two DXGWs with VGW associations | Only VPC CIDRs are advertised, so the sites never learn each other. |

**Summary:**
- **VGW / single DXGW** → advertises VPC CIDRs only → no VIF-to-VIF transit (except true VPN CloudHub, which is a VPN feature).
- **TGW** → Allowed Prefix List with no route validation → VIF-to-VIF transit can be built intentionally, using two DXGWs for DX-to-DX.

## DX vs Peering (Public VIF vs PNI)

### Key Differences

| Attribute | DX Public VIF | Public/Private Peering (PNI) |
|---|---|---|
| Official AWS service | Yes | No |
| SLA | Yes | No |
| AWS Support coverage | Yes | No (handled by Global Interconnect Strategy team) |
| Internal LOCAL_PREF | Higher | Lower |
| Path preference | **Preferred** (higher LP) | Lower priority |

### Important Guidance

- If the **same prefix** is received by AWS over both DX Public VIF and Peering (PNI, IXP, or Transit), **DX Public VIF is the preferred path** (higher internal LOCAL_PREF)
- Public Peering / PNI is NOT an official AWS service — no SLA, no support expectation from the technical field
- **Steer customers toward DX** when they need reliability and support coverage
- There is no expectation for the technical field to support Public Peering / PNI engagements

## Design Considerations for Active/Active & Active/Passive

### General Best Practice for DX Routing Selection

- **Always use LP communities (`7224:7300/7200/7100`) for expected egress routing** — High Preference BGP communities are the recommended mechanism for predictable DX egress.
- **AS-path prepending: within a region ONLY** — Use AS-path prepending to influence egress between DX connections belonging to the **same associated AWS region**. Do NOT use AS-path prepending to influence traffic across regions — DXGW's local-region LP makes cross-region prepending unreliable.
  - **When comparing AS-path lengths, distinguish an originating site from a transiting one** — a site that learns a prefix over the on-prem WAN and re-advertises it carries the origin ASN in its path, so its total length is prepend-count + origin ASN(s), not prepend-count alone. Confirm the real path with `list-virtual-interface-routes`. See "Confusing Prepend Count with Total AS-Path Length" in cloudwan-dx-routing-patterns.md.
- **BGP communities: within region OR across regions** — LP communities work for both intra-region path selection and cross-region preference (overriding DXGW's default local-region LP).

### Active/Active (within or across DX locations)

- Understand how AWS selects between multiple active paths using the Private/Transit VIF outbound path-selection order (longest prefix match → local preference → AS_PATH length → MED → ECMP). See [Direct Connect routing policies and BGP communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html).
- ECMP is available at the TGW level across multiple DX-GW attachments (same or different DX-GWs)
- LP communities (`7224:7300/7200/7100`) can influence preference but behavior varies between VGW/TGW/Cloud WAN — always test
- **DXGW ECMPs across equal remote paths** — when a local DX fails and multiple remote DX locations have matching attributes (same LP, same AS-path), DXGW will ECMP across them. This provides load-balanced failover rather than single-path selection.

**Path selection behavior by service (NOT at DXGW):**
- **DXGW:** ECMPs across equal paths — load-balanced failover
- **TGW:** Deterministic — selects oldest route for equal paths. Consistent but not customer-controllable.
- **Cloud WAN CNE:** Deterministic — "deterministically random" at Step 2.4.4 for equal remote CNE paths. Consistent but not customer-controllable.

### Active/Passive

- Use LP communities or AS-path prepending to create primary/secondary paths
- For Cloud WAN: communities override DXGW local-region preference (see cloudwan-dx-routing-patterns.md)
- For TGW: LP communities are NOT honored across multiple DX-GW attachments (see tgw-routing-patterns.md)
- BFD should be enabled for fast failure detection on the active path
