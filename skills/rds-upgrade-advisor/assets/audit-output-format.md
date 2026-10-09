# At-scale audit output format (chat + artifact)

Load this when running an account-wide or scheduled upgrade-readiness audit (tens
to hundreds of databases) and you need to produce the two output surfaces: a
concise CHAT response and a full downloadable ARTIFACT. For a single-database
interactive question you do not need this file.

## DETAIL_THRESHOLD = 10
A single number governs chat verbosity. "DBs with findings" = databases whose
FAILED/BLOCKED upgrade log was parsed (completed-upgrade prechecks are out of
scope and never counted here).

## Per-database upgrade-status glyph (chat AND artifact)
Because only failed/blocked upgrades are parsed, every parsed log is a blocked
one. Use:
- `❌ BLOCKED` — footer errors > 0 (or the engine reported the upgrade could not
  proceed). ERRORs must be fixed BEFORE upgrading.
Databases with no FAILED upgrade log are reported via their EOL/version status
(DEPRECATED / EXTENDED_SUPPORT / UPCOMING_EOL / SUPPORTED) with no glyph; a
completed or clean upgrade is NOT parsed or shown.

## Scope note on completed upgrades (current policy)
Intentionally focus on ERRORS from FAILED/BLOCKED upgrades. Prechecks from
upgrades that COMPLETED — including the "upgraded-with-warnings" case where an
engine (notably Aurora MySQL) lets an upgrade finish despite WARNING-class
precheck items that leave an object non-functional on the new version — are OUT
OF SCOPE for now and are NOT parsed or reported. There are many such engine- and
version-specific WARNING behaviors; rather than enumerate them, skip completed
upgrades entirely in this version and report only blocking ERRORs plus
EOL/version status. (If this policy is later relaxed to surface high-risk
completed-upgrade warnings, do it generically across engines, not as a single
hard-coded example.)

## A) Chat / text response — concise, built for scale
Keep it skimmable; a hundred-DB account must still fit on a screen or two. No
preamble, no restating instructions, no per-DB prose paragraphs.

1. One-line roll-up:
   "128 DBs · 6 need attention · 122 supported · 4 with past upgrade findings."
2. One ENGINE-BREAKDOWN line: "Engines: 40 mysql · 31 postgres · 8 mariadb ·
   9 sqlserver · 6 oracle."

Then ONE SECTION PER ENGINE PRESENT — same per-engine grouping as the artifact,
condensed. INCLUDE A SECTION ONLY IF >=1 instance of that engine exists; order by
descending instance count. Short header, e.g. "### PostgreSQL (31 DBs · 2 need
attention)". Within each engine section:
  a. One status tally line (counts only):
     "DEPRECATED 1 · EXTENDED_SUPPORT 1 · UPCOMING_EOL 0 · SUPPORTED 29".
  b. Needs-attention table — ONE ROW PER NON-SUPPORTED db (omit SUPPORTED):
     `Database | Version | Status | EOSS (days) | Target`.
  c. Past-upgrade findings, governed by DETAIL_THRESHOLD (applied PER ENGINE): if
     the engine's DBs-with-findings <= DETAIL_THRESHOLD, list each with its glyph +
     one-line footer counts + its ERROR findings (one-line remediation each). If
     more, show only the top DETAIL_THRESHOLD (most ERRORs, then nearest EOL) with
     glyph + footer counts + ERRORs only, then one line "+N more in the artifact."
     If the engine has none: omit (c).

If an engine section has zero non-SUPPORTED DBs AND zero findings, collapse it to
one line: "### MariaDB — 8 DBs, all supported, no upgrade findings." Keep
per-finding text to ONE line each (severity — object — fix). Do NOT dump the full
all-DB config view in chat; if total DBs > ~15, end with: "Full config view + all
WARNING/NOTICE detail for every DB is in the artifact '<title>'." No prior
attempts anywhere -> a single line "No prior upgrade attempts found." Cite a
source URL once per unique support-date claim.

## B) Artifact — the full, downloadable report (every invocation)
ALWAYS produce the artifact, and it MUST have a title. The FIRST line of the
artifact MUST be exactly this title (an H1), with no other text before it:
  "RDS/Aurora Upgrade-Readiness Audit — <scope> — <YYYY-MM-DD>"
where <scope> is "all regions" for an account-wide run, or the specific region(s)
scanned if the user limited them, and <YYYY-MM-DD> is today's date. Never emit the
report without this titled header, regardless of how the invoking agent/prompt is
worded. Include each database's region in the config view. It is the complete
report (NOT truncated by DETAIL_THRESHOLD) and contains, in order:
- Text: the one-line roll-up + a short summary paragraph of key trends, including
  an ENGINE BREAKDOWN line.
- Chart (bar): database COUNT BY SUPPORT STATUS
  (DEPRECATED / EXTENDED_SUPPORT / UPCOMING_EOL / SUPPORTED), grouped by engine
  where helpful.
- Table: needs-attention (every non-SUPPORTED db, ALL engines) with the columns
  above plus an Engine column.

### Per-engine sections (the body of the report)
Group the detailed body into one SECTION PER ENGINE, and INCLUDE A SECTION ONLY
IF AT LEAST ONE DATABASE OF THAT ENGINE EXISTS in the scanned region(s). Omit the
section entirely for engines with zero instances. Order sections by descending
instance count (most common engine first); break ties alphabetically. Use these
section headers when present: "## MySQL (RDS)", "## Aurora MySQL",
"## PostgreSQL (RDS)", "## Aurora PostgreSQL", "## MariaDB (RDS)",
"## SQL Server (RDS)", "## Oracle (RDS)", "## Db2 (RDS)". (You MAY merge
`mysql`+`aurora-mysql` under one "MySQL family" header, and
`postgres`+`aurora-postgresql` under one "PostgreSQL family" header, IF both have
instances and it reads cleaner — but still only when instances exist.)
Each engine section contains, scoped to that engine's databases:
  - a one-line engine roll-up (N DBs · N need attention · N with upgrade evidence);
  - the full config view table for that engine
    (Database | Kind | AZ | Multi-AZ | Nodes | Class | Edition/License | Tags);
  - per db that has in-scope upgrade evidence: the status glyph + (for MySQL/
    Aurora MySQL) footer counts, then the FULL findings ERROR -> WARNING -> NOTICE
    each with remediation, plus the upgrade event timeline. For PostgreSQL use the
    pg_upgrade per-database blocker grouping; for MariaDB the error-log findings;
    for Oracle/SQL Server/Db2 the EVENTS + config-readiness checklist (clearly
    marked "no precheck log for this engine — events + config review"). The
    artifact always includes WARNING/NOTICE even when chat omitted them.
  - suggested upgrade method per needs-attention db in that engine (BG omitted for
    Oracle/SQL Server/Db2) with the key reason and engine-specific pre-steps.
If the whole account has only one engine, that single section plus the summary is
the report (do not invent sections for absent engines). The artifact is persisted
in the Agent Space and downloadable from the invocation trajectory and the
Artifacts page.

## Notifications (optional, built-in)
If a notification channel is configured, send one short notification at the end
summarizing: N need attention, N with blocking upgrade ERRORs. If no channel is
set up, continue normally.
