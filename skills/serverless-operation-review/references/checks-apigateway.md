# Check Catalog — Amazon API Gateway

Covers REST APIs (`apigateway`), HTTP APIs and WebSocket APIs (`apigatewayv2`), and their stages.

Pillar codes: **SEC** Security · **REL** Reliability · **PERF** Performance Efficiency ·
**COST** Cost Optimization · **OPS** Operational Excellence

Capability differences that change what counts as a finding — do not report a missing feature that
the API type does not support:

| Capability | REST | HTTP | WebSocket |
|---|---|---|---|
| Response caching | Yes | No | No |
| AWS WAF association | Yes | No | No |
| Usage plans and API keys | Yes | No | No |
| Request/response validation | Yes | Limited | No |
| Access logging | Yes | Yes | Yes |
| Execution logging with `dataTraceEnabled` | Yes | Route-level settings | Yes |
| X-Ray tracing | Yes | No | No |
| mTLS (requires a custom domain) | Yes | Yes | No |

Documented thresholds used below, from
[CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html):
4XX and 5XX error **ratio** 0.05 (5% of requests), `Latency` p90 2500 ms, `IntegrationLatency`
p90 2000 ms.

---

## Security

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-APG-001 | SEC | HIGH | A route or method has `authorizationType: NONE`, no `apiKeyRequired`, and the stage has no WAF association | The endpoint is open to the internet. Add a Lambda authorizer, IAM auth, a JWT authorizer (HTTP APIs), or a Cognito user pool authorizer. Drops to MEDIUM only when the user confirms the route is intentionally public, in which case require WAF plus stage throttling | API Gateway control access |
| SLS-APG-002 | SEC | MEDIUM | REST stage with no AWS WAF web ACL association on a public API | WAF gives managed rule protection against common exploits and rate-based blocking. Note HTTP APIs cannot associate a WAF web ACL — for those, front the API with CloudFront | AWS WAF with API Gateway |
| SLS-APG-003 | SEC | MEDIUM | `disableExecuteApiEndpoint` is `false` on an API that is reached through a custom domain | The default `execute-api` endpoint stays reachable and bypasses the custom domain's controls. Disable it | API Gateway custom domains |
| SLS-APG-004 | SEC | MEDIUM | REST API uses API keys as the only access control | API keys identify a caller for metering; they are not an authentication mechanism. Add a real authorizer | API Gateway usage plans and API keys |
| SLS-APG-005 | SEC | HIGH | `methodSettings` has `dataTraceEnabled: true` on a production stage | Full request and response bodies are written to CloudWatch Logs, which can capture credentials and personal data. Disable it outside of active debugging | API Gateway CloudWatch logging |
| SLS-APG-006 | SEC | LOW | Custom domain with no `mutualTlsAuthentication` on a machine-to-machine API where client identity matters | mTLS authenticates the client certificate at the edge | API Gateway mutual TLS |
| SLS-APG-007 | SEC | LOW | Custom domain `securityPolicy` is not `TLS_1_2` or later | Raise the minimum TLS version | API Gateway custom domain security policy |
| SLS-APG-008 | SEC | MEDIUM | REST stage with `cachingEnabled: true` and `cacheDataEncrypted: false` | Encrypt cached responses, which may contain authorised data for another caller | API Gateway caching |
| SLS-APG-009 | SEC | MEDIUM | REST API with no request validation on methods that accept a body | Validate at the edge so malformed payloads never reach the integration and never bill an invocation | API Gateway request validation |
| SLS-APG-010 | SEC | LOW | Private REST API (`PRIVATE` endpoint type) with a resource policy that does not restrict the source VPC endpoint | Scope the resource policy to the intended `aws:SourceVpce` | API Gateway private APIs |

## Reliability and scaling

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-APG-020 | REL | HIGH | 5XX error ratio ≥ 5% of requests | Something is wrong in the backend, the network, or the integration. Correlate with the integration's own error metric | CloudWatch recommended alarms — `5XXError`/`5xx`, threshold 0.05 |
| SLS-APG-021 | REL | MEDIUM | 4XX error ratio ≥ 5% of requests | Usually authorization or request-shape problems, but also the signature of throttling (HTTP 429). Check for 429s specifically before assuming client error | CloudWatch recommended alarms — `4XXError`/`4xx`, threshold 0.05 |
| SLS-APG-022 | REL | HIGH | Stage has no `throttlingRateLimit`/`throttlingBurstLimit` (inherits only the account limit) | Without stage or method throttling, one caller can consume the account's entire request rate and starve every other API. Set a stage-level limit sized to the expected load | Lens — Limits: "API Gateway and Lambda have different limits for steady and burst request rates" |
| SLS-APG-023 | REL | MEDIUM | Integration timeout is set at or near the API type's maximum while the backing Lambda function's `Timeout` is longer | The client receives a 504 while the function keeps running and billing. Align the two. Read the account's applied `Maximum integration timeout` quota with `service-quotas get-service-quota` rather than assuming the default | API Gateway quotas |
| SLS-APG-024 | REL | MEDIUM | No usage plan on a REST API exposed to third parties | Usage plans give per-consumer throttling and quotas, which protects the backend from a single misbehaving client | API Gateway usage plans |
| SLS-APG-025 | REL | LOW | Single-Region API with no Route 53 failover or multi-Region deployment, for a workload with a stated Regional resilience requirement | Note the gap against the requirement rather than prescribing multi-Region unconditionally | Well-Architected REL |
| SLS-APG-026 | REL | MEDIUM | WebSocket API with `ExecutionError` > 0 | Integration invocation is failing — 5xx from the integration, permissions, throttling, or a deleted target | CloudWatch recommended alarms — `ExecutionError`, threshold 0.05 |
| SLS-APG-027 | REL | MEDIUM | WebSocket API with `ClientError` > 0 above 5% | Authorization or message-shape problems, or a route that no longer exists | CloudWatch recommended alarms — `ClientError`, threshold 0.05 |
| SLS-APG-028 | REL | INFO | `Count` drops far below the established baseline on an API with predictable traffic | Can indicate clients calling the wrong endpoint, or a permissions or configuration change making the API unreachable | CloudWatch recommended alarms — `Count`, `LESS_THAN_THRESHOLD` |

## Performance efficiency

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-APG-040 | PERF | HIGH | `Latency` p90 ≥ 2500 ms | Compare with `IntegrationLatency`: if the two track each other the backend is the cause; if `Latency` is materially higher, the overhead is in API Gateway (authorizer, validation, mapping templates) | CloudWatch recommended alarms — `Latency` p90, threshold 2500 ms |
| SLS-APG-041 | PERF | MEDIUM | `IntegrationLatency` p90 ≥ 2000 ms | The backend is slow. For Lambda integrations correlate with the function's `Duration` and cold-start rate | CloudWatch recommended alarms — `IntegrationLatency` p90, threshold 2000 ms |
| SLS-APG-042 | PERF | LOW | REST stage with caching disabled on read-heavy, cacheable endpoints | Caching cuts both latency and backend cost. Only applies to REST APIs | API Gateway caching |
| SLS-APG-043 | PERF | LOW | REST stage cache hit ratio (`CacheHitCount / (CacheHitCount + CacheMissCount)`) below 50% | The cache is being paid for without benefit. Review the cache key and TTL, or turn it off | API Gateway caching |
| SLS-APG-044 | PERF | LOW | REST API with no `minimumCompressionSize` on endpoints returning large payloads | Compression reduces transfer time and data-out cost | API Gateway payload compression |
| SLS-APG-045 | PERF | LOW | `EDGE` endpoint type where all clients are in one Region, or `REGIONAL` where clients are global and no CloudFront distribution fronts the API | Match the endpoint type to the client distribution | API Gateway endpoint types |

## Operational excellence

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-APG-060 | OPS | HIGH | Stage has no `accessLogSettings` | Without access logs there is no per-request record for incident reconstruction. Enable access logging to CloudWatch Logs or Firehose with a structured format | Lens — Centralized and structured logging |
| SLS-APG-061 | OPS | MEDIUM | `methodSettings` `loggingLevel` is `OFF` | Set `ERROR` at minimum so failures are explainable. `INFO` for debugging only | API Gateway CloudWatch logging |
| SLS-APG-062 | OPS | MEDIUM | REST stage with `tracingEnabled: false` | Enable X-Ray so latency can be attributed across the API, the function, and its downstreams. Not available for HTTP APIs | Lens — Distributed tracing |
| SLS-APG-063 | OPS | MEDIUM | No alarm on `5XXError` | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts (alert on `5XXError`) |
| SLS-APG-064 | OPS | MEDIUM | No alarm on `Latency` | as above | Lens — Metrics and alerts (alert on `Latency`) |
| SLS-APG-065 | OPS | MEDIUM | No alarm on `IntegrationLatency` | as above | Lens — Metrics and alerts (alert on `IntegrationLatency`) |
| SLS-APG-066 | OPS | MEDIUM | WebSocket API with no alarm on `ClientError`, `IntegrationError`, or `ExecutionError` | as above | Lens — Metrics and alerts: "For WebSocket API, use `ClientError`, `IntegrationError` and `ExecutionError`" |
| SLS-APG-067 | OPS | LOW | Detailed CloudWatch metrics disabled on a stage with multiple resources or routes | Without detailed metrics, errors and latency cannot be attributed to a specific method or route | CloudWatch recommended alarms — repeatedly recommends enabling detailed metrics to narrow the source |
| SLS-APG-068 | OPS | LOW | No stage variables or separate stages for environments; a single stage serves multiple environments | Separate stages per environment so throttling, logging, and integrations can differ | API Gateway stages |
| SLS-APG-069 | OPS | LOW | Missing operational tags — `Environment`, `Owner`, `Runbook`, `OnCall` | Tag for ownership routing and cost allocation | Well-Architected OPS |

## Cost optimization

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-APG-080 | COST | MEDIUM | REST API used for a simple proxy integration with no REST-only features (caching, usage plans, request validation, WAF, X-Ray) | HTTP APIs cost materially less per request. Migrating is a real saving when none of the REST-only features are in use | API Gateway pricing; choosing between REST and HTTP APIs |
| SLS-APG-081 | COST | MEDIUM | REST cache enabled with a low hit ratio | The cache cluster is billed hourly by size regardless of hits | API Gateway caching pricing |
| SLS-APG-082 | COST | LOW | Access logs or execution logs with `dataTraceEnabled` writing to a log group with no retention policy | Set retention; execution logging at `INFO` with data tracing is a large ingestion cost | CloudWatch Logs retention |
| SLS-APG-083 | COST | LOW | Stage with near-zero `Count` over the window that still holds a cache cluster or a custom domain | Decommission unused stages | API Gateway pricing |

---

## Remediation snippets

### Enable structured access logging on a stage

```bash
aws apigateway update-stage \
  --rest-api-id abc123 \
  --stage-name prod \
  --patch-operations \
    op=replace,path=/accessLogSettings/destinationArn,value=arn:aws:logs:REGION:ACCOUNT:log-group:/aws/apigateway/prod \
    op=replace,path=/accessLogSettings/format,value='{"requestId":"$context.requestId","ip":"$context.identity.sourceIp","requestTime":"$context.requestTime","httpMethod":"$context.httpMethod","routeKey":"$context.routeKey","status":"$context.status","protocol":"$context.protocol","responseLength":"$context.responseLength","integrationLatency":"$context.integrationLatency","authorizerError":"$context.authorizer.error"}'
```

### Set stage throttling and turn off data tracing

```bash
aws apigateway update-stage \
  --rest-api-id abc123 \
  --stage-name prod \
  --patch-operations \
    op=replace,path=/*/*/throttling/rateLimit,value=1000 \
    op=replace,path=/*/*/throttling/burstLimit,value=500 \
    op=replace,path=/*/*/logging/loglevel,value=ERROR \
    op=replace,path=/*/*/logging/dataTrace,value=false \
    op=replace,path=/*/*/metrics/enabled,value=true
```

### Disable the default execute-api endpoint (SAM)

```yaml
Resources:
  CheckoutApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      DisableExecuteApiEndpoint: true
      TracingEnabled: true
      MethodSettings:
        - ResourcePath: "/*"
          HttpMethod: "*"
          LoggingLevel: ERROR
          DataTraceEnabled: false
          MetricsEnabled: true
          ThrottlingRateLimit: 1000
          ThrottlingBurstLimit: 500
      AccessLogSetting:
        DestinationArn: !GetAtt ApiAccessLogGroup.Arn
        Format: '{"requestId":"$context.requestId","status":"$context.status","integrationLatency":"$context.integrationLatency"}'
```

### Confirm the account's applied integration timeout quota

```bash
aws service-quotas list-service-quotas \
  --service-code apigateway \
  --query "Quotas[?contains(QuotaName,'integration timeout')].[QuotaName,Value,Adjustable]" \
  --output table
```
