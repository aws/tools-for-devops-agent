---
name: aws-mediaconnect-investigate
description: >-
  Deep investigation of a single AWS Elemental MediaConnect flow. Use when a customer reports a
  MediaConnect problem or when evidence in a media pipeline investigation points at the
  contribution/transport layer: source disconnections, packet loss, zero or degraded source
  bitrate, entitlement issues between accounts, bridge/gateway faults, or router problems. Covers
  source connectivity, protocol-aware packet loss (ARQ/FEC recovery layering), TR 101 290
  transport stream health, per-output delivery, content quality monitoring, entitlement
  verification, bridge/gateway inspection, and router diagnostics. MediaConnect emits no
  CloudWatch Logs, so diagnosis works from CloudWatch metrics, describe-flow error messages, and
  EventBridge events. Not for MediaLive encoding faults or MediaPackage packaging faults;
  investigate those layers with aws-medialive-investigate or aws-mediapackage-investigate.
metadata:
  author: blends
  version: "1.0.0"
  summary: "Read-only investigation of a MediaConnect flow or Router path: source loss, packet recovery, TR 101 290 health, entitlements, bridges and gateways."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaConnect"
  aws-devops-agent-skills.technical-domains: "Operations, Observability"
---
# MediaConnect Deep Investigation

## Purpose

Perform a comprehensive investigation of a single MediaConnect flow when either:
1. Evidence from a broader media pipeline investigation points at the contribution/transport layer
2. The customer asks specifically about a MediaConnect flow issue

This skill goes deeper than a metric snapshot — it layers
protocol-aware analysis, transport stream health checks, per-output inspection,
and checks surfaces unique to MediaConnect (entitlements, bridges, routers,
EventBridge events).

## Critical constraint: NO native CloudWatch Logs

MediaConnect does NOT emit CloudWatch Logs. Unlike MediaLive (which has encoder
logs) or MediaPackage (which has access logs), MediaConnect has zero log output.

The only log-equivalent diagnostic surfaces are:

1. **`describe-flow` → `Messages.Errors[]`** — Active error messages on the flow
2. **EventBridge events** (source: `aws.mediaconnect`) — State change and health events
3. **CloudWatch metrics** — The primary diagnostic surface

Always report this asymmetry explicitly:
```
DATA GAP: MediaConnect has no native CloudWatch Logs. Diagnostic surfaces
are limited to: CloudWatch metrics, describe-flow Messages.Errors[], and
EventBridge events (if a rule forwarding "aws.mediaconnect" exists).
```

## Prerequisites

- Flow ARN known (from the customer, or by enumerating with `aws mediaconnect list-flows`)
- Time window established (the customer's impact window, or the anomaly window
  observed in CloudWatch)
- Evidence of a MediaConnect anomaly, OR direct customer request to investigate
  a specific flow

## Investigation checklist

Copy this list into your working notes and tick each step as you complete it. Run the
steps in order; skip a conditional step only when its condition says so, and say so.

- [ ] Step 1: Flow state and error messages
- [ ] Step 2: Source connectivity analysis
- [ ] Step 3: Packet loss analysis (protocol-layered)
- [ ] Step 4: Transport stream health (TR 101 290)
- [ ] Step 5: Per-output health
- [ ] Step 6: Content quality monitoring
- [ ] Step 7: Entitlement verification (if applicable)
- [ ] Step 8: Bridge and gateway inspection (if applicable)
- [ ] Step 9: Router inspection (if applicable)
- [ ] Step 10: EventBridge event check
- [ ] Step 11: Compile findings

## Step 1: Flow state and error messages

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --no-cli-pager --output json
```

Extract and evaluate:

Table: [Step 1: Flow state and error messages](references/lookup-tables.md#step-1-flow-state-and-error-messages). Load it when you run this step.

If `Messages.Errors[]` is non-empty, report each error verbatim — these are
the closest thing to logs that MediaConnect provides.

If `Status` ≠ ACTIVE:
- STANDBY → Flow not started; metrics are only generated while the flow is
  active and ingesting/transmitting data; tell customer to start the flow
- ERROR → Flow has a fatal configuration issue; quote Messages.Errors[]
- UPDATING/DELETING → Transient state; wait and re-check

## Step 2: Source connectivity analysis

### Protocol-specific metric availability

Not all metrics emit for all protocols. Check the source protocol first:

Table: [Step 2: Source connectivity analysis: Protocol-specific metric availability](references/lookup-tables.md#step-2-source-connectivity-analysis-protocol-specific-metric-availability). Load it when you run this step.

¹ NDI emits a separately defined `SourceConnected` indicating connection to an
NDI sender. It also emits `SourceAudioFrames`, `SourceVideoFrames`, and
`SourceDiscoveredSources`. Flows with NDI outputs require `FlowSize=LARGE`.

² CDI uses payload-level metrics instead of transport-stream metrics:
`SourceDroppedPayloads`, `SourceLatePayloads`, `SourceTotalPayloads`.

**Deprecated**: Fujitsu QoS (`fujitsu-qos`) is no longer supported by
MediaConnect. The protocol value is retained in the API only for legacy
flows. Do not include it in new flow configurations or active troubleshooting.

For protocols without SourceConnected (RIST, RTP, UDP, CDI, ST 2110):
connectivity is inferred from SourceBitRate > 0 and SourceTotalPackets > 0.
For RIST, also check the flow-level `Connected` metric (which includes RIST).

### Connectivity check

Run dimension discovery then query:

```
aws cloudwatch list-metrics \
  --namespace AWS/MediaConnect \
  --metric-name SourceConnected \
  --dimensions Name=FlowARN,Value=$FLOW_ARN \
  --no-cli-pager --output json
```

If no results: protocol does not emit SourceConnected — note this and fall back
to SourceBitRate analysis.

If results exist, query with discovered dimensions:
- `SourceConnected` Minimum = 1 → Connected throughout window
- `SourceConnected` Minimum = 0 → Disconnection occurred in window
- Correlate with `SourceDisconnections` Sum to count events

Valid dimensions for source metrics: `SourceARN`, `FlowARN`,
`AvailabilityZone`, and the aggregate `All flows` dimension.

### Bitrate analysis

```
SourceBitRate Average vs MaxBitrate from describe-flow → Source.Transport.MaxBitrate
```

Classification:
- Within 10% of MaxBitrate → Healthy
- 50%–90% of MaxBitrate → Possible concern (check protocol)
- < 50% of MaxBitrate → Investigate (but check Zixi exception below)
- = 0 → Source not delivering content

**Zixi/entitled flow exception**: On Zixi and entitled flows, null-packet
substitution reduces SourceBitRate when content is repetitive (e.g., slate,
color bars). This is normal behavior. Only classify as a real issue when
accompanied by:
- SourceTotalPackets declining or zero
- NotRecoveredPackets Sum > 0
- SourceRoundTripTime or SourceJitter rising

## Step 3: Packet loss analysis (protocol-layered)

Packet loss analysis must layer metrics by error correction mechanism.

### Layer 1: Raw loss detection

Table: [Step 3: Packet loss analysis (protocol-layered): Layer 1: Raw loss detection](references/lookup-tables.md#step-3-packet-loss-analysis-protocol-layered-layer-1-raw-loss-detection). Load it when you run this step.

### Layer 2: Recovery mechanisms

Table: [Step 3: Packet loss analysis (protocol-layered): Layer 2: Recovery mechanisms](references/lookup-tables.md#step-3-packet-loss-analysis-protocol-layered-layer-2-recovery-mechanisms). Load it when you run this step.

Recovery > 0 is the error correction system working correctly.
Only escalate when NotRecoveredPackets > 0.

### Layer 3: Unrecoverable loss (THE critical metric)

| Metric | Meaning | Severity |
|---|---|---|
| NotRecoveredPackets (flow-level) | Packets lost despite all recovery | High |
| SourceNotRecoveredPackets (per-source) | Same, per source granularity | High |

**Any NotRecoveredPackets Sum > 0 indicates packet loss that may cause
viewer-visible corruption** depending on the affected payload (reference
frames vs. B-frames) and downstream decoder error concealment. Treat as
high severity regardless.

### Layer 4: Network path health

Table: [Step 3: Packet loss analysis (protocol-layered): Layer 4: Network path health](references/lookup-tables.md#step-3-packet-loss-analysis-protocol-layered-layer-4-network-path-health). Load it when you run this step.

### CDI-specific loss detection

For CDI flows, use payload metrics instead of transport-stream metrics:

Table: [Step 3: Packet loss analysis (protocol-layered): CDI-specific loss detection](references/lookup-tables.md#step-3-packet-loss-analysis-protocol-layered-cdi-specific-loss-detection). Load it when you run this step.

### Packet loss decision tree

```
NotRecoveredPackets > 0?
  ├─ YES → CONTENT LOSS CONFIRMED
  │   ├─ SourceARQRequests also rising? → Network path degrading, ARQ buffer exhausted
  │   ├─ SourceRoundTripTime > 100ms? → Latency too high for ARQ recovery window
  │   ├─ SourceFECRecovered also rising? → FEC partially recovering, but overwhelmed
  │   └─ No recovery metrics rising? → Sudden packet loss (routing change, burst)
  │
  └─ NO → Check SourceRecoveredPackets
       ├─ RecoveredPackets > 0? → Recovery working — network impaired but content intact
       │   └─ RecoveredPackets rate increasing? → Degrading path, may eventually exceed recovery
       └─ RecoveredPackets = 0? → No loss detected or no recovery mechanism configured
```

## Step 4: Transport stream health (TR 101 290)

TR 101 290 metrics detect transport stream structural errors that survive
network delivery intact but corrupt the content. These apply to transport-stream
protocols (Zixi, SRT, RIST, RTP, UDP) — not to CDI or NDI.

### Priority 1 indicators (P1)

Table: [Step 4: Transport stream health (TR 101 290): Priority 1 indicators (P1)](references/lookup-tables.md#step-4-transport-stream-health-tr-101-290-priority-1-indicators-p1). Load it when you run this step.

**P1 errors originate at the SOURCE ENCODER, not in the network.**
If any P1 metric > 0, the problem is upstream of MediaConnect — the source
is sending a malformed transport stream.

### Priority 2 indicators (P2)

Table: [Step 4: Transport stream health (TR 101 290): Priority 2 indicators (P2)](references/lookup-tables.md#step-4-transport-stream-health-tr-101-290-priority-2-indicators-p2). Load it when you run this step.

### TR 101 290 investigation flow

```
ContinuityCounter Sum > 0?
  ├─ YES → Source encoder problem
  │   Report: "TR 101 290 P1: ContinuityCounter errors detected.
  │   This indicates the SOURCE ENCODER is producing a malformed
  │   transport stream. The issue is upstream of MediaConnect."
  │
  └─ NO → Check P2 metrics
       └─ Any P2 > 0? → Structural issue (less critical, may be transient)
```

## Step 5: Per-output health

Each flow output delivers to a different downstream consumer. Check EVERY output.

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --query 'Flow.Outputs[].{Name:Name,ARN:OutputArn,Protocol:Transport.Protocol,Destination:Destination,MediaLiveInput:MediaLiveInputArn,Status:OutputStatus}' \
  --no-cli-pager --output json
```

**Check `OutputStatus` first**: Since July 2024, outputs can be individually
disabled (`OutputStatus=DISABLED`) while remaining attached to the flow. A
disabled output stops streaming and does not incur data transfer costs. If
`OutputStatus=DISABLED`, `OutputBitrate=0` is expected — not a failure.

For each ENABLED output, run dimension discovery and query:

Table: [Step 5: Per-output health](references/lookup-tables.md#step-5-per-output-health). Load it when you run this step.

Valid dimensions for output metrics: `OutputARN`, `FlowARN`,
`AvailabilityZone`, and the aggregate `All flows` dimension.

**NDI output metrics** (if protocol is `ndi-speed-hq`):

Table: [Step 5: Per-output health (2)](references/lookup-tables.md#step-5-per-output-health-1). Load it when you run this step.

**CDI output metrics** (if protocol is `cdi`):

Table: [Step 5: Per-output health (3)](references/lookup-tables.md#step-5-per-output-health-2). Load it when you run this step.

### Output-level decision tree

```
For each output:
  OutputStatus = DISABLED?
    → EXPECTED: Output intentionally disabled. Not a failure.

  OutputConnected = 0 OR OutputDisconnections > 0?
    ├─ YES → Output delivery failure
    │   ├─ Source healthy? → Problem is between MC and downstream
    │   ├─ MediaLiveInputArn set? → Check ML input state via describe-input
    │   └─ Check network path: security groups, CIDR allow-lists, destination reachability
    │
    └─ NO → Output delivering
         └─ OutputBitrate << SourceBitRate? → Possible output throttling or mismatch
```

**Critical pattern**: Source healthy + Output disconnected = the flow is receiving
content but cannot deliver it downstream. This is DIFFERENT from a source issue
and points to output configuration, network path, or downstream availability.

## Step 6: Content quality monitoring (load on demand)

Only available if `SourceMonitoringConfig` is enabled on the flow. When black,
frozen or silent content is in question, load
[references/secondary-checks.md](references/secondary-checks.md) and run the
content quality section; it carries the metric table and the DATA GAP text for
flows without content quality analysis.

## Step 7: Entitlement verification (if applicable)

Entitlements are the cross-account sharing mechanism. A flow may CONSUME an
entitlement (subscriber side) or GRANT one (granter side).

**Note**: MediaConnect does not support source failover on entitlement flows.

### Subscriber side (this flow consumes an entitlement)

Check `describe-flow → Flow.Source.EntitlementArn`:

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --query 'Flow.Source.EntitlementArn' \
  --no-cli-pager --output json
```

If non-null:
- This flow receives content from ANOTHER account's MediaConnect flow
- The upstream flow is NOT directly observable from this account
- Report: "This flow consumes an entitlement from another account. Upstream
  source health cannot be directly verified from this account."

Check entitlement status:
```
aws mediaconnect list-entitlements --no-cli-pager --output json
```

### Granter side (this flow grants entitlements)

Check `describe-flow → Flow.Entitlements[]`:

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --query 'Flow.Entitlements[].{Name:EntitlementName,ARN:EntitlementArn,Subscribers:Subscribers,Status:EntitlementStatus}' \
  --no-cli-pager --output json
```

| Status | Meaning |
|---|---|
| ENABLED | Entitlement active and available to subscriber |
| DISABLED | Entitlement suspended — subscriber receives nothing |

If a subscriber reports issues and the entitlement is ENABLED, the problem
is likely at the source level (check Steps 1–4 on this flow).

### Two-sided verification

When entitlements are involved, always state which side you CAN observe:
```
Observed: Entitlement [ARN] is ENABLED on the granter side.
Cannot verify: Whether the subscriber's flow is correctly consuming this
entitlement (subscriber account not accessible from this session).
Question: Has the subscriber confirmed their flow Status=ACTIVE?
```

## Step 8: Bridge and gateway inspection (if applicable, load on demand)

If the flow uses bridges or MediaConnect Gateway, load
[references/secondary-checks.md](references/secondary-checks.md) and run the
bridge and gateway section. Skip it for a single-region, single-account flow.

## Step 9: Router inspection (if applicable)

MediaConnect Router (GA November 2025) enables dynamic routing of live video
between sources and destinations. Check if the flow is connected to a router:

```
aws mediaconnect list-router-inputs --no-cli-pager --output json
aws mediaconnect list-router-outputs --no-cli-pager --output json
```

If router resources exist:

```
aws mediaconnect get-router-input --arn $ARN \
  --no-cli-pager --output json
aws mediaconnect get-router-output --arn $ARN \
  --no-cli-pager --output json
```

Router-specific metrics (dimensions include `RouterInputName`, `RouterInputID`,
`DownstreamFlowARN`, `DownstreamFlowSourceName`, `DownstreamMediaLiveInputID`,
`RouterInputAvailabilityZone`):

| Metric | Meaning |
|---|---|
| OutputEnabled | Whether the router output is enabled (0/1) |
| OutputBitrate | Bitrate at the router output |

Router input source metadata and thumbnails:
```
aws mediaconnect get-router-input-source-metadata \
  --arn $ARN --no-cli-pager --output json
aws mediaconnect get-router-input-thumbnail \
  --arn $ARN --no-cli-pager --output json
```

If no router resources found, skip this step.

## Step 10: EventBridge event check

MediaConnect emits state change events to EventBridge. Check if a forwarding
rule exists:

```
aws events list-rules \
  --no-cli-pager --output json \
  --query "Rules[?contains(EventPattern, 'mediaconnect')]"
```

If a rule exists that forwards to CloudWatch Logs, query those logs:
```
aws logs filter-log-events \
  --log-group-name <TARGET_LOG_GROUP> \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '"aws.mediaconnect"' \
  --limit 50 --no-cli-pager --output json
```

If no forwarding rule exists:
```
DATA GAP: No EventBridge rule forwards "aws.mediaconnect" events to
CloudWatch Logs. State change events (flow state transitions, source
health changes) are not being captured. Only real-time metrics and
describe-flow Messages.Errors[] are available for this flow.
```

See [references/eventbridge-events.md](references/eventbridge-events.md) for
the full event taxonomy.

## Step 11: Compile findings

Structure each finding as Observed (the value plus the API or metric it came
from), Expected (the threshold or benchmark plus its source), and Question:
why? Do not declare a definitive root cause; surface evidence and the precise
question that follows from it. Report sections:

1. **Flow identity**: ARN, status, source protocol, source address
2. **Source health**: Connected/disconnected, bitrate vs expected, packet loss layers
3. **Transport stream**: TR 101 290 P1/P2 findings (or CDI payload metrics)
4. **Output health**: Per-output status (connected, bitrate, disconnections, enabled/disabled)
5. **Content quality**: Monitoring results or DATA GAP
6. **Cross-account**: Entitlement status or N/A
7. **Bridge/gateway**: Status or N/A
8. **Router**: Status or N/A
9. **EventBridge events**: Findings or DATA GAP
10. **Open questions**: Ranked by severity using the classifications in the steps above

Reference the [flow-health-checklist](references/flow-health-checklist.md) for
the mechanical pass/fail evaluation, and
[redundancy-patterns](references/redundancy-patterns.md) if the flow uses
failover or merge mode.

### Before presenting

Check the compiled findings and fix anything that fails before presenting them:

- Every Observed value names the API field or metric it came from, with its dimensions and time window.
- Every Expected value names its source: a threshold, a documented limit, or the resource's own configuration.
- No section asserts a definitive root cause; each finding ends in a question or a named handoff.
- Every signal that was not observable is reported as a DATA GAP with its reason, never as a healthy zero.
- No account IDs, ARNs, secrets or passphrases are reproduced; resources are named by type and name.
- Loss findings cite NotRecoveredPackets, not PacketLossPercent alone, before loss is said to have reached an output.
