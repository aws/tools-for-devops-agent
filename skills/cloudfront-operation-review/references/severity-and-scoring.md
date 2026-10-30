# Severity and Scoring — Amazon CloudFront Operational Review

Load in Step 5, before findings are rated and scored.

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Content or credentials exposed now (for example, plaintext HTTP to viewers or origin, SSLv3) | Fix within 24–48 hours |
| HIGH | Significant security or availability gap likely to cause an incident | Fix within 1 week |
| MEDIUM | Notable improvement opportunity | Plan within 30 days |
| LOW | Minor optimization or hygiene. Does not reduce the score | Address when convenient |
| INFO | Observation, no action required | N/A |

## Readiness score

Per distribution and per pillar:

```
score = passes ÷ (passes + warnings + fails) × 100
```

- LOW findings count as passes.
- Inspect, N/A and not-evaluated checks are excluded from both terms.
- Report the excluded count beside every score.
