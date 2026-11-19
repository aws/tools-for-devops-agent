# Encryption presets, key design, and DRM security levels

Independent synthesis from DASH-IF CPIX v2.3, AWS public MediaPackage documentation, and DRM-vendor
documentation. Security-level and HDCP specifics carry currency risk -- verify against current vendor docs.

## Video presets (SPEKE v2)

MediaPackage configures the encryption contract through two API fields, `PresetSpeke20Video` and
`PresetSpeke20Audio`. Video presets are **labelled** `PRESET-VIDEO-1` through `PRESET-VIDEO-8`. The number is
a label, not a key count.

| Preset | Distinct video keys | Split |
|---|---|---|
| `PRESET-VIDEO-1` | 1 | all video (one `VideoFilter`, no attributes) |
| `PRESET-VIDEO-2` | 2 | SD (`<=589,824`) / HD (`>589,824`) |
| `PRESET-VIDEO-3` | 3 | SD / HD (`<=2,073,600`) / UHD (`>2,073,600`) -- most common |
| `PRESET-VIDEO-4` | 4 | SD / HD / UHD1 (`<=8,847,360`) / UHD2 (`>8,847,360`) |
| `PRESET-VIDEO-5` | 5 | SD / HD1 (`<=921,600`) / HD2 (`<=2,073,600`) / UHD1 / UHD2 |
| `PRESET-VIDEO-8` | varies | compound filters using `hdr`, `minFps`, `maxFps`, `minPixels`, `maxPixels` |

**Reconciliation of "8 keys" vs "5 keys":** the maximum number of *distinct resolution-tier video keys* is
**5** (`PRESET-VIDEO-5`: SD/HD1/HD2/UHD1/UHD2). The `-8` in the preset name is the preset-numbering ceiling,
not a key count; `PRESET-VIDEO-8` uses compound filters and does not imply eight keys. State capacity as
"**up to 5 resolution-tier video keys + up to 3 audio keys**"; "8 video keys" is a misreading of the label.

## Audio presets
| Preset | Keys | Configuration |
|---|---|---|
| `PRESET-AUDIO-1` | 1 | all audio (`AudioFilter`, no attributes) |
| `PRESET-AUDIO-2` | 2 | stereo (`maxChannels=2`) / multichannel (`minChannels=3`) |
| `PRESET-AUDIO-3` | 3 | stereo / MC 3-6ch / MC 7+ch |

## Common production configurations
| Content type | Video preset | Audio preset | Total keys |
|---|---|---|---|
| Premium UHD (early window) | `PRESET-VIDEO-3` | `PRESET-AUDIO-1` | 4 |
| Standard multi-tier | `PRESET-VIDEO-2` | `PRESET-AUDIO-1` | 3 |
| Single-key (FAST/AVOD) | `intendedTrackType="ALL"` (shared) | -- | 1 |

## PlayReady SL3000 audio-key rule (critical)

PlayReady has two robustness levels relevant here: **SL2000** (software DRM, SD/HD) and **SL3000** (hardware
TEE, premium UHD). The license server enforces these. **A content key used for SL3000 video must not also
encrypt audio.** If audio shares the SL3000 video key, the license policy effectively downgrades the entire
stream to SL2000 -- meaning premium video is no longer served at SL3000 robustness.

Consequence: premium PlayReady **requires multi-key** (SPEKE v2). The minimum is a UHD video key plus a
separate audio key (`PRESET-AUDIO-1` provides that separate audio key). This is the single most common
preset-design mistake for premium content.

## Security-level mapping (verify against current vendor docs; values drift)

| Content tier | Widevine | PlayReady | HDCP (typical studio policy) | Preset target |
|---|---|---|---|---|
| SD & audio | L3 (software) | SL2000 | not required | SD key |
| 720p HD | L1 (TEE) or L3 | SL2000 | v1.4 | HD key |
| 1080p+ / HDR / HFR / early window | L1 (HW_SECURE_ALL) | SL3000 | v2.2 | UHD key (separate audio key) |

Per-track encryption is a **packaging-side** mechanism (which key encrypts which track); robustness-level
enforcement is a **license-server-side** mechanism (which keys a device is licensed to receive). They work in
tandem: an L3/software device receives only the SD key; an L1/hardware device receives HD and UHD keys.

> Currency note: Widevine security-level names, PlayReady SL tiers, and studio HDCP requirements change over
> time and vary by studio/MovieLabs policy version. Treat this table as a starting map and confirm the current
> requirements for the specific title and distribution window.

---
Primary sources: AWS public MediaPackage `PresetSpeke20Video` / `PresetSpeke20Audio` documentation; Google
Widevine and Microsoft PlayReady robustness documentation; DASH-IF CPIX v2.3 filter semantics.
