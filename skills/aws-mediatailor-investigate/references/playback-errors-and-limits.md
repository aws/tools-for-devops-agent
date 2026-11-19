# MediaTailor Playback Errors, Fixed Limits, and CDN Context

Reference for Step S4 (player-facing status triage) and the S1 CDN precheck.
Sources (public user guide, read 2026-08-17): `playback-errors`, `limits`,
`parameter-troubleshooting`, `emt-error-codes-reference`, `cdn-bp`,
`cdn-optimize-caching`, `cdn-routing-behaviors`, `troubleshooting-event-flow`.

## How MediaTailor reports a playback error

A player request (direct or through the CDN) that fails returns an HTTP status,
an exception name in the `x-amzn-ErrorType` response header, and a JSON
message. Client errors (4xx) are usually the request itself: formatting, a
parameter, a bad URL, CDN forwarding, or player behavior. Server errors (5xx)
are usually MediaTailor or one of its dependencies (origin, ADS). This is a
starting split, not a verdict; confirm the pattern (init vs mid-session,
per-viewer vs fleetwide, at peak only) before routing.

## Client (4xx) codes

| Code | Exception | Meaning | What to check |
|---|---|---|---|
| 400 | `BadRequestException` | Formatting or content error: a parameter improperly formatted or unencoded, an invalid playback configuration or session ID, a missing configuration alias | Playback endpoint on the player matches `ManifestEndpointPrefix` from `GetPlaybackConfiguration`; encoding and alias rules below; CDN query-string forwarding. **A 400 that appears only after a pause or background** is the session-expiration rule below |
| 403 | `AccessDeniedException` | The request `Host` header does not match the manifest endpoint prefix configured for the playback URL; CDN misconfiguration | CDN origin host / manifest endpoint prefix; for segments, see the CDN-context table |
| 404 | `NotFoundException` | URL maps to nothing, configuration not defined or inactive, or session unavailable | Configuration exists and is active; playback URL matches `ManifestEndpointPrefix`; CDN routing forwards to the right endpoint; reinitialize the session |
| 409 | `ConflictException` | An HLS player loaded multiple playlists simultaneously for one session (session consistency conflict) | Player must request playlists one at a time per the HLS spec; a session URL shared across viewers, or a CDN that drops `aws.sessionId`, produces the same symptom |
| 410 | `Gone` | AWS Support blocked a session or configuration after very high 4xx volume from errant traffic (rare) | AWS Support case; not a configuration bug |

## Server (5xx) codes

| Code | Exception | Meaning | What to check |
|---|---|---|---|
| 500 | `InternalServiceError` | Unhandled exception | Retry; AWS Health Dashboard for MediaTailor in the region |
| 502 | `BadGatewayException` | Origin or ADS address invalid (private IP, `localhost`) | `VideoContentSourceUrl`, `AdDecisionServerUrl` |
| 502 | `UnsupportedManifestException` | Origin manifest changed so it cannot be personalized, or the format is unsupported (for example HLS playlist alignment: SCTE markers not aligned across playlists) | Often one session; reinitialize. If persistent, verify origin manifest support -> origin handoff |
| 503 | `LoadShed` | MediaTailor resource constraint | Retry; AWS Health |
| 503 | `ThrottlingException` | Transactions per second reached the account quota | Ad Insertion Requests quota (below); Service Quotas increase is an operator action |
| 504 | `GatewayTimeoutException` | Timeout contacting the origin server | Origin health and response time against the fixed content-origin timeout below -> origin handoff. ADS slowness never yields a 504; it yields an unfilled avail |

## Fixed limits that explain symptoms

From the MediaTailor quotas page. "Fixed" limits have no increase path; the
remedy is workload-side.

| Limit | Value | Symptom when hit | Adjustable |
|---|---|---|---|
| Content origin server timeout | 2 s | 504 `GatewayTimeoutException`; `Origin.Timeouts` | No |
| ADS timeout | 3 s | Unfilled avail; `AdDecisionServer.Timeouts`; `ERROR_ADS_TIMEOUT` | No |
| Server-side beacon request timeout | 3 s | `ERROR_FIRING_BEACON_FAILED` in the ADS log | No |
| Session expiration | 10x the manifest duration of inactivity | 400 on the next request from a paused or backgrounded player; the player must start a new session (parameters are set once at init and are immutable) | No |
| Ad Insertion Requests | 10,000 requests/s per Region (manifests, session init, tracking, ad segments) | 503 `ThrottlingException` | Yes (Service Quotas) |
| Manifest size | 2 MB per origin manifest | `Origin.ManifestFileSizeTooLarge`; gzip the origin manifest | No |
| ADS URL length | 25,000 characters | Configuration rejected | No |
| Configurations | 1,000 per account | Create fails | Check quotas page |
| Prefetch schedules | 25 active per playback configuration | Create fails; expired schedules do not count | Check quotas page |

Event-flow timing guidance from the troubleshooting chapter (guidance, not
SLA): total ad-insertion flow over 5 s, ADS response over 2 s, or manifest
personalization over 1 s each warrant a look at, respectively, the whole path,
the ADS/network, and creative processing or the origin.

## Parameter and alias rules (400 at session init)

- Unsupported characters used unencoded in parameter values (`:`, `?`, `&`,
  `=`, `%`, `/`) cause 400s at init, truncated values, or malformed ADS
  requests; URL-encode them.
- Domain variables used in critical URLs (`VideoContentSourceUrl`,
  `AdSegmentUrlPrefix`, `ContentSegmentUrlPrefix`) must be defined in
  `ConfigurationAliases` and the list of aliased values must be exhaustive; a
  missing or invalid alias value is a 400.
- Player parameters are referenced in the ADS URL template as
  `[player_params.<name>]` and supplied by the player as `ads.<name>` query
  parameters (or in the session-init body); a value sent without the `ads.`
  prefix is not treated as a player parameter. A macro that substitutes empty
  shows up as `WARNING_URL_VARIABLE_SUBSTITUTION_FAILED` in the ADS log, and the
  request actually sent is in `MAKING_ADS_REQUEST.adsRequestUrl` (an ADS-request
  warning, not a player 4xx). Verify the exact prefix rules on the
  `variables-player` guide page before advising a customer.

## CDN context

### Cardinal caching rule (SSAI)

Personalized manifests are per session and must never be cached or shared
between viewers. Content and ad segments should be cached aggressively.

| Content type | TTL | Path pattern | Cache key |
|---|---|---|---|
| Multivariant playlists | 0 s | `/v1/master/*` | URL path + all query parameters |
| Media playlists | 0 s | `/v1/manifest/*` | URL path + all query parameters |
| DASH MPDs | 0 s | `/v1/dash/*` | URL path + all query parameters |
| Content segments | 24 h+ | content-specific | URL path only |
| Ad segments | 24 h+ | `/v1/segment/*` | URL path only |

Also forward all query strings (ad variables and `aws.sessionId` must reach
MediaTailor) and the `User-Agent`, `Host`, `X-Forwarded-For`, and
`Accept-Encoding` headers. Server-guided (SGAI) and Channel Assembly manifests
have different TTL rules; see the caching-optimization page.

Symptom map: "everyone gets the same ads", stale breaks, or tracking that
belongs to another viewer with healthy MediaTailor metrics = a cached
personalized manifest (any `Hit` cache status on a manifest path proves it).
Isolate CDN from service by requesting the manifest directly against the
MediaTailor endpoint with a fresh `aws.sessionId`: distinct ads direct but
identical through the CDN pins it on the CDN.

### Codes as passed through the CDN

| Code | Common cause | Check |
|---|---|---|
| 400 | Malformed or missing query parameters, invalid session ID | CDN query-string forwarding; parameter encoding |
| 403 (ad segment) | Player requested a segment that does not exist or is not permitted; MediaTailor may have emitted an invalid ad-segment URL | AWS Support if MediaTailor is generating invalid segment URLs |
| 403 (content segment) | Origin access restrictions or authentication | Origin permissions and credentials; segment exists at the URL -> origin handoff |
| 404 | Configuration missing or inactive, wrong playback path, non-existent resource | Configuration state; `ManifestEndpointPrefix`; CDN routing rules |
| 500 | Origin issues, ADS connectivity, manifest processing | Origin health, ADS response validity, service status |
| 502 | Origin unreachable or invalid response; `UnsupportedManifestException` on HLS playlist alignment | Origin manifest -> origin handoff |

`CdnConfiguration` semantics from the configuration: `AdSegmentUrlPrefix` names
the CDN prefix MediaTailor writes for ad segments (unset means ad segments come
from a MediaTailor-owned domain, which is why DASH ad periods reference a domain
the customer "doesn't recognize"); `ContentSegmentUrlPrefix` substitutes the
content-segment origin with the CDN prefix (unset preserves the origin URLs).
