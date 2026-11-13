# MediaLive Output Destination Checks

Per destination type checks for Step 4 of SKILL.md. Read only the section for the
output group's destination type.


## MediaPackage v1 output groups
- Check `Destinations[].MediaPackageSettings[].ChannelId`
- Verify the MP channel exists and is healthy
- Both pipelines should push to both MP ingest endpoints for redundancy

## HLS/DASH/MSS to S3
- Check `Destinations[].Settings[].Url` for S3 path
- Output5xxErrors → S3 throttling or bucket policy issue

## RTMP output groups
- Check `Destinations[].Settings[].Url` for RTMP endpoint
- RTMP destinations can be CDN origins (Twitch, YouTube, etc.)
- Output failures → destination not accepting connections

## UDP/RTP output groups
- Check `Destinations[].Settings[].Url` for UDP/RTP endpoint
- These are push-based; security group and network path issues are common
