# Identity hygiene / key lifecycle

Review access keys and long-lived credentials, classify who they belong to, and
recommend a safe migration. Read-only: list keys, their metadata, last-used, and
the identity's effective permissions.

**Permissions this capability needs:** `iam:ListUsers`, `iam:ListAccessKeys`
(key IDs, status, create date) and `iam:GetAccessKeyLastUsed` (last-used date).
The AWS managed DevOps Agent policies may not include the last two. If either
call is denied, report it in one coverage line that names the action, e.g.
"Could not read key last-used dates: `iam:GetAccessKeyLastUsed` was denied, so
NEVER_USED / IDLE flags are unknown (LASTUSED_UNKNOWN)." If `iam:ListAccessKeys`
is denied you have no key inventory: say so and do not report the sweep as
clean.

## Identity classification (first match wins, in this order)
1. **Human** — username contains `@`, or a `first.last` / `first_last` pattern.
   → recommend **SSO / federation** (stop issuing humans long-lived keys).
2. **CI/CD** — username contains `-ci-`, `-cicd-`, `-deployer-`,
   `-github-actions-`, `-gitlab-`, `-jenkins-`, or boundary variants.
   → recommend **OIDC federation**. (Checked before "service" so
   `svc-deployer-ci` maps to OIDC, not a plain IAM role.)
3. **Service** — `svc-`, `service-`, `-lambda-`, `-eks-`, `-ecs-`, `-ec2-`,
   `-runner`, `-worker`, `-agent`, etc.
   → recommend an **IAM role** (instance/task/execution role).
4. **No match** → **cross-account role with external ID** as a *safe
   placeholder, investigate first* — not a settled recommendation.
5. **Root** overrides everything → **remove root access keys** (always
   critical). Root is not in `ListUsers`; detect via account summary
   (`AccountAccessKeysPresent`).

Match the identity signal **anywhere** in the name (real names carry env/team
prefixes and suffixes); use word boundaries, never whole-string anchors.

## Risk flags (fixed order)
- **ADMIN** — inline `Action: *` or managed `AdministratorAccess`
- **BROAD:<policy>** — any broad managed policy (e.g. `*FullAccess`,
  `PowerUserAccess`, `IAMFullAccess`, `ReadOnlyAccess`)
- **SERVICE_WILDCARD:<svc>** — inline `svc:*`
- **RESOURCE_WILDCARD** — Allow on `Resource: *`
- **KEY_AGE_<n>d** — key age ≥ 365 days (over-age)
- usage (one of): **LASTUSED_UNKNOWN** (lookup failed — replaces the usage
  flags, never joins them) / **NEVER_USED** (no last-used date) /
  **IDLE_<n>d** (idle > 90 days)
- **MULTI_ACTIVE_KEYS** — the user has ≥ 2 active keys

If effective-permission resolution fails, keep the age/usage/multi-key flags but
**drop** the permission-derived flags (ADMIN/BROAD/WILDCARD) — never claim admin
without the data to back it.

## Priority ladder
Root → **Critical**. ADMIN (with or without stale) → **Critical**. BROAD or
SERVICE_WILDCARD → **High**. never-used / idle only → **Cleanup**. age /
multi-key only → **Rotation**. Default **Rotation**. Sort Critical → High →
Cleanup → Rotation, then by descending key age.

## Migration recommendations
Give the *what*, not brittle CLI (docs cover the *how*). Every migration ends the
same way: **deactivate → monitor a full business cycle → delete**. Never a bare
delete of a key that might back a rare-but-critical job.

**SMTP-rotation warning.** If the user may send email through the Amazon SES
SMTP interface (SES permissions such as `ses:SendRawEmail`, or a name or tag
that suggests mail), say so before any rotate or deactivate step: SES SMTP
credentials are derived from the access key, so rotating or deactivating the key
breaks SMTP sending until new SMTP credentials are generated from the new key
and deployed to the mail client. Include that step in the migration plan, and
treat the "monitor" window as covering mail delivery too.

Always attach the usage-lag caveat: last-used data can lag by hours, and a
low-frequency workload may back a rare-but-critical job that looks idle — verify
with the resource owner before deactivating. Extend it when it applies:
- **S3 object activity.** S3 object calls are CloudTrail *data events*, which
  are off by default and never appear in `LookupEvents`. Any CloudTrail-based
  view of what a key did will miss them. Whether the key's last-used date
  (`GetAccessKeyLastUsed`) reflects S3 object calls is **not verified** by this
  skill; if the user has S3 object permissions, say a NEVER_USED or IDLE flag
  may not account for S3 object use.
- **SES SMTP sends** are not logged in CloudTrail at all. Whether the key's
  last-used date reflects SMTP sends is **not verified**; if the user may send
  mail over SMTP, say a NEVER_USED or IDLE flag may not account for it.
In both cases keep the flag, lower your confidence, and ask the owner to confirm
before any deactivation.

## Tone
Advisory, not imperative: "candidate for rotation", "recommend reviewing",
"consider federating" — never "delete this key". Present rows in priority order
with the identity classification and the flags that drove it.
