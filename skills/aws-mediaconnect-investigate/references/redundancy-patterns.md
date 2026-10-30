# MediaConnect Redundancy Patterns

Reference for evaluating MediaConnect flow redundancy configurations:
failover mode, merge mode, and the metrics that distinguish healthy
redundancy from pathological flapping.

## Redundancy mode availability

MediaConnect supports source failover on most transport-stream protocols,
with these exceptions:
- **CDI flows**: Source failover is NOT supported
- **NDI flows**: Source failover is NOT supported
- **Entitlement flows**: Source failover is NOT supported

## Redundancy modes

MediaConnect supports two redundancy modes via `SourceFailoverConfig`:

| Mode | Behavior | Use case |
|---|---|---|
| **FAILOVER** | Active/passive — one source active, failover on failure | Simple redundancy; one source idle |
| **MERGE** | Active/active — both sources contribute, duplicate packets merged | Zero-interruption redundancy; both sources always active |

## Detecting redundancy configuration

```
aws mediaconnect describe-flow --flow-arn $FLOW_ARN \
  --query 'Flow.SourceFailoverConfig' \
  --no-cli-pager --output json
```

Response fields:

| Field | Values | Meaning |
|---|---|---|
| `State` | ENABLED / DISABLED | Whether failover is active |
| `FailoverMode` | FAILOVER / MERGE | Which mode |
| `RecoveryWindow` | 100–15000 (ms), default 200 ms | Buffer window for merge deduplication (MERGE mode only) |
| `SourcePriority.PrimarySource` | Source name | Which source is preferred (FAILOVER mode) |

If `SourceFailoverConfig` is null or `State=DISABLED`:
- Flow has no redundancy — skip redundancy analysis
- Single source failure = total content loss

## Failover mode analysis

### How failover works

1. Primary source delivers content
2. Secondary source is connected but standby
3. If the active source does not send data for **500 milliseconds**,
   MediaConnect switches to the other source
4. `FailoverSwitches` increments on each switch
5. `SourceSelected` changes to indicate active source

### Auto-return behavior (critical distinction)

Failover behavior differs based on whether a primary source is designated:

**When `SourcePriority.PrimarySource` IS set:**
- MediaConnect uses the designated primary source to provide content
- If the primary fails, the flow switches to the secondary
- **The flow automatically switches back to the primary source as soon
  as data returns** — this is the documented default behavior
- A single `FailoverSwitches` increment followed by another increment
  back to primary is a completed, healthy failover-and-recovery cycle

**When NO primary source is designated:**
- MediaConnect randomly selects one of the sources at flow start
- If the active source fails, the flow switches to the other source
- **The flow does NOT automatically return to any preferred source** —
  it continues with whichever source is currently providing data
- The flow can continue switching back and forth between sources as needed

### Healthy failover metrics

| Metric | Healthy state | Meaning |
|---|---|---|
| FailoverSwitches Sum = 0 | ✅ | No failover events — primary stable |
| FailoverSwitches Sum = 1 | ⚠️ | Single failover occurred — investigate why |
| SourceSelected stable | ✅ | Consistently on one source |

### Unhealthy failover: flapping

**Flapping** = rapid alternation between sources. Indicators:

| Metric | Flapping pattern | Severity |
|---|---|---|
| FailoverSwitches | Sum > 3 in a 5-minute window | High |
| SourceSelected | Alternating values within short periods | High |

Flapping means BOTH sources are unhealthy — each fails shortly after being
selected. This typically indicates:
- Both source encoders have the same upstream network issue
- Both encoders share a failing component (splitter, router)
- Both sources are independently unstable

## Merge mode analysis

### How merge works

1. Both sources deliver content simultaneously
2. MediaConnect maintains a deduplication buffer (sized by `RecoveryWindow`,
   default 200 ms, configurable 100–15000 ms)
3. Duplicate packets are identified and merged
4. Output receives the best packet from either source
5. If one source fails, the other continues seamlessly (zero-interruption)

### Healthy merge metrics

| Metric | Healthy state | Meaning |
|---|---|---|
| MergeActive Minimum = 1 | ✅ | Merge operating — both sources contributing |
| MergeLatency Average stable (< RecoveryWindow) | ✅ | Sources synchronized within buffer |
| SourceMergeStatusWarnSolo = 0 | ✅ | Not operating on single source |
| SourceMergeStatusWarnMismatch = 0 | ✅ | Sources are compatible |

### Unhealthy merge: solo operation

| Metric | Condition | Meaning | Severity |
|---|---|---|---|
| MergeActive Minimum = 0 | Merge not operating | One or both sources failed to merge | High |
| SourceMergeStatusWarnSolo Minimum = 1 | Solo warning active | Only one source contributing — no redundancy | High |

**MergeActive = 0 with both sources "connected"** can mean:
- Sources are too far out of sync (latency difference > RecoveryWindow)
- One source has mismatched content (different program structure)
- Packet timing mismatch prevents deduplication

### Unhealthy merge: content mismatch

| Metric | Condition | Meaning | Severity |
|---|---|---|---|
| SourceMergeStatusWarnMismatch Minimum = 1 | Mismatch warning | Sources producing incompatible content | High |

Content mismatch means the two sources are not producing identical transport
streams. The merge system cannot deduplicate packets that don't match.
Causes:
- Different encoder configurations on redundant paths
- Different source content on each path
- Clock drift between source encoders

### Merge latency analysis

`MergeLatency` measures the time offset between matching packets from both sources.

| MergeLatency | Interpretation |
|---|---|
| Stable, < 50% of RecoveryWindow | Healthy — comfortable buffer margin |
| Stable, > 75% of RecoveryWindow | At risk — buffer nearly exhausted |
| Rising trend | Sources drifting apart — will eventually exceed buffer |
| Spiking/variable | Network path instability on one or both sources |

If MergeLatency approaches RecoveryWindow, the merge will eventually fail
(MergeActive → 0). Recommend increasing RecoveryWindow or investigating
why sources are diverging in timing.

## Zixi null-packet substitution pattern

This is NOT a redundancy feature, but it interacts with redundancy analysis
and is a common false-positive trigger.

### What it is

Zixi protocol (and entitled flows that use Zixi transport) performs
null-packet substitution: when content is repetitive (slate, color bars,
static images), Zixi replaces redundant packets with null markers to save
bandwidth. The receiver reconstructs the full stream.

### How it manifests in metrics

- `SourceBitRate` drops significantly below `MaxBitrate`
- This is NORMAL for Zixi — not an error

AWS docs confirm this verbatim: in a 30 Mbps stream with repetitive content,
Zixi optimization might reduce the bitrate to 5 Mbps. These bitrate
fluctuations are normal and don't affect content quality.

### How to distinguish from real packet loss

| Condition | Zixi null-packet (normal) | Real packet loss |
|---|---|---|
| SourceBitRate | < MaxBitrate | < MaxBitrate |
| SourceTotalPackets | Stable or slowly declining | Rapidly declining or zero |
| NotRecoveredPackets | = 0 | > 0 |
| SourceRoundTripTime | Stable | Rising |
| SourceJitter | Stable | Rising |
| SourceARQRequests | Stable or zero | Rising |

### Decision rule

```
Zixi flow with SourceBitRate < MaxBitrate:

  NotRecoveredPackets = 0 AND SourceTotalPackets stable?
    → NORMAL: Null-packet substitution on repetitive content
    → Do NOT flag as an issue

  NotRecoveredPackets > 0 OR SourceTotalPackets declining?
    → REAL ISSUE: Content loss despite Zixi optimizations
    → Classify per the severity guidance in SKILL.md
```

## Redundancy + downstream propagation

When a redundancy event occurs (failover switch or merge degradation),
downstream services may see brief interruptions. The following timings
are **empirical observations, not documented AWS guarantees**:

| Redundancy event | Expected downstream impact (empirical) |
|---|---|
| Failover switch (FAILOVER mode) | ML InputLossSeconds spike of ~0.5–3 s during switch |
| MergeActive → 0 (MERGE mode) | Usually zero impact if remaining source is healthy |
| MergeActive → 0 with both sources degraded | ML may see intermittent input issues |
| Flapping (rapid failover switches) | Repeated ML InputLossSeconds spikes |

When downstream MediaLive shows brief `InputLossSeconds` spikes that correlate
with `FailoverSwitches` timestamps, classify the ML symptom as PROPAGATED,
not as an independent MediaLive issue.

Note: The 500 ms failover trigger is documented by AWS. The downstream
propagation timings above are operational observations and may vary based
on network conditions and channel configuration.

## Reporting template for redundancy findings

```
Redundancy mode: [FAILOVER / MERGE]
Primary source designated: [Yes — <name> / No]
RecoveryWindow: [X ms] (MERGE mode only)
Auto-return to primary: [Yes (primary designated) / No (no primary)]
Status: [HEALTHY / DEGRADED / FAILED]

Observations:
  - [Metric findings with timestamps]

Assessment:
  - [Is redundancy functioning as designed?]
  - [If degraded: which source is the problem?]
  - [If flapping: what do both sources share that could explain joint failure?]
```
