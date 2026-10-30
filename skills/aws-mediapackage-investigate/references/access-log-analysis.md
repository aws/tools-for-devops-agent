# MediaPackage Access Log Analysis

Reference for querying and interpreting MediaPackage access logs in
CloudWatch Logs. Covers both v1 (native config) and v2 (Vended Logs)
with their different field naming conventions.

## Log location

### v1 access logs

Configured per-channel via `configure-logs`. Check configuration:

```
aws mediapackage describe-channel --id $CHANNEL_ID \
  --query '{IngressLogs:IngressAccessLogs,EgressLogs:EgressAccessLogs}' \
  --no-cli-pager --output json
```

Default log group names (created by the `AWSServiceRoleForMediaPackage`
service-linked role):
- `/aws/MediaPackage/IngressAccessLogs`
- `/aws/MediaPackage/EgressAccessLogs`

### v2 access logs (Vended Logs)

v2 uses CloudWatch Vended Logs — the customer configures delivery via
`put-delivery-source`, `put-delivery-destination`, and `create-delivery`.
Destinations can be CloudWatch Logs, S3, or Firehose (up to 3 deliveries
per log type per channel group).

Discover configured deliveries:

```
aws logs describe-delivery-sources \
  --no-cli-pager --output json
```

Filter for `resourceArn` containing `mediapackagev2`.

## Log schemas

### v1 egress log entry (camelCase)

```json
{
  "timestamp": "2026-05-19T14:32:15.293656Z",
  "clientIp": "198.51.100.10",
  "processingTime": 0.445,
  "statusCode": "200",
  "receivedBytes": 468,
  "sentBytes": 2587370,
  "method": "GET",
  "request": "https://abc123.mediapackage.us-east-1.amazonaws.com/out/v1/my_endpoint/index.m3u8",
  "protocol": "HTTP/1.1",
  "userAgent": "Mozilla/5.0...",
  "account": "123456789012",
  "channelId": "my-channel",
  "channelArn": "arn:aws:mediapackage:us-east-1:123456789012:channels/my-channel",
  "domainName": "abc123.mediapackage.us-east-1.amazonaws.com",
  "requestId": "abc123-def456",
  "endpointId": "my-endpoint",
  "endpointArn": "arn:aws:mediapackage:us-east-1:123456789012:origin_endpoints/my-endpoint"
}
```

**v1 ingress logs** have the same general shape but are expected to lack
`endpointId` and `endpointArn` fields (ingress is per-channel, not
per-endpoint). **Caveat:** AWS does not publish a separate ingress-only
schema; this is operationally observed behavior, not a contractual
guarantee. Do not hard-depend on these fields being absent — check for
their presence before assuming the log version.

**Important:** `statusCode` is a STRING ("200", "404"), not an integer.
Logs Insights queries must compare as strings or use explicit casting.

### v2 access log entry (snake_case)

```json
{
  "event_timestamp": "2026-05-19T14:32:15.789Z",
  "resource_arn": "arn:aws:mediapackagev2:us-east-1:123456789012:channelGroup/my-group",
  "client_ip": "198.51.100.10",
  "time_to_first_byte": 0.445,
  "status_code": "200",
  "received_bytes": 468,
  "sent_bytes": 2587370,
  "method": "GET",
  "request": "https://abc123.egress.mediapackagev2.us-east-1.amazonaws.com/out/v1/my-group/my-channel/my-endpoint/index.mpd",
  "request_query_params": "aws.manifestfilter=...",
  "protocol": "HTTP/1.1",
  "user_agent": "Mozilla/5.0...",
  "account": "123456789012",
  "channel_id": "my-channel",
  "channel_arn": "arn:aws:mediapackagev2:us-east-1:123456789012:channelGroup/my-group/channel/my-channel",
  "domain_name": "abc123.egress.mediapackagev2.us-east-1.amazonaws.com",
  "request_id": "mno345-pqr678",
  "endpoint_id": "my-endpoint",
  "endpoint_arn": "arn:aws:mediapackagev2:...",
  "channel_group_id": "my-group",
  "manifest_name": "index",
  "manifest_type": "DASH"
}
```

v2 ingress logs additionally include `input_type` (HLS/CMAF) and
`input_index` ("1"/"2").

**Important:** `status_code` is a STRING, same as v1. The fields `method`
and `account` are the same name in both v1 and v2.

## Field rename map (v1 → v2)

v1 uses camelCase; v2 uses snake_case for most fields. Some field names
change entirely. When writing Logs Insights queries, use the exact field
names for the version.

| Concept | v1 field | v2 field | Notes |
|---|---|---|---|
| Timestamp | `timestamp` | `event_timestamp` | Name changes |
| Client IP | `clientIp` | `client_ip` | Case change |
| Processing time | `processingTime` | `time_to_first_byte` | Name changes |
| Status code | `statusCode` | `status_code` | Both are strings |
| Bytes received | `receivedBytes` | `received_bytes` | Case change |
| Bytes sent | `sentBytes` | `sent_bytes` | Case change |
| HTTP method | `method` | `method` | Same in both |
| Request URL | `request` | `request` | Same in both |
| Protocol | `protocol` | `protocol` | Same in both |
| User agent | `userAgent` | `user_agent` | Case change |
| Account | `account` | `account` | Same in both |
| Channel ID | `channelId` | `channel_id` | Case change |
| Channel ARN | `channelArn` | `channel_arn` | Case change |
| Domain name | `domainName` | `domain_name` | Case change |
| Request ID | `requestId` | `request_id` | Case change |
| Endpoint ID | `endpointId` | `endpoint_id` | Case change |
| Endpoint ARN | `endpointArn` | `endpoint_arn` | Case change |
| Channel group | — | `channel_group_id` | v2 only |
| Resource ARN | — | `resource_arn` | v2 only |
| Manifest name | — | `manifest_name` | v2 only |
| Manifest type | — | `manifest_type` | v2 only (HLS/DASH) |
| Query params | — | `request_query_params` | v2 only |
| Input type | — | `input_type` | v2 ingress only (HLS/CMAF) |
| Input index | — | `input_index` | v2 ingress only ("1"/"2") |

## Version detection in logs

Before running queries, determine whether you're querying v1 or v2 logs.
Check a sample entry:

```
fields @timestamp, @message
| limit 1
```

If the message contains `clientIp` → v1 format (camelCase).
If the message contains `client_ip` → v2 format (snake_case).

## CloudWatch Logs Insights query templates

### 4xx breakdown by path (v1)

```
filter statusCode >= "400" and statusCode < "500"
| stats count(*) as errorCount by statusCode, request
| sort errorCount desc
| limit 20
```

### 4xx breakdown by path (v2)

```
filter status_code >= "400" and status_code < "500"
| stats count(*) as errorCount by status_code, request
| sort errorCount desc
| limit 20
```

### 5xx time series (v1)

```
filter statusCode >= "500"
| stats count(*) as errors by bin(1m)
| sort @timestamp asc
```

### 5xx time series (v2)

```
filter status_code >= "500"
| stats count(*) as errors by bin(1m)
| sort @timestamp asc
```

### Latency percentiles (v1)

```
stats avg(processingTime) as avg_ms,
      pct(processingTime, 50) as p50,
      pct(processingTime, 95) as p95,
      pct(processingTime, 99) as p99,
      max(processingTime) as max_ms
by bin(5m)
| sort @timestamp asc
```

### Latency percentiles (v2)

```
stats avg(time_to_first_byte) as avg_ms,
      pct(time_to_first_byte, 50) as p50,
      pct(time_to_first_byte, 95) as p95,
      pct(time_to_first_byte, 99) as p99,
      max(time_to_first_byte) as max_ms
by bin(5m)
| sort @timestamp asc
```

### Top requesting client IPs (v1)

```
stats count(*) as requests by clientIp
| sort requests desc
| limit 20
```

### Top requesting client IPs (v2)

```
stats count(*) as requests by client_ip
| sort requests desc
| limit 20
```

### Error requests from specific IP (v1)

```
filter clientIp = "198.51.100.10" and statusCode >= "400"
| fields timestamp, method, request, statusCode, processingTime
| sort timestamp desc
| limit 50
```

### Error requests from specific IP (v2)

```
filter client_ip = "198.51.100.10" and status_code >= "400"
| fields event_timestamp, method, request, status_code, time_to_first_byte
| sort event_timestamp desc
| limit 50
```

### CDN authorization failures (v2 only)

v2 access logs may include CDN authorization fields when configured.
CDN auth configuration is on the origin endpoint **policy** (retrieved
via `get-origin-endpoint-policy`), not on the endpoint object itself.

```
filter status_code = "403"
| stats count(*) as failures by client_ip
| sort failures desc
```

If `cdn_authorization_status` and `cdn_authorization_status_details`
fields are present in the logs, use them for targeted diagnosis:

```
filter status_code = "403"
| fields event_timestamp, client_ip, request, status_code
| sort event_timestamp desc
| limit 50
```

### ForceEndpointError 404s vs genuine 404s (v2)

```
filter status_code = "404"
| stats count(*) as count by request
| sort count desc
| limit 20
```

If all 404s concentrate on the same manifest paths → likely
ForceEndpointError behavior (check `get-origin-endpoint` for
`ForceEndpointErrorConfiguration`). If 404s scatter across varied
paths → likely wrong URLs from players.

**Note:** `STALE_MANIFEST` ForceEndpointError only fires on actual
encoder/path failures; orderly MediaLive stops send `EXT-X-ENDLIST`
and convert to VOD instead of triggering 404s.

### Ingest health per endpoint (v1 ingress logs)

```
filter method = "PUT"
| stats count(*) as requests,
        sum(statusCode = "200") as success,
        sum(statusCode >= "400") as errors
by bin(1m)
| sort @timestamp asc
```

### Manifest vs segment breakdown (v2)

v2 logs include `manifest_name` and `manifest_type`:

```
filter status_code >= "400"
| stats count(*) as errors by manifest_type, status_code
| sort errors desc
```

This can also be correlated with the CloudWatch `RequestType` dimension
(manifest vs segment) and the `OutputType` dimension (HLS/DASH/MSS/CMAF).

**Note:** AWS docs may spell the output-type dimension as `OuputType`
(missing a 't'). CloudWatch dimension keys are case-sensitive — check
both spellings when correlating metrics with log data.

### Slow requests (v1)

```
filter processingTime > 2.0
| fields timestamp, clientIp, request, statusCode, processingTime
| sort processingTime desc
| limit 50
```

### Slow requests (v2)

```
filter time_to_first_byte > 2.0
| fields event_timestamp, client_ip, request, status_code, time_to_first_byte
| sort time_to_first_byte desc
| limit 50
```

## Running Logs Insights queries via CLI

```
aws logs start-query \
  --log-group-name $LOG_GROUP \
  --start-time $START_EPOCH \
  --end-time $END_EPOCH \
  --query-string '<QUERY>' \
  --no-cli-pager --output json
```

Returns a `queryId`. Retrieve results:

```
aws logs get-query-results \
  --query-id $QUERY_ID \
  --no-cli-pager --output json
```

Poll until `status` = `Complete` (typically 5–30 seconds).

## Diagnostic patterns

### Distinguishing CDN issues from origin issues

If 4xx errors concentrate on specific `clientIp` (v1) or `client_ip` (v2)
values → likely CDN configuration issue on specific edge nodes.

If 4xx errors span all client IPs → origin-side issue (MP config, auth,
content availability).

### Correlating logs with metrics

Access logs provide per-request detail that metrics aggregate:
- Metrics show "4xx count = 150 in 5 minutes"
- Logs show "all 150 were 403 on /manifest.m3u8 from CDN IP 198.51.100.10"

Always start with metrics for overview, then drill into logs for specifics.

When correlating v2 logs with CloudWatch metrics by output format, note
the potential dimension spelling inconsistency (`OutputType` vs `OuputType`
in the AWS docs). Query both defensively.

### Time correlation

v1 `timestamp` / v2 `event_timestamp` is the request completion time (not
start time). For latency correlation, subtract `processingTime` (v1) or
`time_to_first_byte` (v2) to estimate request start time. This matters
for correlating with upstream ingest timing from MediaLive.
