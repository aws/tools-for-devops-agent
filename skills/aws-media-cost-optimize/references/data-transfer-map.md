# Inter-Service Data Transfer Map

Check every hop in the discovered pipeline topology against this table.
Transfer charges hide between services and rarely appear in anyone's
mental model of "what the channel costs."

Rates shown are us-east-1 illustrations; always take live figures from
the pricing snapshot, and sum tiered families tier by tier.

| Leg | Charged? | Notes |
|---|---|---|
| Contribution encoder (internet) -> MediaConnect / MediaLive input | No (data transfer IN is free) | Sender pays their own egress |
| MediaConnect flow -> MediaLive input, same region | Yes, ~$0.01/GB (in-region to AWS) on the MediaConnect side | Same-AZ placement matters for statmux; a different-AZ flow adds transfer to every statmux hour |
| MediaConnect flow -> MediaConnect flow, cross-region | Yes, ~$0.02/GB | Plus the second flow's hourly fee |
| MediaConnect flow -> internet | Yes, ~$0.09/GB after small free allowance | The reserved outbound bandwidth lever applies here |
| MediaConnect entitlement to another account | Transfer billed per `DataTransferSubscriberFeePercent` split | Verify the split matches commercial intent |
| MediaLive -> MediaPackage ingest, same region | No MediaLive transfer line item | MediaPackage bills ingest per GB; STANDARD channel = 2 pipelines = ~2x ingest GB |
| MediaLive -> other HTTP destinations (internet) | Yes, standard AWS data transfer out | Archive/S3 outputs in-region are free transfer; S3 storage is out of media scope |
| MediaPackage -> CloudFront origin fetch | Free on the transfer leg (AWS origin -> CloudFront) | MediaPackage still bills origination egress per GB fetched; cache hit ratio reduces it |
| MediaPackage -> non-CloudFront CDN | Yes: MediaPackage egress plus internet data transfer on the origin leg | Only the CloudFront leg is free |
| MediaPackage -> players directly (no CDN) | Yes, MediaPackage egress on every viewer GB | Usually dominated by CDN economics at scale; architecture flag |
| MediaConnect Router output cross-region (`RoutingScope=GLOBAL`) | Yes, per-hour cross-region add-on plus data-in | Router-specific; not per-GB like flows |
| MediaConnect Router output -> internet | Yes, per-hour internet egress add-on per output | Illustration +$1.79/hr at 100 Mbps tier |
| CloudFront -> viewers | Yes, tiered per geography | The largest delivery line item; see cloudfront-cost-levers.md |
| MediaTailor manifest/ADS traffic | Request-scale, not bulk-GB | Cost surfaces are insertions, transcode, logs (see mediatailor-cost-levers.md) |
| Encoder/service logs -> CloudWatch Logs | Yes, ingestion + storage per GB | MediaLive encoder logs at DEBUG on busy channels, MediaTailor logs at 100% sampling, and CloudFront real-time logs are the usual offenders |

Reporting pattern for a hop with material cost:

```
Observed: MediaConnect flow <ARN> (AZ use1-az2) feeds MediaLive channel
<ARN> pipeline 0 (AZ use1-az4). Cross-AZ transfer applies to this leg.
Modeled: <GB/month> x <rate> = <amount>/month.
Question: Can the flow or the channel input be placed in the same AZ?
```
