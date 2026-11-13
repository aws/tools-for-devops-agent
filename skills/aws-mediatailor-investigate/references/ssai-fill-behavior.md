# MediaTailor SSAI Fill Behavior: why the viewer saw what they saw

Behavior semantics for the "viewers saw X" class of complaint. It maps the
playback-configuration fields read in Step S1 (`AvailSuppression`,
`SlateAdUrl`, `PersonalizationThresholdSeconds`, `Bumper`,
`LivePreRollConfiguration`) plus the playback context (live vs VOD, join time,
live edge) onto what the viewer actually sees: personalized ads, slate,
underlying source content, or a partially filled break. It explains *why* a
configuration produced a behavior; the metrics and log queries that confirm it
live in the metric and log references.

Sources (public user guide, read 2026-08-17): `ad-rules` (avail suppression),
`slate-management` (slate and personalization threshold), `bumpers`,
`ad-behavior-preroll`, `ad-behavior` and `ad-behavior-live`.

## Symptom router: "the viewer saw X"

| Reported behavior | Most likely cause | Section |
|---|---|---|
| Source content instead of ads for a whole break, only for viewers who joined mid-break or are behind the live edge | `BEHIND_LIVE_EDGE` suppression | Avail suppression |
| No ads for the first N minutes of every session, then normal | `AFTER_LIVE_EDGE` suppression (session elapsed time below Value) | Avail suppression |
| Ads for part of a break, source content for the rest | `AFTER_LIVE_EDGE` with `PARTIAL_AVAIL`, or ADS underfill within the threshold | Avail suppression / Threshold |
| Slate (still image or looped video) instead of ads | A break MediaTailor is personalizing could not be filled: empty VAST/VMAP, ADS error or timeout, ad not yet transcoded, or remainder after ads | Slate |
| No ads, no slate, just source content, with a healthy ADS response | Unfilled time exceeded `PersonalizationThresholdSeconds`; whole break abandoned | Threshold |
| No slate even though one is configured | The break was suppressed (never personalized) or abandoned; slate only appears in a break being personalized | Slate |
| No pre-roll at session start | Live pre-roll not configured; empty/timeout/404 from the pre-roll ADS; pre-roll overlapped by another break | Live pre-roll |
| VOD: all ads bunched at the start, or at unexpected times | No SCTE markers, so a single ADS call: VAST = one pre-roll, VMAP = its offsets | VOD insertion vs replacement |
| Bumper missing on the first break only | Bumpers do not play in the pre-roll break when pre-roll is configured | Bumpers |
| A 30 s break with no ads although the ADS returned ads | Every returned ad was longer than the break; MediaTailor inserts only ads that fit | Live selection rules |

Scopes at a glance: **avail suppression = live SSAI only** (not VOD, not
SGAI). **Slate = live and live-to-VOD only.** **Personalization threshold =
ad replacement** (live and VOD), and only when a slate is configured. **Live
pre-roll = live only.**

## Avail suppression (live SSAI only)

Avail suppression tells MediaTailor to skip personalizing certain live ad
breaks, so the origin's underlying content passes through untouched. All
comparisons are against the live edge of the stream.

| `Mode` | What is NOT personalized | `FillPolicy` | Whole break or partial |
|---|---|---|---|
| `OFF` (default) | Nothing; all breaks personalized | n/a | n/a |
| `BEHIND_LIVE_EDGE` | Breaks that start on or before (live edge minus `Value`) in the manifest lookback window | Always `FULL_AVAIL_ONLY` | Always the entire break |
| `AFTER_LIVE_EDGE` | Breaks within live edge plus `Value` (until session elapsed time reaches `Value`) | `FULL_AVAIL_ONLY` (default) or `PARTIAL_AVAIL` | Whole break, or partial fill of the portion after the suppression window |

- `Value` is `HH:MM:SS`, relative to the live edge. `00:00:00` means in sync
  with the live edge (for `BEHIND_LIVE_EDGE`: suppress every break starting on
  or before the edge; for `AFTER_LIVE_EDGE`: no suppression window). Example
  from the docs: `BEHIND_LIVE_EDGE` with `00:45:00` fills breaks within 45
  minutes behind the live edge and suppresses breaks on or behind 45 minutes.
- `AFTER_LIVE_EDGE` with `PARTIAL_AVAIL` gives a mid-break joiner the tail of
  the break; the portion during or before the window stays unpersonalized.
- The same three settings can be supplied per session on the initial playback
  request (`aws.availSuppressionMode`, `aws.availSuppressionValue` URL-encoded,
  `aws.availSuppressionFillPolicy`); mode and value are both required for the
  override to take effect.

**Why suppression reads as a fill-rate drop.** A suppressed break is never sent
to the ADS and never personalized. It produces no `FILLED_AVAIL` event and no
`SkippedReason.*` metric, and it lowers `Avail.FillRate` while
`AdDecisionServer.FillRate` stays healthy. Large DVR or lookback windows with
`BEHIND_LIVE_EDGE` suppress many historical avails, which is often misread as a
regression. This is the third branch of the Step S2 diagnostic split.

## Slate

`SlateAdUrl` is a default MP4 played instead of live content during a break
(live and live-to-VOD only). Requirements: high-quality MP4 with both audio and
video; if hosted over HTTPS the certificate must be from a well-known CA (no
self-signed); mandatory for VPAID (MediaTailor inserts slate to hold space for
the player-inserted VPAID ad). MediaTailor shows slate in exactly four
situations, all inside a break it is personalizing:

1. To fill time remaining in a break not replaced by personalized ads.
2. The ADS returns an empty VAST or VMAP response.
3. Error conditions such as ADS timeout or HTTP 500 from the ADS.
4. An ad is not available for insertion (for example, not finished transcoding).

No slate configured means MediaTailor falls back to the underlying content in
those cases. A suppressed or abandoned break is never personalized, so slate
never appears there; "slate is configured but does not show" almost always
means suppression or an abandoned break, not a broken slate.

## Personalization threshold

`PersonalizationThresholdSeconds` defines the maximum duration of underfilled
ad time (seconds) allowed in a break. It applies to ad replacement (live and
VOD, because it relies on an underlying stream) and only operates when a slate
is configured. Behavior per the API definition and the guide prose:

- Unfilled time **exceeds** the threshold: MediaTailor abandons personalization
  of the entire break; underlying content shows; no ads, no slate, no bumpers.
- Unfilled time within the threshold: ads and slate are inserted (bumpers too
  if configured).
- Threshold greater than the break duration: ads insert, slate fills the
  remainder, bumpers insert if configured.
- Slate configured and no threshold: slate plays for the full origin avail
  duration or whatever remains after the ads.

Worked example: a 90 s break, the ADS fills 60 s, threshold 8 s. Unfilled is
30 s, which exceeds 8 s, so the whole break is abandoned and viewers see 90 s of
source content with no ads and no slate. Raising the threshold above the
possible unfilled time (or removing it) restores ads plus slate fill.

Doc caveat: the "Detailed behavior matrix" on the slate-management page prints
the row for filling unused ad-replacement time as "if personalization threshold
greater than unfilled time: no ads/slates inserted, else ads and slates
inserted", which is inverted relative to the page's own prose and the
`PersonalizationThresholdSeconds` API definition (abandon when unfilled time
exceeds the threshold). Follow the prose and API definition; the matrix's other
rows (empty VAST, ADS timeout, ad unavailable, pre-roll, bumpers) are consistent
with them: threshold configured and smaller than the break means no slate on
those failures, threshold absent or larger than the break means slate.

## Bumpers

`Bumper.StartUrl` and `Bumper.EndUrl` are short clips at the start and/or end
of a break. They play in every break except the pre-roll break when pre-roll is
configured, are transcoded to match the source, and only appear when the break
is being personalized (abandoned or suppressed breaks get no bumpers). See the
`bumpers` guide page for the current duration and marker requirements.

## Live pre-roll

`LivePreRollConfiguration` = `AdDecisionServerUrl` plus optional
`MaxDurationSeconds`; live workflows only. If total ad duration is within the
maximum, all ads are inserted; otherwise MediaTailor inserts the subset that
fits without exceeding it (no clipping). If the pre-roll overlaps another ad
break, MediaTailor does not personalize the overlapped portion of that break.
Empty VAST, ADS timeout, or 404 during pre-roll yields slate (or nothing, per
the threshold rules) and no pre-roll. In SSAI the pre-roll replaces live
content per viewer at session start; in server-guided mode MediaTailor places a
pre-roll `EXT-X-DATERANGE` with `CUE="PRE,ONCE"` in the shared manifest.

## Live selection rules and VOD insertion vs replacement

Live is always ad replacement. With a duration set, MediaTailor picks a set of
full ads that fit; a CUE-IN cuts to content immediately; running out of ads
yields slate (if configured) or content. Documented examples: a 70 s break with
two 40 s ads plays one ad, then slate or content; a 30 s break whose shortest ad
is 40 s plays no ads (slate for 30 s if configured, else content).

VOD depends on origin markers and the ADS response type. SCTE-35 markers
present: ads insert at the markers (an `EXT-X-CUE-OUT` of 0 duration signals
insertion). No markers: one ADS call; a VAST response becomes a single pre-roll
at manifest start, a VMAP response creates breaks at its time offsets.

## Behavior to signature (confirm from data)

| Observed behavior | ADS log signature (per session) | Metric signature |
|---|---|---|
| Break suppressed (behind or after live edge) | No `FILLED_AVAIL` for that avail; no ADS request for it | `Avail.FillRate` low while `AdDecisionServer.FillRate` healthy; `SkippedReason.*` flat |
| Personalization abandoned (threshold exceeded) | No `FILLED_AVAIL` for the break; `WARNING_NO_ADVERTISEMENTS` may appear | `SkippedReason.PersonalizationThresholdExceeded` > 0; avail fill low, ADS fill healthy |
| Slate filled the remainder | `FILLED_AVAIL` with `avail.slateAd` set; `avail.fillRate` < 1.0 | `Avail.FilledDuration` < `Avail.Duration`; `Avail.ObservedSlateDuration` > 0; ADS fill healthy |
| Empty ADS response | `EMPTY_VAST_RESPONSE` / `EMPTY_VMAP_RESPONSE` | `AdDecisionServer.FillRate` low; `AdDecisionServer.Errors` counts empty responses |
| ADS error or timeout | `ERROR_ADS_TIMEOUT` / `ERROR_ADS_INVALID_RESPONSE` / `ERROR_ADS_IO` | `AdDecisionServer.Errors` / `AdDecisionServer.Timeouts` > 0 |
| Ad not transcoded yet | `FILLED_AVAIL` with `avail.skippedAds[].skippedReason` transcode-related | `SkippedReason.TranscodeInProgress` / `NewCreative` / `TranscodeError` > 0; `AdNotReady` > 0 |
| Variant or profile mismatch | `avail.skippedAds[].skippedReason` variant/profile-related | `SkippedReason.NoVariantMatch` / `ProfileNotFound` > 0 |

Never assert a numeric fill rate from this table; read it. The queries are in
the log catalog and the formulas in the metric reference.
