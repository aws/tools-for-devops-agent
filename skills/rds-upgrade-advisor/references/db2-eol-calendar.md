# IBM Db2 (RDS) Support-Date Calendar

Authoritative support dates for RDS for Db2 (verified 2026-10-06). RDS for Db2
support tracks IBM's Db2 LUW End of Support (EOS) lifecycle rather than a separate
AWS-published calendar; dates below come from IBM's Db2 Distributed EOS page.
There is NO RDS Extended Support tier for Db2 (that is a MySQL/PostgreSQL-only
feature) — "Extended" below is IBM's own paid Extended Support, not RDS Extended
Support. For the advisor's purposes, treat IBM base EOS as the end-of-standard-
support milestone.

Editions / engine identifiers: `db2-se` (Standard), `db2-ae` (Advanced),
`db2-ce` (Community — new in 12.1, free with IBM-enforced 4 vCPU / 8 GB limits).
Dates are the same across editions.

Version-major parsing: Db2 majors are two-part (`11.5`, `12.1`). RDS reports
`EngineVersion` like `11.5.9.0.sb00090009.r1` or `12.1.5.0.sb00088454.r1`; the
major is the first two dot-components (`11.5`, `12.1`).

## RDS for Db2
Sources:
- https://www.ibm.com/support/pages/db2-distributed-end-support-eos-dates (IBM EOS)
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Db2.Concepts.VersionMgmt.html
- https://aws.amazon.com/rds/db2/faqs/

| Major | IBM base EOS (= end of standard support) | IBM Extended EOS | Recommended target |
|-------|-------------------------------------------|------------------|--------------------|
| 11.5  | 2027-04-30                                | 2031-04-30       | 12.1               |
| 12.1  | TBD (IBM not yet published)               | base + 4 years   | (latest)           |

## Notes
- RDS for Db2 currently offers two majors: **11.5** (11.5.9.x) and **12.1**
  (12.1.4.x / 12.1.5.x). Supported major upgrade path: **11.5.9 -> 12.1**.
- Db2 11.5 base EOS is 2027-04-30 — within the advisor's 180-day UPCOMING_EOL
  window only after ~2026-11; before that it classifies SUPPORTED. After
  2027-04-30 it is past standard support -> DEPRECATED (no RDS Extended Support).
- 12.1 base EOS is not yet published by IBM; treat 12.1 as SUPPORTED and
  recommend confirming the date via IBM / `describe-db-major-engine-versions`.
- Community Edition (`db2-ce`) exists only on 12.1; it is not an upgrade target
  for a Standard/Advanced 11.5 instance unless the user explicitly chooses to
  change edition at upgrade time (compute-limited).
- Pre-11.5 (e.g. 11.1) is NOT createable on RDS; those migrate in via
  backup/restore. Treat any sub-11.5 Db2 as DEPRECATED / migrate-first.
- Re-verify IBM dates near a boundary; also `aws rds
  describe-db-major-engine-versions --engine db2-se` surfaces RDS's own
  start/end support dates when populated.
