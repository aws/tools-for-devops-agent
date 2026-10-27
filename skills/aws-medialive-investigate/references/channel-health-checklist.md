# MediaLive Channel Health Checklist

Mechanical pass/fail checklist for evaluating a single MediaLive channel.
Run each check in order. Metrics only emit while channel State = RUNNING.

## Prerequisites

- Channel ID known
- Time window established
- Dimension discovery completed for all metrics below
- Channel confirmed in RUNNING state (IDLE/RECOVERING = skip metric checks)

## Checklist

### 1. Channel state

```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --query '{State:State,Class:ChannelClass,Pipelines:PipelinesRunningCount,LogLevel:LogLevel}' \
  --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| State = RUNNING | ✅ | Any other state | Critical (if unexpected) |
| PipelinesRunningCount = 2 (STANDARD) | ✅ | < 2 | Critical — pipeline failure |
| PipelinesRunningCount = 1 (SINGLE_PIPELINE) | ✅ | = 0 | Critical — channel not encoding |
| LogLevel ≠ DISABLED | ✅ | = DISABLED | DATA GAP (not a severity) |

If State ≠ RUNNING: metrics will not emit. Report state and stop metric checks.
If RECOVERING: wait 2–5 min and re-check before concluding failure.

### 2. Input health (per-pipeline)

Dimensions: ChannelId + Pipeline ("0", "1" for STANDARD; "0" for SINGLE_PIPELINE)

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| InputVideoFrameRate Average = expected (29.97/30/59.94/60/25/50) | ✅ | Unstable or zero | Critical |
| InputVideoFrameRate variance < 10% | ✅ | High variance | Medium |
| InputLossSeconds Sum = 0 | ✅ | Sum > 0 | Critical — input not received |
| ChannelInputErrorSeconds Sum = 0 | ✅ | Sum > 0 | High — input errors |
| NetworkIn Average > 0 | ✅ | = 0 | Critical — no data arriving |
| NetworkIn Average ≈ expected source bitrate | ✅ | Significantly lower | High |

**Note:** InputLossSeconds only applies to RTP Push and MediaConnect inputs.
For other input types, use NetworkIn = 0 and InputVideoFrameRate = 0 as
the input-loss indicators.

For failover channels, additionally query with `ActiveInputFailoverLabel` per label.

### 3. Encoding health (per-pipeline)

Dimensions: ChannelId + Pipeline

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| ActiveAlerts Maximum = 0 | ✅ | > 0 | Critical — alert condition active |
| DroppedFrames Sum = 0 | ✅ | Sum > 0 | High — encoder exhaustion |
| SvqTime Maximum < 80% of period | ✅ | Sustained > 80% | Medium — quality at risk |

### 4. Fill frame analysis (per-pipeline)

Dimensions: ChannelId + Pipeline

| Check | PASS | FAIL context | Severity |
|---|---|---|---|
| FillMsec Maximum = 0 | ✅ | > 0 WITH InputLossSeconds > 0 | High (PROPAGATED from input) |
| FillMsec Maximum = 0 | ✅ | > 0 WITHOUT input issues | High (encoding pipeline issue) |
| FillMsec Maximum = 0 | ✅ | > 0 aligned with scheduled INPUT_SWITCH | Informational (expected) |

FillMsec is capped at 60,000 ms (1 minute). After the cap, the metric
stays at 60,000 until it drops to zero.

### 5. Output health (per-pipeline, per-output-group)

Dimensions: ChannelId + Pipeline + OutputGroupName

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Output4xxErrors Sum = 0 | ✅ | Sum > 0 | High — destination rejecting |
| Output5xxErrors Sum = 0 | ✅ | Sum > 0 | Critical — downstream server errors |
| ActiveOutputs Minimum > 0 | ✅ | = 0 (unexpected) | Critical — output delivery stopped |
| ActiveOutputs Minimum = 0 (InputLossAction=PAUSE_OUTPUT) | Expected | — | Informational (deliberate) |

**InputLossAction check:** This is a per-output-group setting, not a global
channel setting. Check each output group type:

```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --query 'EncoderSettings.OutputGroups[].{Name:Name,InputLossAction:OutputGroupSettings.*.InputLossAction|[0]}' \
  --no-cli-pager --output json
```

Values: `EMIT_OUTPUT` (continue with fill content) or `PAUSE_OUTPUT` (stop
sending). The setting lives at paths like:
- `HlsGroupSettings.InputLossAction`
- `UdpGroupSettings.InputLossAction`
- `RtmpGroupSettings.InputLossAction`
- `MsSmoothGroupSettings.InputLossAction`

### 6. Pipeline synchronization (STANDARD channels only)

Dimensions: ChannelId + Pipeline

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| PipelinesLocked Minimum = 1 | ✅ | = 0 | High — pipelines out of sync |

PipelinesLocked is emitted at the (ChannelId, Pipeline) granularity and
reflects the aggregate locking status across all eligible output groups
(HLS, MediaPackage, MS Smooth, UDP) on that pipeline. A value of 0 means
at least one eligible pipeline pair is not synchronized.

### 7. Network output

Dimensions: ChannelId + Pipeline

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| NetworkOut Average > 0 | ✅ | = 0 | Critical — no encoded output |
| NetworkOut Average ≈ sum of encoding bitrates | ✅ | Significantly lower | High |

## Exceptions and deliberate behaviors

Before classifying a check as FAIL, verify:

- **InputLossAction = PAUSE_OUTPUT**: ActiveOutputs = 0 is the CONFIGURED
  behavior when input is lost. Check the per-output-group setting (e.g.,
  `HlsGroupSettings.InputLossAction`). Different output groups on the same
  channel can have different settings.
- **Scheduled PAUSE action**: ActiveOutputs = 0 may be a scheduled pause.
  Check `describe-schedule` for actions in the window.
- **Scheduled INPUT_SWITCH**: Brief FillMsec spike (100–500ms) during switch is normal.
- **RECOVERING state**: Transient metric gaps and ActiveAlerts during recovery
  are expected — not a new incident unless sustained > 5 min.
- **Channel just started**: First 10–30 seconds after start may show transient
  alerts and unstable metrics as pipelines initialize.

## Summary template

```
Channel Health: [ALL PASS / DEGRADED / CRITICAL FAILURE]
Channel: $CHANNEL_ID | Class: [STANDARD/SINGLE_PIPELINE] | State: [state]
Pipelines: [X/expected] | LogLevel: [level]

Checks passed: X/Y
First failure: [metric] at [severity] — [brief description]

Critical findings:
  - [list Critical-severity FAILs]

High findings:
  - [list High-severity FAILs]

Data gaps:
  - [list unavailable surfaces with reasons]
```
