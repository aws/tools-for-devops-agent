# MySQL / Aurora MySQL Support-Date Calendar

Authoritative support dates, cross-referenced from AWS documentation
(verified 2026-09-18). RDS-for-MySQL and Aurora MySQL are tracked separately
because their dates differ even where MySQL-compat versions overlap.

## RDS for MySQL
Source: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MySQL.Concepts.VersionMgmt.html

| Major | End of standard support | End of Extended Support | Recommended target |
|-------|-------------------------|--------------------------|--------------------|
| 5.7   | 2024-02-29              | 2029-06-30               | 8.0                |
| 8.0   | 2026-07-31              | 2029-07-31               | 8.4                |
| 8.4   | 2029-07-31              | 2032-07-31               | (latest LTS)       |

## Aurora MySQL
Source: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraMySQLReleaseNotes/AuroraMySQL.release-calendars.html

| Aurora major | MySQL compat | End of standard support | End of Extended Support | Recommended target |
|--------------|--------------|-------------------------|--------------------------|--------------------|
| 1            | 5.6          | 2023-02-28 (deprecated) | n/a                      | 3                  |
| 2            | 5.7          | 2024-10-31              | 2029-06-30               | 3                  |
| 3            | 8.0          | 2028-04-30              | 2029-07-31               | 8.4                |
| 8.4          | 8.4          | 2032-04-30              | TBD                      | (latest LTS)       |

## Notes
- Extended Support is paid; RDS auto-enrolls instances past end of standard
  support unless `EngineLifecycleSupport` is set to disable it.
- Treat end of standard support (not Extended Support) as the migration
  milestone for production systems.
