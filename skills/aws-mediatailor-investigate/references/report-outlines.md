# MediaTailor Findings Report Outlines

Section outlines for Step F of SKILL.md. Use the SSAI outline for an SSAI
investigation and the Channel Assembly outline for a Channel Assembly
investigation. Each finding inside a section keeps the Observed / Expected /
Question structure and its confidence tag.

## SSAI
1. Configuration identity: name, ADS URL, content source, insertion mode, slate,
   suppression, threshold, DASH settings.
2. Observability state: `PercentEnabled`, delivery strategy and vended chain,
   IAM role presence, excluded event types, what is and is not observable (set
   expectations up front).
3. Fill analysis: avail vs ADS fill (simple and weighted), with the three-branch
   diagnostic split from S2 and the baseline comparison.
4. ADS health: errors, timeouts, latency (ADS-owner handoff if the ADS is the
   source).
5. Skipped reasons: the dominant `SkippedReason.*` contributors.
6. Origin and manifest: origin errors/timeouts; stale-manifest decomposition;
   upstream handoff if indicated.
7. Player-facing status triage (if applicable) and CDN precheck result.
8. Log evidence or DATA GAP.
9. Open questions ranked by severity.

## Channel Assembly
1. Channel identity: name, state, playback mode, tier, outputs.
2. Schedule health: gaps, filler-slate fallbacks, upcoming-window depth.
3. Source resolution: source locations, sources, SourceGroup contract, access
   configuration.
4. Alerts: ListAlerts findings mapped via the catalog (or DATA GAP if
   pre-2021-07-14).
5. Output metrics: 4xx/5xx/RequestCount/TotalTime.
6. As-Run evidence or DATA GAP.
7. Open questions ranked by severity.
