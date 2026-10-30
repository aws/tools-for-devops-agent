---
name: aws-mediatailor-investigate
description: >-
  Use this skill for AWS Elemental MediaTailor SSAI (server-side ad insertion) and Channel Assembly. Use
  for ad symptoms: avails not filling, slate or source content instead of ads, empty VAST/VMAP,
  ADS timeouts or errors, VAST parse failures, skipped ads (transcode, variant match,
  personalization threshold), unused prefetch, identical ads for every viewer, stale personalized
  manifests, beaconing gaps, missing or sampled session logs, and playback 4xx/5xx (400 session
  expiry, 403 host prefix, 409, 502, 503 throttling, 504 origin timeout). Use for Channel
  Assembly: channel STOPPED, schedule gaps or filler slate, source alerts, SourceGroup mismatch,
  output 4xx/5xx. Covers only the MediaTailor layer; when evidence points at the origin
  (Origin.Errors, manifest-service timeouts) hand off to aws-mediapackage-investigate. Not for
  SCTE-35 field meanings (aws-media-spec-reference), encoder-side marker insertion
  (aws-medialive-investigate), or CloudFront behavior (aws-media-cloudfront-investigate).
metadata:
  author: blends
  version: "1.0.0"
  summary: "Read-only investigation of MediaTailor SSAI and Channel Assembly: unfilled avails, slate, ADS errors, playback 4xx/5xx and session log gaps."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaTailor"
  aws-devops-agent-skills.technical-domains: "Operations, Observability"
---
# AWS Elemental MediaTailor Investigation

## Purpose

Investigate a single MediaTailor capability instance: either a playback
configuration (SSAI) or a linear channel (Channel Assembly). The skill collects
configuration state, CloudWatch metrics, and (where the customer has enabled
them) CloudWatch Logs, then produces "Observed X, Expected Y, Question: Why?"
findings. It does not declare a definitive root cause; it surfaces evidence and
the precise question that follows from it.

MediaTailor exposes two unrelated capabilities that share a service namespace
but almost nothing else. Treat them as two distinct investigations:

- **SSAI**: personalizes manifests by stitching ads from an Ad Decision Server
  (ADS) into content pulled from an origin (often a MediaPackage endpoint).
- **Channel Assembly**: assembles a linear OTT channel from VOD and live
  sources on a schedule, optionally with SSAI layered on top.

## Scope boundary: this is not the upstream cascade, and ADS is not MediaTailor

MediaTailor has two external dependencies it cannot control, the **origin** it
reads content from and the **ADS** it asks for ads, and it sits *behind* the
customer's viewer-facing **CDN**. Rule all three out before attributing anything
to MediaTailor itself; conclusions about them belong to their owners.

- **Origin.** A broken MediaLive channel produces a stale MediaPackage
  manifest, which MediaTailor faithfully serves (see
  aws-mediapackage-investigate and aws-medialive-investigate). When evidence
  points upstream (`Origin.Errors`, `Origin.Timeouts`, a manifest-service
  `TIMEOUT_ERROR` / `CONNECTION_ERROR` against the origin URL, a playback 504),
  report the handoff explicitly rather than absorbing it:

```
Observed: MediaTailor Origin.Errors > 0 and manifest-service CONNECTION_ERROR
against origin <VideoContentSourceUrl>.
This points UPSTREAM of MediaTailor. Investigate the origin (MediaPackage
endpoint) with aws-mediapackage-investigate. MediaTailor is reporting an
origin it cannot reach, not generating the fault itself.
```

- **ADS.** Customer- or vendor-owned. `AdDecisionServer.Errors` / `Timeouts`,
  `EMPTY_VAST_RESPONSE`, and VAST content errors are ADS-owner findings; hand
  them off with the exact request evidence (`MAKING_ADS_REQUEST.adsRequestUrl`,
  latency, response event type).
- **CDN.** A cached personalized manifest produces "everyone gets the same
  ads" with every MediaTailor metric healthy. Step S1 has a compact precheck;
  the CDN itself is not investigated here.

## Critical constraint: observability is off by default

This is the dominant design fact for MediaTailor and the most common reason an
investigation cannot reach a conclusion. CloudWatch **metrics** are always
published (no opt-in, available by configuration or channel, and for many SSAI
metrics also as an account-level series with no dimensions). CloudWatch
**logs** are largely off by default and, for SSAI, sampled and filterable.

Five gates decide what a log can prove. Check them in Step S1 before reading
any log, and load the "Observability preconditions" section of
[references/ssai-log-catalog.md](references/ssai-log-catalog.md) when you need
the exact field, default, cap or documented trap:

- `LogConfiguration.PercentEnabled`: defaults to 0, and anything below 100
  samples sessions, so a missing log line is not evidence of health.
- `EnabledLoggingStrategies`: `LEGACY_CLOUDWATCH` needs the MediaTailor IAM
  role; `VENDED_LOGS` needs the complete delivery chain, and switching to it
  stops logs until the chain is complete.
- `ExcludeEventTypes` on both log types can hide the event you need, and
  `RAW_ADS_RESPONSE` is opt-in.
- DEBUG mode is per session, capped at 10 active sessions, and silently
  dropped over the cap; confirm it with a `SESSION_INITIALIZED` event.
- Channel Assembly As-Run logs are off until enabled per channel.

So lead every log-based step with a configuration precheck, and when the signal
is not configured, emit a DATA GAP rather than a false all-clear:

```
DATA GAP: <signal> is not observable for this resource.
Reason: <PercentEnabled=0 | IAM role absent | vended chain incomplete |
        event type excluded | DEBUG not set or over cap | As-Run off>.
What this means: <which conclusions cannot be drawn>.
To make it observable: <exact API call / field the customer must change>.
Metrics remain available, so the following can still be assessed: <list>.
```

Metrics-first reasoning is the rule: even in a total log gap, CloudWatch metrics
support real conclusions; logs add per-session and per-ad detail on top.

## Prerequisites: intake coordinates

Capture these before running anything; ask for what is missing rather than
guessing. Every finding later must carry them as evidence coordinates.

- Capability and name: SSAI configuration name, or Channel Assembly channel
  name (or enumerate in Step 0).
- Region. MediaTailor is regional; resources live in `AWS_REGION`. There is no
  global-namespace special casing here (unlike CloudFront).
- Time window (UTC): the customer's impact window, or the anomaly window
  observed in CloudWatch. Also the *baseline* window (same hours yesterday or
  same weekday last week) for Step S2.
- Protocol (HLS or DASH) and, for player-facing errors, the endpoint path
  (`/v1/master` implicit init, `/v1/session` explicit init, `/v1/manifest` or
  `/v1/dash` media/MPD requests) plus the HTTP status and `x-amzn-ErrorType`.
- `sessionId` when the complaint is about one viewer; otherwise say the
  investigation is aggregate.

## Investigation checklist

Copy this list into your working notes and tick each step as you complete it. Run
Step 0 first; it decides whether the SSAI path (S1 to S4) or the Channel Assembly
path (C1 to C4) applies. Skip a conditional step only when its condition says so,
and say so in the findings. Finish with Step F.

- [ ] Step 0: Identify capability, enumerate resources, route the symptom
- [ ] Step S1: Configuration and logging precheck
- [ ] Step S2: Metric analysis (dimension discovery first)
- [ ] Step S3: ADS and manifest log analysis (only if enabled)
- [ ] Step S4: Player-facing status triage (only if the complaint carries an HTTP status)
- [ ] Step C1: Channel and output state (Channel Assembly path, in references/channel-assembly-procedure.md)
- [ ] Step C2: Schedule, programs, and sources (Channel Assembly path, in references/channel-assembly-procedure.md)
- [ ] Step C3: ListAlerts (Channel Assembly path, in references/channel-assembly-procedure.md)
- [ ] Step C4: Metrics and As-Run log (Channel Assembly path, in references/channel-assembly-procedure.md)
- [ ] Step F: Compile findings

## Step 0: Identify capability, enumerate resources, route the symptom

If the customer named a configuration or channel, skip to the matching path.
Otherwise enumerate both. Omit `--max-results` and all pagination flags so the
SDK auto-paginates; passing caps causes errors and `--no-paginate` returns only
one page.

```
aws mediatailor list-playback-configurations --no-cli-pager --output json
aws mediatailor list-channels --no-cli-pager --output json
```

- Playback configurations present, ad symptom described -> **SSAI path** (S1).
- Channels present, linear/scheduling symptom described -> **Channel Assembly
  path** (C1).
- A channel with SSAI layered on it can require both paths; run the SSAI path
  against the configuration that fronts the channel output.

Then map the symptom to where the answer usually lives. Start at "First stop";
escalate only if it does not explain the symptom.

| Symptom as reported | First stop | Escalate to |
|---|---|---|
| Fill rate dropped / empty breaks (aggregate) | S2 fill split | S3 logs |
| Viewers see slate, or source content, or half a break | S1 config + `references/ssai-fill-behavior.md` | S2, S3 |
| Empty break or skipped ad on one specific session | S3 single-session trace | S1 (log gate) |
| Everyone gets the same ads / stale ads | S1 CDN precheck | S2 (`GetManifest.Age`) |
| Prefetch not used / ads still fetched just-in-time | S1 prefetch check | S3 prefetch-vs-JIT query |
| Ads fill on HLS but not on DASH | S1 `DashConfiguration` | S3 manifest-service events |
| Player gets a MediaTailor 4xx/5xx | S4 status triage | S2 (`Origin.*`), origin handoff |
| Session logs missing, sampled, or lacking event types | S1 logging precheck | DATA GAP |
| Beacons/tracking not firing | S2 (`Avail.Impression`/`Complete`) | S3 beacon query |
| Manifest stale at the player | S2 stale-manifest decomposition | origin handoff |
| Channel STOPPED / nothing plays | C1 | — |
| Schedule gaps / filler slate on air | C2 schedule + C3 alerts | C2 sources |
| Source alert (UNAUTHORIZED, mismatches, UNPARSABLE) | C3 alerts + `references/channel-assembly-checklist.md` | C2 sources |
| Channel output 4xx/5xx | C4 metrics | C1 policy/state |

If the symptom maps to none of these rows (for example, an encoder-side marker
question, a MediaConvert transcode failure, or a CDN tuning question), say so
plainly and stop; do not run the SSAI path against a non-SSAI complaint.

---

# SSAI path

## Step S1: Configuration and logging precheck

```
aws mediatailor get-playback-configuration --name $CONFIG_NAME \
  --no-cli-pager --output json
```

Read the configuration before touching metrics: it tells you what "expected"
means and what is observable.

Table: [Step S1: Configuration and logging precheck](references/lookup-tables.md#step-s1-configuration-and-logging-precheck). Load it when you run this step.

**Logging precheck.** If `PercentEnabled = 0`, record now that Step S3 will be a
DATA GAP and name the fix (`configure-logs-for-playback-configuration
--percent-enabled <N> --playback-configuration-name <n>`; operator action,
report it, do not attempt it). If the strategy is `VENDED_LOGS`, verify the
chain read-only before blaming sampling:

```
aws logs describe-delivery-sources --no-cli-pager --output json
aws logs describe-delivery-destinations --no-cli-pager --output json
aws logs describe-deliveries --no-cli-pager --output json
```

A source without a delivery, or a cross-account destination without a
destination policy, is a total log outage that looks like `PercentEnabled=0`.
Then check `ExcludeEventTypes`: if the customer "never sees" a family of
events, they may have excluded it.

**Prefetch check** (only if the customer uses prefetch):

```
aws mediatailor list-prefetch-schedules --playback-configuration-name $CONFIG_NAME \
  --no-cli-pager --output json
```

Confirm a schedule exists and its retrieval/consumption windows and
`AvailMatchingCriteria` cover the break in question (25 active schedules per
configuration is the documented quota). Whether prefetch was actually used is
visible only in the log: `MAKING_ADS_REQUEST.prefetchScheduleName` present =
prefetch, absent = just-in-time (query in the log catalog).

**CDN precheck for "everyone gets the same ads" / stale ads.** Personalized
manifests must not be cached (TTL 0 on `/v1/master/*`, `/v1/manifest/*`,
`/v1/dash/*`; cache key = path plus all query strings; query strings and the
`User-Agent`, `Host`, `X-Forwarded-For`, `Accept-Encoding` headers forwarded).
Ask for CDN cache status on manifest requests: any `Hit` on a manifest path is
the finding, with every MediaTailor metric healthy. Record it with the CDN owner
as next step; details in the playback-errors reference ("CDN context").

## Step S2: Metric analysis (dimension discovery first)

Discover dimensions live before querying. The published MediaTailor dimension
table documents `ConfigurationName` (all metrics) and the `Function.*`
dimensions, while the console and prose reference channel/output and an
`originID` dimension. Treat `list-metrics` output as authoritative, never the
docs.

```
aws cloudwatch list-metrics --namespace AWS/MediaTailor \
  --dimensions Name=ConfigurationName,Value=$CONFIG_NAME \
  --no-cli-pager --output json
```

Bind queries to the dimensions actually returned. The full metric catalog, the
simple-vs-weighted fill-rate formulas, render rate and video completion rate,
and good/bad guidance live in
[references/ssai-metric-reference.md](references/ssai-metric-reference.md). The
decision-relevant core:

**Fill rate.** `Avail.FillRate` and `AdDecisionServer.FillRate` are SIMPLE
averages of per-avail percentages; compute weighted averages separately and
report which you used (the reference file has the formulas). The diagnostic
split has three branches, not two:

- ADS fill low AND avail fill low -> the ADS is not returning enough ad time.
  Pursue `AdDecisionServer.Errors`, `AdDecisionServer.Timeouts`, and the log
  events `EMPTY_VAST_RESPONSE` / `WARNING_NO_ADVERTISEMENTS`. This is an
  ADS-owner finding.
- ADS fill healthy BUT avail fill low AND `SkippedReason.*` non-zero -> ads
  are returned but not inserted. Pursue the dominant `SkippedReason.*` using
  the skipped-reason catalog in the metric reference.
- ADS fill healthy, avail fill low, `SkippedReason.*` near zero -> the break
  was never personalized: avail suppression, or personalization abandoned by
  the threshold, or the session joined mid-break. Read `AvailSuppression`,
  `PersonalizationThresholdSeconds`, and `SlateAdUrl` from S1 and map the
  behavior with [references/ssai-fill-behavior.md](references/ssai-fill-behavior.md).
  Suppressed and abandoned breaks produce no `FILLED_AVAIL` in the log either,
  so a log that "shows nothing" for the break is consistent with this branch.

**ADS health.** `AdDecisionServer.Errors` and `AdDecisionServer.Timeouts`
should be ~0. Read `AdDecisionServer.Latency` against the bands in the metric
reference (ADS metrics); sustained latency far above typical is an ADS or
network problem, and the fixed ADS request timeout is in the playback-errors
reference.

**Stale manifests.** Decompose `GetManifest.Age` into `Origin.Age` (origin held
the manifest; not emitted on CDN-cached responses) versus
`GetManifest.MediaTailorAge` plus `GetManifest.Latency` (MediaTailor side). High
`GetManifest.Age` with low MediaTailor-side components points upstream.

**Skipped detail.** Each `SkippedReason.*` metric explains a gap between
`AdDecisionServer.Ads` and inserted ads. Map each to its meaning via the
reference file before concluding.

**Is it actually anomalous?** MediaTailor traffic is diurnal and event-driven,
so a value means little without the configuration's own baseline. Before
calling anything a problem: compare against the same clock hours a day earlier
and the same weekday a week earlier (identical `Period`); pair every error or
timeout count with `Requests` over the same window so no rate is reported
without its denominator; and correlate the sibling metric before naming a layer.
The baseline method, the `ANOMALY_DETECTION_BAND` read-only expression, and the
correlation map are in the metric reference ("Baseline and correlation").

## Step S3: ADS and manifest log analysis (only if enabled)

First confirm observability from Step S1. If `PercentEnabled = 0` or the
vended chain is incomplete, emit the DATA GAP and stop this step. If sampled
(<100), every log conclusion carries the caveat that absence is not proof.

Log groups (streams prefixed with the configuration name):

- `MediaTailor/AdDecisionServerInteractions` (ADS request/response, fill,
  errors, beaconing, redirects, skipped ads, prefetch use)
- `MediaTailor/ManifestService` (origin retrieval and manifest processing;
  typically only errors unless DEBUG)
- `MediaTailor/TranscodeService` (ad transcode status)

The event-type catalog (request, fill, error, VAST, redirect, beacon, and
Functions events), the key log fields and objects (`avail`, `vastResponse`,
`skippedAds[]`), the manifest-service event types, the DEBUG-only events, the
ready-to-run Logs Insights queries, the metric-name-versus-log-enum casing
trap, and the known schema bugs (notably that a `VAST_RESPONSE` event may carry
no `vastResponse` object on empty responses) are all in
[references/ssai-log-catalog.md](references/ssai-log-catalog.md).

Highest-value starting queries (full set in the reference file):

- Event-type histogram (`stats count(*) by eventType`) to see the shape of the
  problem before drilling in.
- Skipped-ad reasons from `FILLED_AVAIL` events (`skippedAds.0.skippedReason`).
- Prefetch versus just-in-time split from `MAKING_ADS_REQUEST`.
- A single failing session or request trace (`filter sessionId = "..."` or
  `filter requestId = "..."`).

Run Logs Insights with the async start-query / get-query-results pattern
(start-query uses epoch seconds; filter-log-events uses epoch milliseconds).

## Step S4: Player-facing status triage (only if the complaint carries an HTTP status)

MediaTailor returns a status code, an exception name (`x-amzn-ErrorType`
response header), and a message. 4xx is the request/config/CDN/player class;
5xx is the MediaTailor-or-dependency class. The public table, the fixed limits
that produce them, and the parameter-encoding rules are in
[references/playback-errors-and-limits.md](references/playback-errors-and-limits.md).
The routing summary:

Table: [Step S4: Player-facing status triage (only if the complaint carries an HTTP status)](references/lookup-tables.md#step-s4-player-facing-status-triage-only-if-the-complaint-carries-an-http-status). Load it when you run this step.

---

# Channel Assembly path

Steps C1 to C4 (channel and output state; schedule, programs and sources;
ListAlerts; metrics and As-Run log) are in
[references/channel-assembly-procedure.md](references/channel-assembly-procedure.md).
Load it when Step 0 routes a Channel Assembly symptom, run the steps in order,
then compile the findings with Step F below.

## Step F: Compile findings

Structure the output as follows. For each finding:
Observed (the metric/log/config value plus the API or namespace it came from,
with its coordinates: configuration or channel name, region, window, and
`sessionId` where applicable), Expected (the threshold or benchmark plus its
source), Question: Why?, and a confidence tag: **Observed-healthy**,
**Observed-problem**, or **DATA-GAP**. Evidence that cannot be re-derived from
the coordinates you give is not evidence; paste the metric values or the log
line, not "the logs show".

Use the matching report outline (SSAI or Channel Assembly) in
[references/report-outlines.md](references/report-outlines.md) when compiling
the report; load it at this step only.

Use [references/channel-assembly-checklist.md](references/channel-assembly-checklist.md)
for the mechanical PASS/FAIL pass on the Channel Assembly path, and
[references/ssai-metric-reference.md](references/ssai-metric-reference.md),
[references/ssai-log-catalog.md](references/ssai-log-catalog.md),
[references/ssai-fill-behavior.md](references/ssai-fill-behavior.md), and
[references/playback-errors-and-limits.md](references/playback-errors-and-limits.md)
for the SSAI detail.

Thresholds that should change the call: any `5xxErrorCount` on a channel; any
`AdDecisionServer.Errors` or `Timeouts` sustained above 0; `Avail.FillRate` well
below `AdDecisionServer.FillRate` (insertion or suppression, not an ADS
problem); `GetManifest.Age` beyond the workflow's tolerance; any non-Info
ListAlerts entry present; any `Hit` cache status on a personalized manifest
path.

### Before presenting

Check the compiled findings and fix anything that fails before presenting them:

- Every Observed value names the API field or metric it came from, with its dimensions and time window.
- Every Expected value names its source: a threshold, a documented limit, or the resource's own configuration.
- No section asserts a definitive root cause; each finding ends in a question or a named handoff.
- Every signal that was not observable is reported as a DATA GAP with its reason, never as a healthy zero.
- No account IDs, ARNs, secrets or passphrases are reproduced; resources are named by type and name.
- Every fill finding says which branch of the three-way split it landed in, and every log conclusion states the PercentEnabled and delivery strategy it depends on.
