# MediaConnect Secondary Checks

Conditional checks relocated from SKILL.md Steps 6 and 8 so the main procedure
stays compact. Run only the section the SKILL.md step points at. All commands
are read-only.

## Content quality monitoring

Only available if `SourceMonitoringConfig` is configured on the flow with
`ContentQualityAnalysisState=ENABLED`. Default thresholds are 30 seconds
for black/frozen/silent detection. The reliable detection method is checking
whether content quality metrics exist in CloudWatch:

```
aws cloudwatch list-metrics \
  --namespace AWS/MediaConnect \
  --metric-name VideoStreamMissing \
  --dimensions Name=FlowARN,Value=$FLOW_ARN \
  --no-cli-pager --output json
```

If metrics exist:

| Metric | Minimum | Meaning |
|---|---|---|
| VideoStreamMissing | 1 | Video elementary stream absent |
| AudioStreamMissing | 1 | Audio elementary stream absent |
| BlackFramesBreaching | 1 | Black frames detected beyond threshold |
| FrozenFramesBreaching | 1 | Frozen frames detected beyond threshold |
| SilentAudioBreaching | 1 | Silent audio detected beyond threshold |
| TimecodePresent | 0 | Timecode absent from stream |

If no content quality metrics exist:
```
DATA GAP: SourceMonitoringConfig not enabled on this flow.
Content quality analysis (black/frozen/silent detection) unavailable.
Only transport-level metrics can be assessed.

To enable: update the flow's source monitoring config with
ContentQualityAnalysisState=ENABLED (default thresholds: 30 seconds).
```

## Bridge and gateway inspection (if applicable)

Bridges connect flows across Availability Zones or regions via MediaConnect Gateway.

```
aws mediaconnect list-bridges --no-cli-pager --output json
```

If bridges exist:

```
aws mediaconnect describe-bridge --bridge-arn $BRIDGE_ARN \
  --no-cli-pager --output json
```

Check:
- `BridgeState` — must be ACTIVE
- `Sources[]` and `Outputs[]` — verify flow ARN references
- `PlacementArn` — gateway instance placement
- `BridgeMessages[]` — active bridge-level alerts

Bridge/gateway-specific metrics (namespace `AWS/MediaConnect`,
requires `BridgeARN` or gateway dimensions):
- **Gateway metrics require period ≥ 60 seconds** (not available in
  high-resolution 1-second periods). Cloud flow metrics support 1-second
  resolution.

If no bridges found and the flow doesn't use entitlements:
- Skip this step — flow is single-region, single-account
