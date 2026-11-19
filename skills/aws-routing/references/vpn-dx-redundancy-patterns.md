---
inclusion: manual
---

# VPN and Direct Connect Redundancy Patterns

This document captures route preference behavior for VPN and DX redundancy designs with VGW. Use this knowledge when advising on active/active, active/passive, and failover architectures.

## Reference Documentation

- [AWS Site-to-Site VPN routing](https://docs.aws.amazon.com/vpn/latest/s2svpn/VPNRoutingTypes.html)
- [Direct Connect routing policies and BGP communities](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)
- [DX Resiliency Recommendations](https://aws.amazon.com/directconnect/resiliency-recommendation/)

## Assumptions

- Customer's network does not overlap with VPC CIDR
- Customer Gateway (CGW) device is configured to handle asymmetric routing
- Static VPN tunnels are Route-Based only (not Policy-Based)
- Customer advertises the same on-prem routes through all redundant connections (DX and VPN)

## Key Behavior: VGW Does NOT ECMP Across VPN Connections

A VGW does **not** use Equal-Cost Multi-Path routing (ECMP) across VPN tunnels or VPN connections. Return traffic from VPC to on-prem over VPN always takes a **single tunnel/path** — the "Preferred Tunnel." This is a fundamental constraint for VPN redundancy designs on a VGW.

Scope of this rule:
- It applies to **VPN on a VGW**. Two DX private VIFs on the same VGW can flow-hash (see the same-location rule below).
- **Transit Gateway and Cloud WAN do support VPN ECMP.** On a TGW, the VPN connection must use **dynamic (BGP) routing**; ECMP is not supported on static VPN connections ([TGW quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html), [VPN quotas](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-limits.html)). If a design needs VPN ECMP, use a TGW or Cloud WAN instead of a VGW.

---

## Part 1: Redundancy Only on AWS End

### VPN Connection — 2 Active Tunnels (Static)

- Customers can have static route-based tunnels in Active/Active mode
- **Customer → VPC:** Can load balance (equal route metrics) or prefer one tunnel (unequal metrics)
- **VPC → Customer:** Always takes a single tunnel (Preferred Tunnel) — VGW does not ECMP across VPN tunnels

- Customers can have BGP tunnels in Active/Active mode
- **Customer → VPC:** Load balance (equal LP) or prefer one (unequal LP)
- **VPC → Customer:** Always a single tunnel. Customer can influence by:
  - Advertising **lower AS-path** to VGW over the desired tunnel
  - Advertising **lower MED** to VGW over the desired tunnel

### DX Connection with Backup VPN

- DX is **always preferred over VPN** for return traffic to the same on-prem subnet
- Customer must ensure on-prem traffic is sent over DX when both are UP
- Attempting to prefer VPN over DX will cause asymmetric routing (VGW always returns via DX)

### 2 DX Connections (Same VGW)

- 2 private VIFs to the same VGW over 2 DX connections
- **Active/Active:** Equal LP + AS-path on CGW → return traffic is flow-hashed across both DX connections
- **Active/Passive:** Unequal LP + AS-path → customer-to-VPC uses the higher LP set on the customer router; VPC-to-customer uses the higher DX local-preference community, then the lower AS-path (see below)
- **DX local-preference communities are honored on private VIFs attached directly to a VGW** (documented for private and transit VIFs in [Private virtual interface and transit virtual interface routing policies](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html#private-routing-policies)): tagging `7224:7300` (high), `7224:7200` (medium) or `7224:7100` (low) on the advertisements sent over each VIF steers VPC-to-customer (AWS → on-prem) traffic. Local preference is evaluated **before AS_PATH**, then MED, so an AS-path prepend does not override a higher LP community. Use LP communities as the primary lever for AWS → on-prem preference across the two DX connections; AS-path and MED only break ties when local preference is equal.

**⚠️ [Field knowledge] ECMP only works when both DX connections terminate at the SAME DX location:**
- Same location (e.g., both at Equinix DC, Ashburn) → flow-hashed (ECMP)
- Different locations in same region (e.g., Equinix DC Ashburn + CoreSite NYC) → **single path only**

---

## Part 2: Redundancy on AWS and Customer Ends

### 2 VPN Connections from 2 CGW Devices (Recommended Design)

- 2 BGP VPN connections (4 active tunnels) to same VGW from different on-prem CGW devices
- **Recommended:** Use higher LP + lower AS-path on preferred VPN connection to avoid routing issues
- **Customer → VPC:** Traffic uses tunnel(s) with higher LP
- **VPC → Customer:** Single tunnel (Preferred Tunnel). Customer influences via lower AS-path on desired connection.

### DX + Backup VPN from 2 CGW Devices

- DX and VPN from different on-prem CGW devices
- When both UP: customer must ensure on-prem traffic goes over DX only
- **VPC → Customer:** Always sent over DX (DX always preferred over VPN by VGW)
- Design works correctly as active/passive (DX active, VPN passive)

### 2 DX Connections from 2 CGW Devices

- 2 DX connections from different on-prem CGW devices, 2 private VIFs to same VGW
- **Active/Active:** Equal LP + AS-path → flow-hashed return traffic
- **Active/Passive:** Unequal LP + AS-path → deterministic path preference
- **[Field knowledge, SME-confirmed]** As with a single CGW, DX local-preference communities (`7224:7300/7200/7100`) on the VIF advertisements steer AWS → on-prem traffic on a VGW and are evaluated before AS_PATH (then MED). Tag the preferred CGW's VIF with the higher community so return traffic matches the inbound path.

**Same ECMP caveat applies ([Field knowledge]):** Flow-hashing only works when both DX connections are at the same DX location. Different locations → single path selected.

---

## Part 3: Designs That Cause Routing Issues

### ❌ 2 Static VPN Connections from 2 CGW Devices

- VPC → Customer always traverses single tunnel (Preferred Tunnel)
- If customer sends traffic on CGW 2, return may come back on CGW 1 → **asymmetric routing**
- Only works if CGW devices have synchronization (ECMP) and accept asymmetric traffic

### ❌ 2 BGP VPN Connections with Same LP and AS-Path from 2 CGW Devices

- Same problem as static: VPC → Customer takes single tunnel, may not match inbound path
- **Fix:** Use unequal LP + AS-path to prefer one VPN connection over the other
- Or ensure CGW devices handle asymmetric routing

### ❌ DX + VPN — Attempting to Prefer VPN Over DX

- If customer tries to prefer VPN over DX, return traffic (VPC → on-prem) STILL goes over DX
- VGW always prefers DX over VPN regardless of BGP attributes
- **Result:** Asymmetric routing — customer sends via VPN, AWS returns via DX
- This is true whether using same CGW device or different CGW devices
- **Fix:** Advertise more-specific routes on VPN — longest prefix match wins before attachment-type preference, so a /24 via VPN will be preferred over a /16 via DX for matching traffic

### ❌ 2 VPN Connections from 2 CGW Devices with Different ASNs

- 2 BGP VPN connections from 2 data centers (different ASNs) advertising same networks
- VPC → Customer: single tunnel, may not match inbound path → asymmetric
- **Fix:** Use unequal AS-path values to prefer one VPN connection
- Cannot achieve ECMP across different ASNs

### ❌ DX + VPN from 2 CGW Devices with Different ASNs

- If customer sends traffic over VPN, return goes over DX (DX always wins)
- **Must avoid using same networks in multiple datacenters** to prevent routing issues
- Or accept that DX is always the return path regardless of inbound path

---

## Summary: Route Preference Rules at VGW

| Traffic Direction | Rule |
|---|---|
| VPC → On-prem (same prefix) | DX **always** preferred over VPN |
| VPC → On-prem (VPN only) | Single tunnel — lowest AS-path or MED; VGW does not ECMP across VPN (use TGW/Cloud WAN with dynamic VPN for VPN ECMP) |
| VPC → On-prem (2 DX, same location) | Flow-hashed (ECMP) — [Field knowledge] |
| VPC → On-prem (2 DX, different locations) | Single path — [Field knowledge] |
| VPC → On-prem (2 DX, unequal attributes) | Higher DX local-preference community (`7224:7300/7200/7100`) on the VIF advertisement wins, evaluated before AS_PATH, then MED — [Field knowledge, SME-confirmed] |
| On-prem → VPC (VPN) | Customer controls via LP (higher wins) |
| On-prem → VPC (DX) | Customer controls via LP (higher wins) |
| On-prem → VPC (DX + VPN both UP) | Customer must direct to DX |

## Key Takeaways for Customer Guidance

1. **VGW does not ECMP across VPN connections** — VPN return traffic always takes one tunnel. TGW and Cloud WAN do support VPN ECMP (dynamic routing required on TGW; not supported on static VPN)
2. **DX always wins over VPN** at the VGW — cannot prefer VPN for return traffic
3. **[Field knowledge] Same DX location required for flow-hashing** across two DX VIFs on one VGW — different locations in same region get single-path selection
4. **Use unequal LP + AS-path** for active/passive designs to avoid asymmetric routing
5. **Asymmetric routing is the primary failure mode** — designs with equal attributes from multiple CGW devices without synchronization will cause issues
6. **MED can influence VGW path selection** — documented at [VPN route priority](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-route-priority.html)
