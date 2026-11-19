# Direct Connect BGP Resilience — Reference

Deep material supporting the dx-vif-resilience skill. All claims grounded in
public AWS documentation.

## Why Layer-3 review matters

Layer-1/2 resiliency (redundant connections, diverse Direct Connect locations
and devices) determines whether a *path* survives a failure. Layer-3 prefix
coverage determines whether *traffic* survives: BGP forwards per-prefix, so a
destination is only failover-safe if every redundant VIF can route it. The two
reviews are independent — perfect physical diversity with asymmetric prefix
advertisement still blackholes traffic on failover.

## The two directions

| Direction (`routeDirection`) | Meaning | Failure mode if a prefix is missing |
|---|---|---|
| `accepted` | Routes received from the customer network over the VIF | AWS cannot reach that on-prem destination via this VIF after failover |
| `advertised` | Routes advertised to the customer network over the VIF | On-prem cannot reach that AWS destination via this VIF after failover |

`ListVirtualInterfaceRoutes` returns structured routes: `cidr`,
`addressFamily`, `asPath`, `communities`, `awsLogicalDeviceId`,
`routeDirection`. Paginated at up to 100 routes per call.

## Coverage classification

For each unique prefix P across the redundant set, against each peer VIF:

1. **Covered** — exact match, or a supernet of P exists on the peer.
   Longest-prefix-match delivers traffic for P via the supernet.
2. **Partial supernet** — the peer has no exact/supernet match but carries
   more-specifics inside P. The uncovered residual (P minus those
   more-specifics) is exactly the space at risk. Example:
   VIF-B `10.10.0.0/22`, VIF-A only `10.10.1.0/24` → residual
   `10.10.0.0/24` + `10.10.2.0/23`. Whether the residual matters depends on
   whether it hosts workloads — a /22 may be pure aggregation. Conditional
   severity; customer confirms.
3. **Gap** — no exact match, no supernet, no more-specific. Guaranteed
   blackhole for P if the carrying VIF fails.

Sub-prefixes of a supernet are never enumerated (a /8 contains 65k /24s);
risk is reported as computed residual CIDR ranges.

## Traffic engineering vs. gaps

Same prefix with differing attributes across VIFs is deliberate path
preference, not a gap:

- **AS-PATH prepending** — longer path = less preferred.
- **MED** — lower = preferred, tie-breaker after AS-PATH.
- **Local-preference communities** (`7224:7100` low / `7200` medium / `7300`
  high) — evaluated before AS-PATH for AWS→on-prem egress.

Outbound AWS evaluation order (private/transit VIF): longest prefix match →
local preference (communities) → AS-PATH length → MED → ECMP.

## DXGW allowed prefix lists

The allowed-prefix list is applied at the DXGW↔gateway association and affects
all VIFs on that DXGW equally — VIFs sharing a DXGW receive identical AWS
advertisements. VIFs on *different* DXGWs have independent lists and can
diverge; that is the highest-risk topology for the `advertised` direction.
The live `advertised` route output already reflects the post-filter reality —
no separate filter inspection is needed.

## Quotas that mimic misconfiguration

Always check the current [Direct Connect quotas page](https://docs.aws.amazon.com/directconnect/latest/UserGuide/limits.html)
— several of these are adjustable, so the account's effective quota may differ
from the defaults below.

- **200 prefixes (IPv4 + IPv6 combined)** advertised from AWS per DXGW↔TGW
  association (transit VIFs). At or near the quota, missing prefixes may be
  quota-clipped rather than misconfigured. Increases go through AWS (SA/TAM).
  Cloud WAN core-network attachments have a separate, much higher quota (5,000).
- **Routes accepted from on-prem** per BGP session on a private or transit VIF:
  default **100 each for IPv4 and IPv6**, self-service adjustable up to
  **1,000 each** via [prefix controls](https://docs.aws.amazon.com/directconnect/latest/UserGuide/prefix-controls.html)
  (console or `UpdateVirtualInterfaceAttributes`). Exceeding the configured
  allocation does NOT silently drop routes — the BGP session goes idle and
  reports status DOWN, so a quota breach presents as a session-health finding,
  not a coverage gap. Public VIFs: 1,000, not adjustable.

## Resiliency groups (declared intent)

Resiliency groups are a Direct Connect construct (flat-rate dedicated
connections) declaring intended redundancy at the **connection** level: AWS
pairs qualifying connections in a group as port-pairs. Discovery:
`ListResiliencyGroups` → `ListResiliencyGroupAssociations` (members referenced
by `connectionArn`) → map to VIFs via the connection ID in the ARN. Signals:

- Members whose `billingMode` shows `PortPairFlatRateTier*` are actively
  paired; `FlatRateTier*` inside a group means pairing requirements are not
  met (different speed/tier, same device) — a declared-but-broken redundancy
  finding.
- Groups exist only for flat-rate dedicated connections; absence of groups
  carries no signal for pay-as-you-go or hosted connections.

## BGP state caveats

- BGP `up` does not mean routes are correct — an established session with an
  empty table is itself a finding.
- Comparing a BGP-down VIF's stale/empty table against live peers produces
  false positives; exclude and report instead.
- All results are point-in-time snapshots; assess during stable traffic
  periods and re-run after changes.

## Out of scope for this skill

End-to-end physical path diversity (cross-connects, last-mile), BFD tuning,
on-prem router configuration, MACsec, and any mutating validation (BGP
failover tests are deliberately excluded — this skill is read-only).
