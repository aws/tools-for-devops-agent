# Support Cases & Critical Trusted Advisor Report

**Data window:** <start-date> → <end-date> (<window description, e.g. "trailing 12 months">)
**Accounts analyzed:** <account-id>, <account-id>, …

> If the window is the skill's default rather than a window the user asked for, say so here.

---

## Section 1 — Top 5 services by support case count

For multiple accounts, keep `Account` as a column. For a single account, drop the
column and state the account ID once above the table.

| Account | Service | Total cases | Critical-severity (open/total) | Resolution status |
|---|---|---|---|---|
| <account-id> | <service> | <n> | <open>/<total> | <e.g. 3 resolved, 2 open> |

**Critical-severity (high/urgent) cases** — list each individually; do not reduce to a count. If a top-5 service has none, say so.

- <service> / <account-id>: `<case-id>` — <subject> — <status>
- …

---

## Section 2 — Critical Trusted Advisor findings (status `error` only)

Only `status: error` (red) findings belong here. Never include `warning` or `ok`.

| Account | Check | Affected resources / regions | Why it's urgent |
|---|---|---|---|
| <account-id> | <check description> | <count + regions> | <impact> |

---

## Section 3 — Cross-reference overlap

Account/service pairs that appear in both Section 1 (top-5 volume) and Section 2
(critical TA finding), matched on the same account ID. If there is no overlap, state that.

- <account-id> — <service>: <top-5 support volume> + <related critical TA finding> → recurring operational risk
- …
