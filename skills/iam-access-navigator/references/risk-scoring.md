# Risk scoring and prioritization

Rank IAM identities so the user gets an ordered, defensible "fix this first" list
instead of an undifferentiated dump. **iam-access-navigator derives its own findings from
raw IAM + CloudTrail** — it does not depend on any external findings source. There
are three scoring lenses; they answer different questions and are not on one
shared scale.

## Deriving findings (no external findings source required)

Enumerate IAM directly and detect the risk signals yourself, per identity:

- **Roles** — `list-roles`; for each, read attached + inline policy documents
  (`list-attached-role-policies`, `list-role-policies`, `get-role-policy`,
  `get-policy` / `get-policy-version`), the trust policy
  (`AssumeRolePolicyDocument`), and usage (CloudTrail + `RoleLastUsed`).
- **Users** — `list-users`; attached/inline/group policies, access keys
  (`list-access-keys`, `get-access-key-last-used`), console login profile.
- **Policies** — `list-policies --scope Local`; attachment counts via
  `list-entities-for-policy` (feeds blast radius).

Signals to detect per identity (each becomes a self-derived "finding"):
- **admin / full-access** — inline `Action:*`, or a managed policy like
  `AdministratorAccess` / `*FullAccess` / `PowerUserAccess`
- **wildcard action** — `service:*` or `*`
- **broad resource** — `Resource:*` on sensitive actions
- **public trust** — role trust `Principal:"*"` (with/without condition)
- **cross-account trust** — external AWS account principal (with/without
  condition)
- **unused** — no CloudTrail activity in the window AND `RoleLastUsed` empty/old
  (see `least-privilege.md` for the session-name matching rule)
- **over-age / idle / never-used / multi-key** credentials (see `key-hygiene.md`)

## Lens A — Backlog of self-derived findings

Score each derived finding 0–100:

1. **Signal base** (in place of an external severity):
   - public trust → 40 (CRITICAL-class)
   - admin / full-access → 35
   - cross-account trust w/o condition → 30
   - wildcard action, or broad resource on sensitive action → 25
   - over-age or exposed credential → 20
   - unused role / idle key → 15
   - minor hygiene → 10
2. **Modifiers:**
   - unused **and** high-privilege → +15 (prime attack target; also a quick win
     to remove)
   - attached to many entities (> 5) → +15 (blast radius)
   - purely unused / idle with low privilege → mark **quick win**, effort
     *trivial*
3. Cap at 100.

**Risk-if-ignored** wording by score: ≥ 60 "expanded attack surface; potential
credential-compromise impact"; ≥ 40 "unnecessary permissions increase blast
radius"; else "minor hygiene issue; low immediate risk".

Order by score descending, number 1..N. Report the true total analyzed. Call out
**quick wins** (low effort, real risk reduction — typically unused/idle) as an
obvious starting point. Effort→time estimate: trivial 5 min, low 15, medium 30,
high 60. "High priority" ≈ score ≥ 70.

## Lens B — A single identity's risk (deep-dive on one finding)

Start from the identity's top signal base (above), then adjust:
- +20 public trust
- +10 cross-account / external
- +15 if an attached policy has many dependents (> 5) — high blast radius
- −10 if the role was **never used** (lower immediate impact, but see the
  high-privilege-unused modifier — don't net it to "safe")

Bands: ≥ 80 CRITICAL, ≥ 60 HIGH, ≥ 40 MEDIUM, else LOW. SLA: CRITICAL "immediate
action"; HIGH "within 7 days"; MEDIUM "within 30 days"; LOW "next security
sprint".

## Lens C — A role's intrinsic risk (for "compare these roles")

Score 0–100, record a human-readable reason per factor:
- admin / full-access policy → +30
- wildcard (`*`) action → +20
- more than 50 actions granted → +10
- inactive (no CloudTrail usage in window) → +20 (unused permissions are
  unnecessary attack surface)
- minimal activity → +10
- publicly assumable trust with no condition → +30
- cross-account trust with no condition → +15

Bands: ≥ 80 CRITICAL, ≥ 60 HIGH, ≥ 40 MEDIUM, else LOW.

## Optional enrichment (only if the account happens to run these)

iam-access-navigator needs neither, but if they're already present it will fold them in:

- **IAM Access Analyzer findings** — if analyzers exist, ingest their
  external-access findings (public / cross-account exposure confirmed by AWS's
  own reachability analysis) and, if an unused-access analyzer is configured,
  its unused-role / unused-permission / unused-key findings. These *corroborate*
  and add confidence to the signals iam-access-navigator already computes, and unused-
  access findings add AWS-side confirmation of idleness.
- **Security Hub findings** — if Security Hub aggregates IAM-related findings,
  ingest them for severity context and cross-control correlation.

When enrichment data is present, say so in the coverage statement ("corroborated
by Access Analyzer") and reconcile rather than double-count. When it is absent,
**do not treat that as a gap** — the self-derived analysis is the baseline, not a
fallback. Never imply the user needs to enable a service.

## Presentation rules

- Highest risk first, always.
- Never frame a risk result as an achievement. A "top roles by risk" table is a
  **warning list** — no trophy/celebration framing, no "winner". Name the column
  "Role of concern" and phrase each reason as *why it matters*.
- Separate "act now" (critical/high) from "plan" (medium/low).
- Legitimate priority signals: self-computed privilege (admin/wildcard/action
  count), trust exposure, observed CloudTrail usage, credential age/idleness,
  blast radius — plus enrichment findings when present. Don't invent others.
