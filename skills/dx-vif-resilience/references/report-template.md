# Report template — DX VIF Resilience Assessment

Use this structure for the final report. Replace `<...>` placeholders with
live data from the tool output; never invent values.

```
## DX VIF Resilience Assessment (Layer 3 — BGP Prefix Coverage)
Account: <id> | Region: <region> | Assessment time: <timestamp>
Redundant set: <vifs> (intent source: memory | resiliency group <id> | inferred — confirm)

### BGP session health
<per-VIF status; excluded VIFs and why>

### Direction 1 — Routes received from on-prem (accepted)
Summary: N prefixes | gaps N | partial-supernet N | partial N | covered N
🚨 Gaps: table (prefix | present on | missing from | failover consequence)
⚠️ Partial supernet coverage: table (supernet | peer | uncovered residual | "confirm if workloads exist in residual")
✅ Covered: count

### Direction 2 — Routes advertised by AWS (advertised)
<same structure>

### Additional findings
<empty VIFs, default routes, **device diversity AND DX-location diversity as
two separate lines**, resiliency-group pairing issues (or "cannot verify" for
hosted/cross-account VIFs), orphan VIFs, route-count-vs-quota proximity
(against the account's effective quotas, which are adjustable)>

### Recommended customer actions
<plain-language, prioritized; note that intentional asymmetry is fine but the
failover consequence for the listed prefixes must be a conscious decision>

Note: This assessment covers BGP prefix coverage and device diversity. It does
not validate physical path diversity end-to-end, BFD configuration, or
on-prem router behavior. It is a point-in-time snapshot of live BGP tables.
```
