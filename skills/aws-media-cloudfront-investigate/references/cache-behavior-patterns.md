# CloudFront Cache-Behavior Patterns for Media Delivery

How to read a distribution's cache behaviors, pick the correct caching shape for
HLS/DASH, and recognize the misconfigurations that degrade media delivery.
Read this from `aws-media-cloudfront-investigate` Step 5 when a distribution
delivers poorly despite healthy-looking error rates, or when origin load is high
relative to viewer requests.

## Contents

- Cache-behavior precedence model
- Content-type → caching matrix
- AWS-managed policies relevant to MediaPackage
- Cache-key fragmentation (the hit-ratio killer)
- Misconfiguration catalogue
- What this layer can and cannot observe

## Cache-behavior precedence model

A distribution has one `DefaultCacheBehavior` plus an **ordered** list of
`CacheBehaviors`. For each request, CloudFront evaluates path patterns top to
bottom and uses the **first** match; if none match, the default applies. Order
matters: a broad pattern placed above a specific one shadows it.

Each behavior binds:

- `PathPattern` — e.g. `*.m3u8`, `index_*.ts`, `/out/v1/*`
- `TargetOriginId` — which origin (must resolve to a real `Origins.Items[].Id`)
- `ViewerProtocolPolicy` — `redirect-to-https` is standard for media
- `CachePolicyId` — controls TTLs and the cache key (modern config)
- `OriginRequestPolicyId` — controls what is forwarded to the origin
- Legacy `ForwardedValues` — older distributions only; still defines cache key

When `CachePolicyId` is present, TTLs and cache key come from the policy, and
legacy `MinTTL`/`MaxTTL`/`DefaultTTL`/`ForwardedValues` on the behavior are
ignored. Read the policy with `get-cache-policy --id <id>` if deeper TTL detail
is needed.

## Content-type → caching matrix

| Content | Typical path patterns | Caching intent | Failure mode if wrong |
|---|---|---|---|
| HLS manifest | `*.m3u8` | Short TTL (a few seconds) or no-store | Too long → player never sees new live segments → **stall** |
| DASH manifest | `*.mpd` | Short TTL or no-store | Same stall symptom |
| HLS segments | `*.ts` | Long TTL (immutable) | Too short / per-request key → **origin hammering**, low hit ratio |
| CMAF segments | `*.m4s`, `*.cmfv`, `*.cmfa` | Long TTL | Same hammering symptom |
| Init/MP4 | `*.mp4`, `init*.cmf*` | Long TTL | Same |
| Image/captions | `*.jpg`, `*.vtt`, `*.webvtt` | Long TTL | Minor |

The cardinal split: **manifests fresh, segments long.** A live stream wants the
player to re-fetch the manifest constantly (to discover new segments) while
serving each immutable segment from cache. Most media-delivery CDN problems that
present *without* an error-rate spike trace back to this split being wrong.

## AWS-managed policies relevant to MediaPackage

AWS publishes managed cache and origin-request policies; prefer them over
hand-rolled `ForwardedValues`. Confirm exact IDs/names at runtime with
`list-cache-policies` and `list-origin-request-policies` rather than memorizing —
managed-policy catalogs change.

| Need | Managed policy family | Why |
|---|---|---|
| Cache static segments aggressively | A "caching optimized" managed cache policy | Path-only cache key, long TTLs, gzip/br |
| Never cache (manifests, if not handled by TTL) | A "caching disabled" managed cache policy | Forces revalidation |
| Forward the headers MediaPackage needs | An Elemental-MediaPackage managed origin-request policy | Forwards the origin headers (and CDN-auth header pattern) the origin expects |

When inspecting a distribution, note whether segment behaviors use a long-TTL
caching policy and a **path-only** cache key. If a behavior forwards all query
strings/headers/cookies into the cache key, flag it (next section).

## Cache-key fragmentation (the hit-ratio killer)

The cache key is the set of attributes that make two requests "the same" to the
cache. For segments it should be the **URI path alone**. When the cache key also
includes:

- **Query strings** — per-viewer tokens, cache-busting params, session ids
- **Cookies** — any forwarded cookie
- **Headers** — viewer-specific headers (e.g. `User-Agent` at full granularity)

…then otherwise-identical segment requests split into many distinct cache
entries. Each "new" key is a miss → an origin fetch. Hit ratio collapses, origin
(MediaPackage `EgressRequestCount`) climbs, and the symptom looks like an origin
overload that is actually a cache-key bug at the edge.

Diagnostic: a low **segment** hit ratio with healthy error rates and a segment
behavior whose cache policy includes query strings/cookies/headers is a
fragmentation finding. Manifests legitimately have low hit ratios (short TTL) —
judge fragmentation on segment paths, not manifest paths.

## Misconfiguration catalogue

| Symptom | Likely cache-behavior cause |
|---|---|
| Playback stalls, error rates normal | Manifest behavior TTL too long |
| High origin `EgressRequestCount` vs viewer `Requests`, low segment hit ratio | Segment TTL too short, or query-string/cookie in the segment cache key, or Origin Shield off |
| 404 on segments only | OriginPath or path-pattern mismatch vs the MediaPackage endpoint URL structure |
| 403 on all paths | Viewer protocol/auth (OAC, CDN-auth header) or geo restriction, not caching |
| Some segments cached, some not | A broad path pattern shadowing a specific one (precedence order wrong) |
| Compression-related size oddities | `Compress=true` on already-compressed media (segments are not re-compressible; usually harmless but explains size metrics) |

## What this layer can and cannot observe

The agent reads configuration and metrics; it does not change them. Cache TTLs,
policy assignments, and Origin Shield placement are **observations and
candidates** — reported as "Observed … / Expected … / Question …", never as an
executed fix. Hit ratio derived from logs is an
estimate (sampling, Origin Shield accounting); state the derivation when citing
it so the customer can weigh it.
