# CPIX authoring and the SPEKE encryption contract

Independent reference. Synthesized from the DASH-IF CPIX v2.0 / v2.3 specifications and ISO/IEC 23001-7.
Worked examples below are original (fresh content IDs and KIDs). Protocol facts (element names, mandatory
attributes, error strings) are functional interface facts.

## The four CPIX sections (SPEKE v2)

A SPEKE v2 CPIX document has three mandatory list sections plus one optional section for live key rotation:

1. **`ContentKeyList`** (mandatory, live + VOD) -- one or more `ContentKey`, each with:
   - `kid` (mandatory) -- key-identifier UUID
   - `commonEncryptionScheme` (mandatory) -- `cenc` / `cbcs` / `cbc1` / `cens`
   - `explicitIV` (optional)
   - `Data/Secret/PlainValue` (clear key) or `EncryptedValue` (RSA-wrapped key)
2. **`DRMSystemList`** (mandatory, live + VOD) -- one or more `DRMSystem` per key, each with:
   - `kid` (mandatory, references a `ContentKey`)
   - `systemId` (mandatory, the DRM system UUID)
   - `PSSH` (mandatory if ISO-BMFF encapsulation)
   - two `HLSSignalingData` elements, `playlist="media"` and `playlist="master"` (if HLS)
   - `ContentProtectionData` (optional, DASH manifest signaling)
   - `SmoothStreamingProtectionHeaderData` (if MSS)
   - Rule: if both `PSSH` and the `ContentProtectionData` inner `<pssh>` are present, they must be identical.
3. **`ContentKeyPeriodList`** (optional, live only) -- one or more `ContentKeyPeriod`, each with `id`
   (UUID recommended) and `index` (period counter).
4. **`ContentKeyUsageRuleList`** (mandatory, live + VOD) -- the encryption contract. Each
   `ContentKeyUsageRule` has `kid`, a mandatory `intendedTrackType`, at least one `AudioFilter` or
   `VideoFilter`, and an optional `KeyPeriodFilter` for rotation.

Top-level `CPIX` requires `contentId` (mandatory, immutable -- the key provider cannot override it),
`version` (mandatory, `"2.3"` for SPEKE v2), and the `cpix`/`pskc` namespaces.

## Encryption-contract rules

- `intendedTrackType` must be **unique** across rules in a document; it cannot repeat. Values may be simple
  (`ALL`, `VIDEO`, `AUDIO`, `SD`, `HD`, `UHD`, ...) or compound, joined with `+` (e.g. `SD+HD`).
- The number of `VideoFilter`/`AudioFilter` children must match the number of `+`-joined sub-components.
  `intendedTrackType="SD+HD"` -> two `VideoFilter` elements with different attributes.
- **Special case:** `intendedTrackType="ALL"` requires exactly one `AudioFilter` and one `VideoFilter`,
  both with **no attributes**. Any other filter combination under `ALL` is invalid.
- Filters supported by SPEKE (others are ignored or rejected):

  | Filter | Supported attributes | Not supported |
  |---|---|---|
  | `VideoFilter` | `minPixels`, `maxPixels`, `hdr`, `minFps`, `maxFps` | `wcg` |
  | `AudioFilter` | `minChannels`, `maxChannels` | -- |
  | `KeyPeriodFilter` | `periodId` | -- |
  | `BitrateFilter` | (not supported) | all |
  | `LabelFilter` | (not supported) | all |

- Range inclusivity: `VideoFilter` pixels `[minPixels, maxPixels]` inclusive on both ends; fps
  `(minFps, maxFps]` inclusive only on `maxFps`; `AudioFilter` channels `[minChannels, maxChannels]`
  inclusive on both ends.

### Pixel boundaries (resolution tiers)
- SD = up to 1024x576 = **589,824** px
- HD = up to 1920x1080 = **2,073,600** px
- UHD1 = up to 4096x2160 = **8,847,360** px

A common 3-key split: SD `maxPixels="589824"`, HD `minPixels="589825" maxPixels="2073600"`,
UHD `minPixels="2073601"`.

### Problematic situations (encryptor vs key provider behavior)
| Situation | Encryptor should | Key provider should |
|---|---|---|
| No rule applies to a track | check external config; error if encryption was expected | n/a (no streamset knowledge) |
| Multiple rules overlap a track | apply the last rule evaluated in document order | n/a |
| Contract changes mid-cycle | raise and stop | must not modify the contract |
| Malformed contract | do not send the request | return `Malformed encryption contract` |
| Violates DRM security constraints | raise if aware | return `Requested CPIX encryption contract not supported` |
| No filters present | do not send the document | return `Missing CPIX encryption contract` |

## SPEKE v2 mandatory error contract

A SPEKE v2 key provider must return these exact strings, with an HTTP **4XX or 5XX** code -- **never 200** for
an error. `422` is recommended for SPEKE/CPIX errors. On an error in the response body, the encryptor must
**throw and not retry the request as SPEKE v1** (this prevents silent version-downgrade).

| Error case | Required message |
|---|---|
| `CPIX@contentId` missing | `Missing CPIX@contentId` |
| `CPIX@version` missing | `Missing CPIX@version` |
| `CPIX@version` unsupported | `Unsupported CPIX@version` |
| `ContentKey@commonEncryptionScheme` missing | `Missing ContentKey@commonEncryptionScheme for KID {id}` |
| Mixed scheme values in one document | `Non compliant ContentKey@commonEncryptionScheme combination` |
| Scheme incompatible with a DRM system | `ContentKey@commonEncryptionScheme non compatible with DRMSystem {id}` |
| Unsupported SPEKE version (header) | `Unsupported SPEKE version` |
| Malformed contract | `Malformed encryption contract` |
| Contract violates DRM security levels | `Requested CPIX encryption contract not supported` |
| No `VideoFilter`/`AudioFilter` present | `Missing CPIX encryption contract` |

The key provider must not modify the encryption contract from the request, and cannot override
`CPIX@contentId`, `CPIX@version`, `ContentKey@commonEncryptionScheme`, or the `X-Speke-Version` header.

## KID override

The key provider may return a different KID than the request carried (both v1 and v2). When it does, every
element -- `ContentKey`, `DRMSystem`, and `ContentKeyUsageRule` -- must consistently use the new KID.

## Worked example -- SPEKE v2 live request (one video key, one audio key, FairPlay + Widevine + PlayReady)

Original example. Two keys: a video key and a separate audio key (also the minimum for premium PlayReady).

```xml
<cpix:CPIX contentId="demo-channel-2026" version="2.3"
    xmlns:cpix="urn:dashif:org:cpix" xmlns:pskc="urn:ietf:params:xml:ns:keyprov:pskc">
  <cpix:ContentKeyList>
    <cpix:ContentKey kid="3f0a1c44-7e21-4b8a-9c30-0a11bb22cc01" commonEncryptionScheme="cbcs"/>
    <cpix:ContentKey kid="9b7d5e10-2c44-4f6a-8e91-7a55dd66ee02" commonEncryptionScheme="cbcs"/>
  </cpix:ContentKeyList>
  <cpix:DRMSystemList>
    <!-- FairPlay (video key) -->
    <cpix:DRMSystem kid="3f0a1c44-7e21-4b8a-9c30-0a11bb22cc01"
        systemId="94ce86fb-07ff-4f43-adb8-93d2fa968ca2">
      <cpix:HLSSignalingData playlist="media"/>
      <cpix:HLSSignalingData playlist="master"/>
    </cpix:DRMSystem>
    <!-- Widevine (video key) -->
    <cpix:DRMSystem kid="3f0a1c44-7e21-4b8a-9c30-0a11bb22cc01"
        systemId="edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
      <cpix:HLSSignalingData playlist="media"/>
      <cpix:HLSSignalingData playlist="master"/>
      <cpix:ContentProtectionData/>
      <cpix:PSSH/>
    </cpix:DRMSystem>
    <!-- PlayReady (video key) -->
    <cpix:DRMSystem kid="3f0a1c44-7e21-4b8a-9c30-0a11bb22cc01"
        systemId="9a04f079-9840-4286-ab92-e65be0885f95">
      <cpix:HLSSignalingData playlist="media"/>
      <cpix:HLSSignalingData playlist="master"/>
      <cpix:ContentProtectionData/>
      <cpix:PSSH/>
      <cpix:SmoothStreamingProtectionHeaderData/>
    </cpix:DRMSystem>
    <!-- the audio key would repeat the same three DRMSystem blocks with the audio kid -->
  </cpix:DRMSystemList>
  <cpix:ContentKeyUsageRuleList>
    <cpix:ContentKeyUsageRule kid="3f0a1c44-7e21-4b8a-9c30-0a11bb22cc01" intendedTrackType="VIDEO">
      <cpix:VideoFilter/>
    </cpix:ContentKeyUsageRule>
    <cpix:ContentKeyUsageRule kid="9b7d5e10-2c44-4f6a-8e91-7a55dd66ee02" intendedTrackType="AUDIO">
      <cpix:AudioFilter/>
    </cpix:ContentKeyUsageRule>
  </cpix:ContentKeyUsageRuleList>
</cpix:CPIX>
```

In the response, the key provider fills `Data/Secret/PlainValue` (or `EncryptedValue`) per key and populates
the signaling elements (`PSSH`, `HLSSignalingData`, `ContentProtectionData`, `SmoothStreamingProtectionHeaderData`).

## SPEKE v1 differences (when rotation is required)

SPEKE v1 (CPIX 2.0) uses the custom `urn:aws:amazon:com:speke` namespace, a single key per content (no
multi-track keys), `URIExtXKey` + `speke:KeyFormat` / `speke:KeyFormatVersions` for HLS, and
`SPEKE:ProtectionHeader` for MSS PlayReady. Rotation uses `KeyPeriodFilter` + `ContentKeyPeriod@index`. There
is no `X-Speke-Version` header and no mandatory `commonEncryptionScheme`. Use v1 only when MediaPackage key
rotation is required (see the trade-off in SKILL.md).

## Content-key encryption (optional RSA-2048 layer)

To encrypt content keys in transit, the encryptor adds a `DeliveryDataList` (carrying an X.509 cert); the key
provider returns a `DocumentKey` (AES-256-CBC, RSA-OAEP-wrapped), a `MACMethod` (HMAC-SHA512), and content
keys via `pskc:EncryptedValue` instead of `pskc:PlainValue`. Certificates live in ACM, same region as the
encryptor. SPEKE does not support XMLDSIG and requires 2048-bit RSA certificates.

---
Primary sources: DASH-IF CPIX v2.0 / v2.3; ISO/IEC 23001-7 (Common Encryption); DASH-IF system-ID registry.
