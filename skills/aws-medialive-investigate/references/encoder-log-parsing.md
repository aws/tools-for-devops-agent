# MediaLive Encoder Log Parsing

Reference for reading and interpreting MediaLive encoder logs in
CloudWatch Logs. These logs are the PRIMARY source of alert detail
and schedule execution confirmation.

## Log group name

The log group is named `ElementalMediaLive` (fixed name).

**NOT** `/aws/MediaLive/...` or `/aws/medialive/...` — these patterns
are wrong and will return no results.

```
aws logs describe-log-groups \
  --log-group-name-prefix ElementalMediaLive \
  --limit 1 --no-cli-pager --output json
```

If the log group does not exist:
- Logging has never been enabled for any channel in this account/region
- OR the log group was manually deleted
- Report as DATA GAP

## Log stream naming convention

Each channel pipeline has its own log stream:

```
arn_aws_medialive_<REGION>_<ACCOUNT_ID>_channel_<CHANNEL_ID>_<PIPELINE_INDEX>
```

Example:
```
arn_aws_medialive_us-east-1_123456789012_channel_1234567_0
arn_aws_medialive_us-east-1_123456789012_channel_1234567_1
```

- Pipeline 0 = first pipeline (always exists)
- Pipeline 1 = second pipeline (STANDARD channels only)

To query both pipelines, use the channel prefix:
```
--log-stream-name-prefix "arn_aws_medialive_${REGION}_${ACCOUNT}_channel_${CHANNEL_ID}"
```

## LogLevel and what it controls

Check current LogLevel:
```
aws medialive describe-channel --channel-id $CHANNEL_ID \
  --query 'LogLevel' --no-cli-pager --output text
```

| LogLevel setting | Severity letters logged | Alert detail available |
|---|---|---|
| DISABLED | Nothing | ❌ No encoder logs at all |
| ERROR | E (Critical), F (Fatal) | ⚠️ Only critical/fatal alerts |
| WARNING | W (Warning) + above | ✅ Alert set/clear detail available |
| INFO | I (Info) + above | ✅ Full detail + schedule execution |
| DEBUG | D (Debug) + above | ✅ Maximum detail (very verbose) |

**Important terminology note:** The AWS documentation labels the log
level collected by `LogLevel=ERROR` as "Critical" and "Fatal" — not
"Error". The severity letter `E` in the JSON corresponds to what AWS
docs call "Critical", and `F` corresponds to "Fatal". Always filter
by the single-character severity code (`$.severity = "E"`) in queries,
never by the human-readable word.

**Minimum for alert retrieval: WARNING**
**Minimum for schedule as-run verification: INFO**

If LogLevel = DISABLED:
```
DATA GAP: MediaLive channel $CHANNEL_ID has LogLevel=DISABLED.
Encoder logs are unavailable. Alert detail (what caused ActiveAlerts > 0)
and schedule execution history cannot be retrieved.
If logging were enabled at WARNING or higher, "Setting alert" and
"Clearing alert" lines would explain the specific alert conditions.
```

## Log entry structure

Each log entry is a JSON object:

```json
{
  "encoder_pipeline": 0,
  "severity": "W",
  "timestamp": "2026-05-19T14:32:15.123Z",
  "channel_arn": "arn:aws:medialive:us-east-1:123456789012:channel:1234567",
  "logger_name": "",
  "message": "Setting alert: Audio PID not found in input"
}
```

| Field | Type | Notes |
|---|---|---|
| `encoder_pipeline` | integer | 0 or 1 — which pipeline emitted this log |
| `severity` | string | Single character: D, I, W, E, F (see table below) |
| `timestamp` | string | ISO 8601 with milliseconds |
| `channel_arn` | string | Full channel ARN |
| `logger_name` | string | Usually empty; may contain component name |
| `message` | string | Human-readable log message |

## Severity letters

| Letter | AWS doc label | Meaning | Collected by LogLevel ≥ |
|---|---|---|---|
| D | Debug | Frame-level processing detail (very verbose) | DEBUG |
| I | Info | State transitions, schedule execution | INFO |
| W | Warning | Alerts set/cleared, degraded conditions | WARNING |
| E | Critical | Errors requiring attention, failed operations | ERROR |
| F | Fatal | Unrecoverable errors, pipeline crash | ERROR |

**Always filter by the single letter in queries**, not by the AWS doc
label word. The letters D/I/W/E/F appear in the JSON `severity` field.

## Alert lines (the most diagnostically valuable entries)

### Setting alert pattern

When MediaLive sets an alert (ActiveAlerts increments):

```
"message": "Setting alert: <ALERT_DESCRIPTION>"
```

The full format in encoder logs is:
```
"message": "Setting alert [<code>] [<context>] [<key>] [<description>] [Setting]"
```

Common alert descriptions:

| Alert text | Meaning | Typical cause |
|---|---|---|
| `Audio PID not found in input` | Expected audio PID missing from TS | Source encoder config change or TS error |
| `Video PID not found in input` | Expected video PID missing from TS | Source not sending video |
| `Input loss on pipeline X` | No data on input | Upstream source or network failure |
| `Output error to <destination>` | Cannot push to output destination | Destination unreachable or rejecting |
| `CC error count exceeds threshold` | TR 101 290 P1 errors from source | Source encoder producing bad TS |
| `Network output error` | Network-level output failure | Destination DNS/routing/firewall |
| `Encoder resource constraint` | Processing resources exhausted | Channel undersized for content |
| `Pipeline X not locked` | Pipeline sync lost | Single-pipeline disruption |

### Clearing alert pattern

When MediaLive clears an alert (ActiveAlerts decrements):

```
"message": "Clearing alert: <ALERT_DESCRIPTION>"
```

The description matches the corresponding "Setting alert" line.

### Query for alert lines

```
aws logs filter-log-events \
  --log-group-name ElementalMediaLive \
  --log-stream-name-prefix "arn_aws_medialive_${REGION}_${ACCOUNT}_channel_${CHANNEL_ID}" \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '"Setting alert"' \
  --limit 50 --no-cli-pager --output json
```

To get both set and clear events:
```
  --filter-pattern '?"Setting alert" ?"Clearing alert"'
```

## Schedule execution entries (as-run log)

As-run logs are produced **regardless of LogLevel setting** — they are
always available if the channel has run. They use a separate log stream
with the `_as_run` suffix.

When a scheduled action executes (also visible in encoder logs at
LogLevel ≥ INFO):

```
"message": "ActionTriggered: <ACTION_TYPE> at <TIMESTAMP>"
```

Or for input switches:
```
"message": "Input switch to <INPUT_ATTACHMENT_NAME> completed"
```

### Query for schedule execution

```
aws logs filter-log-events \
  --log-group-name ElementalMediaLive \
  --log-stream-name-prefix "arn_aws_medialive_${REGION}_${ACCOUNT}_channel_${CHANNEL_ID}" \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '?"ActionTriggered" ?"Input switch"' \
  --limit 50 --no-cli-pager --output json
```

### SCTE-35 entries

SCTE-35 splice insert/return events appear as:

```
"message": "SCTE-35 splice_insert: event_id=<ID>, pts=<PTS>"
"message": "SCTE-35 return_to_network: event_id=<ID>"
```

Query:
```
  --filter-pattern '"SCTE-35"'
```

## Input switch entries

When the channel switches inputs (automatic failover or scheduled):

```
"message": "Input switch from <OLD_INPUT> to <NEW_INPUT>"
```

Or for failover:
```
"message": "Automatic input failover triggered: switching to <INPUT_NAME>"
```

## Error entries

Critical or fatal-level entries that explain pipeline crashes:

```
aws logs filter-log-events \
  --log-group-name ElementalMediaLive \
  --log-stream-name-prefix "arn_aws_medialive_${REGION}_${ACCOUNT}_channel_${CHANNEL_ID}" \
  --start-time $START_MS --end-time $END_MS \
  --filter-pattern '{ $.severity = "E" || $.severity = "F" }' \
  --limit 50 --no-cli-pager --output json
```

**Note:** Severity `E` corresponds to what AWS docs call "Critical"
(not "Error"). Severity `F` corresponds to "Fatal". Both are collected
when `LogLevel = ERROR` or higher.

## Practical query sequence for investigation

1. **First**: Check if logs exist at all
   ```
   aws logs describe-log-groups --log-group-name-prefix ElementalMediaLive --limit 1 --no-cli-pager
   ```

2. **Second**: Check LogLevel on the channel
   ```
   aws medialive describe-channel --channel-id $ID --query 'LogLevel' --no-cli-pager --output text
   ```

3. **Third**: Get alert detail (if LogLevel ≥ WARNING)
   ```
   --filter-pattern '?"Setting alert" ?"Clearing alert"'
   ```

4. **Fourth**: Get critical and fatal entries
   ```
   --filter-pattern '{ $.severity = "E" || $.severity = "F" }'
   ```

5. **Fifth** (if relevant): Get schedule execution and input switches
   ```
   --filter-pattern '?"ActionTriggered" ?"Input switch" ?"SCTE-35"'
   ```

## Time format conversion

CloudWatch Logs `--start-time` and `--end-time` use UNIX milliseconds:

```bash
# Convert ISO 8601 to milliseconds
date -d "2026-05-19T14:00:00Z" +%s000
# Or on macOS:
date -j -f "%Y-%m-%dT%H:%M:%SZ" "2026-05-19T14:00:00Z" +%s000
```

The agent should compute these from the investigation time window.
