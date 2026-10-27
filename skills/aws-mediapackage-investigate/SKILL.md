---
name: aws-mediapackage-investigate
description: >-
  Deep investigation of AWS Elemental MediaPackage, v1 and v2. Use when a customer reports a
  MediaPackage problem or when evidence points at the packaging/origin layer: ingest failures or
  401/403/SigV4 errors, egress 4xx/5xx, player 404s, origin latency, origin-side access rejections
  (403 with CDNAuthorizationStatus Unauthorized, endpoint policy grants for CloudFront/OAC, secret
  or role faults), or harvest job failures. Auto-detects v1 vs v2, then branches into
  version-specific diagnosis covering ingest health, egress errors, latency, CDN authorization,
  ForceEndpointError awareness, content quality (MQCS), harvest jobs, stuck-endpoint reset
  assessment, and access log analysis. Not for encoder-side faults (use
  aws-medialive-investigate), ad-insertion and Channel Assembly behavior (use
  aws-mediatailor-investigate), or CloudFront cache behavior, TTLs, OAC attachment or origin
  headers on the distribution, and edge-side error attribution (use
  aws-media-cloudfront-investigate).
metadata:
  author: blends
  version: "1.0.0"
  summary: "Read-only investigation of MediaPackage v1 and v2: ingest and egress errors, latency, CDN authorization, harvest jobs and access log analysis."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaPackage"
  aws-devops-agent-skills.technical-domains: "Operations, Observability"
---
# MediaPackage Deep Investigation

## Purpose

Perform a comprehensive investigation of MediaPackage when either:
1. Evidence from a broader media pipeline investigation points at the packaging/origin layer
2. The customer asks specifically about a MediaPackage packaging/delivery issue

This skill auto-detects whether the resource is v1 or v2 and branches into
the appropriate diagnostic path. The two versions have different APIs,
different metric dimensions, different auth models, and different log formats.

## Prerequisites

- MediaPackage channel ID or name known (from the customer, or via
  `list-channels` / `list-channel-groups`)
- Time window established (the customer's impact window, or the anomaly window
  observed in CloudWatch)
- Upstream MediaLive confirmed HEALTHY (see aws-medialive-investigate),
  OR MediaPackage is the layer the evidence points at
- Evidence of a MediaPackage anomaly

## Investigation checklist

Copy this list into your working notes and tick each step as you complete it. Run the
steps in order; skip a conditional step only when its condition says so, and say so.

- [ ] Step 1: Version detection (v1 vs v2)
- [ ] Step 2A: v1 ingest health
- [ ] Step 2B: v2 ingest health
- [ ] Step 3: Egress error analysis
- [ ] Step 4: CDN authorization diagnosis (v2 only)
- [ ] Step 5: ForceEndpointErrorConfiguration awareness (v2 only)
- [ ] Step 6: Latency analysis
- [ ] Step 7: ActiveInput interpretation (v1 only)
- [ ] Step 8: MQCS quality metrics (v2 CMAF only)
- [ ] Step 9: Harvest job status (VOD extraction)
- [ ] Step 10: Stuck endpoint recovery (v2 only)
- [ ] Step 11: Origin endpoint configuration verification
- [ ] Step 12: Access log analysis
- [ ] Step 13: Compile findings

## Step 1: Version detection (v1 vs v2)

MediaPackage v1 and v2 are separate services with different APIs. Detect
which version by attempting both:

### Try v1 first:

```
aws mediapackage describe-channel --id $CHANNEL_ID \
  --no-cli-pager --output json 2>&1
```

If successful → v1 channel. Proceed to Step 2A.

### If v1 not found, try v2:

```
aws mediapackagev2 get-channel \
  --channel-group-name $CHANNEL_GROUP \
  --channel-name $CHANNEL_NAME \
  --no-cli-pager --output json 2>&1
```

If the channel group is unknown, list them:
```
aws mediapackagev2 list-channel-groups --no-cli-pager --output json
```

Then list channels within each group:
```
aws mediapackagev2 list-channels \
  --channel-group-name $GROUP_NAME \
  --no-cli-pager --output json
```

If successful → v2 channel. Proceed to Step 2B.

### If neither found:
- Verify region is correct
- Verify the identifier format (v1 uses a channel ID string; v2 uses
  channel-group-name + channel-name)
- Check if the resource was recently deleted

## Step 2A: v1 ingest health

### Channel and endpoint details

```
aws mediapackage describe-channel --id $CHANNEL_ID \
  --query '{Ingress:HlsIngest.IngestEndpoints[].{Id:Id,Url:Url,Username:Username},IngressLogs:IngressAccessLogs,EgressLogs:EgressAccessLogs}' \
  --no-cli-pager --output json
```

v1 channels have two ingest endpoints for redundancy (matching MediaLive's
dual-pipeline output). Each endpoint has a unique URL and WebDAV credentials
(Username/Password).

### Credential verification

If MediaLive is pushing to MediaPackage v1 and receiving 401/403 errors:
- Credentials may have been rotated without updating MediaLive
- Check `Output4xxErrors` on the MediaLive side
- Credential rotation: `rotate-ingest-endpoint-credentials` generates new
  creds — if called without updating ML, ingest breaks immediately

### Ingest metrics

Namespace: `AWS/MediaPackage`
Dimension: `Channel` = channel ID

| Metric | Statistic | Healthy | Unhealthy |
|---|---|---|---|
| IngressBytes | Sum | > 0 | = 0 (no content arriving) |
| IngressResponseTime | Average, Maximum | < 500ms | > 2000ms (slow upstream push) |

Per-endpoint breakdown (dimensions: `Channel` + `IngestEndpoint`):
- `IngressBytes` per endpoint — both should be non-zero for full redundancy
- If one endpoint receives zero: the corresponding ML pipeline may be down

### Ingest diagnosis

```
IngressBytes = 0 on both endpoints?
  → ML is not pushing — check ML Output5xxErrors / NetworkOut
  → Or credentials are wrong (check ML Output4xxErrors for 401/403)

IngressBytes = 0 on ONE endpoint?
  → Single pipeline issue on ML side (PipelinesRunningCount < 2)
  → Or one endpoint's credentials are stale

IngressBytes > 0 but IngressResponseTime > 2000ms?
  → Slow segment delivery from ML — check ML SvqTime and NetworkOut
  → May cause downstream latency for players
```

## Step 2B: v2 ingest health

### Channel and endpoint details

```
aws mediapackagev2 get-channel \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --no-cli-pager --output json
```

v2 channels use SigV4 authentication (no per-endpoint credentials).
The `IngestEndpoints[]` array provides the ingest URLs.

Key fields:
- `InputType`: HLS or CMAF — determines metric availability
- `IngestEndpoints[].Url`: Where MediaLive pushes to

### v2 ingest metrics

Namespace: `AWS/MediaPackage`
Dimensions: `ChannelGroup` + `Channel`

Table: [Step 2B: v2 ingest health: v2 ingest metrics](references/lookup-tables.md#step-2b-v2-ingest-health-v2-ingest-metrics). Load it when you run this step.

Note: v2 `IngressRequestCount` uses `StatusCode` dimension (not `StatusCodeRange`).

### SigV4 authentication

v2 uses IAM-based authentication. If ingest is failing with 403:
- The MediaLive channel's IAM role needs `mediapackagev2:PutObject` permission
  on the channel's resource ARN
- Check the channel's resource policy:
  ```
  aws mediapackagev2 get-channel-policy \
    --channel-group-name $GROUP --channel-name $CHANNEL \
    --no-cli-pager --output json
  ```
- If no policy exists and the pusher is cross-account → ingest will fail with 403

### InputSwitchConfiguration (CMAF only)

For CMAF input type, check if input switching is configured:
```
aws mediapackagev2 get-channel \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --query 'InputSwitchConfiguration' \
  --no-cli-pager --output json
```

This affects how v2 handles failover between ingest endpoints.
Fields: `MQCSInputSwitching` (boolean) and `PreferredInput` (integer 1
or 2 — tie-breaker when both ingest pipelines have equal MQCS scores).

## Step 3: Egress error analysis

### v1 egress metrics

Dimensions: `Channel` + `OriginEndpoint` + `StatusCodeRange`

```
aws cloudwatch list-metrics \
  --namespace AWS/MediaPackage \
  --metric-name EgressRequestCount \
  --dimensions Name=Channel,Value=$CHANNEL_ID \
  --no-cli-pager --output json
```

`StatusCodeRange` values: `2xx`, `3xx`, `4xx`, `5xx`

Table: [Step 3: Egress error analysis: v1 egress metrics](references/lookup-tables.md#step-3-egress-error-analysis-v1-egress-metrics). Load it when you run this step.

### v2 egress metrics

Dimensions: `ChannelGroup` + `Channel` + `OriginEndpoint` + `StatusCode`

**CRITICAL dimension difference:** v2 uses `StatusCode` not `StatusCodeRange`.
Querying with `StatusCodeRange` on v2 returns empty data silently.

**IMPORTANT: AWS docs typo warning.** The v2 dimension for output format is
documented as `OuputType` (missing a 't') in some versions of the AWS docs.
CloudWatch dimension keys are case-sensitive. When querying by output format,
try both `OutputType` and `OuputType` defensively until AWS resolves the typo.

Additional v2 dimensions:
- `RequestType`: `manifest` or `segment` — distinguish manifest fetches from segment fetches
- `OutputType` (or `OuputType`): `HLS`, `DASH`, `MSS`, `CMAF` — per-format breakdown

### v2 egress diagnosis

```
EgressRequestCount with StatusCode=403?
  → CDN authorization failure — see Step 4 (CDN authorization)

EgressRequestCount with StatusCode=404?
  → Check ForceEndpointErrorConfiguration first — may be DELIBERATE
  → See Step 5 (ForceEndpointError awareness)

EgressRequestCount with StatusCode=5xx?
  → Server-side error — packaging failure or resource exhaustion
  → Check if EgressResponseTime is also elevated (correlated)
```

## Step 4: CDN authorization diagnosis (v2 only)

v2 supports CDN authorization headers for origin shielding. When configured,
requests without valid CDN auth headers are rejected with HTTP 403.

### Check configuration

CDN authorization is configured on the origin endpoint **policy**, NOT on the
endpoint object itself. Retrieve it via:

```
aws mediapackagev2 get-origin-endpoint-policy \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json 2>&1
```

If `ResourceNotFoundException` → no endpoint policy exists (CDN auth is not
configured). This is normal for endpoints without origin shielding.

If a policy exists, inspect the `CdnAuthConfiguration` object:
- `CdnIdentifierSecretArns[]` — ARNs of Secrets Manager secrets containing
  the expected CDN header values
- `SecretsRoleArn` — IAM role MediaPackage assumes to read the secrets

The CDN sends the header `X-MediaPackageV2-CDNIdentifier` with each request.
MediaPackage validates the header value against the stored secrets.

### CDN authorization metrics

Dimension: `CDNAuthorizationStatus` — values: `Authorized`, `Unauthorized`
Dimension: `CDNAuthorizationStatusDetails` — detailed reason

Table: [Step 4: CDN authorization diagnosis (v2 only): CDN authorization metrics](references/lookup-tables.md#step-4-cdn-authorization-diagnosis-v2-only-cdn-authorization-metrics). Load it when you run this step.

### CDN auth diagnosis

```
High 403 rate + CDNAuthorizationStatusDetails = MissingCdnAuthHeader?
  → CDN is not sending the X-MediaPackageV2-CDNIdentifier header
  → Customer needs to configure their CDN to include the header

High 403 rate + CDNAuthorizationStatusDetails = HeaderSecretMismatched?
  → Secret mismatch between MP endpoint policy and CDN config
  → Secret may have been rotated without updating CDN

High 403 rate + CDNAuthorizationStatusDetails = MissingCdnIdentifierSecretArns?
  → Endpoint policy exists but has no secret ARNs configured
  → Customer needs to add CdnIdentifierSecretArns to the policy

High 403 rate + CDNAuthorizationStatusDetails = MissingSecretsRoleArn?
  → Endpoint policy exists but has no role to read secrets
  → Customer needs to add SecretsRoleArn to the policy

High 403 rate + SecretsManager* errors?
  → Secrets Manager connectivity, throttling, or internal issue
  → MP cannot validate the CDN header against the stored secret

CDNAuthorizationStatus = Unauthorized with no corresponding errors?
  → Unauthorized requests are being blocked correctly (working as designed)
```

## Step 5: ForceEndpointErrorConfiguration awareness (v2 only)

v2 endpoints can be configured to deliberately return errors (typically 404)
under specific conditions. This is a CDN failover signal, NOT a bug.

### Check configuration

```
aws mediapackagev2 get-origin-endpoint \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --query 'ForceEndpointErrorConfiguration' \
  --no-cli-pager --output json
```

### EndpointErrorConditions

Table: [Step 5: ForceEndpointErrorConfiguration awareness (v2 only): EndpointErrorConditions](references/lookup-tables.md#step-5-forceendpointerrorconfiguration-awareness-v2-only-endpointerrorconditions). Load it when you run this step.

### Behavioral nuance: STALE_MANIFEST and orderly shutdowns

`STALE_MANIFEST` only fires on actual encoder/path failures. When MediaLive
stops cleanly, it sends `EXT-X-ENDLIST`, which converts the stream to VOD
rather than triggering a stale-manifest 404. Do NOT expect ForceEndpointError
404s during orderly MediaLive channel stops.

### Diagnosis

When the endpoint shows a high 404 rate, run the ForceEndpointError diagnosis tree in
[references/secondary-checks.md](references/secondary-checks.md). It branches on whether a
configuration exists and on which condition fired, and names the upstream handoffs.

**Critical**: Do NOT flag ForceEndpointError 404s as failures without checking
the configuration. Report as:
```
Observed: EgressRequestCount 404 elevated on endpoint $ENDPOINT.
ForceEndpointErrorConfiguration is active with condition: $CONDITION.
This is deliberate CDN failover behavior, not a packaging error.
Question: Is the triggering condition (stale/incomplete manifest) expected
given the current ingest state?
```

## Step 6: Latency analysis

### v1 latency

| Metric | Dimensions | Meaning |
|---|---|---|
| IngressResponseTime | Channel | Time to accept ingest segments |
| EgressResponseTime | Channel + OriginEndpoint | Time to serve player requests |

### v2 latency

| Metric | Dimensions | Meaning |
|---|---|---|
| IngressResponseTime | ChannelGroup + Channel | Time to accept ingest segments |
| EgressResponseTime | ChannelGroup + Channel + OriginEndpoint | Time to serve player requests |

### Latency diagnosis

```
IngressResponseTime elevated?
  → Slow ingest from MediaLive (check ML NetworkOut and SvqTime)
  → If ML output is healthy: possible MP ingest processing bottleneck

EgressResponseTime elevated?
  → Packaging is slow (complex manifest, many variants)
  → Check segment duration config — very short segments = more packaging work
  → Check if correlated with specific OutputType (HLS vs DASH vs MSS)

Both elevated simultaneously?
  → Possible resource contention at the MP layer
  → Check if IngressBytes spiked (content complexity increase)
```

## Step 7: ActiveInput interpretation (v1 only, load on demand)

When redundancy or which v1 ingest endpoint is active is in question, run the
ActiveInput section of [references/secondary-checks.md](references/secondary-checks.md).
`ActiveInput` is a v1-only metric; for v2 see Step 8.

## Step 8: MQCS quality metrics (v2 CMAF only, load on demand)

When content quality is declining or you need to know which v2 ingest pipeline
is active, run the MQCS section of [references/secondary-checks.md](references/secondary-checks.md).
It carries the DATA GAP text for channels that are not CMAF input type.

## Step 9: Harvest job status (VOD extraction, load on demand)

When the customer mentions VOD clips, Live-to-VOD or harvest job failures, run the
harvest jobs section of [references/secondary-checks.md](references/secondary-checks.md).

## Step 10: Stuck endpoint recovery (v2 only)

If a v2 endpoint appears stuck — manifest not updating despite healthy
ingest, or errors persisting after a malformed ingest was corrected —
consider whether a state reset is needed.

### Detecting stuck state

Symptoms:
- IngressBytes > 0 and stable (ingest is healthy)
- EgressRequestCount shows elevated 404s or no 2xx responses
- ForceEndpointErrorConfiguration is NOT the cause
- The issue started after a period of malformed ingest or encoder failure

### Recommending a reset

v2 provides two reset operations that clear stale ingest/packaging state
without recreating the resource. These are WRITE operations and are
deliberately outside this skill's read-only IAM scope — never attempt to
run them. When the stuck-state symptoms above are confirmed, recommend
that the customer run one of the following themselves:

```
aws mediapackagev2 reset-channel-state \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --no-cli-pager --output json
```

```
aws mediapackagev2 reset-origin-endpoint-state \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json
```

**WARNING for the customer:** a reset discards in-flight content and
creates a discontinuity in the stream. Recommend performing it during a
maintenance window.

After a reset, `get-channel.ResetAt` or `get-origin-endpoint.ResetAt`
will show the reset timestamp. A recent reset can explain a manifest
discontinuity that might otherwise look like a packaging failure.

## Step 11: Origin endpoint configuration verification (load on demand)

When the container type, manifest URLs, DRM/SPEKE settings or LL-HLS with CloudFront
OAC are in question, run the origin endpoint configuration section of
[references/secondary-checks.md](references/secondary-checks.md).

## Step 12: Access log analysis (load on demand)

When CloudWatch metrics are not granular enough, run the access log section of
[references/secondary-checks.md](references/secondary-checks.md) to confirm logs are
configured, then use [references/access-log-analysis.md](references/access-log-analysis.md)
for the log schemas and Logs Insights query templates.

## Step 13: Compile findings

Structure each finding as Observed (the value plus the API or metric it came
from), Expected (the threshold or benchmark plus its source), and Question:
why? Do not declare a definitive root cause; surface evidence and the precise
question that follows from it. Report sections:

1. **Resource identity**: Version (v1/v2), channel ID/name, channel group (v2),
   ContainerType (v2: TS/CMAF/ISM)
2. **Ingest health**: IngressBytes, response time, credential/SigV4 status
3. **Egress errors**: 4xx/5xx breakdown with correct dimensions per version
4. **CDN authorization**: v2 CDNAuth findings from endpoint policy, or N/A
5. **ForceEndpointError**: Configuration status and deliberate 404 assessment
6. **Latency**: Ingress and egress response times
7. **Redundancy**: ActiveInput status (v1) or MQCS/input switch config (v2)
8. **Quality**: MQCS findings (v2 CMAF) or N/A
9. **Harvest jobs**: v1 or v2 job status if applicable
10. **Stuck state**: ResetAt timestamp check, reset recommendation if applicable (v2)
11. **Access logs**: Per-request findings or DATA GAP
12. **Open questions**: Ranked by severity

Reference the appropriate checklist:
- v1: [references/v1-health-checklist.md](references/v1-health-checklist.md)
- v2: [references/v2-health-checklist.md](references/v2-health-checklist.md)

### Before presenting

Check the compiled findings and fix anything that fails before presenting them:

- Every Observed value names the API field or metric it came from, with its dimensions and time window.
- Every Expected value names its source: a threshold, a documented limit, or the resource's own configuration.
- No section asserts a definitive root cause; each finding ends in a question or a named handoff.
- Every signal that was not observable is reported as a DATA GAP with its reason, never as a healthy zero.
- No account IDs, ARNs, secrets or passphrases are reproduced; resources are named by type and name.
- Every egress finding names the version (v1 or v2) and the dimension (StatusCodeRange or StatusCode) it was read with.
