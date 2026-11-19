# MediaConnect Cost Levers

## Contents

1. Billing model
2. Lever: idle and standby flow cleanup
3. Lever: reserved outbound bandwidth
4. Lever: Flows to Router migration modeling
5. Lever: placement and transfer path
6. Existing reservation audit
7. Operator action mapping

## 1. Billing model

Billable resource types, each with different math:

**Transport stream flows** (`Source.Transport.Protocol` in `zixi-push`,
`zixi-pull`, `srt-caller`, `srt-listener`, `rist`, `rtp`, `rtp-fec`,
`udp`): per-hour running-flow fee that is FLAT regardless of
`Source.Transport.MaxBitrate` (us-east-1 illustration $0.16/hr; AWS bills
10, 30, and 50 Mbps flows identically) plus per-GB data transfer out
(in-region to AWS services ~$0.01/GB, inter-region ~$0.02/GB, internet
~$0.09/GB after a small monthly free allowance; all tiered, sum per
tier). ARQ/FEC protocols retransmit, and retransmissions are billable
bytes on per-GB outputs; report the overhead, never recommend dropping
error correction to save it.

**FlowSize** (`MEDIUM`, `LARGE`, `LARGE_4X`) does not change the TS
hourly rate. It gates capability: LARGE is required for NDI and raises
aggregate output limits; LARGE_4X serves uncompressed up to UHD 2160p60.

**CDI / ST 2110 JPEG XS flows**: per-hour flow fee scaled by max video
size (illustrations: 1080i $3.00/hr, 1080p $6.00/hr in listed regions)
plus a per-hour per-output fee (e.g. $0.13/hr per CDI output). No per-GB
internet path in the usual same-AZ pattern, but cross-AZ/cross-region
legs still bill transfer.

**NDI flows** (`ndi-speed-hq`, requires LARGE): per-hour flow fee
(illustration $1.50/hr); NDI outputs carry no VPC data transfer charge.

**Router inputs and outputs** (GA November 2025): independent resources
billed per active hour by `Tier`. There are exactly three tiers each:
inputs `INPUT_20`, `INPUT_50`, `INPUT_100`; outputs `OUTPUT_20`,
`OUTPUT_50`, `OUTPUT_100` (max Mbps). us-east-1 100 Mbps illustration:
input $0.14/hr, output $0.10/hr; internet egress add-on ~+$1.79 per
output-hour; cross-region output (`RoutingScope=GLOBAL`) carries its own
running and data-in add-ons. 20 and 50 Mbps tier prices are unverified;
take them from the snapshot. **Router I/O in `STANDBY` bills nothing;
only `ACTIVE` bills.**

**Standby is free**: a flow in STANDBY is not an active resource and
incurs no running cost even with sources, outputs, and entitlements fully
configured. This is the key fact behind the cleanup lever: money stops
when the flow stops, not when config is deleted.

Billing-relevant fields from `describe-flow`:

| Field | Why it matters |
|---|---|
| `Status` | ACTIVE bills hourly; STANDBY does not |
| `Source.Transport.Protocol` | selects the billing family (TS / uncompressed / NDI); this is the only source field that changes the hourly rate for TS |
| `Source.Transport.MaxBitrate` | no TS rate effect; a ceiling for coherence checks against MediaLive `InputSpecification` |
| `FlowSize` | capability gate, not a rate tier |
| `Outputs[]` count, protocols, destinations | per-output fees (CDI) and per-GB egress paths (TS) |
| `Entitlements[]` | granted entitlements shift the subscriber's transfer costs; DataTransferSubscriberFeePercent allocates internet egress between accounts |
| `AvailabilityZone` | cross-AZ legs to MediaLive bill transfer (see data-transfer-map.md) |

## 2. Lever: idle and standby flow cleanup

Detection: flows ACTIVE across the lookback window with `SourceBitRate`
absent or ~0 (dimension discovery first; cite only get-metric-data).
Distinguish deliberately warm standby paths from forgotten flows: that is
a customer question, not an inference.

Modeled saving: idle hours x flow hourly rate, plus any per-output CDI
fees. Recommendation: set the flow to STANDBY (stop it) rather than
delete; config is preserved and cost stops. Deletion is a second,
stronger step only when the customer confirms the flow is dead.

## 3. Lever: reserved outbound bandwidth

A 12-month commitment at a fixed bandwidth tier (offered at set levels,
e.g. 50/150/500/1500 Mbps) that discounts internet egress from flows.
AWS's worked 50 Mbps example: $1.161/hr reserved, equivalent to about
$0.052/GB vs $0.09/GB on-demand, a 42% saving; AWS cites 40-70%+ for
24x7 distribution.

Constraints that shape the recommendation:

- **One active reservation per account per region.** An existing active
  reservation makes the account ineligible for another; check first.
- Commitment bills for the tier regardless of actual egress; below ~40%
  projected utilization of the tier, on-demand is cheaper. Gate there.
- Applies to internet egress from flows, not to in-region AWS transfer.

Procedure: estimate sustained internet egress GB/month from
`SourceBitRate` x active hours per internet-destined output (or output
metrics where present); compare on-demand tiered cost vs the reserved
tier rate from `list-offerings`:

```
aws mediaconnect list-offerings --no-cli-pager --output json
aws mediaconnect describe-offering --offering-arn $ARN \
  --no-cli-pager --output json
aws mediaconnect list-reservations --no-cli-pager --output json
```

Offerings carry `ResourceSpecification.ResourceType=Mbps_Outbound_Bandwidth`,
`PriceUnits=HOURLY`, `DurationUnits=MONTHS`, `CurrencyCode=USD`.
Cross-check offering rates against Reserved terms in the pricing
snapshot.

## 4. Lever: Flows to Router migration modeling

Router changes the economics for fan-out and switching architectures:
flows bill whenever ACTIVE regardless of use, while router inputs and
outputs bill only while started and can be rewired dynamically.

Candidate pattern: a customer keeps many flows ACTIVE primarily to
preserve routing paths between sources and destinations (contribution
switching, disaster-recovery paths, occasional-use distribution). The
idle-but-active flow hours are the waste Router removes.

Model both architectures side by side over the same observed month:

```
Current:  sum over flows(active hours x flow rate) + transfer
Router:   sum over needed inputs(started hours x input tier rate)
        + sum over needed outputs(started hours x output tier rate)
        + internet/cross-region add-on hours where applicable
        + transfer that remains
```

Feasibility gate first: Router inputs and outputs support `RTP`, `RIST`,
`SRT_CALLER`, and `SRT_LISTENER` only. A flow on Zixi, UDP, CDI, JPEG XS,
NDI, or Fujitsu has no direct Router equivalent; do not model a migration
for it, state the protocol gap instead. Router can also feed a MediaLive
input directly (`RouterOutputType=MEDIALIVE_INPUT`, MediaLive input type
`MEDIACONNECT_ROUTER`), which removes a flow hop where a flow exists only
to bridge router and encoder.

Honesty requirements for this model:

- Take Router tier rates from the live pricing snapshot (they are inside
  the MediaConnect offer file). Only the lowest tier has been verified
  as an illustration; the full tier table must come from the snapshot.
- Router hourly pricing can exceed flow pricing for a 24x7 single-path
  workload (an always-on input+output pair may cost more per hour than
  one flow). The saving comes from paths that are idle much of the time
  or from consolidating N point-to-point flows into one routed fabric.
  If the model shows Router costing more, report that; the migration may
  still be justified operationally, but not as a cost saving.
- Migration effort, protocol support, and feature parity (entitlements,
  failover behavior, monitoring surfaces) are architecture questions to
  hand to the customer alongside the numbers. Mark confidence MEDIUM at
  best until the customer validates the target architecture.

## 5. Lever: placement and transfer path

- Flow-to-MediaLive same-AZ placement avoids cross-AZ transfer; statmux
  outputs must traverse MediaConnect, and a different-AZ flow adds
  transfer cost to every statmux hour.
- Inter-region distribution through second-region flows doubles flow
  hours and adds ~$0.02/GB; check whether the second region is still
  needed.
- Entitlement fee allocation (`DataTransferSubscriberFeePercent`) shifts
  who pays internet egress; verify the split matches the commercial
  intent before attributing cost.
- Two sources on one flow (`SourceFailoverConfig.FailoverMode` FAILOVER
  or MERGE) do not double the flow hourly rate; two separate flows do.
  Flag pairs of flows carrying primary and backup of the same feed to
  the same destination.

## 6. Existing reservation audit

`list-reservations` with status ACTIVE: compare the committed tier against
observed egress. Under-utilized committed bandwidth is spend without
benefit; over-utilized means overflow bills at on-demand rates (correct
behavior, but worth showing). Also surface expiration dates: an expiring
reservation on a continuing 24x7 workload is a renewal recommendation.

## 7. Operator action mapping

| Recommendation | Operator action (NOT EXECUTED by this skill) |
|---|---|
| Stop idle flow | `mediaconnect:StopFlow` (to STANDBY) |
| Delete dead flow | `mediaconnect:DeleteFlow` (after customer confirms) |
| Reserve outbound bandwidth | `mediaconnect:PurchaseOffering` with offering ARN, reservation name, start |
| Router migration | net-new architecture work: create router, inputs, outputs; start/stop I/O on demand; decommission replaced flows |
| Remove unused outputs | `mediaconnect:RemoveFlowOutput` |
