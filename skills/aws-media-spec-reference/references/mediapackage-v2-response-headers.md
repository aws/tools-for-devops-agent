---
inclusion: manual
---
# MediaPackage V2 Response Headers Reference

Source: Live capture from DirecTV FIFA 2026 workflow (sa-east-1), 2026-05-02

## Manifest Response Headers
- content-type: application/vnd.apple.mpegurl
- **cache-control: max-age=3** (3 seconds -- half the 6s segment duration, standard for live)
- cmsd-static: st=l (live), ot=m (manifest), com.amazonaws-mqcs-seq="100"
- x-amzn-mediapackage-endpoint-id, channel-id, channel-uniqueid, endpoint-uniqueid
- x-amzn-mediapackage-manifest-last-sequence: 296280595
- x-amzn-mediapackage-active-input: 1

## Segment Response Headers
- content-type: video/MP2T
- **cache-control: max-age=1209600** (14 days -- immutable content, long cache)
- cmsd-static: st=l, sf=(h) HLS, d=6000 (6s segment), br=4864000 (4.864 Mbps), ot=av
- com.amazonaws-mqcs="100", com.amazonaws-mqcs-seq="100"
- com.amazonaws-mqcs-seq-tracks="v:100;a:100;s:100;m:100"

## CMSD Header Fields
- st=l: stream type live
- ot=m: object type manifest | ot=av: object type audio+video
- sf=(h): streaming format HLS
- d=6000: segment duration 6000ms
- br=4864000: bitrate 4.864 Mbps
- com.amazonaws-mqcs: MQCS quality score (0-100)
- com.amazonaws-mqcs-seq: sequence quality score
- com.amazonaws-mqcs-seq-tracks: per-track scores (v:video, a:audio, s:subtitle, m:muxed)
