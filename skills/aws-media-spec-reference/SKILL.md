---
name: aws-media-spec-reference
description: >-
  Use this skill when a question asks what a field, value, opID, or header means in one of four
  streaming standards: the AV1 codec (AOM spec: profiles, tiers, levels, device support), SCTE-35
  program insertion (ANSI/SCTE 35: splice commands and the full segmentation_type_id and UPID
  tables behind ad markers and program boundaries), SCTE-104 (ANSI/SCTE 104: the
  automation-to-encoder API that produces SCTE-35, with opIDs, request types, result codes), and
  MediaPackage v2 response headers (manifest and segment HTTP headers and CMSD fields for origin
  and CDN debugging). Use it even when the standard is not named, for example 'what does type_id
  0x30 mean' or 'which AV1 level covers 4K60'. It explains the standards; it does not inspect a
  file, analyze a stream, or run a tool. Not for H.264/H.265 stream analysis or HDR10 SEI
  verification, and not a DRM or encryption reference; DRM questions belong to
  aws-media-speke-drm-reference.
metadata:
  author: blends
  version: "1.0.0"
  summary: "Reference for AV1 profiles and levels, SCTE-35 and SCTE-104 tables, and MediaPackage v2 response headers including CMSD fields."
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaLive, AWS Elemental MediaPackage, AWS Elemental MediaTailor"
  aws-devops-agent-skills.technical-domains: "Operations"
---

# Media Spec Reference

A lookup layer for four standards that are referenced far more often than they're
remembered correctly. Each lives in its own reference file; load the one you need.

This skill deliberately **complements rather than duplicates** any file-analysis
capability. The split is by *activity*:

- **Analysing a file** against codec/container/loudness specs, verifying HDR10 SEI presence,
  or *detecting* whether SCTE-35 markers exist in a stream → that's file analysis, not this skill.
- **Looking up what a spec field, value, or signalling flow means** for AV1, SCTE-35,
  SCTE-104, or MediaPackage v2 response headers → that's here.

If a question is "is this file compliant," that's file analysis. If it's "what does this value
*mean*," you're in the right place.

## Which reference to read

Load only the one the question is about:

- Load [references/av1-reference.md](references/av1-reference.md) when the question is about the AOM AV1 codec. Profile hierarchy (Main / High /
  Professional), tiers, the full level table with comparisons to HEVC/H.264, device-support
  landscape, AV1-in-HLS/DASH, film-grain synthesis, tiling/parallelism, and when AV1 is
  worth recommending over HEVC. Use for "what does AV1 level 5.1 allow," "which profile do I
  need for 10-bit 4:2:0," or "is AV1 worth it here."

- Load [references/scte35-reference.md](references/scte35-reference.md) when the question is about ANSI/SCTE 35 digital program insertion. The
  `splice_info_section`, the splice commands (`splice_insert`, `time_signal`), the
  `segmentation_descriptor`, and — the part people actually look up — the complete
  `segmentation_type_id` table (program/chapter/break/ad-provider/ad-distributor/overlay/
  promo/ad-block boundaries) and the `segmentation_upid_type` table. Use for "what type_id
  marks a provider ad start," "how do I tell a program boundary from a chapter," or "what
  UPID type is this."

- Load [references/scte104-reference.md](references/scte104-reference.md) when the question is about ANSI/SCTE 104, the automation-system-to-encoder
  API that *generates* the SCTE-35 a downstream packager/ad-server consumes. Message
  formats (single vs multiple operation), the opID tables, key request types
  (`splice_request_data`, `time_signal_request_data`, `insert_segmentation_descriptor`), the
  splice_insert→SCTE-35 mapping, result codes, and how SCTE-104 reaches a live encoder. Use
  for "what opID is this," "how does a splice from automation become a SCTE-35 marker," or
  "what does this result code mean."

- Load [references/mediapackage-v2-response-headers.md](references/mediapackage-v2-response-headers.md) when the question is about the HTTP response headers on
  MediaPackage v2 manifest and segment responses, plus the CMSD header fields, for
  origin/CDN cache-and-latency debugging. Use for "what does this response header tell me,"
  or "what CMSD field should I look at."

Each reference is organised around the spec's own tables, so you can match a value you're
holding straight to its meaning.

## Gotchas

- `segmentation_type_id` values are hexadecimal in the tables. A decimal value from a log (48) is
  0x30; convert before looking it up.
- SCTE-104 is the automation request, SCTE-35 is what the encoder emits. An opID or result code
  question is SCTE-104; a type_id or UPID question is SCTE-35.
- "Are the markers present in this stream" is file analysis, not a lookup. Say so instead of guessing.
- Clause and table numbers move between editions; cite the edition you are holding.

## A note on citations and editions

The references cite clause/table numbers for the editions in current use (e.g. ANSI/SCTE 35
2023r2, ANSI/SCTE 104 2023). Spec clause numbers occasionally move between editions — cite
the edition you're actually holding when the exact number matters, and treat the reference
as a fast index into the standard rather than a substitute for it.

## Before answering

Check the answer before presenting it:

- The value was matched in the reference table, not recalled; if the table lacks it, say so rather than guess.
- Hex and decimal forms of the identifier agree with the question (0x30 is 48).
- The standard named is the right one: opIDs and result codes are SCTE-104, type_ids and UPIDs are SCTE-35.
- The edition cited matches the clause or table number given.
