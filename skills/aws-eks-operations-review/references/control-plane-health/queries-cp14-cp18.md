# Core CloudWatch Logs Insights queries CP14–CP18

Run in order after CP10–CP13. Query IDs are not scorecard IDs.

## CP14 — KCM request latency by service account
```text
fields @timestamp, @message
| filter @logStream like "kube-apiserver-audit"
| filter user.username like "system:serviceaccount:kube-system:horizontal-pod-autoscaler"
| parse requestReceivedTimestamp /\d+-\d+-(?<StartDay>\d+)T(?<StartHour>\d+):(?<StartMinute>\d+):(?<StartSec>\d+).(?<StartMsec>\d+)Z/
| parse stageTimestamp /\d+-\d+-(?<EndDay>\d+)T(?<EndHour>\d+):(?<EndMinute>\d+):(?<EndSec>\d+).(?<EndMsec>\d+)Z/
| fields (StartDay * 86400 + StartHour * 3600 + StartMinute * 60 + StartSec + StartMsec / 1000000) as StartTime,
         (EndDay * 86400 + EndHour * 3600 + EndMinute * 60 + EndSec + EndMsec / 1000000) as EndTime,
         (EndTime - StartTime) as duration_in_sec
| display requestURI, userAgent, objectRef.resource, objectRef.subresource, duration_in_sec
| sort duration_in_sec desc
```

Iterate the standard controllers listed in the legacy query reference; prefer 1.28+ `workqueue_*` metrics for backpressure and retain this query for attribution.

## CP15 — LIST latency raw per-request
```text
fields @timestamp, @message
| filter @logStream like "kube-apiserver-audit"
| filter requestURI not like "limit"
| filter requestURI not like "continue"
| filter verb = "list"
| parse requestReceivedTimestamp /\d+-\d+-(?<StartDay>\d+)T(?<StartHour>\d+):(?<StartMinute>\d+):(?<StartSec>\d+).(?<StartMsec>\d+)Z/
| parse stageTimestamp /\d+-\d+-(?<EndDay>\d+)T(?<EndHour>\d+):(?<EndMinute>\d+):(?<EndSec>\d+).(?<EndMsec>\d+)Z/
| fields (StartDay * 86400 + StartHour * 3600 + StartMinute * 60 + StartSec + StartMsec / 1000000) as StartTime,
         (EndDay * 86400 + EndHour * 3600 + EndMinute * 60 + EndSec + EndMsec / 1000000) as EndTime,
         (EndTime - StartTime) as duration_in_sec
| display requestURI, userAgent, objectRef.resource, objectRef.subresource,
          duration_in_sec, requestReceivedTimestamp, stageTimestamp
| sort requestReceivedTimestamp desc
```

## CP16 — Eviction events by EKS node manager
```text
fields @logStream, @timestamp, @message
| filter @logStream like /^kube-apiserver-audit/
| sort @timestamp desc
| filter user.username == "eks:node-manager" and requestURI like "eviction" and requestURI like "pod"
| limit 999
```

## CP17 — Pods failing eviction (count)
```text
fields @timestamp, @message
| stats count(*) as count by objectRef.name
| filter @logStream like /audit/
| filter user.username == "eks:node-manager" and requestURI like "eviction" and requestURI like "pod"
| sort count desc
```

## CP18 — Unscheduled pods in scheduler log
```text
fields timestamp, pod, err, @message
| filter @logStream like "scheduler"
| filter @message like "Unable to schedule pod"
| parse @message /^.(?<date>\d{4})\s+(?<timestamp>\d+:\d+:\d+\.\d+)\s+\S*\s+\S+\]\s\"(.*?)\"\s+pod=(?<pod>\"(.*?)\")\s+err=(?<err>\"(.*?)\")/
| stats count(*) as count by pod, err
| sort count desc
```

On EKS 1.28+, prefer `scheduler_pending_pods{queue="unschedulable"}` and use the log query for per-pod cause. If structured scheduler logs make the regex empty, use the structured level/message fallback from the legacy query reference.

## Empty-result rule

Verify logging/streams, delivery delay, filters, and time window before interpreting empty output. Missing logging makes log-derived signals N/A, not PASS.