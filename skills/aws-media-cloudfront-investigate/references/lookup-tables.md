# CloudFront Deep Investigation for Media Delivery: Lookup Tables

Metric catalogs, status tables and field tables relocated from SKILL.md so they load
only when the step that uses them runs. Each heading names the SKILL.md step and
subsection the table belongs to; the surrounding instructions stay in SKILL.md.

## Step 2: Confirm the distribution and its origin binding

| Field | What it tells you | Watch for |
|---|---|---|
| `Status` | `Deployed` = live; `InProgress` = a config change is still propagating | An `InProgress` status during an incident may mean a recent config change is the trigger |
| `Origins[].Domain` | Must match the MediaPackage egress domain | A stale or wrong origin domain is a direct cause of edge 502/504 |
| `Origins[].OriginPath` | Prepended to every origin request | A mismatch with the MediaPackage endpoint path structure causes 403/404 |
| `OriginGroups` | Primary/secondary origin failover (often two MediaPackage endpoints or two regions) | Failover on 404/5xx means edge status can hide which origin actually served; check both members' metrics |
| `Geo` | `whitelist`/`blacklist` blocks viewers by country at the edge → CloudFront-generated 403 | Geo blocks surface as 4xx that never reach the origin |
| `CustomErrors` | Origin status codes may be **rewritten** (e.g., 503→200 with a static page) | A rewritten error masks the true origin status — reconcile against MediaPackage metrics, not the edge status alone |
| `LegacyLogging` | Legacy standard logging (S3) on/off | Feeds Step 7 |

## Step 3: Collect delivery health metrics (us-east-1)

| Metric | Stat | Meaning | Reading |
|---|---|---|---|
| `Requests` | Sum | Total viewer requests | The denominator for every rate; a sharp drop can mean viewers left or a CNAME/DNS failure |
| `BytesDownloaded` | Sum | Bytes delivered to viewers | Falling with steady Requests → smaller responses (errors, truncated segments) |
| `TotalErrorRate` | Average | % returning 4xx or 5xx | The headline health number |
| `4xxErrorRate` | Average | % returning 4xx | Client/auth/path/geo errors |
| `5xxErrorRate` | Average | % returning 5xx | Server/origin errors |

## Step 4: Attribute the error — CDN-layer vs origin-surfaced: 5xx attribution

| Observation | Attribution |
|---|---|
| `5xxErrorRate` elevated **with** MediaPackage `EgressRequestCount(5xx) > 0` in the same window | **Origin-surfaced** — MediaPackage is the root cause; CloudFront is forwarding faithfully |
| `5xxErrorRate` elevated **without** any MediaPackage 5xx | **CDN-side candidate** — origin protocol/SNI mismatch (502), origin unreachable (503), or origin timeout (504). Check `OriginLatency` p99 and the Step 2 origin config |
| `504` specifically, **with** elevated MediaPackage `EgressResponseTime` | **Origin-surfaced** — origin is slow; CloudFront timed out waiting |
| `502` **with** zero origin log entries | **CDN-side** — TLS/protocol negotiation to the origin failed (revisit v2 SNI/HTTPS) |

## Step 4: Attribute the error — CDN-layer vs origin-surfaced: 4xx attribution

| Observation | Attribution |
|---|---|
| `4xxErrorRate` elevated **with** MediaPackage v2 `ForceEndpointErrorConfiguration` set, and MP 404 volume matching | **Deliberate** — MediaPackage is intentionally returning 404 for CDN failover. Classify Informational, not an error |
| `403` spike, geo-restriction present in Step 2 | **CDN-generated** — viewers blocked by country at the edge |
| `403` spike, CDN auth in use, **no** geo restriction | **Origin-surfaced auth rejection** — MediaPackage returns the 403; CloudFront only passes it through. Check the distribution side here (custom header present on the origin, OAC attached on v2), then hand the verdict to MediaPackage. Reconcile against MediaPackage v2 `CDNAuthorizationStatusDetails` (aws-mediapackage-investigate Step 4) |
| `404` spike, no ForceEndpointError | **Path or staleness** — viewers requesting aged-out live segments (fell behind the sliding window), or an OriginPath/path-pattern mismatch. Correlate to specific `cs-uri-stem` values in the logs |

## Step 6: Origin Shield

| Observation | Reading |
|---|---|
| Origin Shield **disabled**, with MediaPackage `EgressRequestCount` high relative to CloudFront `Requests` | Candidate cause of origin overload — enabling/region-correcting the shield would cut origin load |
| Origin Shield **enabled** but `OriginShieldRegion` far from the origin region | Adds a hop; latency without the collapsing locality benefit |
| Origin Shield enabled, region correct, origin load still high | Look elsewhere — cache-key fragmentation or segment TTL (Step 5), not the shield |

## Step 7: Access-log analysis

| Mode | Destination | Latency | How to detect | Queryable by the agent? |
|---|---|---|---|---|
| Standard logging (legacy) | S3 (batched) | Minutes | `LegacyLogging.Enabled` from Step 2 | No — S3 objects; ask the customer to run the analysis (Athena or download) and report back |
| Standard logging (v2) | CloudWatch Logs, Data Firehose, or S3 (via CloudWatch vended logs) | Minutes | `aws logs describe-delivery-sources --region us-east-1`, resource ARN containing the distribution | Yes, when the destination is CloudWatch Logs — Logs Insights |
| Real-time logs | Kinesis Data Streams | Sub-second, sampled | `RealtimeLogConfigArn` on a cache behavior (Step 5) | Not directly; the customer's stream consumer holds the data |

## Step 7: Access-log analysis (2)

| Field | Use |
|---|---|
| `x-edge-result-type` | Cache outcome: `Hit`, `RefreshHit`, `Miss`, `LimitExceeded`, `CapacityExceeded`, `Error`, `Redirect` — the basis for hit-ratio and origin-load reads |
| `x-edge-detailed-result-type` | Finer outcome (e.g. an Origin Shield hit vs an edge hit, miss-forward-to-origin) |
| `sc-status` | The status CloudFront returned to the viewer |
| `x-edge-response-result-type` | Whether the response was served as error/hit/miss — reconcile with `sc-status` to spot rewritten errors |
| `cs-uri-stem` | The requested path — separates manifest vs segment, and surfaces stale-segment 404 patterns |
| `time-taken` / `time-to-first-byte` | Edge and origin latency at request granularity |
