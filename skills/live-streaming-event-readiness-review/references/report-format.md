# LSE Readiness — report format (S6)

Render the entire review as **one Markdown message**, with these headings in this
exact order, none omitted. A section with nothing to report still appears with an
explicit `None` line.

1. `# Live Streaming Event Readiness Review — {event} ({date})`
2. `## 1. Executive summary` — readiness verdict (Ready / Ready-with-risks / Not
   ready), the top risks in viewer terms, the weeks-to-event framing, and a one-line
   **Coverage** note: which companion skills were available vs missing, and whether
   any pillar ran at reduced depth as a result.
3. `## 2. Event & architecture snapshot` — event context from S0 (date/window,
   expected peak concurrency, Regions, critical viewer path), the services
   discovered, and **any assumptions** made when context was not provided.
4. `## 3. Prioritized action plan` — every FAIL, Critical → Low, each mapped to its
   capacity-planning timeline milestone and (if close to the event) a day-of
   mitigation.
5. `## 4. Detailed findings` — one block per FAIL: evidence, impact in viewer terms,
   severity, remediation, authoritative AWS link.
6. `## 5. Scorecards` — list **every** canonical check for each in-scope pillar, by
   its exact `best-practices.md` ID (CAP1…CAP9, QTA1…QTA5, RES1…RES7, CDN1…CDN9,
   NET1…NET4, DAT1…DAT7, TST1…TST7, OBS1…OBS6, SUP1…SUP7), with verdict
   (PASS / FAIL / N/A), the severity assigned in `best-practices.md` for FAILs, and
   bounded evidence. Do not omit, renumber, re-bucket, or invent checks — an
   out-of-scope check is listed N/A with a reason. A missing or non-canonical ID is
   a defect.
7. `## 6. Capacity-planning timeline status` — the milestone table with each row
   marked done / at-risk / missed for this event.
8. `## 7. What was not assessed` — every N/A check with its exact reason, and a
   **Companion-skill coverage** list: each reuse skill, whether it was available and
   used this run, and for any missing companion the pillars assessed at reduced depth
   plus the install pointer (import the `skills/<name>` directory from
   `aws/tools-for-devops-agent`, or upload its zip).

End the message with this disclaimer verbatim:

> This review is AI-generated from read-only discovery and must be independently
> verified before you rely on it for an event. All remediations are proposals
> requiring human approval; this skill changes nothing.

Rules:
- One message, not split across turns; never drop, merge, reorder, or rename a section.
- Customer-facing text excludes internal tool names and employee aliases.
- Every FAIL in §4 must quote evidence, explain viewer impact, carry a severity, and
  link an authoritative AWS/Kubernetes source.
