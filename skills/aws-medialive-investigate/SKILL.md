---
name: aws-medialive-investigate
description: >-
  Deep investigation of a single AWS Elemental MediaLive channel. Use when a customer reports a
  MediaLive problem or when evidence points at the encoding layer: input loss, dropped frames,
  fill or black frames in output, active alerts, output 4xx/5xx push errors, pipeline
  desynchronization on STANDARD channels, or schedule and input-switch anomalies, including
  SCTE-35 schedule actions. Covers channel state, per-input-type diagnosis (MediaConnect, RTP/RTMP
  push, pull, Link input devices, SRT), encoding health (ActiveAlerts, DroppedFrames, FillMsec,
  SvqTime), per-output-group analysis, STANDARD pipeline synchronization, and schedule
  verification. Not for upstream transport loss on a MediaConnect flow (use
  aws-mediaconnect-investigate), downstream packaging and origin faults (use
  aws-mediapackage-investigate), or SCTE-35 field meanings (use aws-media-spec-reference).
metadata:
  author: blends
  version: "1.0.0"
  summary: "Read-only investigation of a MediaLive channel: input loss, dropped frames, fill, alerts, output 4xx/5xx, pipeline sync and schedule actions."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaLive"
  aws-devops-agent-skills.technical-domains: "Operations, Observability"
---
# MediaLive Deep Investigation

## Purpose

Perform a comprehensive investigation of a single MediaLive channel when either:
1. Evidence from a broader media pipeline investigation points at the encoding layer
2. The customer asks specifically about a MediaLive channel issue

This skill goes deeper than a metric snapshot — it layers
input-type-specific diagnosis, per-output-group analysis, pipeline sync
evaluation, encoder log retrieval, and schedule verification.

## Prerequisites

- Channel ID known (from the customer, or by enumerating with `aws medialive list-channels`)
- Time window established (the customer's impact window, or the anomaly window
  observed in CloudWatch)
- Upstream MediaConnect (if present) confirmed HEALTHY (see
  aws-mediaconnect-investigate), OR MediaLive is the layer the evidence points at
- Evidence of a MediaLive anomaly

## Investigation checklist

Copy this list into your working notes and tick each step as you complete it. Run the
steps in order; skip a conditional step only when its condition says so, and say so.

- [ ] Step 1: Channel state analysis
- [ ] Step 2: Input diagnosis
- [ ] Step 3: Encoding diagnosis
- [ ] Step 4: Output diagnosis
- [ ] Step 5: Schedule verification
- [ ] Step 6: Compile findings

## Step 1: Channel state analysis

```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --no-cli-pager --output json
```

Extract and evaluate:

Table: [Step 1: Channel state analysis](references/lookup-tables.md#step-1-channel-state-analysis). Load it when you run this step.

### State interpretation

Table: [Step 1: Channel state analysis: State interpretation](references/lookup-tables.md#step-1-channel-state-analysis-state-interpretation). Load it when you run this step.

**Note:** UPDATING is captured in the console but is NOT emitted via
EventBridge. Do not rely on EventBridge state-change events to detect
config updates in progress.

**EventBridge delivery caveat:** MediaLive state-change events are
delivered on a best-effort basis. STARTING/RUNNING events are less
reliable than STOPPING/CREATED/DELETED. For deterministic state checks,
always poll `describe-channel.State` rather than relying on EventBridge
events alone.

### RECOVERING state handling

RECOVERING means MediaLive detected a pipeline failure and is automatically
restarting. During RECOVERING:
- Metrics may gap for 30–120 seconds
- Transient ActiveAlerts are expected
- If RECOVERING persists > 5 minutes → likely stuck; escalate

```
Observed: Channel $ID in RECOVERING state for > 5 minutes.
Expected: RECOVERING typically resolves within 2 minutes.
Question: Is there an underlying resource or configuration issue
preventing successful pipeline restart?
```

### Pipeline count evaluation

| ChannelClass | Expected PipelinesRunningCount | Pipeline failure if |
|---|---|---|
| STANDARD | 2 | < 2 |
| SINGLE_PIPELINE | 1 | < 1 (= 0, channel not encoding) |

A STANDARD channel with PipelinesRunningCount = 1 is degraded but still
operational on a single pipeline. Viewers may not notice until the remaining
pipeline also fails — but redundancy is gone.

## Step 2: Input diagnosis

### Gather input details

For each input in `InputAttachments[]`:

```
aws medialive describe-input --input-id $INPUT_ID \
  --no-cli-pager --output json
```

Extract: `Type`, `State`, `AttachedChannels[]`, `Sources[]`, `MediaConnectFlows[]`

### Per-input-type diagnostic patterns

Read only the section for the input `Type` you found in
[references/input-type-patterns.md](references/input-type-patterns.md)
(MEDIACONNECT, MEDIACONNECT_ROUTER, RTP_PUSH, RTMP_PUSH, RTMP_PULL / URL_PULL,
INPUT_DEVICE, SRT_CALLER). Load it when Step 2 reaches the per-type checks.

### Failover channel handling (ActiveInputFailoverLabel)

If the channel has automatic input failover configured:

```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --query 'InputAttachments[].AutomaticInputFailoverSettings' \
  --no-cli-pager --output json
```

When failover is configured:
- Metrics emit with the `ActiveInputFailoverLabel` dimension
- Query metrics PER failover label to see each input's health independently
- Track failover events by querying `PrimaryInputActive` per pipeline — value
  changes from 1 → 0 indicate a switch away from the primary input
- Correlate `InputVideoFrameRate` and `InputLossSeconds` per
  `ActiveInputFailoverLabel` to determine which input degraded first
- Rapid alternation in `PrimaryInputActive` = both inputs degraded (same pattern as MC flapping)

**Dimension trap**: Adding `ActiveInputFailoverLabel` on a non-failover channel
returns empty data. Only add this dimension when failover is confirmed configured.

### Input metric collection (per-pipeline)

Query with dimensions `ChannelId` + `Pipeline` ("0" and "1" for STANDARD):

Table: [Step 2: Input diagnosis: Input metric collection (per-pipeline)](references/lookup-tables.md#step-2-input-diagnosis-input-metric-collection-per-pipeline). Load it when you run this step.

**Note:** `InputLossSeconds` only applies to RTP Push and MediaConnect
inputs. For other input types, use `NetworkIn = 0` and
`InputVideoFrameRate = 0` as the input-loss indicators.

### Input diagnosis decision tree

```
InputLossSeconds > 0?
  ├─ YES, with upstream MC issues → PROPAGATED from MediaConnect
  ├─ YES, MEDIACONNECT input, MC healthy → MC output → ML input path issue
  ├─ YES, RTP_PUSH input → Source not sending or blocked by security group
  ├─ YES, PULL input → Source URL unreachable or auth failure
  └─ YES, INPUT_DEVICE → Link device disconnected or misconfigured

ChannelInputErrorSeconds > 0, InputLossSeconds = 0?
  → Input arriving but malformed (codec mismatch, resolution mismatch)

NetworkIn = 0?
  → No data reaching channel at all — upstream delivery failure

InputVideoFrameRate unstable or zero?
  → Source signal quality issue (variable frame rate, no video in stream)
```

## Step 3: Encoding diagnosis

Encoding metrics assess the channel's internal processing health.

### Core encoding metrics (per-pipeline)

Dimensions: `ChannelId` + `Pipeline`

Table: [Step 3: Encoding diagnosis: Core encoding metrics (per-pipeline)](references/lookup-tables.md#step-3-encoding-diagnosis-core-encoding-metrics-per-pipeline). Load it when you run this step.

### DroppedFrames analysis

DroppedFrames > 0 means the encoder cannot keep up with the input:
- Check `InputSpecification` from describe-channel — is the input resolution/bitrate
  within the channel's `MaximumBitrate` and `Resolution` specification?
- High-complexity content (fast motion, many scene cuts) with constrained
  `InputSpecification` → expected under peak load
- Sustained DroppedFrames → channel is undersized for this content

### FillMsec analysis

**Dimensions**: `ChannelId` + `Pipeline`

FillMsec measures the duration of inserted fill/black frames in the output,
capped at 60,000 ms (1 minute). After the cap, the metric stays at 60,000
until it drops to zero.

FillMsec > 0 WITH input issues (InputLossSeconds > 0):
→ **PROPAGATED** from input — fill frames replace missing input content

FillMsec > 0 WITHOUT input issues:
→ Encoding pipeline timing issue (PTS discontinuity, GOP alignment problem)
→ Check if a scheduled input switch occurred in the same window

FillMsec > 0 on only ONE pipeline of a STANDARD channel:
→ Single-pipeline issue — possible pipeline-specific processing failure

### SvqTime analysis

SvqTime measures the percentage of time MediaLive has reduced quality
optimizations to maintain real-time output (SVQ = speed versus quality):
- < 50% → comfortable headroom
- 50–80% → normal operation
- > 80% sustained → encoder approaching capacity; quality degradation (ABR ladder affected)
- Near 100% → frames will be dropped imminently; DroppedFrames expected

### Alert detail retrieval

ActiveAlerts > 0 tells you something is wrong but not WHAT.

To get alert details, see [references/alert-retrieval.md](references/alert-retrieval.md).

Three paths:
1. ListAlerts API: `aws medialive list-alerts --resource-arn $CHANNEL_ARN`
   (added October 2025; supports `--state SET` filter for active alerts only)
2. Encoder logs (if LogLevel ≥ WARNING): search for "Setting alert" pattern
3. EventBridge events (if rule configured): `MediaLive Channel Alert` events

If none are available:
```
DATA GAP: ActiveAlerts=$COUNT but alert detail unavailable.
LogLevel=DISABLED and no EventBridge rule captures MediaLive alerts.
Cannot determine the specific alert condition(s).
```

## Step 4: Output diagnosis

### Gather output group names

```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --query 'EncoderSettings.OutputGroups[].{Name:Name,Type:OutputGroupSettings|keys(@)[0]}' \
  --no-cli-pager --output json
```

This returns the OutputGroupName values needed as metric dimensions.

### Per-output-group metrics

For EACH output group, query with dimensions ChannelId + Pipeline + OutputGroupName:

Table: [Step 4: Output diagnosis: Per-output-group metrics](references/lookup-tables.md#step-4-output-diagnosis-per-output-group-metrics). Load it when you run this step.

Pipeline locking (STANDARD channels only) — query with dimensions
`ChannelId` + `Pipeline`:

| Metric | Statistic | Meaning |
|---|---|---|
| PipelinesLocked | Minimum | 0 = at least one eligible pipeline pair out of sync |

### Output error analysis

```
Output5xxErrors > 0?
  ├─ Check downstream service (MediaPackage, S3, RTMP destination)
  ├─ Correlate timing with MP IngressResponseTime / IngressBytes
  └─ If destination is MediaPackage: check MP health first

Output4xxErrors > 0?
  ├─ 401/403 pattern → Authentication/authorization failure at destination
  ├─ 404 pattern → Destination endpoint doesn't exist or wrong URL
  └─ 409 pattern → MediaPackage channel ID conflict or duplicate push

ActiveOutputs = 0 (unexpected)?
  ├─ Check per-output-group InputLossAction setting:
  │   HLS:  EncoderSettings.OutputGroups[].OutputGroupSettings.HlsGroupSettings.InputLossAction
  │   UDP:  ...UdpGroupSettings.InputLossAction
  │   RTMP: ...RtmpGroupSettings.InputLossAction
  │   MSS:  ...MsSmoothGroupSettings.InputLossAction
  │   └─ If InputLossAction = PAUSE_OUTPUT → deliberate pause on input loss (not a bug)
  ├─ Check if all destinations are unreachable (multiple Output5xx)
  └─ Check if channel is in RECOVERING state
```

**Note:** `InputLossAction` is a per-output-group setting, not a global
channel setting. The enum values are `EMIT_OUTPUT` (continue encoding with
fill content) and `PAUSE_OUTPUT` (stop sending output). Different output
groups on the same channel can have different `InputLossAction` settings.

### PipelinesLocked (STANDARD channels only)

**Dimensions**: `ChannelId` + `Pipeline`

PipelinesLocked = 1 → All eligible pipeline pairs are synchronized (healthy)
PipelinesLocked = 0 → At least one eligible pipeline pair has diverged

The metric is emitted at the (ChannelId, Pipeline) granularity. It reflects
the aggregate locking status across all eligible output groups on that
pipeline. Pipeline locking applies to HLS, MediaPackage, MS Smooth, and
UDP output groups.

Causes of sync loss:
- One pipeline experienced transient input loss while the other didn't
- One pipeline is processing more slowly (resource contention)
- After a pipeline restart (RECOVERING), sync may take 30–60 seconds to re-establish

### Destination type-specific checks

When Output4xxErrors, Output5xxErrors or NetworkOut anomalies point at a destination,
read the section for that output group's destination type in
[references/output-destination-checks.md](references/output-destination-checks.md)
(MediaPackage v1, HLS/DASH/MSS to S3, RTMP, UDP/RTP).

## Step 5: Schedule verification

MediaLive channels can have scheduled actions (input switches, SCTE-35
insertions, pause/unpause).

### Check for a schedule

```
aws medialive describe-schedule --channel-id $CHANNEL_ID \
  --no-cli-pager --output json
```

If schedule actions exist in the investigation time window:

Table: [Step 5: Schedule verification: Check for a schedule](references/lookup-tables.md#step-5-schedule-verification-check-for-a-schedule). Load it when you run this step.

### Schedule correlation

If a metric anomaly (FillMsec spike, ActiveOutputs drop, input switch)
aligns with a scheduled action timestamp:
→ The anomaly is DELIBERATE, not a failure
→ Report as: "Metric deviation at [time] correlates with scheduled
[action type] — this is expected behavior, not a fault."

### As-run log verification

If encoder logs are available (LogLevel ≥ INFO), search for schedule
execution entries:

```
aws logs filter-log-events \
  --log-group-name ElementalMediaLive \
  --log-stream-name-prefix "arn_aws_medialive_${REGION}_${ACCOUNT}_channel_${CHANNEL_ID}" \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '"ActionTriggered"' \
  --limit 50 --no-cli-pager --output json
```

See [references/encoder-log-parsing.md](references/encoder-log-parsing.md)
for log format details and as-run entry structure.

## Step 6: Compile findings

Structure each finding as Observed (the value plus the API or metric it came
from), Expected (the threshold or benchmark plus its source), and Question:
why? Do not declare a definitive root cause; surface evidence and the precise
question that follows from it. Report sections:

1. **Channel identity**: ID, state, class, pipelines running, log level
2. **Input health**: Per-input status, type-specific findings, failover state
3. **Encoding health**: Alerts, dropped frames, fill, SvqTime
4. **Output health**: Per-output-group status (4xx/5xx, ActiveOutputs, PipelinesLocked)
5. **Schedule**: Any actions in window and correlation with anomalies
6. **Data gaps**: LogLevel=DISABLED, missing EventBridge rules, etc.
7. **Open questions**: Ranked by severity using the classifications in the steps above

Reference the [channel-health-checklist](references/channel-health-checklist.md)
for the mechanical pass/fail evaluation.

### Before presenting

Check the compiled findings and fix anything that fails before presenting them:

- Every Observed value names the API field or metric it came from, with its dimensions and time window.
- Every Expected value names its source: a threshold, a documented limit, or the resource's own configuration.
- No section asserts a definitive root cause; each finding ends in a question or a named handoff.
- Every signal that was not observable is reported as a DATA GAP with its reason, never as a healthy zero.
- No account IDs, ARNs, secrets or passphrases are reproduced; resources are named by type and name.
- Every metric finding states which Pipeline dimension it came from; a dual-pipeline average is never reported as a pipeline finding.
