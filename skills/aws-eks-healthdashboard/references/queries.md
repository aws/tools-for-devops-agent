# CloudWatch Logs Insights queries

The queries the skill runs against `/aws/eks/{cluster-name}/cluster`. CP1–CP18 are the core set (scaling events, latency percentiles, response-code distribution, etcd write churn, throttling, KCM per-controller QPS, scheduler lag, eviction stalls); **CP19–CP25 are additional diagnostic queries** (auth denials, write-path latency, change-correlation for RCA, watch volume, mutation attribution, anonymous access).

> **Default time window:** 60 minutes for `oneshot`/`tool`, 1440 minutes (24 h) for `scan`. Maximum 7 days.
> **Concurrency:** CW Logs Insights supports concurrent queries against the same log group. The skill fans these out in parallel and stitches the results.
> **Sources:** EKS support engineering patterns and the [EKS Control Plane Monitoring guide](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html). Nothing here is exotic — these are documented, repeatable patterns.

## Contents

- Query index (CP1–CP25 at a glance)
- CP1–CP18 — core query definitions
- CP19–CP25 — additional diagnostic queries
- Cost guidance

## Query index

| ID | Topic | Primary signal | Severity if breached |
|----|-------|----------------|----------------------|
| CP1 | API server scaling events | Was the control-plane ASG scaled? | informational |
| CP2 | Average LIST latency by URI | Steady-state SLO health | high if any URI > 1 s |
| CP3 | Max LIST latency by URI | Worst-case latency | critical if any URI > 20 s |
| CP4 | LIST pods latency + traffic by user agent | P99 / P90 / P50 per caller | high if any caller's P99 > 5 s |
| CP5 | Top clients listing pods | Identify the noisiest LIST source | investigative |
| CP6 | Total API request count by user agent | Overall load attribution | investigative |
| CP7 | HTTP response code distribution | API server health snapshot | critical if 5xx > 0 sustained |
| CP8 | API server 5xx errors | Server-side failures | critical |
| CP9 | API server 4xx errors | Client errors, deprecated APIs | medium (planning) |
| CP10 | Top writes to etcd | What is filling the database | high if churn dominated by 1 type |
| CP11 | Control-plane component errors (non-audit) | Scheduler / KCM / authenticator errors | high |
| CP12 | API server health-check failures | Control plane unhealthy | critical |
| CP13 | Client-side throttling | Caller hit APF | high |
| CP14 | KCM request latency by service account | Per-controller latency | medium |
| CP15 | LIST latency raw per-request | Build a precise timeline | investigative |
| CP16 | Eviction events by EKS node manager | Pod disruption during scale-down | informational |
| CP17 | Pods failing eviction | Stuck PDBs / finalizers | high |
| CP18 | Unscheduled pods (scheduler log) | CA / Karpenter needs to scale | high |
| CP19 | Denied / forbidden requests | authz `forbid` / 403 + authenticator "denied" | high (auth breakage / probing) |
| CP20 | Slow mutating (write-path) requests | create/update/patch/delete p99 latency | high if p99 > 1 s (etcd apply latency) |
| CP21 | Recent changes to core add-ons / DaemonSets (kube-system) | change-correlation for RCA | investigative — "what changed before it broke" |
| CP22 | aws-auth / access mutations | access-config changes explaining sudden auth breakage | high (correlate with CP19) |
| CP23 | WATCH request volume by user agent | apiserver connection / watch-cache pressure | high if one caller dominates |
| CP24 | Mutations by user (attribution) | who is writing to the API — RCA / audit | investigative |
| CP25 | Anonymous / unauthenticated access | `system:anonymous` / `system:unauthenticated` | critical (security red flag) |

## CP1 — API server scaling events

Was the control-plane ASG scaled during a load event?

```text
fields @timestamp, @message
| filter @logStream not like "audit"
| filter @message like "Resetting endpoints for master service"
| sort @timestamp asc
| limit 10000
```

## CP2 — Average LIST latency by request URI

Any URI > 1 second is a [Kubernetes SLO breach](https://github.com/kubernetes/community/blob/master/sig-scalability/slos/slos.md#steady-state-slisslos). Over 20 seconds warrants urgent investigation.

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

Worst-case latency per endpoint. Use to find the single slowest LIST during a scale event.

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

P99 / P90 / P50 per caller. Identifies which component is driving LIST pressure.

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
```

## CP7 — HTTP response code distribution

A healthy cluster is almost entirely 2xx. Look for 429s (APF throttling) and 5xx (server errors).

```text
fields @timestamp, @message
| filter @logStream like /audit/
| stats count(*) as count by responseStatus.code
| sort count desc
```

## CP8 — API server 5xx errors

Healthy clusters return zero results.

```text
fields @timestamp, responseStatus.code, @message
| filter @logStream like /audit/
| filter responseStatus.code >= 500
| limit 50
```

## CP9 — API server 4xx errors

Deprecated API usage shows up here — useful for [upgrade planning](https://repost.aws/knowledge-center/eks-cluster-upgrade-api-errors).

```text
stats count(*) as count by requestURI, verb, responseStatus.code, userAgent
| filter @logStream =~ "kube-apiserver-audit"
| filter responseStatus.code >= 400
| filter responseStatus.code < 500
| sort count desc
```

## CP10 — Top writes to etcd

**The primary diagnostic for "what is filling etcd?"** Identifies the most-written resource types — events, CSRs, leases, replicasets, jobs, secrets are the usual suspects.

```text
fields @timestamp, @message, @logStream, requestURI, verb
| filter @logStream like "kube-apiserver-audit"
| filter verb not like "get"
| filter verb not like "list"
| filter verb not like "watch"
| display @logStream, requestURI, verb
| stats count(*) as count by requestURI, verb
| sort count desc
```

## CP11 — Control-plane component errors (non-audit)

Catches errors from scheduler, controller-manager, authenticator — things that don't appear in audit logs.

```text
fields @timestamp, @message
| filter @message like /error/
| filter @logStream not like /audit/
| sort @timestamp desc
| limit 20
```

## CP12 — API server health-check failures

Any results indicate the control plane was unhealthy.

```text
fields @message
| sort @timestamp asc
| filter @logStream like "kube-apiserver"
| filter @logStream not like "kube-apiserver-audit"
| filter @message like "healthz check failed"
```

## CP13 — Client-side throttling

Maps directly to API Priority and Fairness behavior on the server side.

```text
filter @message like "Throttling request"
```

## CP14 — KCM request latency by service account

Latency per controller-manager queue. Swap the filter to target each controller in turn.

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

> Standard controller list to iterate over: `deployment-controller`, `replicaset-controller`, `cronjob-controller`, `job-controller`, `endpoint-controller`, `endpointslice-controller`, `generic-garbage-collector`, `horizontal-pod-autoscaler`, `persistent-volume-binder`. Counts approaching the default `kubeAPIQPS=20` ceiling indicate the controller is being client-side throttled.

> **EKS 1.28+ public-metric alternative:** `workqueue_depth` / `workqueue_adds_total` via `metrics.eks.amazonaws.com/v1/kcm` give controller backpressure directly, without parsing audit logs. This CP14 query stays the source for per-caller QPS attribution. See [`metric-sources.md` §4.6](metric-sources.md).

## CP15 — LIST latency raw per-request

Build a precise timeline during a known incident window.

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

Usually indicates missing PDBs or stuck finalizers.

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

> **EKS 1.28+ public-metric alternative:** `scheduler_pending_pods{queue="unschedulable"}` via `metrics.eks.amazonaws.com/v1/ksh` is the direct metric equivalent — prefer it on 1.28+ and keep this log query as the fallback for older clusters (and for the per-pod failure reason). See [`metric-sources.md` §4.6](metric-sources.md).

# CP19–CP25 — additional diagnostic queries

These extend CP1–CP18 to cover auth denials, write-path latency, and change-correlation for
root-cause analysis. Sources: [Retrieve EKS control plane logs](https://repost.aws/knowledge-center/eks-get-control-plane-logs) · [EKS Auditing & Logging best practices](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html) · [Detect security issues with GuardDuty](https://aws.amazon.com/blogs/security/how-to-detect-security-issues-in-amazon-eks-clusters-using-amazon-guardduty-part-1/).

> **When to run:** CP19–CP25 are **triggered diagnostics, not scorecard rows** — run one only after a matching signal appears in the core CP1–CP18 pass (auth denials → CP19, write-path latency → CP20, change-correlation for RCA → CP21/CP22/CP24, WATCH volume → CP23, anonymous access → CP25). Do not run all seven unconditionally on every dashboard pass — each is a billable Logs Insights scan. When grading their output, apply [`grading-guards.md`](grading-guards.md): a 403 is authorization, not authentication (FP4), and an empty result is unknown, not healthy (FP11).

## CP19 — Denied / forbidden requests

RBAC/authorizer denials (403) and authenticator "denied". A spike means broken access (a controller
or workload lost permission) or someone probing. Complements CP9 (all 4xx).

```text
fields @timestamp, user.username, verb, objectRef.resource, objectRef.namespace, responseStatus.code, responseStatus.reason
| filter @logStream like /^kube-apiserver-audit/
| filter responseStatus.code = 403
| stats count(*) as denied by user.username, verb, objectRef.resource
| sort denied desc
```

Authenticator-stream denials (IAM→RBAC mapping failures):

```text
fields @logStream, @timestamp, @message
| filter @logStream like /authenticator/
| filter @message like "denied"
| sort @timestamp desc
| limit 50
```

> The audit annotation `authorization.k8s.io/decision = "forbid"` (with `authorization.k8s.io/reason`) is the precise signal where the field is queryable.

## CP20 — Slow mutating (write-path) requests

CP2–CP4 measure LIST (read) latency; this measures the **write path** (create/update/patch/delete).
High p99 here points at etcd apply latency or a slow admission webhook. Kubernetes mutating SLO ≈ 1 s.

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

## CP21 — Recent changes to core add-ons / DaemonSets (kube-system)

Change-correlation: "what changed just before the incident." Surfaces create/update/patch/delete on
kube-system DaemonSets / Deployments / ConfigMaps (CoreDNS, kube-proxy, aws-node, add-ons).

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

Mutations to the `aws-auth` ConfigMap (logged at RequestResponse level by the EKS audit policy) —
the usual explanation for a sudden cluster-wide access/auth break. Correlate with CP19.

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

Watches hold long-lived apiserver connections and drive watch-cache memory. One client opening a
flood of watches is a saturation source CP4/CP6 (LIST) don't show.

```text
fields userAgent, @timestamp
| filter @logStream like /kube-apiserver-audit/
| filter verb = "watch"
| stats count(*) as watches by userAgent
| sort watches desc
| limit 20
```

## CP24 — Mutations by user (attribution)

"Who is writing to the API?" — attribution for RCA and audit. CP10 shows *what* resource is written;
this shows *who*.

```text
fields @timestamp, user.username, verb, objectRef.resource, objectRef.namespace
| filter @logStream like /^kube-apiserver-audit/
| filter verb like /(create|update|patch|delete)/
| stats count(*) as mutations by user.username, verb, objectRef.resource
| sort mutations desc
| limit 50
```

## CP25 — Anonymous / unauthenticated access

Any `system:anonymous` / `system:unauthenticated` API access is a critical red flag (matches the
GuardDuty `Policy:Kubernetes/AnonymousAccessGranted` scenario) — usually a bad RBAC binding.

```text
fields @logStream, @timestamp, user.username, verb, requestURI, sourceIPs.0
| filter @logStream like /^kube-apiserver-audit/
| filter user.username = "system:anonymous"
| sort @timestamp desc
| limit 50
```

## Cost guidance

CloudWatch Logs Insights queries scan log data and are billed by GB scanned. A 7-day window over a busy cluster's audit log can scan tens of GB. The skill's defaults keep this under control:

- `oneshot` / `tool` modes default to 60 minutes — usually < 1 GB scanned.
- `scan` mode defaults to 24 hours, runs nightly, and uses query results caching where available.
- Customers can override with `time_window_minutes` for incident triage; we cap at 7 days.

For frequent re-runs (e.g., during an active incident), prefer the `tool` mode — it lets the agent run only the queries it needs (`cp_etcd_pressure` runs CP10; `cp_apf_health` runs CP7 + CP13) instead of all 18 every time.
