# Unlisted Symptoms

**Sources:** public AWS FSx for NetApp ONTAP documentation (`docs.aws.amazon.com`) and live validation. Read-only, control-plane.


Use this path when the reported symptom matches no row in the Step 3 routing
table and none of SKILL.md Step 3 items 1–11 (for example: an unfamiliar
error string, an intermittent issue with no metric signature, or a feature
behaving unexpectedly). The goal is an honest, evidence-led report — not a
best guess dressed up as a root cause.

1. **Confirm it is in scope.** It must involve an FSx for NetApp ONTAP file
   system. If it is really FSx for Windows / Lustre / OpenZFS, EFS, or a
   client-application problem, say so and stop.
2. **Run the baseline anyway.** Complete SKILL.md Step 2 collection and the §9
   baseline checks. An unlisted symptom is often a listed failure mode
   described in unfamiliar words (e.g. "files disappear" can be §1 capacity or
   §4 tiering).
3. **Correlate in time.** Anchor on when the symptom started. Look for, in
   order: an AWS Health event (`dependencies-and-errors.md`), a configuration change
   in CloudTrail — FSx **and** dependency events (`cloudtrail-audit.md`) — and a
   metric step-change in the same window.
4. **Walk the Service Dependency Map** (`dependencies-and-errors.md`) for any dependency the symptom could
   plausibly touch.
5. **Check product gaps** (review-checks.md, analysis rule 4) — the "issue" may be an
   unsupported feature, not a fault.
6. **Report it as "No matching playbook."** In the Findings table:
   - present only observed evidence, each item with its source API/metric;
   - label every causal explanation as a **hypothesis (unverified)** and state
     the evidence that would confirm or refute it;
   - cite a `docs.aws.amazon.com` page for any claim about FSx behavior; if
     no public source exists, say so rather than asserting it;
   - assign severity from **observed impact only** (review-checks.md, Severity definitions); if
     impact is unknown, use INFO or MEDIUM and state the assumption.
7. **Name the data gap.** If answering needs ONTAP CLI / REST (EMS events,
   export policies, share ACLs, volume-level state), follow **When ONTAP CLI
   Is Required** and hand over the `ontap-cli-pack.md` command pack.
8. **Include the escalation-readiness packet** (§10) with category `Other`,
   pre-filled with the evidence and timeline gathered above — an unresolved,
   unexplained symptom is the case AWS Support is for.

Never fall back on general ONTAP knowledge to fill a gap without saying so,
and never invent thresholds, error-code meanings, or API behavior.

