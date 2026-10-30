# MediaLive Deep Investigation: Lookup Tables

Metric catalogs, status tables and field tables relocated from SKILL.md so they load
only when the step that uses them runs. Each heading names the SKILL.md step and
subsection the table belongs to; the surrounding instructions stay in SKILL.md.

## Step 1: Channel state analysis

| Field | Healthy | Unhealthy | Notes |
|---|---|---|---|
| `State` | RUNNING | IDLE, CREATE_FAILED, RECOVERING, STOPPING, DELETING | IDLE = not started; RECOVERING = auto-restart |
| `ChannelClass` | STANDARD or SINGLE_PIPELINE | — | Determines expected PipelinesRunningCount |
| `PipelinesRunningCount` | 2 (STANDARD) or 1 (SINGLE_PIPELINE) | Less than expected | Pipeline failure |
| `LogLevel` | ERROR, WARNING, INFO, DEBUG | DISABLED | DISABLED = no encoder logs available |
| `InputAttachments[]` | Non-empty | — | Lists all attached inputs |
| `Destinations[]` | Non-empty | — | Lists all output destinations |
| `EncoderSettings.OutputGroups[]` | Non-empty | — | Output group names for metric dimensions |

## Step 1: Channel state analysis: State interpretation

| State | Meaning | Action |
|---|---|---|
| RUNNING | Normal operation | Proceed with metric analysis |
| IDLE | Channel not started — metrics will not emit | Tell customer; this is not a failure |
| CREATE_FAILED | Channel failed to create | Check error reason in console events |
| RECOVERING | Automatic restart in progress | Expect metric gaps; wait 2–5 min and re-check |
| UPDATING | Config change in progress | Transient; re-check after completion |
| STOPPING/DELETING | Being stopped or removed | Explains sudden metric drop |

## Step 2: Input diagnosis: Input metric collection (per-pipeline)

| Metric | Statistic | Meaning |
|---|---|---|
| InputLossSeconds | Sum | Any > 0 = input not received for that duration |
| ChannelInputErrorSeconds | Sum | Any > 0 = input received but with errors |
| NetworkIn | Average | Should match source output bitrate |
| InputVideoFrameRate | Average, Minimum | Should be stable at source frame rate |
| RtpPacketsReceived | Sum | RTP inputs only — packet count baseline |
| RtpPacketsLost | Sum | RTP inputs only — any > 0 = network loss |
| RtpPacketsRecoveredViaFec | Sum | RTP inputs only — FEC working (not an error) |

## Step 3: Encoding diagnosis: Core encoding metrics (per-pipeline)

| Metric | Statistic | Healthy | Unhealthy | Severity |
|---|---|---|---|---|
| ActiveAlerts | Maximum | 0 | > 0 | Critical |
| DroppedFrames | Sum | 0 | > 0 | High — encoder exhaustion |
| FillMsec | Maximum | 0 | > 0 | High — content gap in output |
| SvqTime | Maximum | < 80% of period | Sustained near 100% | Medium — quality at risk |

## Step 4: Output diagnosis: Per-output-group metrics

| Metric | Statistic | Meaning |
|---|---|---|
| Output4xxErrors | Sum | Destination rejecting pushes (auth, config, not found) |
| Output5xxErrors | Sum | Destination server errors (downstream overloaded/down) |
| ActiveOutputs | Minimum | Below expected = output delivery failing |
| NetworkOut | Average | Should match encoding config sum |

## Step 5: Schedule verification: Check for a schedule

| Action type | What it does | Metric impact |
|---|---|---|
| `INPUT_SWITCH` | Switches active input | Brief FillMsec spike during switch (normal) |
| `PAUSE` | Pauses output pipeline(s) | ActiveOutputs → 0 (deliberate) |
| `UNPAUSE` | Resumes output pipeline(s) | ActiveOutputs resumes |
| `SCTE35_SPLICE_INSERT` | Ad insertion signal | No metric impact (signal only) |
| `SCTE35_RETURN_TO_NETWORK` | Return from ad | No metric impact |
| `INPUT_PREPARE` | Pre-loads next input | No metric impact |
