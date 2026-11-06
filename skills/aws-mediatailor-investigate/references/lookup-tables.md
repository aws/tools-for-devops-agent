# MediaTailor Investigation: Lookup Tables

Metric catalogs, status tables and field tables relocated from SKILL.md so they load
only when the step that uses them runs. Each heading names the SKILL.md step and
subsection the table belongs to; the surrounding instructions stay in SKILL.md.

## Step S1: Configuration and logging precheck

| Field | Why it matters |
|---|---|
| `AdDecisionServerUrl` | The ADS endpoint; template macros here drive `WARNING_URL_VARIABLE_SUBSTITUTION_FAILED` if unresolved (`[player_params.*]` need the `ads.` prefix on the session request; domain variables must be exhaustively mapped in `ConfigurationAliases`) |
| `VideoContentSourceUrl` | The origin; an unreachable origin produces `Origin.Errors` (likely an upstream handoff) |
| `SlateAdUrl` | If set, unfilled avails in a break MediaTailor is personalizing are padded with slate; high `Avail.ObservedSlateDuration` is expected when fill is low. Slate never appears in a suppressed or abandoned break |
| `PersonalizationThresholdSeconds` | Only active when a slate is set. If unfilled time in a break exceeds it, personalization of the whole break is abandoned: no ads, no slate, no bumpers, source content shows (`SkippedReason.PersonalizationThresholdExceeded`) |
| `AvailSuppression` (`Mode`, `Value`, `FillPolicy`) | Live SSAI only. `BEHIND_LIVE_EDGE` skips breaks starting on or before live edge minus Value (always whole-break); `AFTER_LIVE_EDGE` skips breaks until session elapsed time reaches Value (`PARTIAL_AVAIL` fills the post-window tail). Suppressed breaks are never sent to the ADS, so they lower `Avail.FillRate` while ADS fill stays healthy: expected, not a fault |
| `LivePreRollConfiguration`, `Bumper` | Explain "no pre-roll" and "bumper missing on first break" complaints; see the fill-behavior reference |
| `ManifestProcessingRules.AdMarkerPassthrough` | Affects which ad markers survive into the personalized manifest |
| `InsertionMode` (`STITCHED_ONLY` / `PLAYER_SELECT`) | PLAYER_SELECT (HLS interstitials) changes the meaning of `Observed*` metrics to estimates |
| `DashConfiguration.OriginManifestType` | `MULTI_PERIOD` (default) or `SINGLE_PERIOD`; must match how the origin structures periods. "Fills on HLS but not DASH" starts here |
| `DashConfiguration.MpdLocation` | `EMT_DEFAULT` (default) includes the DASH `Location` tag so players keep refreshing the session-specific MPD URL; `DISABLED` omits it. Relevant when DASH players appear to start a new session on every refresh |
| `AdConditioningConfiguration.StreamingMediaFileConditioning` | `TRANSCODE` (default) vs `NONE` (preconditioned / bring-your-own ads). Explains `SkippedReason.ImportError` / `ImportInProgress` |
| `CdnConfiguration` (`AdSegmentUrlPrefix`, `ContentSegmentUrlPrefix`) | Which CDN prefixes MediaTailor writes into manifests; unset ad prefix means ad segments come from a MediaTailor-owned domain |
| `LogConfiguration.PercentEnabled` | **The gate.** 0 = no session logs. <100 = sampled. Drives DATA GAP for all log steps |
| `LogConfiguration.EnabledLoggingStrategies`, `AdsInteractionLog.ExcludeEventTypes` / `PublishOptInEventTypes`, `ManifestServiceInteractionLog.ExcludeEventTypes` | Delivery path and event filters; see the observability section |

## Step S4: Player-facing status triage (only if the complaint carries an HTTP status)

| Code | Exception | Most likely | Read next |
|---|---|---|---|
| 400 | `BadRequestException` | Malformed or unencoded params, invalid session ID, missing configuration alias at init; **or a session that expired after inactivity of 10x the manifest duration** (paused/backgrounded players) | When did it fire (init vs after a pause)? Alias and encoding rules in the reference |
| 403 | `AccessDeniedException` | Request `Host` header does not match `ManifestEndpointPrefix`; CDN misconfiguration | Compare CDN origin host to the configuration's endpoint prefix |
| 404 | `NotFoundException` | URL maps to nothing, configuration undefined/inactive, session unavailable | Validate URL against `ManifestEndpointPrefix`; reinitialize the session |
| 409 | `ConflictException` | HLS player loaded multiple playlists at once for one session (spec says one at a time), or a session URL shared across viewers | Player behavior; CDN `aws.sessionId` passthrough |
| 410 | `Gone` | AWS Support blocked a session/configuration after very high errant 4xx volume | Support case; not a config bug |
| 500 | `InternalServiceError` | Unhandled exception | Retry; check the AWS Health Dashboard for the region |
| 502 | `BadGatewayException` | Origin or ADS address invalid (private IP, localhost) | Audit `VideoContentSourceUrl` / `AdDecisionServerUrl` |
| 502 | `UnsupportedManifestException` | Origin manifest changed or format unsupported (for example SCTE markers not aligned across playlists) | Reinitialize; verify origin manifest support -> origin handoff |
| 503 | `LoadShed` | MediaTailor resource constraint | Retry; AWS Health |
| 503 | `ThrottlingException` | Account TPS reached the Ad Insertion Requests quota (10,000 RPS default, adjustable) | Service Quotas increase (operator) |
| 504 | `GatewayTimeoutException` | Origin did not answer within the fixed 2 s content-origin timeout | `Origin.Timeouts` / `Origin.Errors` -> **origin handoff** |
