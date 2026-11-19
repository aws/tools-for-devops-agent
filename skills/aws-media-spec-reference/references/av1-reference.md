---
name: av1-reference
description: "AV1 codec spec reference. Use for AV1 encoding questions, MediaLive AV1 support, or device compatibility."
inclusion: manual
---
# AV1 Codec Reference (AOM AV1 Bitstream & Decoding Process Specification)

Source: AV1 Bitstream & Decoding Process Specification v1.0.0 with Errata 1 (681 pages), from Alliance for Open Media. Royalty-free codec.

## Key Differences from H.264/AVC and H.265/HEVC

- **Royalty-free**: No patent licensing fees (unlike H.264 via MPEG-LA, H.265 via MPEG-LA/HEVC Advance/Velos)
- **~30% better compression than HEVC** at equivalent quality
- **Superblocks** up to 128×128 (vs 64×64 CTU in HEVC, 16×16 MB in H.264)
- **Coding units** recursively split to 4×4
- **67 intra prediction modes** (vs 35 in HEVC, 9 in H.264)
- **Compound inter prediction**: Weighted combination of two reference frames
- **Warped motion**: Affine transformations for global and local motion
- **Film grain synthesis**: Noise modeled and stripped at encoder, re-synthesized at decoder
- **Loop restoration filter**: Wiener and self-guided filters in addition to deblocking + CDEF
- **CDEF** (Constrained Directional Enhancement Filter): Edge-preserving filter replacing SAO
- **Two tiers**: Main (seq_tier=0) and High (seq_tier=1), similar to HEVC
- **No CAVLC/CABAC**: Uses a multi-symbol arithmetic coder with CDF-based probability updates
- **No B-frames in traditional sense**: AV1 uses "altref" frames (alternate reference) for temporal prediction without display, achieving similar compression to B-frames without the reordering terminology

## Profiles

AV1 has only 3 profiles — much simpler than H.264 (15+) or HEVC (30+):

| Profile | seq_profile | Bit Depth | Monochrome | Chroma Subsampling | Use Case |
|---------|-------------|-----------|------------|-------------------|----------|
| Main | 0 | 8 or 10 | Yes | YUV 4:2:0 | **Standard OTT streaming, SDR and HDR.** |
| High | 1 | 8 or 10 | No | YUV 4:4:4 | Screen content, gaming, professional. |
| Professional | 2 | 8, 10, or 12 | Yes | YUV 4:2:0, 4:2:2, 4:4:4 | Broadcast contribution, archival. |

### Profile Hierarchy

```
Main ⊂ High ⊂ Professional
```

A High decoder can decode all Main profile streams. A Professional decoder can decode all streams.

### Profile Selection for MediaLive

| Use Case | Profile | Rationale |
|----------|---------|-----------|
| SDR/HDR OTT streaming | Main (0) | 4:2:0, 8 or 10 bit. All consumer devices. |
| Screen sharing / gaming | High (1) | 4:4:4 for sharp text/graphics. |
| Professional contribution | Professional (2) | 12-bit, 4:2:2 support. |

## Tiers

Like HEVC, AV1 has two tiers:
- **Main Tier** (seq_tier=0): Lower bitrate limits. Standard consumer streaming.
- **High Tier** (seq_tier=1): Higher bitrate limits. Only defined for levels 4.0+.

## Levels

| Level | seq_level_idx | MaxPicSize (samples) | MaxHSize | MaxVSize | MaxDisplayRate (samples/s) | MainMbps | HighMbps | MainCR | MaxTiles | Example |
|-------|--------------|---------------------|----------|----------|--------------------------|----------|----------|--------|----------|---------|
| 2.0 | 0 | 147,456 | 2,048 | 1,152 | 4,423,680 | 1.5 | — | 2 | 8 | 426×240@30 |
| 2.1 | 1 | 278,784 | 2,816 | 1,584 | 8,363,520 | 3.0 | — | 2 | 8 | 640×360@30 |
| 3.0 | 4 | 665,856 | 4,352 | 2,448 | 19,975,680 | 6.0 | — | 2 | 16 | 854×480@30 |
| 3.1 | 5 | 1,065,024 | 5,504 | 3,096 | 31,950,720 | 10.0 | — | 2 | 16 | 1280×720@30 |
| 4.0 | 8 | 2,359,296 | 6,144 | 3,456 | 70,778,880 | 12.0 | 30.0 | 4 | 32 | 1920×1080@30 |
| 4.1 | 9 | 2,359,296 | 6,144 | 3,456 | 141,557,760 | 20.0 | 50.0 | 4 | 32 | 1920×1080@60 |
| 5.0 | 12 | 8,912,896 | 8,192 | 4,352 | 267,386,880 | 30.0 | 100.0 | 6 | 64 | 3840×2160@30 |
| 5.1 | 13 | 8,912,896 | 8,192 | 4,352 | 534,773,760 | 40.0 | 160.0 | 8 | 64 | 3840×2160@60 |
| 5.2 | 14 | 8,912,896 | 8,192 | 4,352 | 1,069,547,520 | 60.0 | 240.0 | 8 | 64 | 3840×2160@120 |
| 5.3 | 15 | 8,912,896 | 8,192 | 4,352 | 1,069,547,520 | 60.0 | 240.0 | 8 | 64 | 3840×2160@120 |
| 6.0 | 16 | 35,651,584 | 16,384 | 8,704 | 1,069,547,520 | 60.0 | 240.0 | 8 | 128 | 7680×4320@30 |
| 6.1 | 17 | 35,651,584 | 16,384 | 8,704 | 2,139,095,040 | 100.0 | 480.0 | 8 | 128 | 7680×4320@60 |
| 6.2 | 18 | 35,651,584 | 16,384 | 8,704 | 4,278,190,080 | 160.0 | 800.0 | 8 | 128 | 7680×4320@120 |
| 6.3 | 19 | 35,651,584 | 16,384 | 8,704 | 4,278,190,080 | 160.0 | 800.0 | 8 | 128 | 7680×4320@120 |

Notes:
- Level numbering: X.Y where X = 2 + (seq_level_idx >> 2), Y = (seq_level_idx & 3)
- Levels 2.2, 2.3, 3.2, 3.3, 4.2, 4.3, 7.0-7.3 exist in the numbering but are not yet defined
- seq_level_idx=31 = "maximum parameters" (no level constraints — for extreme still images)
- MaxPicSize is in luma samples (same unit as HEVC)
- MaxBitrate: Main Tier = MainMbps × 1,000,000; High Tier = HighMbps × 1,000,000
- MaxBufferSize = MaxBitrate × 1 second
- BitrateProfileFactor: Main(0)=1.0, High(1)=2.0, Professional(2)=3.0 — multiplier for profile bitrate limits
- High Tier only defined for levels 4.0+ (same as HEVC)

### Common Level Selections

| Content | Level | Why |
|---------|-------|-----|
| 720p30 | 3.1 | MaxPicSize=1,065,024 supports 1280×720 |
| 1080p30 | 4.0 | MaxPicSize=2,359,296 supports 1920×1080 |
| 1080p60 | 4.1 | MaxDisplayRate=141M supports 1080p@60 |
| 4K30 | 5.0 | MaxPicSize=8,912,896 supports 3840×2160 |
| 4K60 | 5.1 | MaxDisplayRate=534M supports 4K@60 |
| 8K30 | 6.0 | MaxPicSize=35,651,584 supports 7680×4320 |

### Level Comparison: AV1 vs HEVC vs H.264

For 4K60 content:
| Codec | Level | MaxBitrate Main Tier | MaxBitrate High Tier |
|-------|-------|---------------------|---------------------|
| H.264 | 5.2 | 240 Mbps | N/A (no tiers) |
| HEVC | 5.1 | 40 Mbps | 160 Mbps |
| AV1 | 5.1 | 40 Mbps | 160 Mbps |

AV1 and HEVC have identical level structure for levels 4.0-6.3 (same MaxPicSize, MaxDisplayRate, MaxBitrate values). This is intentional — AOM aligned AV1 levels with HEVC.

## Practical Notes for MediaLive Operations

### AV1 Encoding Cost
AV1 is ~5-10× more CPU-intensive to encode than HEVC (which is already 2-3× more than AVC). Real-time AV1 encoding requires:
- Hardware acceleration (GPU or specialized ASIC) for production use
- Software encoding (libaom, SVT-AV1, rav1e) is too slow for real-time live at high quality
- MediaLive AV1 support uses hardware-accelerated encoding when available

### AV1 Device Support (as of 2026)
- **Chrome 70+**: Software decode, hardware on supported GPUs
- **Firefox 67+**: Software decode
- **Safari 17+ / iOS 17+**: Hardware decode on A15+ and M1+ chips
- **Android 10+**: Software decode; hardware on Dimensity/Snapdragon 8 Gen 1+
- **Samsung TV 2020+**: Hardware decode
- **Smart TVs**: Varies widely — many 2022+ models support AV1 hardware decode
- **PlayStation 5**: Not supported (as of 2026)
- **Xbox Series X/S**: Hardware decode supported

### AV1 in HLS/DASH
- **CMAF**: AV1 in ISOBMFF (MP4) with codec string `av01.P.LLT.DD` (P=profile, LL=level, T=tier, DD=bit depth)
- **HLS**: Supported via `#EXT-X-STREAM-INF` with `CODECS="av01.0.04M.08"` (Main profile, Level 3.0, Main tier, 8-bit)
- **DASH**: Supported with same codec string in MPD
- **Codec string format**: `av01.<profile>.<level><tier>.<bitDepth>` where tier is M (Main) or H (High)

### When to Recommend AV1 Over HEVC
- **Royalty concerns**: Customer wants to avoid HEVC patent licensing complexity
- **Maximum compression**: Customer's viewers are on modern devices (Chrome, Safari 17+, Android 10+)
- **Bandwidth-constrained markets**: 30% bitrate reduction over HEVC means significant CDN cost savings
- **Not recommended when**: Low-latency is critical (encoding latency higher), legacy device support required, or customer's player doesn't support AV1 decode

### Film Grain Synthesis
AV1's film grain synthesis is a unique feature for live streaming:
- Encoder analyzes and strips film grain noise, encodes the clean image
- Film grain parameters are transmitted as metadata (~100 bytes per frame)
- Decoder re-synthesizes grain, restoring visual appearance
- Net effect: 10-20% bitrate reduction for grainy content (sports, concerts) with no visual quality loss
- MediaLive does not currently expose film grain synthesis controls

### Parallelism: Tiles
AV1 supports tiles for parallel encoding/decoding. Constraint at levels 5.1+: per-tile decode rate must fit within 4K60×1.1 to ensure sufficient parallelism. This means encoders producing 4K120 or 8K content MUST use multiple tiles.


---

*Encoder-specific AV1 implementation details (which settings a given encoder exposes,
default/fixed values, and account-level enablement) are product- and version-specific —
consult the encoder's own current documentation rather than relying on a static reference.*
