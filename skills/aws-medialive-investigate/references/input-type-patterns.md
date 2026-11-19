# MediaLive Input Type Diagnostic Patterns

Per input type checks for Step 2 of SKILL.md. Read only the section for the
input `Type` returned by `describe-input`.


## MEDIACONNECT inputs

If upstream MediaConnect was confirmed healthy:
- Problem is at the MC→ML delivery path
- Check: MC output metrics (OutputConnected, OutputDisconnections)
- Check: ML `NetworkIn` matches MC `OutputBitrate`
- Check: Security group on the ML input allows MC's source CIDR

If upstream MediaConnect was NOT checked:
- Investigate the upstream flow first with aws-mediaconnect-investigate

## MEDIACONNECT_ROUTER inputs

- MediaLive receives input from a MediaConnect SDI router output
- Similar diagnostics to MEDIACONNECT — check the router output health
- Verify the router input source is active via `get-router-input-source-metadata`
- Check router output metrics: `OutputBitrate`, `OutputEnabled`

## RTP_PUSH inputs

- Source pushes RTP to MediaLive's IP:port
- Check `InputSecurityGroups` → CIDR allow-list includes source IP
- Key metrics: `RtpPacketsReceived`, `RtpPacketsRecoveredViaFec`, `RtpPacketsLost`
- `NetworkIn` = 0 with security group OK → source encoder not sending

## RTMP_PUSH inputs

- Source pushes RTMP to MediaLive's endpoint
- Check input endpoint URLs from `describe-input → Destinations[]`
- `NetworkIn` = 0 → source not publishing to the RTMP endpoint
- If RTMP_PUSH with two endpoints (STANDARD channel): both must receive for full redundancy

## RTMP_PULL / URL_PULL inputs

- MediaLive pulls from source URL
- Check `Sources[].Url` — is the source accessible?
- `InputLossSeconds` > 0 → pull failing (source down, auth expired, network)
- These inputs retry automatically on failure

## INPUT_DEVICE (Elemental Link)

```
aws medialive describe-input-device --input-device-id $DEVICE_ID \
  --no-cli-pager --output json
```

Check `ConnectionState` (CONNECTED/DISCONNECTED) and `DeviceState` (IDLE/STREAMING)

## SRT_CALLER inputs

- MediaLive calls out to source SRT listener
- Check `Sources[].Url` for SRT endpoint
- Latency and packet loss visible in input metrics
- `NetworkIn` = 0 → SRT connection failed (firewall, wrong passphrase, endpoint down)
