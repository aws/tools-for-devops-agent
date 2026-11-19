# SPEKE / DRM Reference: Lookup Tables

Metric catalogs, status tables and field tables relocated from SKILL.md so they load
only when the step that uses them runs. Each heading names the SKILL.md step and
subsection the table belongs to; the surrounding instructions stay in SKILL.md.

## Core facts to keep in context: DRM system UUIDs

| DRM system | System ID (UUID) |
|---|---|
| Google Widevine | `edef8ba9-79d6-4ace-a3c8-27dcd51d21ed` |
| Microsoft PlayReady | `9a04f079-9840-4286-ab92-e65be0885f95` |
| Apple FairPlay | `94ce86fb-07ff-4f43-adb8-93d2fa968ca2` |
| HLS AES-128 (clear key) | `81376844-f976-481e-a84e-cc25d39b0b33` |

## Core facts to keep in context: The central trade-off: multi-key vs key rotation  (signature accuracy point)

| Need | SPEKE version | MediaPackage version | Cost of the choice |
|---|---|---|---|
| Key rotation | v1 | v1 (EMPv1) | single key only -- no per-resolution multi-key |
| Multi-key (per-resolution keys) | v2 | v1 (DASH/CMAF) or v2 | no key rotation in MediaPackage |
| Cross-region failover | v2 | v2 | no key rotation |

## Core facts to keep in context: SPEKE v1 vs v2 at a glance

| | SPEKE v1 (CPIX 2.0) | SPEKE v2 (CPIX 2.3) |
|---|---|---|
| XML namespace | custom `urn:aws:amazon:com:speke` | standard CPIX only |
| Multi-key | no (single key per content) | yes |
| HLS signaling | `URIExtXKey` + `speke:KeyFormat` | two `HLSSignalingData` (`playlist="media"` and `"master"`) |
| MSS signaling | `SPEKE:ProtectionHeader` | `SmoothStreamingProtectionHeaderData` |
| Version header | none | `X-Speke-Version: 2.0` (mandatory) |
| Content ID | `CPIX@id` | `CPIX@contentId` (mandatory, immutable) |
| Encryption scheme | implicit | `ContentKey@commonEncryptionScheme` (mandatory) |
| On error | unspecified | encryptor must NOT silently retry as v1 |
| Heartbeat | `GET /heartbeat` | deprecated |
