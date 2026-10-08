# Core CloudWatch Logs Insights queries CP1–CP9

Run in order against `/aws/eks/{cluster}/cluster`. These are query IDs, not scorecard IDs. Default 60 minutes; scan mode 24 hours; maximum 7 days. Record each bounded result in the transient ledger before loading the next shard.

## CP1 — API server scaling events
```text
fields @timestamp, @message
| filter @logStream not like "audit"
| filter @message like "Resetting endpoints for master service"
| sort @timestamp asc
| limit 10000
```

## CP2 — Average LIST latency by request URI
```text
fields @timestamp, @message
| filter @logStream like "kube-apiserver-audit"
| filter ispresent(requestURI)
| filter verb = "list"
| filter verb not like "watch"
| parse requestReceivedTimestamp /\d+-\d+-(?<StartDay>\d+)T(?<StartHour>\d+):(?<StartMinute>\d+):(?<StartSec>\d+).(?<StartMsec>\d+)Z/
| parse stageTimestamp /\d+-\d+-(?<EndDay>\d+)T(?<EndHour>\d+):(?<EndMinute>\d+):(?<EndSec>\d+).(?<EndMsec>\d+)Z/
| fields (StartDay * 86400 + StartHour * 3600 + StartMinute * 60 + StartSec + StartMsec / 1000000) as StartTime,
         (EndDay * 86400 + EndHour * 3600 + EndMinute * 60 + EndSec + EndMsec / 1000000) as EndTime,
         (EndTime - StartTime) as DeltaTime
| stats avg(DeltaTime) as AverageDeltaTime, count(*) as CountTime by requestURI
| sort AverageDeltaTime desc
```

## CP3 — Max LIST latency by request URI

The day-arithmetic formula in CP2/3/4 and later CP14/15/20 is invalid across month boundaries. Split the window or prefer epoch/native metrics.
```text
fields @timestamp, @message
| filter @logStream like "kube-apiserver-audit"
| filter ispresent(requestURI)
| filter verb = "list"
| filter verb not like "watch"
| parse requestReceivedTimestamp /\d+-\d+-(?<StartDay>\d+)T(?<StartHour>\d+):(?<StartMinute>\d+):(?<StartSec>\d+).(?<StartMsec>\d+)Z/
| parse stageTimestamp /\d+-\d+-(?<EndDay>\d+)T(?<EndHour>\d+):(?<EndMinute>\d+):(?<EndSec>\d+).(?<EndMsec>\d+)Z/
| fields (StartDay * 86400 + StartHour * 3600 + StartMinute * 60 + StartSec + StartMsec / 1000000) as StartTime,
         (EndDay * 86400 + EndHour * 3600 + EndMinute * 60 + EndSec + EndMsec / 1000000) as EndTime,
         (EndTime - StartTime) as DeltaTime
| stats max(DeltaTime) as MaxDeltaTime, count(*) as CountTime by requestURI
| sort MaxDeltaTime desc
```

## CP4 — LIST pods latency and traffic by user agent
```text
fields @timestamp, @message
| filter @logStream like "kube-apiserver-audit"
| filter verb == "list"
| filter objectRef.resource == "pods"
| filter objectRef.apiVersion == "v1"
| parse requestReceivedTimestamp /\d+-\d+-(?<StartDay>\d+)T(?<StartHour>\d+):(?<StartMinute>\d+):(?<StartSec>\d+).(?<StartMsec>\d+)Z/
| parse stageTimestamp /\d+-\d+-(?<EndDay>\d+)T(?<EndHour>\d+):(?<EndMinute>\d+):(?<EndSec>\d+).(?<EndMsec>\d+)Z/
| fields (StartDay * 86400 + StartHour * 3600 + StartMinute * 60 + StartSec + StartMsec / 1000000) as StartTime,
         (EndDay * 86400 + EndHour * 3600 + EndMinute * 60 + EndSec + EndMsec / 1000000) as EndTime,
         (EndTime - StartTime) as duration_in_sec
| stats pct(duration_in_sec, 99) as p99_latency_in_sec,
        pct(duration_in_sec, 90) as p90_latency_in_sec,
        pct(duration_in_sec, 50) as p50_latency_in_sec,
        avg(duration_in_sec) as avg_duration,
        count(*) as cnt
        by user.username, userAgent
| sort p99_latency_in_sec desc
```

## CP5 — Top clients listing pods
```text
filter @logStream like "kube-apiserver-audit"
| filter ispresent(requestURI)
| filter verb = "list"
| filter requestURI like "/api/v1/pods"
| stats count(*) as count by userAgent
| sort count desc
| limit 10
```

## CP6 — Total API request count by user agent
```text
fields userAgent, requestURI, @timestamp, @message
| filter @logStream =~ "kube-apiserver-audit"
| stats count(userAgent) as count by userAgent
| sort count desc
| limit 50
```

## CP7 — HTTP response code distribution
```text
fields @timestamp, @message
| filter @logStream like /audit/
| stats count(*) as count by responseStatus.code
| sort count desc
```

## CP8 — API server 5xx errors
```text
fields @timestamp, responseStatus.code, @message
| filter @logStream like /audit/
| filter responseStatus.code >= 500
| limit 50
```

## CP9 — API server 4xx errors
```text
stats count(*) as count by requestURI, verb, responseStatus.code, userAgent
| filter @logStream =~ "kube-apiserver-audit"
| filter responseStatus.code >= 400
| filter responseStatus.code < 500
| sort count desc
```

## Empty-result rule

Empty is not healthy until logging is enabled, delivery delay is excluded, stream naming/filter match is verified, and the window is sufficient. Otherwise mark the dependent signal N/A and raise the visibility finding.