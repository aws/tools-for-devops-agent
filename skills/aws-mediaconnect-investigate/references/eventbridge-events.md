# MediaConnect EventBridge Events

Complete taxonomy of EventBridge events emitted by MediaConnect
(source: `aws.mediaconnect`). These are the only log-equivalent surface
for MediaConnect — the service has no native CloudWatch Logs.

Reference: https://docs.aws.amazon.com/eventbridge/latest/ref/events-ref-mediaconnect.html

## Event discovery

Check if a forwarding rule exists that captures these events:

```
aws events list-rules \
  --no-cli-pager --output json \
  --query "Rules[?contains(EventPattern, 'mediaconnect')]"
```

If no rule exists, these events are emitted but not captured anywhere
queryable. Report as a DATA GAP.

## Event envelope

All MediaConnect events follow this structure:

```json
{
  "source": "aws.mediaconnect",
  "detail-type": "<EVENT_TYPE>",
  "detail": {
    ...
  }
}
```

Delivery is best-effort. Always corroborate with `describe-flow` and
CloudWatch metrics for definitive state.

## Alert events

### MediaConnect Alert

Fired when a resource hits an error condition. These errors are also
visible as a snapshot in `describe-flow → Messages.Errors[]`, but
EventBridge provides the historical timeline that the API snapshot does not.

| Detail field | Type | Meaning |
|---|---|---|
| `errored` | boolean | `true` = alert set, `false` = alert cleared |
| `error-code` | string | Machine-readable error identifier |
| `error-message` | string | Human-readable error description |

Diagnostic use: Correlate `errored=true` timestamps with metric anomalies
(SourceDisconnections, NotRecoveredPackets). The `error-message` provides
detail that CloudWatch metrics cannot — it explains WHY the alert fired.

## Flow lifecycle events

### MediaConnect Flow Status Change

Fired on flow state transitions.

| Detail field | Type | Values |
|---|---|---|
| `previousStatus` | string | STANDBY, STARTING, ACTIVE, STOPPING, UPDATING, DELETING, ERROR |
| `currentStatus` | string | Same set as above |

State transition interpretation:
- ACTIVE → STANDBY: Flow stopped (customer action or API call)
- ACTIVE → ERROR: Fatal error — check `MediaConnect Alert` events and `describe-flow → Messages.Errors[]`
- ACTIVE → UPDATING: Configuration change in progress — expect transient metric gaps
- STANDBY → ACTIVE: Flow started successfully
- Any → DELETING: Flow being removed

Diagnostic use: Correlate with metric gaps. Metrics are only generated while
the flow is active and ingesting/transmitting data. A transition out of ACTIVE
explains empty metric data during that window.

### MediaConnect Flow Maintenance

Fired during AWS-managed maintenance windows.

| Detail field | Type | Values |
|---|---|---|
| `currentStatus` | string | SCHEDULED, INPROGRESS, FINISHED, RESCHEDULED, CANCELED, FAILED |

Note: The status value during active maintenance is **INPROGRESS** (not
"STARTED").

Diagnostic use: If a customer reports a brief interruption that aligns
with a maintenance window, this event confirms it was AWS-initiated
maintenance, not a source or network issue. Check `describe-flow →
Maintenance` for the maintenance schedule.

Correlate with the CloudWatch maintenance metrics (`MaintenanceScheduled`,
`MaintenanceStarted`, `MaintenanceSucceeded`, `MaintenanceFailed`,
`MaintenanceCanceled`, `MaintenanceRescheduled`) for aggregate counts.

## Source health events

### MediaConnect Source Health

Fired when a source's health state changes. Provides more granular
information than CloudWatch metrics, including TR 101 290 error detail.

| Detail field | Type | Meaning |
|---|---|---|
| `unhealthy` | boolean | `true` = source has active health issues |
| `current` | object | Current health state (see below) |
| `previous` | object | Previous health state (same structure as `current`) |

`current` and `previous` structure:

| Field | Type | Meaning |
|---|---|---|
| `state` | string | `CONNECTED` or `DISCONNECTED` |
| `tr101` | object | TR 101 290 error indicators |
| `tr101.ts_sync_loss` | boolean | Transport stream sync loss detected |
| `tr101.continuity_count_error` | boolean | Continuity counter errors detected |
| `tr101.transport_error` | boolean | Transport error indicator set |
| `tr101.pcr_error` | boolean | PCR accuracy error detected |

Diagnostic use: This event pinpoints the exact moment of a source health
change with sub-second precision — more precise than 60-second CloudWatch
metric periods. Compare `previous` and `current` to determine what changed.

Key patterns:
- `state: CONNECTED → DISCONNECTED`: Source stopped sending. Correlate
  with `SourceDisconnections` metric.
- `state: DISCONNECTED → CONNECTED`: Source resumed. Calculate total
  disconnection duration from event timestamps.
- `unhealthy: true` with `tr101` errors: Source is sending but the
  transport stream is corrupted — problem is at the source encoder.
- Multiple rapid CONNECTED → DISCONNECTED → CONNECTED transitions:
  Flapping source — unstable network or encoder restarts.

## Flow health events

### MediaConnect Flow Health

Fired when the aggregate flow health changes. This is a flow-level
summary that combines source health and failover state.

| Detail field | Type | Meaning |
|---|---|---|
| `unhealthy` | boolean | `true` = flow has active health issues |
| `current` | object | Current flow health state (see below) |

`current` structure:

| Field | Type | Meaning |
|---|---|---|
| `failover_switch` | boolean | A failover switch occurred |
| `source_state` | string | Aggregate source connectivity state |
| `tr101` | object | Same TR 101 290 structure as Source Health events |

Diagnostic use: For flows with multiple sources, this event provides the
aggregate view. Use `MediaConnect Source Health` events for per-source
granularity.

## Output health events

### MediaConnect Output Health

Fired when an output's delivery state changes.

| Detail field | Type | Meaning |
|---|---|---|
| `current` | object | Current output health state |
| `previous` | object | Previous output health state |

`current` and `previous` structure:

| Field | Type | Values |
|---|---|---|
| `state` | string | `connected`, `sending`, `disconnected`, `idle` |

Note: AWS documentation shows lowercase values in descriptive text but
uppercase in some JSON examples. Treat comparison as case-insensitive.

State interpretation:
- `connected` / `sending`: Output is delivering content to downstream
- `disconnected`: Output lost connection to downstream consumer
- `idle`: Output exists but is not actively sending

Diagnostic use: When the source is healthy but a downstream MediaLive
input reports `InputLossSeconds`, check for `MediaConnect Output Health`
events showing `state: disconnected`. This isolates the problem to the
output path (network, security groups, downstream availability) rather
than the source.

Key pattern — source healthy + output disconnected:
- Problem is between MediaConnect and downstream (not a source issue)
- Check: security groups, CIDR allow-lists, destination reachability
- Check: `describe-flow → Outputs[].MediaLiveInputArn` for ML input state
- Check: `describe-flow → Outputs[].OutputStatus` — if DISABLED, the
  output was intentionally stopped (customer action, not a failure)

### MediaConnect Output Status Change

Fired when an output is administratively enabled or disabled.

| Detail field | Type | Meaning |
|---|---|---|
| `previousStatus` | string | Previous output status (ENABLED/DISABLED) |
| `currentStatus` | string | Current output status (ENABLED/DISABLED) |

Diagnostic use: If an output was disabled, downstream will lose content.
This is a customer action, not a failure. Since July 2024, outputs can
be individually disabled without removing them from the flow.

## Content quality events

### MediaConnect Flow Content Quality

Fired when content quality thresholds are breached. Requires
`SourceMonitoringConfig` with `ContentQualityAnalysisState=ENABLED`
on the flow (default thresholds: 30 seconds).

| Detail field | Type | Meaning |
|---|---|---|
| `impacted` | boolean | `true` = quality issue detected |
| `streams` | array | Per-stream quality indicators |

Each entry in `streams[]`:

| Field | Type | Meaning |
|---|---|---|
| `audio_missing` | boolean | Audio elementary stream absent |
| `video_missing` | boolean | Video elementary stream absent |
| `black_frames_duration_breaching` | boolean | Black frames exceed configured threshold |
| `frozen_frames_duration_breaching` | boolean | Frozen frames exceed configured threshold |
| `silent_audio_duration_breaching` | boolean | Silent audio exceeds configured threshold |
| `timecode_present` | boolean | Whether timecode is present in the stream |

Diagnostic use: These events provide near-real-time content quality
alerts. Correlate with the CloudWatch content quality metrics
(`VideoStreamMissing`, `AudioStreamMissing`, `BlackFramesBreaching`,
`FrozenFramesBreaching`, `SilentAudioBreaching`).

If these events do not fire and content quality metrics are absent:
```
DATA GAP: SourceMonitoringConfig not enabled on this flow.
Content quality events and metrics are unavailable.
```

## CloudTrail events

### AWS API Call via CloudTrail

Standard CloudTrail management events for all MediaConnect API calls.

| Detail field | Type | Meaning |
|---|---|---|
| `eventSource` | string | `mediaconnect.amazonaws.com` |
| `eventName` | string | The API operation (e.g., `StopFlow`, `UpdateFlowSource`) |

Diagnostic use: Determines whether a state change was caused by a
customer API call, console action, or automated process. Useful for
answering "who stopped the flow?"

## Querying captured events

If an EventBridge rule forwards events to a CloudWatch Logs group,
query with:

### All MediaConnect events for a flow

```
aws logs filter-log-events \
  --log-group-name <LOG_GROUP> \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '{ $.source = "aws.mediaconnect" && $.detail.flow_arn = "<FLOW_ARN>" }' \
  --limit 50 --no-cli-pager --output json
```

### Source health changes only

```
aws logs filter-log-events \
  --log-group-name <LOG_GROUP> \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '{ $."detail-type" = "MediaConnect Source Health" }' \
  --limit 50 --no-cli-pager --output json
```

### Alert events only

```
aws logs filter-log-events \
  --log-group-name <LOG_GROUP> \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '{ $."detail-type" = "MediaConnect Alert" && $.detail.errored = true }' \
  --limit 50 --no-cli-pager --output json
```

## Event timing vs metric timing

EventBridge events are near-real-time (typically < 5 seconds latency).
CloudWatch metrics aggregate at 60-second minimum period.

EventBridge events provide MORE PRECISE timing for state transitions
than metrics. When correlating with downstream issues, prefer event
timestamps over metric period boundaries for pinpointing the exact
moment of failure.

## When events are NOT available

If no EventBridge rule is configured for `aws.mediaconnect`, report:

```
DATA GAP: No EventBridge rule forwards "aws.mediaconnect" events to
CloudWatch Logs. Historical state change events (source health
transitions, flow status changes, alerts, content quality) are not
being captured. Only real-time metrics and describe-flow
Messages.Errors[] are available.

Recommendation: Configure an EventBridge rule with event pattern
{"source": ["aws.mediaconnect"]} targeting a CloudWatch Logs group.
This provides state-change history unavailable through any other
MediaConnect diagnostic surface.
```
