---
inclusion: manual
---
# SCTE-104 Automation System to Compression System API Reference (ANSI/SCTE 104 2023)

Source: ANSI/SCTE 104 2023 (129 pages). Defines the API between automation systems and compression systems for triggering SCTE-35 message insertion into MPEG transport streams.

## Overview

SCTE-104 defines the communications API between an Automation System (AS) and the Compression System that inserts SCTE-35 private sections into outgoing MPEG Transport Streams. It is the upstream trigger protocol -- automation systems generate SCTE-104 messages to tell encoders/injectors when and what SCTE-35 messages to insert.

## Relationship to SCTE-35

```
Automation System (playout/traffic)  --SCTE-104-->  Encoder/Injector  --SCTE-35 in TS-->  Splicer/MediaPackage/MediaTailor
```

- **SCTE-104** = upstream trigger (AS tells encoder what to insert)
- **SCTE-35** = downstream TS signaling (encoder inserts for splicers)
- SCTE-104 fields map directly to SCTE-35 splice_info_section fields
- One SCTE-104 splice_request can result in multiple SCTE-35 sections (injector may repeat per SCTE-67)

## System Architecture

| Component | Role |
|-----------|------|
| **Automation System (AS)** | Control system for program origination. Generates splice requests, time signals, descriptors. |
| **Injector (IJ)** | Converts SCTE-104 into SCTE-35 sections and multiplexes into TS. May be encoder, mux, or standalone. |
| **PAMS** | Provisioning and Alarm Management System. Monitors health, switches redundancy, provisions injectors. Optional. |
| **Proxy Device** | Accepts SCTE-104 via TCP/IP or serial and embeds into VANC per SMPTE ST 2010. |

## Data Communications

| Transport | Direction | Notes |
|-----------|-----------|-------|
| **TCP/IP** | Bidirectional | Port **5167**. Private network. Latency << 1 frame time. |
| **Serial (TIA-232/422)** | Bidirectional | Point-to-point with link layer encapsulation. |
| **VANC (SMPTE ST 2010)** | Unidirectional | Messages embedded in SDI Vertical Ancillary Data. |

## Message Formats

### single_operation_message() (Table 8-1)

Carries one Basic request or response (init, alive, inject responses, PAMS messages).

| Field | Bytes | Description |
|-------|-------|-------------|
| opID | 2 | Operation identifier (Table 8-3) |
| messageSize | 2 | Total message size in bytes |
| result | 2 | Result code (0xFFFF for requests) |
| result_extension | 2 | Additional result info (0xFFFF if unused) |
| protocol_version | 1 | Shall be 0x00 |
| AS_index | 1 | Identifies the AS (0 if not required) |
| message_number | 1 | Unique message identifier |
| DPI_PID_index | 2 | Target DPI PID index (0 if not required) |
| data() | * | Operation-specific data |

### multiple_operation_message() (Table 8-2)

Carries one or more Normal/Supplemental/Control requests. Results in SCTE-35 section insertion.

| Field | Bytes | Description |
|-------|-------|-------------|
| Reserved | 2 | 0xFFFF |
| messageSize | 2 | Total message size |
| protocol_version | 1 | 0x00 |
| AS_index | 1 | Identifies the AS |
| message_number | 1 | Unique ID (0-255, must be unique while processing) |
| DPI_PID_index | 2 | Target DPI PID index |
| SCTE35_protocol_version | 1 | 0x00 |
| timestamp() | * | When to process (see Timestamp section) |
| num_ops | 1 | Number of operations |
| *per op:* opID(2) + data_length(2) + data(*) | | Operations executed in order |

Supplemental requests MUST follow the Normal request they modify. A new Normal request indicates the previous is complete.

## opID Values -- single_operation_message (Table 8-3)

| opID | Name | Direction | Simple Profile |
|------|------|-----------|----------------|
| 0x0000 | general_response_data | Any → Any | Y |
| 0x0001 | init_request_data | AS → IJ | Y |
| 0x0002 | init_response_data | IJ → AS | Y |
| 0x0003 | alive_request_data | AS → IJ | Y |
| 0x0004 | alive_response_data | IJ → AS | Y |
| 0x0007 | inject_response_data | IJ → AS | Y |
| 0x0008 | inject_complete_response_data | IJ → AS | Y |
| 0x0009 | config_request_data | AS → PAMS | n/a |
| 0x000A | config_response_data | PAMS → AS | n/a |
| 0x000B | provisioning_request_data | PAMS → AS | n/a |
| 0x000C | provisioning_response_data | AS → PAMS | n/a |
| 0x000F | fault_request_data | AS → PAMS | n/a |
| 0x0010 | fault_response_data | PAMS → AS | n/a |
| 0x0011 | AS_alive_request_data | PAMS → AS | n/a |
| 0x0012 | AS_alive_response_data | AS → PAMS | n/a |

## opID Values -- multiple_operation_message (Table 8-4)

| opID | Name | Usage | Simple Profile |
|------|------|-------|----------------|
| 0x0100 | inject_section_data_request | Normal | Y |
| 0x0101 | splice_request_data | Normal | Y |
| 0x0102 | splice_null_request_data | Normal | Y |
| 0x0103 | start_schedule_download_request | Normal | N |
| 0x0104 | time_signal_request_data | Normal | Y |
| 0x0105 | transmit_schedule_request | Normal | N |
| 0x0106 | component_mode_DPI_request | Supplemental | N |
| 0x0107 | encrypted_DPI_request | Supplemental | N |
| 0x0108 | insert_descriptor_request | Supplemental | Y |
| 0x0109 | insert_DTMF_descriptor_request | Supplemental | Y |
| 0x010A | insert_avail_descriptor_request | Supplemental | Y |
| 0x010B | insert_segmentation_descriptor_request | Supplemental | Y |
| 0x010C | proprietary_command_request | Normal | Y |
| 0x010D | schedule_component_mode_request | Supplemental | N |
| 0x010E | schedule_definition_data | Supplemental | N |
| 0x010F | insert_tier_data | Supplemental | Y |
| 0x0110 | insert_time_descriptor | Supplemental | Y |
| 0x0111 | insert_audio_descriptor | Supplemental | Y |
| 0x0112 | insert_audio_provisioning | Control | Y |
| 0x0113 | insert_alternate_break_duration | Supplemental | Y |
| 0x0300 | delete_ControlWord_data | Control | N |
| 0x0301 | update_ControlWord_data | Control | N |

**Usage:** Basic = single_operation_message only. Normal = results in SCTE-35 section(s). Supplemental = modifies preceding Normal request. Control = encryption key management.

## Key Request Types

### splice_request_data (0x0101) -- Table 9-5

The primary splicing request. Results in SCTE-35 splice_insert() sections.

| Field | Bytes | Description |
|-------|-------|-------------|
| splice_insert_type | 1 | Type of insertion (see below) |
| splice_event_id | 4 | 32-bit unique event ID → SCTE-35 splice_event_id |
| unique_program_id | 2 | 16-bit program ID → SCTE-35 |
| pre_roll_time | 2 | Milliseconds to insertion point. Min non-zero: **4000ms**. |
| break_duration | 2 | Duration in **tenths of seconds**. 0 = no duration. |
| avail_num | 1 | Avail number (0 = not used) |
| avails_expected | 1 | Total avails expected (0 = not used) |
| auto_return_flag | 1 | Non-zero + non-zero duration → auto_return=1 in SCTE-35 |
| not_an_entry_flag | 1 | Non-zero = not an entry point (not passed to SCTE-35) |

### splice_insert_type Values (Table 9-6) and SCTE-35 Mapping (Table 9-7)

| Value | Name | SCTE-35: cancel | out_of_network | immediate | auto_return |
|-------|------|-----------------|----------------|-----------|-------------|
| 1 | spliceStart_normal | 0 | 1 (CUE-OUT) | 0 | 0 or 1 |
| 2 | spliceStart_immediate | 0 | 1 (CUE-OUT) | 1 | 0 or 1 |
| 3 | spliceEnd_normal | 0 | 0 (CUE-IN) | 0 | 0 |
| 4 | spliceEnd_immediate | 0 | 0 (CUE-IN) | 1 | 0 |
| 5 | splice_cancel | 1 | 0 | 0 | 0 |

### time_signal_request_data (0x0104) -- Table 9-23

Generates SCTE-35 time_signal(). Normally accompanied by descriptor requests (especially segmentation).

| Field | Bytes | Description |
|-------|-------|-------------|
| pre_roll_time | 2 | Milliseconds from processing to splice point |

### insert_segmentation_descriptor_request (0x010B) -- Table 9-29

Creates SCTE-35 segmentation_descriptor. Maps 1:1 to SCTE-35 (same type_ids, UPIDs). Sets program_segmentation_flag=1.

| Field | Bytes | Description |
|-------|-------|-------------|
| segmentation_event_id | 4 | Must match between start/end pairs |
| segmentation_event_cancel_indicator | 1 | 1 = cancel previous event |
| duration | 2 | Whole seconds (0 = no duration flag) |
| segmentation_upid_type | 1 | Per SCTE-35 Table 22 |
| segmentation_upid_length | 1 | UPID length (0 if none) |
| segmentation_upid | * | Variable-length UPID |
| segmentation_type_id | 1 | Per SCTE-35 Table 23 (0x34=Provider Placement Opp Start, etc.) |
| segment_num | 1 | Segment number |
| segments_expected | 1 | Total segments |
| duration_extension_frames | 1 | Fractional second (0 to frame_rate-1) |
| delivery_not_restricted_flag | 1 | 1 = unrestricted |
| web_delivery_allowed_flag | 1 | 1 = web OK |
| no_regional_blackout_flag | 1 | 1 = no blackout |
| archive_allowed_flag | 1 | 1 = archiveable |
| device_restrictions | 1 | Per SCTE-35 |
| insert_sub_segment_info | 1 | 1 = include sub-segment fields |
| sub_segment_num | 1 | Optional |
| sub_segments_expected | 1 | Optional |

### Other Supplemental Requests

**insert_avail_descriptor (0x010A):** num_provider_avails(1) + provider_avail_id(4) loop. Creates SCTE-35 avail_descriptor.

**insert_DTMF_descriptor (0x0109):** pre-roll(1, tenths of sec) + dtmf_length(1) + DTMF_char(1 each). Legacy analog cue tone.

**insert_tier_data (0x010F):** tier_data(2, upper nibble=0, lower 12 bits=tier). Default 0xFFF if absent.

**insert_time_descriptor (0x0110):** TAI_seconds(6) + TAI_ns(4) + UTC_offset(2). PTP/TAI time.

**insert_audio_descriptor (0x0111):** audio_count(1) + per-component: component_tag(1), ISO_code(3), Bit_Stream_Mode(1), Num_Channels(1), Full_Srvc_Audio(1).

**insert_alternate_break_duration (0x0113):** alternate_break_duration(4, **milliseconds**). Replaces break_duration with ms precision. 0 = use original.

**splice_null_request (0x0102):** No data. Generates SCTE-35 splice_null() heartbeat.

**inject_section_data_request (0x0100):** SCTE35_command_length(2) + SCTE35_protocol_version(1) + SCTE35_command_type(1) + raw command binary. Direct SCTE-35 command injection.

## Response Messages

**inject_response_data (0x0007):** Sent immediately on receipt of splice/time_signal/splice_null request. Contains message_number(1) of the acknowledged message.

**inject_complete_response_data (0x0008):** Sent when Injector finishes issuing ALL SCTE-35 sections. Contains message_number(1) + cue_message_count(1). message_number is now free for reuse.

**general_response_data (0x0000):** No data. Conveys result code in wrapper. Used for CW update/delete responses.

## PAMS Messages (Section 10)

Optional but normative. All use single_operation_message(). Key messages:

- **config_request (0x0009):** AS → PAMS at init. Provides AS IP/port, activeflag (primary/backup), protocol_version.
- **config_response (0x000A):** PAMS → AS. Returns AS_index for all subsequent messages.
- **provisioning_request (0x000B):** PAMS → AS. Lists all active injectors with IP, port, service_name, DPI_PID_index, component_mode. Sent at init and on any injector change.
- **provisioning_response (0x000C):** AS → PAMS. Acknowledges. May return DPI_PID_index consistency errors.
- **fault_request (0x000F):** AS → PAMS. Reports injector/comms failure (IP, port, service_name, DPI_PID_index).
- **fault_response (0x0010):** PAMS → AS. Acknowledges. May return "no fault found."
- **AS_alive_request/response (0x0011/0x0012):** Heartbeat every 60 seconds on permanent connections.

## timestamp() Structure (Table 12-2)

Controls WHEN requests in a multiple_operation_message() are processed.

| time_type | Name | Additional Fields | Description |
|-----------|------|-------------------|-------------|
| 0 | Immediate | (none) | Process on receipt |
| 1 | UTC | UTC_seconds(4) + UTC_microseconds(2) | Process at UTC time (seconds since Jan 6, 1980 00:00 UTC with leap seconds) |
| 2 | VITC | hours(1) + minutes(1) + seconds(1) + frames(1) | Process at SMPTE timecode |
| 3 | GPI | GPI_number(1) + GPI_edge(1) | Process on contact closure (edge: 0=open→closed, 1=closed→open) |

**time() structure** (used in alive messages): seconds(4) + microseconds(4), same epoch as UTC timestamp.

## Result Codes (Table 14-1)

| Code | Name | Typical Response |
|------|------|-----------------|
| 100 | Successful Response | All |
| 101 | Access Denied -- not authorized for DPI | init_response |
| 102 | CW index has no Code Word | general/inject_response |
| 103 | DPI has been de-provisioned | alive_response |
| 104 | DPI not supported | init_response |
| 105 | Duplicate service name (invalid) | provisioning_response |
| 106 | Duplicate service name is OK | provisioning_response |
| 107 | Encryption not supported | inject_response |
| 108 | Illegal shared DPI PID index | provisioning_response |
| 109 | Inconsistent DPI PID index | provisioning_response |
| 110 | Injector already in use | init_response |
| 111 | Injector not provisioned for this AS | init_response |
| 112 | Injector not provisioned for DPI | init_response |
| 113 | Injector will be replaced | fault_response |
| 114 | Invalid Message Size | All |
| 115 | Invalid Message Syntax | All |
| 116 | Invalid Version (incompatible) | init_response |
| 117 | No fault found | fault_response |
| 118 | Service name missing | provisioning_response |
| 119 | Shared DPI PID index not found | provisioning_response |
| 120 | Splice Request Failed -- Unknown | inject_complete_response |
| 121 | Splice Request Rejected -- Bad parameter | inject_response |
| 122 | Splice Request Too Late -- pre-roll too small | inject_response |
| 123 | Time type unsupported | inject_response |
| 124 | Unknown Failure | All |
| 125 | Unknown opID | All |
| 126 | Unknown DPI_PID_index | All |
| 127 | Version Mismatch | All |
| 128 | Proxy Response (handled by proxy) | init_response |

## Practical Notes for MediaLive Operations

### How SCTE-104 Reaches MediaLive

1. **VANC in SDI inputs** -- Automation systems embed SCTE-104 in VANC per SMPTE ST 2010. MediaLive extracts via Elemental Link devices or MediaConnect flows with SDI sources.
2. **MediaLive Schedule API** -- Maps directly to SCTE-104 concepts:
   - Schedule `splice_insert` → splice_request_data (0x0101)
   - Schedule `time_signal` → time_signal_request_data (0x0104) + insert_segmentation_descriptor_request (0x010B)

### Key Field Mappings

| SCTE-104 | SCTE-35 | Notes |
|----------|---------|-------|
| splice_event_id | splice_event_id | Must match CUE-OUT/CUE-IN for EMPv2 |
| splice_insert_type=1 | out_of_network_indicator=1 | CUE-OUT |
| splice_insert_type=3 | out_of_network_indicator=0 | CUE-IN |
| break_duration (tenths of sec) | break_duration (90kHz ticks) | ticks = value × 9000 |
| alternate_break_duration (ms) | break_duration (90kHz ticks) | ticks = value × 90 |
| pre_roll_time (ms) | splice_time (PTS) | Injector calculates from PCR |
| segmentation duration (sec) | segmentation_duration (90kHz) | ticks = value × 90000 |
| auto_return_flag | auto_return in break_duration() | Auto CUE-IN after break expires |
| segmentation_type_id | segmentation_type_id | 1:1 (same 0x34, 0x35, etc.) |
| segmentation_event_id | segmentation_event_id | 1:1, same matching rules |

### auto_return_flag

When set (non-zero) with non-zero break_duration, the injector automatically generates a CUE-IN after the break expires. No explicit spliceEnd needed from the automation system. This is the SCTE-104 equivalent of MediaLive's `auto_return` setting.

### pre_roll_time

- Minimum non-zero: **4000ms** (4 seconds)
- Recommended: 8-10 seconds (allows injector to send multiple SCTE-35 sections per SCTE-67)
- < 4000ms (non-zero): injector sends the section but returns result 122 ("pre-roll too small")
- 0 with spliceStart_normal: injector sets splice_immediate_flag=1 (not recommended)

### Common Troubleshooting

**SCTE-35 missing from output:**
1. Check VANC extraction -- look for `SCTE35::` or `SCTE104` in encoder logs. Absent = trigger never reached encoder.
2. Check pre_roll_time -- < 4s causes result 122 and may be too late for downstream splicers.
3. Check splice_event_id matching -- EMPv2 SCTE35_ENHANCED requires CUE-IN event_id to match CUE-OUT. Mismatched IDs = stuck avails (#1 cause).
4. Check time synchronization -- deferred processing (time_type=1 or 2) requires synced clocks. Drift = wrong timing or discarded messages.

**Downstream splicer not acting on SCTE-35:**
1. Verify segmentation_type_id matches expectations (MediaTailor needs 0x34/0x36 for ad breaks)
2. Verify segmentation_event_id pairing between start (0x34) and end (0x35)
3. Check break_duration is non-zero for CUE-OUT (some splicers require it)
4. Check auto_return_flag is set if no explicit CUE-IN will be sent

**Immediate vs Normal:** spliceStart_immediate (type=2) sets splice_immediate_flag=1 -- splicer splices at nearest opportunity. Not recommended by SCTE-35; may cause inaccurate splices. Always prefer spliceStart_normal (type=1) with adequate pre_roll for production.
