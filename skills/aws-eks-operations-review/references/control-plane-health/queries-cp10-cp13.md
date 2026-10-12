# Core CloudWatch Logs Insights queries CP10–CP13

Run in order after CP1–CP9. Query IDs are not scorecard IDs.

## CP10 — Top writes to etcd
```text
fields @timestamp, @message, @logStream, requestURI, verb
| filter @logStream like "kube-apiserver-audit"
| filter verb not like "get"
| filter verb not like "list"
| filter verb not like "watch"
| display @logStream, requestURI, verb
| stats count(*) as count by requestURI, verb
| sort count desc
| limit 100
```

## CP11 — Control-plane component errors (non-audit)
```text
fields @timestamp, @message, @logStream
| filter @logStream not like /audit/
| filter @message like /^E\d{4}/ or @message like /\"level\":\"error\"/ or @message like /level=error/
| sort @timestamp desc
| limit 50
```

Use targeted stream filters for broader component-specific searches; never replace the error expression with bare `/error/` because it creates false positives.

## CP12 — API server health-check failures
```text
fields @message
| sort @timestamp asc
| filter @logStream like "kube-apiserver"
| filter @logStream not like "kube-apiserver-audit"
| filter @message like "healthz check failed"
```

## CP13 — Client-side throttling
```text
fields @timestamp, @message, @logStream
| filter @logStream not like /audit/
| filter @message like "Throttling request"
| sort @timestamp desc
| limit 50
```

## Empty-result rule

Verify logging/streams, delivery delay, filters, and time window before interpreting empty output. Missing logging makes log-derived signals N/A, not PASS.