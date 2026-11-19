---
name: scte35-reference
description: "SCTE-35 ad signaling spec reference. Use for splice_insert, time_signal, segmentation_descriptor, or ad break troubleshooting."
inclusion: manual
---
# SCTE-35 Digital Program Insertion Reference (ANSI/SCTE 35-1 2023r2)

Source: ANSI/SCTE 35-1 2023r2 (123 pages). The definitive standard for signaling ad insertion points, program boundaries, and content identification in MPEG transport streams and adaptive bitrate streaming.

## Overview

SCTE-35 messages are carried in MPEG-2 transport streams as sections with table_id 0xFC. They signal splice points (ad breaks), program boundaries, and content identification. In HLS/DASH, they are translated to EXT-X-CUE-OUT/CUE-IN (HLS) or EventStream/Period boundaries (DASH).

## splice_info_section (Table 5)

The top-level structure. Key fields:
- `table_id`: Always 0xFC
- `pts_adjustment`: 33-bit PTS offset added to all splice times in the message. Used when re-multiplexing.
- `tier`: 12-bit authorization tier (0xFFF = ignore/backwards compatible)
- `splice_command_type`: Identifies the command (see below)
- `splice_command_length`: Byte length of the command
- Followed by descriptor loop and CRC_32

## Splice Commands (Table 7)

| Command | Type Value | Description |
|---------|-----------|-------------|
| splice_null | 0x00 | Heartbeat/keepalive. No action. |
| splice_schedule | 0x04 | Schedule future splice events (deprecated in practice). |
| **splice_insert** | **0x05** | **Signal an immediate or scheduled splice point (CUE-OUT/CUE-IN).** |
| **time_signal** | **0x06** | **Carry a PTS time with descriptors (most common for segmentation).** |
| bandwidth_reservation | 0x07 | Reserve bandwidth in a multiplex. |
| private_command | 0xFF | Vendor-specific command. |

### splice_insert (0x05) — Table 10

Signals an ad break start (out) or return (in). Key fields:

| Field | Bits | Description |
|-------|------|-------------|
| splice_event_id | 32 | Unique event identifier. Used to match CUE-OUT with CUE-IN. |
| splice_event_cancel_indicator | 1 | Cancel a previously signaled event. |
| out_of_network_indicator | 1 | **1 = CUE-OUT (leave network), 0 = CUE-IN (return to network).** |
| program_splice_flag | 1 | 1 = splice all PIDs together (standard). Component mode deprecated. |
| duration_flag | 1 | 1 = break_duration() present. |
| splice_immediate_flag | 1 | 1 = splice immediately (no splice_time). |
| event_id_compliance_flag | 1 | 0 = event_id follows segmentation_descriptor rules. |
| splice_time() | variable | PTS time of the splice point (when not immediate). |
| break_duration() | variable | Duration of the break in 90kHz ticks. |
| unique_program_id | 16 | Program identifier. |
| avail_num | 8 | Avail number within the program. |
| avails_expected | 8 | Total avails expected. |

**CUE-OUT**: out_of_network_indicator=1, duration_flag=1 (with break duration)
**CUE-IN**: out_of_network_indicator=0 (return to network)

### time_signal (0x06) — Table 11

Carries a single splice_time() with descriptors. The actual signaling information is in the segmentation_descriptor(s) attached to the message. This is the most common command type for modern ad insertion workflows.

## Splice Descriptors (Table 16)

| Tag | Descriptor | Description |
|-----|-----------|-------------|
| 0x00 | avail_descriptor | Identifies the avail (provider_avail_id). |
| 0x01 | DTMF_descriptor | DTMF signaling (legacy). |
| 0x02 | **segmentation_descriptor** | **Content segmentation — the primary descriptor for ad insertion.** |
| 0x03 | time_descriptor | TAI time reference. |
| 0x04 | audio_descriptor | Audio component information. |

## segmentation_descriptor (0x02) — Table 20

The most important descriptor. Defines what type of content boundary is being signaled.

Key fields:

| Field | Bits | Description |
|-------|------|-------------|
| segmentation_event_id | 32 | **Unique event ID. Must match between start/end pairs.** |
| segmentation_event_cancel_indicator | 1 | Cancel a previously signaled event. |
| program_segmentation_flag | 1 | 1 = applies to entire program. |
| segmentation_duration_flag | 1 | 1 = duration present. |
| delivery_not_restricted_flag | 1 | 1 = no delivery restrictions. |
| web_delivery_allowed_flag | 1 | 0 = web delivery restricted. |
| no_regional_blackout_flag | 1 | 1 = no regional blackout. |
| device_restrictions | 2 | Device restriction flags. |
| segmentation_duration | 40 | Duration in 90kHz ticks (when flag=1). |
| segmentation_upid_type | 8 | Type of content identifier (see Table 22). |
| segmentation_upid_length | 8 | Length of the UPID. |
| segmentation_upid() | variable | Content identifier value. |
| **segmentation_type_id** | **8** | **Type of segmentation event (see Table 23).** |
| segment_num | 8 | Segment number. |
| segments_expected | 8 | Total segments expected. |
| sub_segment_num | 8 | Sub-segment number (for placement opportunities). |
| sub_segments_expected | 8 | Total sub-segments expected. |

## segmentation_type_id Values (Table 23)

### Program Boundaries (0x10-0x1A)

| Type ID | Hex | Name | Description |
|---------|-----|------|-------------|
| 16 | 0x10 | Program Start | Start of a program. |
| 17 | 0x11 | Program End | End of a program. |
| 18 | 0x12 | Program Early Termination | Program ended early. |
| 19 | 0x13 | Program Breakaway | Temporary departure from program. |
| 20 | 0x14 | Program Resumption | Return from breakaway. |
| 25 | 0x19 | Program Join | Join a program already in progress. |

### Chapter Boundaries (0x20-0x21)

| Type ID | Hex | Name |
|---------|-----|------|
| 32 | 0x20 | Chapter Start |
| 33 | 0x21 | Chapter End |

### Break Boundaries (0x22-0x23)

| Type ID | Hex | Name |
|---------|-----|------|
| 34 | 0x22 | Break Start |
| 35 | 0x23 | Break End |

### Ad Insertion — Provider (0x30-0x35)

| Type ID | Hex | Name | MediaLive/MediaTailor Relevance |
|---------|-----|------|-------------------------------|
| 48 | 0x30 | Provider Advertisement Start | Ad start signaled by content provider. |
| 49 | 0x31 | Provider Advertisement End | Ad end. |
| **52** | **0x34** | **Provider Placement Opportunity Start** | **Most common for SSAI. Signals an ad break opportunity.** |
| **53** | **0x35** | **Provider Placement Opportunity End** | **End of ad break opportunity.** |

### Ad Insertion — Distributor (0x32-0x37)

| Type ID | Hex | Name |
|---------|-----|------|
| 50 | 0x32 | Distributor Advertisement Start |
| 51 | 0x33 | Distributor Advertisement End |
| 54 | 0x36 | Distributor Placement Opportunity Start |
| 55 | 0x37 | Distributor Placement Opportunity End |

### Overlay Placement (0x38-0x3B)

| Type ID | Hex | Name |
|---------|-----|------|
| 56 | 0x38 | Provider Overlay Placement Opportunity Start |
| 57 | 0x39 | Provider Overlay Placement Opportunity End |
| 58 | 0x3A | Distributor Overlay Placement Opportunity Start |
| 59 | 0x3B | Distributor Overlay Placement Opportunity End |

### Promo (0x3C-0x3F)

| Type ID | Hex | Name |
|---------|-----|------|
| 60 | 0x3C | Provider Promo Start |
| 61 | 0x3D | Provider Promo End |
| 62 | 0x3E | Distributor Promo Start |
| 63 | 0x3F | Distributor Promo End |

### Ad Block (0x44-0x47)

| Type ID | Hex | Name |
|---------|-----|------|
| 68 | 0x44 | Provider Ad Block Start |
| 69 | 0x45 | Provider Ad Block End |
| 70 | 0x46 | Distributor Ad Block Start |
| 71 | 0x47 | Distributor Ad Block End |

### Network/Unscheduled (0x40-0x51)

| Type ID | Hex | Name |
|---------|-----|------|
| 64 | 0x40 | Unscheduled Event Start |
| 65 | 0x41 | Unscheduled Event End |
| 66 | 0x42 | Alternate Content Opportunity Start |
| 67 | 0x43 | Alternate Content Opportunity End |
| 80 | 0x50 | Network Start |
| 81 | 0x51 | Network End |

## segmentation_upid_type Values (Table 22)

| Type | Length | Name | Description |
|------|--------|------|-------------|
| 0x00 | 0 | Not Used | No UPID present. |
| 0x01 | variable | User Defined | Deprecated: use 0x0C. |
| 0x03 | 12 | Ad-ID | Advertising Digital Identification (4 alpha + 8 alphanumeric). |
| 0x06 | 12 | ISAN | ISO 15706-2 versioned ISAN. |
| 0x08 | 8 | AiringID | Formerly Turner ID. |
| 0x09 | variable | ADI | CableLabs ADI identifier. |
| 0x0A | 12 | EIDR | Entertainment Identifier Registry. |
| 0x0C | variable | MPU() | Managed Private UPID structure. |
| 0x0D | variable | MID() | Multiple UPID (contains nested UPIDs). |
| 0x0E | variable | ADS Information | URI for ad server information. |

## Practical Notes for MediaLive/MediaTailor Operations

### SCTE-35 in MediaLive

MediaLive handles SCTE-35 in three modes:
- **PASSTHROUGH**: Relays source SCTE-35 binary verbatim. No interpretation. Only available on EMPv1.
- **SCTE35_ENHANCED**: Parses SCTE-35 binary and generates HLS CUE tags. Enforces splice_event_id matching between CUE-OUT and CUE-IN. Used by EMPv2 (only option).
- **NONE**: No SCTE-35 processing.

### Event ID Matching (Critical for EMPv2)

In SCTE35_ENHANCED mode, MediaPackage V2 tracks open avails by `segmentation_event_id`. A CUE-IN (end event) must have a matching event ID to close the corresponding CUE-OUT (start event). If event IDs don't match, the CUE-OUT remains open indefinitely (until TTL expiry).

This is the #1 cause of "stuck avails" and "missing CUE-IN" issues when migrating from EMPv1 (PASSTHROUGH) to EMPv2 (SCTE35_ENHANCED).

### Common SCTE-35 Patterns in Encoder Logs

MediaLive logs SCTE-35 messages with full decode:
```
SCTE35::time_signal [Clock=IngestM2TS] [PCR=HH:MM:SS.mmm] [SpliceTime=HH:MM:SS.mmm]
  [Base64=/DB...] [pts_time=NNNNN] [pts_adjustment=0]
  [SegmentationDescriptor [splice_descriptor_tag=0x02] [descriptor_length=NN]
    [segmentation_event_id=0xNNNNNNNN]
    [segmentation_type_id=0x34=Provider Placement Opportunity Start]
    [segmentation_duration=NNNNN=HH:MM:SS.mmm]
    [segment_num=0] [segments_expected=0]]
```

### Duration Conversion

SCTE-35 durations are in 90kHz ticks:
- 1 second = 90,000 ticks
- 30 seconds = 2,700,000 ticks
- 60 seconds = 5,400,000 ticks
- To convert: seconds = ticks / 90,000

### PTS Adjustment

The `pts_adjustment` field in splice_info_section is added to all splice times in the message. When re-multiplexing or transcoding, the pts_adjustment must be updated to reflect the new PTS timeline. MediaLive handles this automatically.

### Start/End Pairing Rules

| Start Type | Expected End Type |
|-----------|------------------|
| 0x10 Program Start | 0x11 Program End |
| 0x20 Chapter Start | 0x21 Chapter End |
| 0x22 Break Start | 0x23 Break End |
| 0x30 Provider Ad Start | 0x31 Provider Ad End |
| 0x34 Provider Placement Opp Start | 0x35 Provider Placement Opp End |
| 0x36 Distributor Placement Opp Start | 0x37 Distributor Placement Opp End |
| 0x44 Provider Ad Block Start | 0x45 Provider Ad Block End |

### MediaTailor Ad Marker Detection

MediaTailor detects ad breaks from:
1. `splice_insert` with `out_of_network_indicator=1` → CUE-OUT
2. `time_signal` with `segmentation_type_id=0x34` (Provider Placement Opportunity Start) → CUE-OUT
3. `time_signal` with `segmentation_type_id=0x36` (Distributor Placement Opportunity Start) → CUE-OUT
4. HLS `#EXT-X-CUE-OUT` / `#EXT-X-CUE-IN` tags (generated by MediaLive/MediaPackage from SCTE-35)
5. DASH `<EventStream>` with `schemeIdUri="urn:scte:scte35:2013:xml"`

### Base64 Decoding

SCTE-35 messages in logs and manifests are base64-encoded binary. The base64 string starts with `/D` (which decodes to 0xFC = table_id). To decode:
```python
import base64
binary = base64.b64decode(base64_string)
# binary[0] = 0xFC (table_id)
# binary[13] = splice_command_type
```
