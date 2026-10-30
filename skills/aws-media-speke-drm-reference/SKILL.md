---
name: aws-media-speke-drm-reference
description: >-
  DRM and content-protection reference for AWS Elemental Media Services (SPEKE, CPIX). Use
  whenever a question involves SPEKE (v1/v2), CPIX, DRM content keys, encryption contracts,
  multi-key presets, DRM system IDs (Widevine/PlayReady/FairPlay), commonEncryptionScheme
  (cenc/cbcs/cbc1/cens), the key-rotation-vs-multi-key trade-off, player CENC/CBCS compatibility,
  the SPEKE v2 error contract, MediaPackage/MediaConvert encryption, or a DRM-layer failure
  (license errors, key-pull failures, rotation stalls, encrypted-segment 404s), even if 'DRM' or
  'SPEKE' is not said. Covers architecture advisory, implementation reference, and
  troubleshooting. CONTENT protection only: NOT for IAM access-key rotation, TLS/ACM or KMS/SSE
  storage encryption, MediaConnect SRT, or MediaLive static-key encryption. Route broad non-DRM
  incidents (channel down, ingest failure, general playback) to the matching service investigation
  skill; use this one for content keys, the SPEKE/CPIX contract, presets, or DRM failures.
metadata:
  author: blends
  version: "1.0.0"
  summary: "Reference for SPEKE v1/v2, CPIX, DRM presets, encryption schemes, player compatibility and DRM troubleshooting on AWS Elemental Media Services."
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaPackage, AWS Elemental MediaConvert"
  aws-devops-agent-skills.technical-domains: "Operations, Security"
---

# SPEKE / DRM Reference for AWS Elemental Media Services

You provide expert, precise guidance on Digital Rights Management for AWS Elemental Media Services.
Lead with the answer: the exact preset, system ID, scheme, API parameter, or error string. Then explain.

## Provenance

This SKILL.md and all reference files are original works synthesized from primary sources -- the
DASH-IF CPIX v2.0 and v2.3 specifications, ISO/IEC 23001-7 (Common Encryption), the DASH-IF
system-ID registry, AWS public service documentation, and DRM-vendor documentation -- and from
operational experience. Protocol facts (registered DRM system UUIDs, commonEncryptionScheme enum
values, the SPEKE v2 mandatory error-message strings, CPIX element/attribute names and cardinality
rules) are functional interface facts, stated as facts with primary-source citations. This
contribution is licensed under the repository's license.

## What this skill handles, and what it does not

**You handle:** content-key design and the SPEKE/CPIX encryption contract; CPIX XML authoring and validation;
DRM system IDs, IAM/API-Gateway auth, and EventBridge/CloudWatch monitoring config; and DRM troubleshooting
across the SPEKE, MediaPackage, CDN, and player layers.

**You do not handle (route elsewhere):**
- Generic **IAM access-key rotation** -- that is credential rotation, not content-key rotation.
- **TLS/ACM certificates** or **KMS/SSE storage encryption** -- transport and at-rest encryption, not DRM.
- **MediaConnect SRT** contribution encryption -- transport encryption on the contribution link.
- **MediaLive static-key** output encryption -- and note: this MUST be OFF when feeding MediaPackage.
- A **broad, non-DRM media incident** (channel down, ingest failure, general playback) -- route to the
  matching service investigation skill (aws-medialive-investigate, aws-mediapackage-investigate).
  Come back here when the failure is specifically in the DRM layer.

## Three operating modes

### Mode 1 - Architecture advisory
Walk the decision tree, then state the concrete configuration:
1. Content value tier (early-window / catalog / FAST-AVOD) and resolution tiers (SD/HD/UHD/HDR/HFR).
2. Target device footprint (Apple, Android, smart TVs, STBs, consoles) -> drives scheme + fallback needs.
3. **Key rotation required?** Yes -> SPEKE v1 + MediaPackage v1 (single key). No -> SPEKE v2 (multi-key).
   *(This is the central trade-off -- see below.)*
4. **Multi-key required?** Yes -> SPEKE v2; pick a preset (see `presets-keys-security.md`).
5. Cross-region failover? Yes -> MediaPackage v2 + CMAF Ingest + epoch locking + deterministic keys.
6. Live-to-VOD? Yes -> unencrypted shadow-endpoint harvest pattern.
7. Ad insertion (MediaTailor)? Manifest-only -- no DRM interaction needed.
8. Provider selection -> `providers.md`.

### Mode 2 - Implementation reference
Generate and validate concrete config: SPEKE v1/v2 CPIX request/response payloads; preset-to-pixel-boundary
maps; DRM system UUIDs; IAM role/trust policies and API Gateway setup; the SPEKE v2 error contract; and
EventBridge/CloudWatch monitoring patterns. Depth lives in `references/cpix-authoring.md` and
`references/presets-keys-security.md`.

### Mode 3 - Troubleshooting
Identify the failing layer and check it. Diagnosis uses **public AWS APIs and the operator's own logs only**
(AWS CLI for MediaPackage / MediaPackage v2 / API Gateway / ACM, CloudWatch metrics, EventBridge events) --
no internal support tooling. Full layer-by-layer runbook in `references/troubleshooting.md`.

```
SPEKE layer    -> key provider unreachable, malformed CPIX, version mismatch
MediaPackage   -> cached-key fallback, 404 on first key, encryption-config / SPEKE-version error
CDN            -> certificate expiry, origin access, cache issues
Player         -> CENC/CBCS incompatibility, license-acquisition failure, rotation stall
```

---

## Core facts to keep in context

These are high-value and frequently mis-stated. Keep them in mind for every answer.

### DRM system UUIDs
Table: [Core facts to keep in context: DRM system UUIDs](references/lookup-tables.md#core-facts-to-keep-in-context-drm-system-uuids). Load it when you need the exact values.

Source: DASH-IF Content Protection system-ID registry. These are stable registered identifiers.

### commonEncryptionScheme values (SPEKE v2, per ISO/IEC 23001-7)
- `cenc` -- AES-CTR, full-sample + video-NAL subsample
- `cbc1` -- AES-CBC, full-sample + video-NAL subsample
- `cens` -- AES-CTR, partial video-NAL pattern
- `cbcs` -- AES-CBC, partial video-NAL pattern *(the cross-DRM CMAF default; FairPlay requires CBC-family)*

A single CPIX document **cannot mix** scheme values, and the scheme must be compatible with every requested
DRM system. `cbcs` is the common choice when one CMAF endpoint must serve FairPlay + Widevine + PlayReady.

### The central trade-off: multi-key vs key rotation  (signature accuracy point)
**The SPEKE v2 *protocol* supports key rotation** (via `KeyPeriodFilter` / `ContentKeyPeriod@index`; the
specification includes live rotation examples). **But MediaPackage's *implementation* of SPEKE v2 disables
key rotation.** Setting `keyRotationIntervalSeconds` to anything other than `0` with a SPEKE v2 encryption
contract returns **`UnprocessableEntityException`**. Because **MediaPackage v2 supports only SPEKE v2**, a
MediaPackage-v2 deployment cannot rotate keys at all.

This is a **MediaPackage implementation limitation, not a SPEKE protocol limitation**, and may be lifted in a
future MediaPackage release. The practical consequence:

Table: [Core facts to keep in context: The central trade-off: multi-key vs key rotation  (signature accuracy point)](references/lookup-tables.md#core-facts-to-keep-in-context-the-central-trade-off-multi-key-vs-key-rotation-signature-accuracy-point). Load it when you need the exact values.

> **Do not** tell a user on MediaPackage v2 to "just set `keyRotationIntervalSeconds`" because "SPEKE v2
> supports rotation." It will fail with `UnprocessableEntityException`. Rotation requires SPEKE v1 on
> MediaPackage v1 (single-key). This is the most common DRM misdiagnosis here.

### PlayReady SL3000 audio-key rule
For premium/UHD content using PlayReady hardware DRM (**SL3000**), the **audio must use a content key that is
separate from the SL3000 video key**. Encrypting audio under the same key as SL3000 video downgrades the whole
stream to **SL2000** (software, SD/HD-capped). This is why premium PlayReady requires multi-key (SPEKE v2):
at minimum a UHD video key plus a separate audio key. Detail and the full security-level map in
`references/presets-keys-security.md`.

### How many keys can SPEKE v2 carry?  (reconciled)
SPEKE v2 supports **multiple content keys**. MediaPackage exposes this through video presets numbered
**`PRESET-VIDEO-1` through `PRESET-VIDEO-8`** plus audio presets `PRESET-AUDIO-1/2/3`. The preset *number* is a
label, not a key count: the highest fixed resolution-tier preset yields **up to 5 distinct video keys**
(SD / HD1 / HD2 / UHD1 / UHD2), and `PRESET-VIDEO-8` uses compound HDR/FPS/pixel filters rather than a fixed
count. Audio splits to **up to 3 keys**. State it as "up to 5 resolution-tier video keys + up to 3 audio keys";
the common shorthand "8 keys" conflates the preset numbering ceiling with the distinct-key count.

### SPEKE v1 vs v2 at a glance
Table: [Core facts to keep in context: SPEKE v1 vs v2 at a glance](references/lookup-tables.md#core-facts-to-keep-in-context-speke-v1-vs-v2-at-a-glance). Load it when you need the exact values.

---

## Reference files (load as needed)

- Load [references/cpix-authoring.md](references/cpix-authoring.md) when authoring or validating a CPIX
  document, or when the SPEKE v2 error contract, a KID override, or a request or response payload is in
  question.
- Load [references/presets-keys-security.md](references/presets-keys-security.md) for key-design and
  security-tier questions: preset-to-key mapping, pixel boundaries, the SL3000 detail, and the
  Widevine/PlayReady security-level and HDCP map.
- Load [references/player-compatibility.md](references/player-compatibility.md) for "this device won't
  play" questions: CENC vs CBCS support per platform, key-rotation support, fallback guidance. Dated; CDM
  support drifts, verify per device.
- Load [references/providers.md](references/providers.md) for provider-selection questions: qualified SPEKE
  DRM providers, integration models, and pricing models without dollar figures. Dated; verify current
  pricing with the vendor.
- Load [references/troubleshooting.md](references/troubleshooting.md) for any DRM-layer incident:
  layer-by-layer failure modes, diagnostics with the public AWS CLI, CloudWatch and EventBridge, monitoring
  patterns, cross-region failover, live-to-VOD, ad insertion, watermarking, the end-to-end encryption stack,
  and the caveated latency reference.
- Load [references/lookup-tables.md](references/lookup-tables.md) when you need an exact value from the DRM
  system ID, trade-off, or SPEKE v1 vs v2 tables.

## Response style

- Lead with the concrete answer (exact preset / system ID / scheme / API parameter / error string), then explain.
- Always distinguish **SPEKE protocol capability** from **MediaPackage implementation behavior**.
- When recommending an architecture, name the preset, the SPEKE version, the MediaPackage version, the scheme,
  and the resulting key count.
- Flag operational facts that carry currency risk (provider pricing, player/CDM support, security-level mappings)
  and tell the user to verify against current vendor/AWS documentation.

### Before answering

Check the answer before presenting it:

- The scheme named is compatible with every DRM system the user targets; `cbcs` for FairPlay.
- The SPEKE version named supports the feature asked for: multi-key needs v2, key rotation on MediaPackage needs v1 on MediaPackage v1.
- The preset named yields the key count stated, using the up to 5 video plus up to 3 audio rule.
- Every fact with currency risk (provider pricing, CDM support, security-level maps) carries a verify-with-vendor note.
- Protocol capability and MediaPackage implementation behavior are stated separately.
