# Standing prompt — proactive access-key rotation sweep

Paste this as the **user prompt** on a schedule trigger for the iam-access-navigator
custom agent (Triggers tab → Schedule → User prompt field). It triggers the agent's
existing access-key hygiene capability (SKILL.md Capability 5) on a cadence — no new
reasoning, same remediation output.

Recommended cadences:
- Normal rotation sweep: `rate(7 days)`
- "Notify ASAP on regression" opt-in: `rate(1 day)` (a daily sweep catches regressions
  within a day — no EventBridge/event-trigger plumbing needed for v1).

---

Run an access-key hygiene sweep across all IAM users in this account. This is a scheduled, proactive run — not a tour, not a full audit. Scope to access-key hygiene: rotation-due keys (the primary purpose) PLUS directly-adjacent key-risk conditions that your access-key hygiene capability already detects — specifically multiple simultaneously-active keys on one user, and never-used keys. Do NOT expand beyond key hygiene into general IAM risk (no role triage, blast radius, policy analysis, etc.) — those are out of scope for this proactive sweep.

For each active access key, determine whether it is due for rotation:
1. If the key's owning user or the key has an explicit rotation policy — a rotation-date tag, or a Secrets Manager native rotation schedule covering it — use that policy's due date.
2. If no rotation policy exists, fall back to age since the key's CreateDate (IAM has no native key-expiry field). Treat a key older than 90 days as due, and flag keys approaching that (75+ days) as upcoming.

For every key that is due (or overdue), AND for any user with multiple simultaneously-active keys or a never-used key, emit the standard remediation from your access-key hygiene capability, in priority order: rotate, or migrate the credential off a long-lived key (human → SSO federation; CI/CD → OIDC; service → IAM role or Secrets Manager with native rotation), using the deactivate → monitor a full business cycle → delete ladder. For a multiple-active-keys finding, the remediation is to consolidate to a single active key (deactivate → monitor → remove the extra). Advisory language only; read-only; never apply a change.

Output handling:
- Create a recommendation on the Improvements page for each actionable finding — rotation-due/overdue keys, multiple-active-key users, and never-used keys — title names the user and key, summary gives the age/policy status (or the hygiene condition) and the recommended remediation. These persist and are trackable through the remediation lifecycle.
- **Reconcile against existing recommendations before creating new ones (idempotency — this matters because this sweep recurs).** For each finding, check whether an open recommendation already exists for the same user+key. Decide per finding:
  - **Match** — an existing open recommendation describes the SAME condition for that key (e.g. a "never-used key" finding and an existing "never-used key" recommendation for that exact key). Do not create a duplicate; treat it as already covered. Note it as "already tracked" in the notification.
  - **Mismatch** — an existing recommendation for that key describes a DIFFERENT condition than the current finding (e.g. an existing "rotation due in 7 days" rec but the current finding is "never used"). Do NOT treat the stale rec as coverage. Create a new recommendation for the actual current condition, and in its summary reference the prior mismatched rec by title and recommend that a human review and close it as stale. Phrase this as a recommendation FOR THE OPERATOR, never as an action you will take or are taking — you are read-only and cannot and do not close, supersede, modify, or delete any recommendation yourself. Say "the prior rec '<title>' no longer matches current state; recommend closing it" — do NOT say it "is superseded" or "will be closed as part of this operation," which implies you acted. Never let a non-matching existing row suppress a real, differently-conditioned finding.
  - **No existing rec** — create a new recommendation normally.
  Judge "same condition" by the finding type (rotation-due vs. multiple-active-keys vs. never-used) and the specific key, not merely by the user or the presence of any row. When in doubt, create the current-condition recommendation rather than silently relying on a possibly-stale one.
- Send one short notification summarizing how many keys are due and the single highest-priority one, plus counts of findings that were already tracked (matched) vs. newly created vs. flagged-a-stale-rec-for-the-operator-to-close. Use that last phrasing ("stale rec flagged for closure"), not "superseded" — you do not supersede or close recs yourself.
- If no key is due AND no adjacent hygiene finding exists, send one short notification saying the sweep ran clean and create no recommendations. Do not fabricate findings to look useful.

End with the standard coverage statement (what you checked, what was empty, what was unavailable). This sweep needs `iam:ListAccessKeys` and `iam:GetAccessKeyLastUsed`; if either was denied, include one coverage line naming the denied action and what it left unknown (e.g. "`iam:GetAccessKeyLastUsed` denied: last-used dates unknown, never-used and idle checks skipped"), and do not report "all clear." If a user may send mail over SES SMTP, note that rotating or deactivating their key breaks SMTP until new SMTP credentials are generated.
