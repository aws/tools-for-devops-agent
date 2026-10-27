# MediaConnect Flow Health Checklist

Mechanical pass/fail checklist for evaluating a single MediaConnect flow.
Run each check in order — stop at the first FAIL for root cause isolation,
but continue for completeness in the report.

## Prerequisites

- Flow ARN known
- Time window established
- Dimension discovery completed for all metrics below
- Valid dimensions include: `FlowARN`, `SourceARN`, `OutputARN`,
  `AvailabilityZone`, and the aggregate `All flows` dimension

## Checklist

### 1. Flow state

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --query '{Status:Flow.Status,Errors:Flow.Messages.Errors}' \
  --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Status = ACTIVE | ✅ | Status ≠ ACTIVE | Critical |
| Messages.Errors[] is empty | ✅ | Non-empty array | Critical |

If FAIL: Quote each error message verbatim. A non-ACTIVE flow or active
errors preclude all further metric analysis (metrics are only generated
while the flow is active and ingesting/transmitting data).

### 2. Source connectivity

| Check | PASS | FAIL | Severity | Protocol scope |
|---|---|---|---|---|
| SourceConnected Minimum = 1 | ✅ | = 0 at any point | Critical | Zixi/SRT only |
| SourceDisconnections Sum = 0 | ✅ | Sum > 0 | Critical | Zixi/SRT only |
| SourceBitRate Average ≈ MaxBitrate (within 10%) | ✅ | < 50% (with evidence) | High | All protocols |
| SourceBitRate Average > 0 | ✅ | = 0 | Critical | All protocols |
| SourceTotalPackets Sum > 0 | ✅ | = 0 | Critical | All protocols |

**Protocol notes**:
- `SourceConnected` emits only for Zixi and SRT sources. For RIST, check
  the flow-level `Connected` metric instead. For NDI, a separately defined
  `SourceConnected` indicates connection to an NDI sender.
- For protocols without SourceConnected (RIST, RTP, UDP, CDI, ST 2110):
  infer connectivity from `SourceBitRate > 0` and `SourceTotalPackets > 0`.

**Exception**: For Zixi/entitled flows, SourceBitRate < MaxBitrate is acceptable
if SourceTotalPackets > 0, NotRecoveredPackets = 0, and no network distress
metrics are rising. This is null-packet substitution on repetitive content.

### 3. Packet loss (unrecoverable)

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| NotRecoveredPackets Sum = 0 | ✅ | Sum > 0 | High — content loss likely |
| SourceNotRecoveredPackets Sum = 0 | ✅ | Sum > 0 | High — per-source |

If FAIL: This is the most critical metric — any value > 0 indicates packet
loss that may cause viewer-visible corruption depending on the affected
payload and downstream decoder error concealment. Proceed to packet loss
analysis (SKILL.md Step 3).

### 4. Recovery system (informational — not failures)

| Check | Status | Meaning |
|---|---|---|
| SourceRecoveredPackets Sum = 0 | No recovery needed | Network path clean |
| SourceRecoveredPackets Sum > 0 | Recovery active | Network impaired but content intact |
| SourceARQRequests Sum > 0 | ARQ active | Retransmission requests being sent (Zixi/SRT/RIST) |

**Do NOT classify recovery activity as a failure.** It is the error correction
system working correctly. Only escalate if NotRecoveredPackets is also > 0.

### 5. Network path health

| Check | PASS | FAIL | Severity | Protocol scope |
|---|---|---|---|---|
| SourceRoundTripTime Average < 100ms | ✅ | > 100ms or rising | Medium | Zixi/SRT/RIST |
| SourceJitter stable (low variance) | ✅ | Rising or spiking | Medium | Most protocols |
| SourcePacketLossPercent Average < 0.1% | ✅ | > 0.1% sustained | Medium | All |

### 6. Transport stream health (TR 101 290)

Applies to transport-stream protocols (Zixi, SRT, RIST, RTP, UDP) only.
Skip for CDI and NDI — use their protocol-specific metrics instead.

**Priority 1 (P1) — source encoder structural errors:**

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| ContinuityCounter Sum = 0 | ✅ | Sum > 0 | High — source encoder continuity errors |
| PATError Sum = 0 | ✅ | Sum > 0 | High — Program Association Table errors |
| PIDError Sum = 0 | ✅ | Sum > 0 | High — PID reference errors |
| PMTError Sum = 0 | ✅ | Sum > 0 | High — Program Map Table errors |
| TSByteError Sum = 0 | ✅ | Sum > 0 | High — transport stream byte errors |
| TSSyncLoss Sum = 0 | ✅ | Sum > 0 | High — transport stream sync loss |

**Priority 2 (P2) — less critical structural issues:**

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| CATError Sum = 0 | ✅ | Sum > 0 | Medium — Conditional Access Table errors |
| CRCError Sum = 0 | ✅ | Sum > 0 | Medium — CRC failures (bit-level corruption) |
| PCRAccuracyError Sum = 0 | ✅ | Sum > 0 | Medium — PCR accuracy drift |
| PCRError Sum = 0 | ✅ | Sum > 0 | Medium — Program Clock Reference errors |
| PTSError Sum = 0 | ✅ | Sum > 0 | Medium — Presentation Timestamp errors |
| TransportError Sum = 0 | ✅ | Sum > 0 | Medium — transport error indicator set |

If P1 FAILs: Problem is at the SOURCE ENCODER, upstream of MediaConnect.
MediaConnect is faithfully reporting corruption it received.

### 6b. CDI payload health (CDI protocol only)

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| SourceDroppedPayloads Sum = 0 | ✅ | Sum > 0 | High — payload loss |
| SourceLatePayloads Sum = 0 | ✅ | Sum > 0 | Medium — timing issues |

### 6c. NDI source health (NDI protocol only)

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| SourceConnected (NDI) Minimum = 1 | ✅ | = 0 | Critical — no NDI sender |
| SourceVideoFrames Sum > 0 | ✅ | = 0 | Critical — no video |
| SourceAudioFrames Sum > 0 | ✅ | = 0 | High — no audio |

### 7. Per-output delivery

For EACH output in `describe-flow → Flow.Outputs[]`:

**First check `OutputStatus`** (available since July 2024):

| Check | Status | Action |
|---|---|---|
| OutputStatus = ENABLED | Active | Proceed with metric checks below |
| OutputStatus = DISABLED | Intentionally stopped | Skip metric checks — not a failure |

For each ENABLED output:

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| OutputConnected Minimum = 1 | ✅ | = 0 | Critical (per output) |
| OutputDisconnections Sum = 0 | ✅ | Sum > 0 | Critical (per output) |
| OutputBitrate Average ≈ SourceBitRate | ✅ | Significantly lower | High |
| ConnectedOutputs Minimum = expected count | ✅ | Below expected | High |

Note: OutputConnected only emits for Zixi/SRT outputs. For other protocols,
use OutputBitrate > 0 as the connectivity indicator.

**NDI output checks** (if protocol is `ndi-speed-hq`):

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| OutputConnectedReceivers Minimum ≥ 1 | ✅ | = 0 | High — no receivers |
| OutputGeneratedVideoFrames Sum > 0 | ✅ | = 0 | Critical — no output |

**CDI output checks** (if protocol is `cdi`):

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| OutputDroppedPayloads Sum = 0 | ✅ | Sum > 0 | High — payload loss |
| OutputLatePayloads Sum = 0 | ✅ | Sum > 0 | Medium — timing issues |

### 8. Content quality (if SourceMonitoringConfig enabled)

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| VideoStreamMissing Minimum = 0 | ✅ | = 1 | Critical |
| AudioStreamMissing Minimum = 0 | ✅ | = 1 | Critical |
| BlackFramesBreaching Minimum = 0 | ✅ | = 1 | High |
| FrozenFramesBreaching Minimum = 0 | ✅ | = 1 | High |
| SilentAudioBreaching Minimum = 0 | ✅ | = 1 | Medium |
| TimecodePresent Minimum = 1 | ✅ | = 0 | Medium (if timecode expected) |

If these metrics do not exist in list-metrics results:
```
DATA GAP: SourceMonitoringConfig not enabled. Content quality
(black/frozen/silent) cannot be assessed.
```

### 9. Redundancy (if SourceFailoverConfig exists)

See [redundancy-patterns.md](redundancy-patterns.md) for detailed evaluation.

**Note**: MediaConnect does not support source failover on CDI flows,
NDI flows, or entitlement flows.

Quick checks:

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| MergeActive Minimum = 1 (merge mode) | ✅ | = 0 | High — merge failed |
| FailoverSwitches Sum = 0 (failover mode) | ✅ | Rapid switching | High — flapping |
| MergeLatency stable | ✅ | Spiking or diverging | Medium |

### 10. Maintenance (if applicable)

Check if a maintenance window coincides with the investigation time window:

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --query 'Flow.Maintenance' \
  --no-cli-pager --output json
```

CloudWatch maintenance metrics (if available):

| Metric | Value | Meaning |
|---|---|---|
| MaintenanceScheduled Sum > 0 | Maintenance was scheduled during window |
| MaintenanceStarted Sum > 0 | Maintenance began during window |
| MaintenanceSucceeded Sum > 0 | Maintenance completed successfully |
| MaintenanceFailed Sum > 0 | Maintenance failed — investigate further |

If maintenance occurred during the impact window, correlate with
`MediaConnect Flow Maintenance` EventBridge events to confirm AWS-initiated
maintenance vs. customer-reported issue.

## Summary template

```
Flow Health: [ALL PASS / DEGRADED / CRITICAL FAILURE]

Checks passed: X/Y
First failure: [metric] at [severity] — [brief description]

Critical findings:
  - [list Critical-severity FAILs]

High findings:
  - [list High-severity FAILs]

Data gaps:
  - [list unavailable surfaces]
```
