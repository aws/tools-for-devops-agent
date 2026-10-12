# Triggered diagnostic queries CP19–CP25

Load only when an auth, write-path, change-correlation, WATCH, mutation-attribution, or anonymous-access signal requires diagnosis. These query IDs are not scorecard IDs.

## CP19 — Denied / forbidden requests
```text
fields @timestamp, user.username, verb, objectRef.resource, objectRef.namespace, responseStatus.code, responseStatus.reason
| filter @logStream like /^kube-apiserver-audit/
| filter responseStatus.code = 403
| stats count(*) as denied by user.username, verb, objectRef.resource
| sort denied desc
```
Authenticator denials:
```text
fields @logStream, @timestamp, @message
| filter @logStream like /authenticator/
| filter @message like "denied"
| sort @timestamp desc
| limit 50
```

## CP20 — Slow mutating requests
```text
fields @timestamp, @message
| filter @logStream like "kube-apiserver-audit"
| filter verb like /(create|update|patch|delete)/
| parse requestReceivedTimestamp /\d+-\d+-(?<SD>\d+)T(?<SH>\d+):(?<SM>\d+):(?<SS>\d+).(?<SmS>\d+)Z/
| parse stageTimestamp /\d+-\d+-(?<ED>\d+)T(?<EH>\d+):(?<EM>\d+):(?<ES>\d+).(?<EmS>\d+)Z/
| fields (SD*86400+SH*3600+SM*60+SS+SmS/1000000) as St,
         (ED*86400+EH*3600+EM*60+ES+EmS/1000000) as Et,
         (Et - St) as duration_in_sec
| stats pct(duration_in_sec,99) as p99, avg(duration_in_sec) as avg, count(*) as cnt
        by objectRef.resource, verb, userAgent
| sort p99 desc
```

## CP21 — Recent kube-system add-on changes
```text
filter @logStream like /^kube-apiserver-audit/
| fields @timestamp, user.username, verb, requestURI, objectRef.name
| filter verb like /(create|update|patch|delete)/
  and (strcontains(requestURI,"/namespaces/kube-system/daemonsets")
    or strcontains(requestURI,"/namespaces/kube-system/deployments")
    or strcontains(requestURI,"/namespaces/kube-system/configmaps"))
| sort @timestamp desc
| limit 50
```

## CP22 — aws-auth / access mutations
```text
fields @logStream, @timestamp, user.username, verb, @message
| filter @logStream like /^kube-apiserver-audit/
| filter requestURI like /\/api\/v1\/namespaces\/kube-system\/configmaps/
| filter objectRef.name = "aws-auth"
| filter verb like /(create|delete|patch|update)/
| sort @timestamp desc
| limit 50
```

## CP23 — WATCH request volume by user agent
```text
fields userAgent, @timestamp
| filter @logStream like /kube-apiserver-audit/
| filter verb = "watch"
| stats count(*) as watches by userAgent
| sort watches desc
| limit 20
```

## CP24 — Mutations by user
```text
fields @timestamp, user.username, verb, objectRef.resource, objectRef.namespace
| filter @logStream like /^kube-apiserver-audit/
| filter verb like /(create|update|patch|delete)/
| stats count(*) as mutations by user.username, verb, objectRef.resource
| sort mutations desc
| limit 50
```

## CP25 — Anonymous / unauthenticated access
```text
fields @logStream, @timestamp, user.username, verb, requestURI, sourceIPs.0
| filter @logStream like /^kube-apiserver-audit/
| filter user.username = "system:anonymous"
| sort @timestamp desc
| limit 50
```

## Cost and empty-result rules

Use 60 minutes by default and cap at 7 days; widen only when required. Empty results are unknown until logging/streams, delivery delay, filters, and window are verified. CP21/22/24 are correlation context, not standalone FAILs.