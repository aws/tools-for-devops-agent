# MediaLive Alert Detail Retrieval

When `ActiveAlerts > 0`, the CloudWatch metric tells you something is wrong
but not WHAT. This reference documents how to retrieve alert detail.

## The problem

`ActiveAlerts` is a count metric — it shows how many alerts are active but
provides zero information about the alert type, message, or affected component.
Without additional retrieval, the agent can only report "alerts are active"
which is not diagnostically useful.

## Three paths to alert detail

### Path A: ListAlerts API (simplest)

**Added October 2025.** The `ListAlerts` API returns alerts for classic
MediaLive channels, Anywhere clusters, and multiplexes.

```
aws medialive list-alerts \
  --resource-arn "arn:aws:medialive:${REGION}:${ACCOUNT}:channel:${CHANNEL_ID}" \
  --no-cli-pager --output json
```

To filter to only active (currently firing) alerts:
```
aws medialive list-alerts \
  --resource-arn "arn:aws:medialive:${REGION}:${ACCOUNT}:channel:${CHANNEL_ID}" \
  --state SET \
  --no-cli-pager --output json
```

**Advantage:** Direct API call, no dependency on logging or EventBridge
configuration. Works for all channel types.

**Limitation:** Alert IDs roll over on channel restart. If the channel was
restarted since the alert fired, the alert history is lost. For historical
investigation across restarts, use Path B (encoder logs).

Related APIs for other resource types:
- `aws medialive list-cluster-alerts --cluster-id $ID` (Anywhere clusters)
- `aws medialive list-multiplex-alerts --multiplex-id $ID` (Multiplexes)

### Path B: Encoder logs (most detailed for historical investigation)

**Requirement:** Channel LogLevel must be ≥ WARNING

If available, this is the most reliable source for full historical timelines.

```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --query 'LogLevel' --no-cli-pager --output text
```

If LogLevel is WARNING, ERROR, INFO, or DEBUG:

```
aws logs filter-log-events \
  --log-group-name ElementalMediaLive \
  --log-stream-name-prefix "arn_aws_medialive_${REGION}_${ACCOUNT}_channel_${CHANNEL_ID}" \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '"Setting alert"' \
  --limit 50 --no-cli-pager --output json
```

This returns entries like:
```json
{
  "message": "{\"encoder_pipeline\":0,\"severity\":\"W\",\"timestamp\":\"2026-05-19T14:32:15.123Z\",\"channel_arn\":\"arn:aws:medialive:...\",\"message\":\"Setting alert: Audio PID not found in input\"}"
}
```

Parse the inner JSON `message` field to extract the alert description.

To also see when alerts cleared:
```
  --filter-pattern '?"Setting alert" ?"Clearing alert"'
```

**Advantage:** Full historical timeline across channel restarts, precise
timestamps, per-pipeline detail.

### Path C: EventBridge events

**Requirement:** An EventBridge rule must exist that captures MediaLive events

Check for a rule:
```
aws events list-rules \
  --no-cli-pager --output json \
  --query "Rules[?contains(EventPattern, 'medialive')]"
```

MediaLive emits `MediaLive Channel Alert` events to EventBridge:

| Detail field | Type | Meaning |
|---|---|---|
| `alarm_state` | string | `SET` or `CLEARED` |
| `alarm_id` | string | Unique identifier for this alert instance |
| `alert_type` | string | Category of alert |
| `pipeline` | string | Which pipeline ("0" or "1") |
| `channel_arn` | string | Affected channel ARN |
| `message` | string | Human-readable alert description |

If events are forwarded to CloudWatch Logs:
```
aws logs filter-log-events \
  --log-group-name <TARGET_LOG_GROUP> \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '{ $.detail-type = "MediaLive Channel Alert" && $.detail.channel_arn = "arn:aws:medialive:REGION:ACCOUNT:channel:CHANNEL_ID" }' \
  --limit 50 --no-cli-pager --output json
```

**Advantage:** Does not require channel LogLevel to be enabled.
**Disadvantage:** Only available if someone configured the EventBridge rule.

**EventBridge delivery caveat:** MediaLive EventBridge events are delivered
on a best-effort basis. Alert events (SET/CLEARED) are generally reliable,
but state-change events (STARTING/RUNNING) can be intermittently dropped.
Never rely solely on EventBridge for definitive alert state — corroborate
with `ListAlerts` or encoder logs.

## Decision tree

```
ActiveAlerts > 0 — need alert detail

1. Try ListAlerts API (always available):
   aws medialive list-alerts --resource-arn $CHANNEL_ARN --state SET
   ├─ Returns results → Use alert descriptions directly
   └─ Empty (channel was restarted since alert fired) → Continue

2. Check LogLevel:
   ├─ LogLevel ≥ WARNING → Use Path B (encoder logs)
   │   └─ Query "Setting alert" pattern → Extract alert descriptions
   │
   └─ LogLevel = DISABLED → Cannot use Path B
       │
       3. Check for EventBridge rule:
       ├─ Rule exists → Use Path C (EventBridge events)
       │   └─ Query log group for "MediaLive Channel Alert" events
       │
       └─ No rule → ONLY ListAlerts AVAILABLE
           └─ If ListAlerts also returned empty, report DATA GAP
```

## DATA GAP reporting template

When alert detail cannot be retrieved through any path:

```
DATA GAP: ActiveAlerts = $COUNT for channel $CHANNEL_ID (pipeline $PIPELINE)
but alert detail cannot be retrieved.

Attempted:
  - ListAlerts API: returned empty (alert IDs roll over on channel restart)
  - Encoder logs: LogLevel = DISABLED → logs not available
  - EventBridge: No rule captures "aws.medialive" events

What would be available if configured:
  - At LogLevel ≥ WARNING: "Setting alert" lines in CloudWatch Logs
    identifying the specific alert condition (e.g., "Audio PID not found",
    "Input loss", "Output error")
  - With an EventBridge rule: MediaLive Channel Alert events with
    alert_type, pipeline, and human-readable message

Recommendation: Enable LogLevel = WARNING on this channel. This adds
minimal log volume but enables alert detail retrieval for future
investigations. Note: changing LogLevel requires the channel to be in
IDLE state. Suggest enabling WARNING during the next maintenance window
when the channel can be briefly stopped.
```

## Correlating alerts with metrics

Once alert descriptions are retrieved, correlate with metrics:

| Alert description pattern | Corresponding metric |
|---|---|
| "Input loss on pipeline X" | InputLossSeconds on pipeline X |
| "Audio PID not found" | Check InputVideoFrameRate (video may still work) |
| "Video PID not found" | InputVideoFrameRate = 0 |
| "Output error to ..." | Output4xxErrors or Output5xxErrors on that output group |
| "CC error count exceeds threshold" | ContinuityCounter rising (upstream MC) |
| "Network output error" | NetworkOut drop, Output5xxErrors |
| "Encoder resource constraint" | DroppedFrames, SvqTime near 100% |
| "Pipeline X not locked" | PipelinesLocked = 0 on that pipeline |

## Alert lifecycle

1. Alert condition detected → "Setting alert" log line → ActiveAlerts increments
2. Alert condition persists → no additional log lines (already counted)
3. Alert condition resolves → "Clearing alert" log line → ActiveAlerts decrements
4. Multiple alerts can be active simultaneously (ActiveAlerts can be > 1)

The delta between "Setting" and "Clearing" timestamps is the alert duration.
If no "Clearing" line exists within the investigation window, the alert is
still active at the end of the window.

Alert IDs returned by `ListAlerts` roll over when the channel is restarted.
If you need alert history across restarts, use encoder logs (Path B).
