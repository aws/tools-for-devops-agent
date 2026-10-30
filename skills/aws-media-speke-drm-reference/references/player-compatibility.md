# Player CENC / CBCS compatibility

Independent reference. **Dated: 2026-06. CDM and OS support drifts -- always verify against the current
device/OS and the player's CDM version.** Use this to diagnose "this device won't play the encrypted stream."

The two encryption schemes in practice are **CENC** (AES-CTR; `cenc`) and **CBCS** (AES-CBC pattern; `cbcs`).
FairPlay requires a CBC-family scheme (`cbcs`). The industry has converged on **CMAF + cbcs**, but CENC is
still needed for some legacy devices.

| Platform | CENC (AES-CTR) | CBCS (AES-CBC) | Key rotation | Notes |
|---|---|---|---|---|
| Chrome 68+ (desktop) | Yes | Yes | Yes | Widevine L3, both schemes |
| Firefox 68+ | Yes | Yes | Yes | Widevine L3 |
| Edge (Chromium) | Yes | Yes | Yes | Widevine L3 + PlayReady |
| Safari (all) | No | Yes | Yes (HLS) | FairPlay only; cbcs mandatory |
| iOS / tvOS (AVPlayer) | No | Yes | Yes | FairPlay only |
| Android 8.0+ (ExoPlayer) | Yes | Yes | Yes | stable cbcs; `setMultiSession` for rotation |
| Android 7.1 (ExoPlayer) | Yes | Buggy | Yes | cbcs can throw `CryptoException` on some devices |
| Android < 7.1 | Yes | No | Glitchy | CENC only; rotation issues |
| Samsung Tizen 2020+ | Yes | Yes | Varies | model-dependent rotation support |
| Samsung Tizen < 2019 | Yes | No | Limited | CENC only; test per model |
| LG webOS 2020+ | Yes | Likely | Varies | depends on CDM version |
| Xbox One 1709+ / Series | Yes | Yes | Yes | PlayReady, both schemes |
| PlayStation 5 | Yes | Yes | Unknown | Widevine + PlayReady |
| Fire TV (4K) | Yes | Yes | Yes | Widevine L1 on 4K models |

## Diagnosing a player failure
1. Identify the device OS/build and the player CDM.
2. Map the failing stream's scheme (`cbcs` or `cenc`) against the row above.
3. If the device lacks the served scheme (classic case: pre-2019 Samsung Tizen on a `cbcs` stream), serve a
   **CENC fallback stream** for those devices, or switch the contract to a scheme the fleet supports.
4. If playback fails only after a rotation boundary, suspect the device's rotation handling -- use longer
   rotation intervals, or single-key (no rotation) for that fleet.

> Because this matrix ages, treat a contradiction between this table and observed device behavior as the table
> being out of date. Verify with the device vendor's current CDM support statement.
