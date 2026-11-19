# Forensics / backwards-troubleshooting

Work backwards from an IAM symptom to the change that caused it, and prescribe a
safe fix. Read-only throughout: this is CloudTrail reconstruction and
correlation, not remediation.

This is the most novel capability and the one most likely to be imperfect. Its
value depends entirely on being **honest about confidence** — a change that
happened before a failure is a *candidate* cause, not a proven one.

## Two modes

### Mode A — Tight loop (a change this skill recommended broke something)
You already have the pre-change snapshot and rollback plan (see `rollback.md`).
1. Confirm the symptom is real and recent (find the `AccessDenied` /
   `UnauthorizedOperation` / failed `AssumeRole` in CloudTrail).
2. Map the denied action to the permission the change removed.
3. Walk the reversal steps from the rollback plan.
This is high-confidence by construction: you know exactly what changed.

### Mode B — Broad (an out-of-band change by someone else)
1. **Establish the symptom.** Find the failing events in CloudTrail: the
   principal, the action denied, the resource, and the **first** occurrence
   (the timestamp matters more than the count).
2. **Reconstruct IAM changes** in a window *before* the first failure. Look for
   the management events in the catalog below, on the roles/policies/users tied
   to the failing principal.
3. **Correlate** — see the confidence rubric.
4. **Prescribe** the fix, and pair it with a rollback plan for the fix itself.

## CloudTrail IAM change-event catalog
Management events that change authorization (source `iam.amazonaws.com` unless
noted):
- Trust policy: `UpdateAssumeRolePolicy`
- Inline role policy: `PutRolePolicy`, `DeleteRolePolicy`
- Managed attachment: `AttachRolePolicy`, `DetachRolePolicy`,
  `AttachUserPolicy`, `DetachUserPolicy`, `AttachGroupPolicy`,
  `DetachGroupPolicy`
- Managed policy versions: `CreatePolicyVersion`, `SetDefaultPolicyVersion`,
  `DeletePolicyVersion`
- Identity lifecycle: `CreateRole`, `DeleteRole`, `CreateUser`, `DeleteUser`,
  `CreatePolicy`, `DeletePolicy`
- Permissions boundary: `PutRolePermissionsBoundary`,
  `DeleteRolePermissionsBoundary`, `PutUserPermissionsBoundary`
- Credentials: `UpdateAccessKey` (Active↔Inactive), `DeleteAccessKey`,
  `CreateAccessKey`
- SCP / org (source `organizations.amazonaws.com`): `AttachPolicy`,
  `DetachPolicy`, `UpdatePolicy` — an org-level deny can cause a symptom with no
  account-local IAM change at all; consider it when the local timeline shows
  nothing.

For each candidate change capture: `eventTime`, `eventName`,
`userIdentity` (who), the affected resource, and the request parameters
(what changed).

## Confidence rubric
State a level and what it rests on. Do not present coincidence as causation.

- **High** — timeline fits (change strictly precedes the first failure), the
  affected principal matches the changed identity, and the denied action maps
  directly to the permission that was removed/denied. Offer the confirming test
  anyway.
- **Medium** — timeline and principal fit, but the action→permission mapping is
  indirect (e.g. a boundary or SCP narrowed it) or more than one change could
  explain it.
- **Low** — timing is suggestive but the principal or action doesn't cleanly
  line up, the window is noisy, or CloudTrail coverage is partial.
- **Insufficient** — CloudTrail is unavailable/lacks history for the window, or
  no candidate change is visible. Say so plainly and say what would be needed
  (a longer trail, CloudTrail Lake / Athena history — see the data-horizon note).

Always give the **confirming test**: the specific thing that would raise
confidence — e.g. "re-add just `s3:GetObject` on `bucket-X` and retry; if the
denial clears, this change is confirmed as the cause."

## Data-horizon note (why this may want an MCP server)
CloudTrail `LookupEvents` covers ~90 days of management events, page by page —
fine for recent incidents. A broad forensic reconstruction over a longer horizon,
or high-volume correlation, wants **CloudTrail Lake** or **Athena over an S3
trail** queried in bulk. That long-horizon, high-volume query path is the part
of this skill that would justify a companion MCP server (data-plane access);
the reasoning in this file stays in the skill. See the README's "Skill vs MCP"
note. Be explicit with the user when you have hit the `LookupEvents` horizon
rather than silently truncating.
