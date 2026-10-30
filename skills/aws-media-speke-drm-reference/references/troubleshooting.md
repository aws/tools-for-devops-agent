# DRM troubleshooting and operations

Independent reference. **Diagnosis uses public AWS APIs and the operator's own logs only** -- AWS CLI for
MediaPackage / MediaPackage v2 / API Gateway / ACM, CloudWatch metrics, EventBridge events. No internal support
tooling is required or assumed.

## Architecture (where the layers are)

```
Encryptor (MediaPackage / MediaConvert)
   | IAM SigV4
   v
API Gateway  (MUST be in the same region as the encryptor)
   |
   v
DRM platform key provider  -->  Player (license requests)
   |
   v
[optional] ACM (RSA-2048 content-key encryption, same region)
```

Auth: IAM role assumption + SigV4. Trust principal is `mediapackage.amazonaws.com` for MediaPackage v1 and
`mediapackagev2.amazonaws.com` for MediaPackage v2. Permission policy: `execute-api:Invoke` on the API Gateway
resource ARN, and nothing else.

## MediaPackage endpoint encryption support

| Endpoint | Max system IDs | Key rotation | SPEKE v1 | SPEKE v2 | Notes |
|---|---|---|---|---|---|
| HLS (TS) | 1 | Yes | Yes | No | AES-128 or Sample-AES only |
| CMAF (HLS) | 3 | Yes (v1 only) | Yes | Yes | cbcs + cenc; Widevine+PlayReady+FairPlay |
| DASH | 2 | Yes (v1 only) | Yes | Yes | Widevine+PlayReady |
| MSS | 1 | No | Yes | No | PlayReady only |

## EMPv1 vs EMPv2 for DRM

| Capability | MediaPackage v1 | MediaPackage v2 |
|---|---|---|
| SPEKE v1 | Yes | No |
| SPEKE v2 | Yes (DASH + CMAF) | Yes (only option) |
| Key rotation | Yes (SPEKE v1 only) | No |
| Multi-key | Yes (SPEKE v2) | Yes (SPEKE v2) |
| Cross-region failover | No | Yes |
| LL-HLS | No | Yes |
| MSS / HLS-TS output | Yes | No |
| IAM trust principal | `mediapackage.amazonaws.com` | `mediapackagev2.amazonaws.com` |

## Layer-by-layer failure modes

### SPEKE layer
| Failure | Symptom | Diagnostic | Mitigation |
|---|---|---|---|
| Key provider unreachable on first request | HTTP 404 to all viewers (no cached key exists yet) | key-provider error event; no prior key | pre-warm the endpoint before go-live |
| Key provider unreachable during rotation | usually no viewer impact (stale key reused) | key-provider error event | monitor; accept stale-key risk |
| SPEKE timeout (`>~29s`) | same as unreachable | API Gateway 504 | co-locate the key provider in the encryptor's region |
| Malformed CPIX response | encryption stops | key-provider logs + the v2 error contract | use a qualified provider; validate CPIX |
| ACM certificate expiry | encryption failure | ACM console / `aws acm describe-certificate` | alarm 30+ days ahead |

### MediaPackage layer
| Failure | Symptom | Diagnostic | Mitigation |
|---|---|---|---|
| Key mismatch after failover | playback disruption across regions | compare keys per region | epoch-locked CMAF + deterministic keys |
| Wrong SPEKE version for endpoint type | encryption error | endpoint config check | match SPEKE version to endpoint (see table) |
| `keyRotationIntervalSeconds` set with SPEKE v2 | `UnprocessableEntityException` | API error response | rotation requires SPEKE v1 on MediaPackage v1 |

### CDN layer
Certificate expiry, origin access (CloudFront OAC or CDN auth header), and cache behavior. These are
transport/access issues at the edge -- distinct from content DRM, but they can present as playback failure.

### Player layer
CENC/CBCS incompatibility, license-acquisition timeout, and rotation stalls. See
`player-compatibility.md`. Classic case: `cbcs` served to a device that only supports CENC -> serve a CENC
fallback stream.

### Cached-key behavior
When SPEKE is unreachable **and a previous key exists**, MediaPackage reuses the last good key (no documented
TTL -- a tension between availability and rights compliance to address in runbooks). When **no key has ever
been retrieved**, viewers get HTTP 404.

## Monitoring (public AWS)

EventBridge rule for key-provider errors (MediaPackage v1):
```json
{ "source": ["aws.mediapackage"], "detail-type": ["MediaPackage Key Provider Notification"] }
```
Key metrics: `EgressRequestCount` filtered to `StatusCodeRange=4xx` (spikes signal key-provider failure);
`EgressResponseTime` on encrypted endpoints (degradation signals SPEKE latency); API Gateway 5xx; SPEKE Lambda
`Duration`/`Errors`.

> Note: MediaPackage v2 does not currently emit a Key Provider Notification event -- build v2 DRM alerting on
> egress 4xx metrics instead.

## Cross-region failover (DRM checklist)
1. MediaLive: CMAF Ingest output, Output Locking Mode = `EPOCH_LOCKING`.
2. MediaPackage v2: CMAF input channels, identical encryption config in both regions.
3. API Gateway: same region as MediaPackage in each region.
4. SPEKE provider: **deterministic** keys for the same resource ID + period index.
5. CloudFront: Origin Group (primary/backup), failover on 404/5xx.
6. Force-endpoint-error: enable "Missing DRM Keys" on primary, disabled on backup.

## Live-to-VOD with DRM
MediaPackage VOD cannot ingest encrypted assets. Pattern: keep encrypted endpoints for live viewers; add an
**unencrypted shadow endpoint** with `AllowOrigination=false` and startover enabled; run the harvest job
(max 24h, segment-accurate) against the shadow endpoint; ingest the harvested asset into MediaPackage VOD; and
apply DRM at the VOD packaging-configuration level via SPEKE.

## Ad insertion (MediaTailor)
MediaTailor is manifest-only -- it never touches or decrypts media segments. Content segments keep their
`EXT-X-KEY`; ad segments get `EXT-X-KEY:METHOD=NONE`; `EXT-X-DISCONTINUITY` is inserted at every boundary. Key
rotation and ad breaks run on independent timers. No special DRM config is needed in MediaTailor.

## Forensic watermarking
Orthogonal to DRM: A/B variants receive **identical** encryption keys; edge switching (CloudFront Functions or
Lambda@Edge) routes per request. Watermarking has no effect on key management or the SPEKE workflow. Studio
policies (MovieLabs ECP) commonly require watermarking for 4K/UHD/HDR/early-window content -- verify the
current policy version for the title.

## End-to-end encryption stack
| Layer | Service | Encryption | Key point |
|---|---|---|---|
| Contribution | MediaConnect | SRT AES-128/192/256 | transport only; passphrase in Secrets Manager |
| Encoding | MediaLive | static AES-128 (HLS only) | **MUST be OFF when feeding MediaPackage** |
| Ingest link (ML -> MP) | -- | HTTPS + SigV4 (v2) / WebDAV digest (v1) | content is clear; transport-secured |
| Delivery | MediaPackage | SPEKE DRM | consumer-facing Widevine/PlayReady/FairPlay |
| CDN | CloudFront | HTTPS + OAC / CDN auth header | prevents origin bypass |

## Latency reference (caveated)
Order-of-magnitude only; measure in your own deployment. AES per segment is hardware-accelerated (sub-ms); a
warm same-region SPEKE call is typically tens to low-hundreds of ms (cold starts higher -- use provisioned
concurrency); **license acquisition dominates time-to-first-frame**. Optimize with license pre-fetch,
certificate pre-load, and PSSH/`ContentProtectionData` in the manifest.

---
Primary sources: AWS public MediaPackage / MediaPackage v2 / MediaTailor / CloudFront documentation;
DASH-IF CPIX v2.3; operational experience. No internal support tooling is referenced.
