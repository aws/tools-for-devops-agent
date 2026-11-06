# CloudFront Access-Log Fields for Media Investigation

The fields that carry diagnostic weight when reading CloudFront access logs for a
media pipeline, the cache result-type decode, and ready patterns for splitting
manifest vs segment traffic and computing hit ratio. Read this from
`aws-media-cloudfront-investigate` Step 7.

## Contents

- Log delivery modes and what the agent can query
- Field reference (the ones that matter for media)
- `x-edge-result-type` decode
- `x-edge-detailed-result-type` and Origin Shield accounting
- Logs Insights queries (standard logging v2 to CloudWatch Logs)
- Hit-ratio computation from logs
- Manifest-vs-segment splitting
- DATA GAP discipline

## Log delivery modes and what the agent can query

| | Standard logging (legacy) | Standard logging (v2) | Real-time logs |
|---|---|---|---|
| Destination | S3 only | CloudWatch Logs, Data Firehose, or S3 (delivered as CloudWatch vended logs) | Kinesis Data Streams |
| Latency | Minutes (batched) | Minutes | Sub-second |
| Completeness | All requests, fixed field set, W3C format | All requests; customer-selected fields; JSON, W3C, plain, or Parquet | Configurable fields, **sampling rate** (may be < 100%) |
| Scope | Whole distribution | Whole distribution (one delivery source per distribution) | Attached to specific cache behaviors |
| Configured / discovered | `DistributionConfig.Logging` | CloudWatch Logs delivery API in **us-east-1** (`describe-delivery-sources`) | `RealtimeLogConfigArn` on the cache behavior |
| Agent can query? | No — S3 objects (Athena or download-and-parse, customer-run) | **Yes** when the destination is CloudWatch Logs — Logs Insights in us-east-1 | No — the customer's stream consumer holds the data |

All three are **opt-in**. If none is configured, the edge-level request detail is
unobserved — report it as a DATA GAP, never as "no errors." Legacy and v2 can
coexist on one distribution.

Before writing any query against a v2 log group, look at a few raw events —
v2 lets the customer choose the field set and the output format, so field
availability and parsing differ per deployment:

```
fields @timestamp, @message
| sort @timestamp desc
| limit 5
```

If the format is JSON, the field names below are usable directly (wrap
hyphenated names in backticks). If it is W3C or plain, `parse @message` into
named fields first.

## Field reference (media-relevant subset)

The standard log has ~30 fields; these are the ones that decide a media
investigation:

| Field | Meaning | Why it matters |
|---|---|---|
| `date` / `time` | Edge timestamp (UTC) | Build the incident timeline |
| `x-edge-location` | Edge POP code | Localize a regional delivery problem |
| `sc-status` | Status returned to the viewer | The viewer-observed outcome |
| `cs-method` | HTTP method | Media is `GET`; unexpected methods are anomalies |
| `cs-uri-stem` | Requested path | Manifest vs segment; surfaces stale-segment 404 patterns |
| `cs-uri-query` | Query string | Cache-key fragmentation evidence if segments carry params |
| `x-edge-result-type` | Cache outcome | Hit-ratio and origin-load basis (see decode) |
| `x-edge-detailed-result-type` | Finer cache outcome | Distinguishes Origin Shield hits, miss-forwards |
| `x-edge-response-result-type` | How the response was classified (Hit/Miss/Error/…) | Reconcile with `sc-status` to spot rewritten errors |
| `time-taken` | Total edge service time (s) | Edge-side latency |
| `time-to-first-byte` | Origin TTFB (s) | Origin latency at request granularity; corroborates `OriginLatency` |
| `x-host-header` | Host requested | Confirms the right distribution/alias |
| `sc-content-type` | Response content type | Cross-check segment vs manifest classification |
| `cs(User-Agent)` | Player/client | Group symptoms by player |

## `x-edge-result-type` decode

| Value | Meaning | Read |
|---|---|---|
| `Hit` | Served from the edge cache | Counts toward hit ratio |
| `RefreshHit` | Revalidated with origin, still served from cache | Counts toward hit ratio (origin touched cheaply) |
| `Miss` | Not in edge cache; fetched from origin (or Origin Shield) | Origin-load contributor at the edge layer |
| `LimitExceeded` | Served an error due to a CloudFront quota | CDN-side; investigate the specific quota |
| `CapacityExceeded` | 503 due to capacity | CDN-side; rare |
| `Error` | An error was served, or the client disconnected mid-transfer | Pair with `sc-status` and `x-edge-response-result-type` — a 200 with `Error` means the viewer disconnected before the whole object was delivered |
| `Redirect` | 3xx (e.g. HTTP→HTTPS) | Usually benign for media |

Hit ratio (edge) ≈ (`Hit` + `RefreshHit`) ÷ all requests.

## `x-edge-detailed-result-type` and Origin Shield accounting

`x-edge-detailed-result-type` refines the coarse type. The accounting subtlety
that matters for origin-load reads: when Origin Shield serves a regional-edge
miss, the **edge** still records a `Miss` in `x-edge-result-type` even though the
origin (MediaPackage) was spared. So edge hit ratio understates how much the
origin was actually protected. To judge true origin load, prefer the detailed
type (which surfaces Origin Shield hits / miss-forward-to-origin) or compare
CloudFront `Requests` against MediaPackage `EgressRequestCount` directly — the
ratio of viewer requests to origin fetches is the cleanest origin-protection
signal.

## Logs Insights queries (standard logging v2 to CloudWatch Logs)

Run in **us-east-1** against the delivery destination log group. Field names
assume JSON output; adjust or `parse` for other formats.

### Status breakdown, manifest vs segment

```
fields @timestamp, `sc-status`, `cs-uri-stem`
| parse `cs-uri-stem` /\.(?<ext>[A-Za-z0-9]+)$/
| filter ext in ["m3u8","mpd","ts","m4s","cmfv","cmfa","mp4"]
| stats count() as requests by `sc-status`, ext
| sort requests desc
```

`m3u8`/`mpd` rows are manifests; the rest are segments. Read the two groups
separately (see manifest-vs-segment splitting below).

### Cache-outcome distribution for segments only

```
fields @timestamp, `x-edge-result-type`, `cs-uri-stem`
| filter `cs-uri-stem` like /\.(ts|m4s|cmfv|cmfa|mp4)$/
| stats count() as n by `x-edge-result-type`
| sort n desc
```

### Segment hit ratio over 5-minute buckets

```
fields @timestamp, `cs-uri-stem`,
       (`x-edge-result-type` = "Hit" or `x-edge-result-type` = "RefreshHit") as is_hit
| filter `cs-uri-stem` like /\.(ts|m4s|cmfv|cmfa|mp4)$/
| stats sum(is_hit) as served_from_cache,
        count() as total,
        served_from_cache / total * 100 as hit_ratio_pct
  by bin(5m)
| sort @timestamp asc
```

### 5xx by result type and origin TTFB (CDN-side vs origin-side split)

```
fields @timestamp, `sc-status`, `x-edge-result-type`, `x-edge-detailed-result-type`, `time-to-first-byte`
| filter `sc-status` >= 500
| stats count() as errors, avg(`time-to-first-byte`) as avg_ttfb
  by `sc-status`, `x-edge-detailed-result-type`
| sort errors desc
```

A 502 with a detailed result type indicating an origin connection/TLS failure
and no matching MediaPackage 5xx is the CDN-side signature from SKILL.md Step 4.

### Stale-segment 404 pattern

```
fields @timestamp, `cs-uri-stem`, `sc-status`
| filter `sc-status` = 404 and `cs-uri-stem` like /\.(ts|m4s|cmfv|cmfa)$/
| stats count() as n by `cs-uri-stem`
| sort n desc
| limit 50
```

Many distinct aged-out segment names with small counts each → viewers behind the
live sliding window. A few names with large counts → a path or OriginPath
mismatch.

### Rewritten errors (custom error responses)

```
fields @timestamp, `sc-status`, `x-edge-result-type`, `x-edge-response-result-type`, `cs-uri-stem`
| filter `x-edge-result-type` = "Error" and `sc-status` < 400
| stats count() as n by `sc-status`, `cs-uri-stem`
| sort n desc
| limit 20
```

## Hit-ratio computation from logs (when CacheHitRate metric is absent)

If the `CacheHitRate` additional metric is not enabled, derive it from a log
window:

1. Filter to **segment** paths only (`cs-uri-stem` matching `*.ts`/`*.m4s`/etc.) —
   manifests have low hit ratios by design and would skew the number.
2. Count `x-edge-result-type` in (`Hit`, `RefreshHit`) as cache-served.
3. hit ratio = cache-served ÷ total segment requests.
4. State it as **log-derived over the window** — it is an estimate (sampling for
   real-time logs; Origin Shield accounting for both), not the metric.

A low segment hit ratio with healthy error rates → cache-key fragmentation, TTL
misconfiguration, or Origin Shield off (see cache-behavior-patterns.md), not an
origin fault.

## Manifest-vs-segment splitting

Most CloudFront media reads need this split because the two content types have
opposite expected behavior:

- **Manifests** (`*.m3u8`, `*.mpd`): expected low hit ratio, frequent re-fetch,
  short TTL. A 404 here is serious (playlist gone). A high TTL here causes stalls.
- **Segments** (`*.ts`, `*.m4s`, `*.cmf*`): expected high hit ratio, immutable. A
  404 here usually means the viewer fell behind the live sliding window, or an
  OriginPath/path-pattern mismatch. A low hit ratio here means a caching problem.

Split on `cs-uri-stem` suffix before computing any rate so the two do not
contaminate each other's reading.

## DATA GAP discipline

- Logs not enabled → "CloudFront access logs not enabled; edge request detail
  unobserved." Never infer health from missing logs.
- Logs enabled but not agent-queryable (legacy S3, Firehose, real-time) → "edge
  request detail exists but was not analyzed in this investigation"; ask the
  customer for the specific numbers (hit ratio, status split) rather than
  guessing.
- Real-time logs sampled below 100% → note the sampling rate; counts are
  estimates, not totals.
- Standard logs delayed (batched) → recent minutes may be incomplete; state the
  log window's end time relative to the incident.
