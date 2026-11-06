# MediaLive MQCS metrics

Media quality confidence score (MQCS) metrics in the `AWS/MediaLive` namespace,
their dimensions and how they relate to the MediaPackage side. Load from SKILL.md
Step 4 when the channel has a CMAF Ingest output group.

## When MediaLive emits MQCS

MediaLive creates an MQCS for the outputs in CMAF Ingest output groups whose
destination is an AWS Elemental MediaPackage channel. The feature is enabled
automatically in those outputs; there is no field for it in
`CmafIngestGroupSettings` or anywhere else in the channel. HLS, MediaPackage
(v1 style), UDP, RTMP, SRT, MSS and Archive output groups are not listed by AWS,
so no MQCS is expected from them and an absent metric there means "not
applicable".

MediaPackage v2 settings that mention MQCS consume the score; they do not gate
MediaLive's CloudWatch emission:

| MediaPackage v2 field | Effect |
|---|---|
| `OutputHeaderConfiguration.PublishMQCS` | When true, MediaPackage includes the MQCS in CMSD response headers to the CDN (CMAF input type only) |
| `InputSwitchConfiguration.MQCSInputSwitching` | When true, MediaPackage switches inputs based on the MQCS received from MediaLive |

## Metrics

| Metric | Scores | Dimensions | Statistic |
|---|---|---|---|
| `MinMQCS` (documented name; `MinMqcs` and `MinVideoMqcs` seen in the console and in field runs; discover with list-metrics) | Minimum overall score in the period across the video and audio encodes of the group | ChannelId, Pipeline, OutputGroupName | Minimum |
| `MqcsBlackFrameDetected` | One or more sequential video frames that are valid but black | ChannelId, Pipeline | Minimum |
| `MqcsFreezeFrameDetected` | One or more sequential video frames that are valid but frozen | ChannelId, Pipeline | Minimum |
| `MqcsFillFrameInsertion` | The encoder inserted fill frames, that is, input loss handling is active | ChannelId, Pipeline | Minimum |
| `MqcsVideoFrameDrops` | One or more sequential segments containing dropped frames | ChannelId, Pipeline | Minimum |
| `MqcsContinuityCounterErrors` | One or more sequential segments containing continuity counter errors (network packet loss) | ChannelId, Pipeline | Minimum |
| `MqcsSvq` | The encoder reduced quality to stay real time | ChannelId, Pipeline | Minimum |

Value semantics, from the MediaLive user guide: the score is 0 to 100 with 0 the
lowest quality; each component score falls as long as its problem persists and
returns to 100 as soon as one frame arrives without the problem; a zero means at
least one encode in at least one output scored 0; no datapoints means the channel
has no output group in which MediaLive generates an MQCS. The score is produced
per segment, so a 60 second Minimum is the worst segment in that minute.

Observed reference values from a published test on a SINGLE_PIPELINE channel: a
frozen source drove `MqcsFreezeFrameDetected` and the minimum score to 25; a
black source drove `MqcsBlackFrameDetected`, `MqcsFreezeFrameDetected` to 25 and
the minimum score to 6, with the other components at 100.

## Queries

```
aws cloudwatch list-metrics --namespace AWS/MediaLive \
  --dimensions Name=ChannelId,Value=$CHANNEL_ID \
  --query "Metrics[?contains(MetricName,'qcs')]" --no-cli-pager --output json

aws cloudwatch get-metric-statistics --namespace AWS/MediaLive \
  --metric-name MqcsFillFrameInsertion \
  --dimensions Name=ChannelId,Value=$CHANNEL_ID Name=Pipeline,Value=0 \
  --start-time $START --end-time $END --period 60 --statistics Minimum \
  --no-cli-pager --output json

aws cloudwatch get-metric-statistics --namespace AWS/MediaLive \
  --metric-name MinMQCS \
  --dimensions Name=ChannelId,Value=$CHANNEL_ID Name=Pipeline,Value=0 \
    Name=OutputGroupName,Value=$CMAF_GROUP_NAME \
  --start-time $START --end-time $END --period 60 --statistics Minimum \
  --no-cli-pager --output json
```

Use the metric name casing that list-metrics returned. Repeat the component
query for each of the six components, and the minimum score query per CMAF
Ingest group and per pipeline.

## Reading a loss event

| Observation | Reading |
|---|---|
| Minimum score < 100, black and freeze at 100 | Real degradation that is not black or frozen source content; read fill, frame drops and continuity counter components |
| `MqcsFillFrameInsertion` < 100 | Input loss handling ran: repeat last frame for `RepeatFrameMsec` (default 1000 ms), then black for `BlackFrameMsec` (default 1000 ms), then the slate or color in `InputLossImageType`. Viewers see black from this, not from the black frame detector |
| `MqcsContinuityCounterErrors` or `MqcsVideoFrameDrops` < 100 | Unrecovered packets or decode damage reached the encoder; compare `ChannelInputErrorSeconds` Sum in the same minutes and hand off upstream |
| `MqcsBlackFrameDetected` or `MqcsFreezeFrameDetected` < 100 | The source itself delivered black or frozen frames; the fault is upstream of the input |
| Minimum score < 80 | MediaLive writes a log message about the drop; alert 6045 "The MQCS score is low for this pipeline" is raised at a level AWS does not publish |
| CMAF Ingest group present, no MQCS datapoints | Query error: `OutputGroupName` missing on the minimum score metric, wrong name casing, or wrong Pipeline value |

Related alerts (`aws medialive list-alerts`): 6045 low MQCS, 5302 stopped
receiving UDP input (includes MediaConnect inputs), 5202 black video detected,
5201 video not detected.

## The MediaPackage side

MediaPackage v2 publishes its own view in `AWS/MediaPackage`: `IngressMQCS`
(the segment score as received from MediaLive, per ingest endpoint, with a
`TrackType` dimension of Video, Audio or Subtitle), `IngressMQCSSequence`,
`ChannelMQCS` (MediaPackage's score for the active input) and
`ChannelMQCSSequence`. MediaLive's `Mqcs*` metrics are the encoder's view per
channel and pipeline; `IngressMQCS` is the same score per ingest endpoint on
arrival. aws-mediapackage-investigate Step 8 covers that side. Whether the
MediaPackage metrics depend on `PublishMQCS` is not documented; query them
rather than assume.

## Sources

- MediaLive user guide, MQCS metrics: https://docs.aws.amazon.com/medialive/latest/ug/eml-metrics-quality-score.html
- MediaLive user guide, media quality confidence score: https://docs.aws.amazon.com/medialive/latest/ug/mqcs.html
- MediaLive user guide, input loss handling: https://docs.aws.amazon.com/medialive/latest/ug/feature-input-loss.html
- MediaPackage v2 API, OutputHeaderConfiguration: https://docs.aws.amazon.com/mediapackage/latest/APIReference/API_OutputHeaderConfiguration.html
- MediaPackage user guide, CloudWatch metrics: https://docs.aws.amazon.com/mediapackage/latest/userguide/monitoring-cloudwatch.html
- AWS Media Blog, media quality aware resiliency (November 2024): https://aws.amazon.com/blogs/media/improve-your-viewers-live-streaming-experience-with-media-quality-aware-resiliency/
- Published test of the metrics on a SINGLE_PIPELINE channel (third party): https://dev.classmethod.jp/articles/medialive-media-quality-confidence-score/
