# Operational Review Report Template

Load this when generating the report (Step 3). Produce a single Markdown report titled
**"Amazon FSx for NetApp ONTAP Operational Review"** with the structure below.

```markdown
# Amazon FSx for NetApp ONTAP Operational Review

**Account IDs:** <comma-separated account IDs>
**File System IDs:** <comma-separated fs-... IDs>
**Regions:** <comma-separated regions>
**Date Range:** <range or "Point-in-time (YYYY-MM-DD)">

> **AI Disclaimer:** The AI-generated insights in this report are provided for informational purposes only. They should be reviewed and validated by qualified personnel before taking any action. AWS is not responsible for any decisions made based on AI-generated content.

## Executive Summary

<severity-ranked roll-up across all pillars: count by severity (Critical / High / Medium / Low), then
the Critical, High, and Medium findings listed most-severe first, each with its one-line
recommendation. Also report per-pillar pass/warning/fail counts. Omit only if there are no findings at
all.>

## <Pillar Name>

### <Check ID — Check Name>

**Guidance**

<what the check evaluates and the relevant FSxN best practice>

**AI Insights**

<optional per-check analysis of the gathered data; prefix with a note that it is AI-generated and must be verified. Omit if not generated.>

**Data**

<a Markdown table of the check's result rows (fields per the pillar's references/<pillar>-checks.md, including a `status` and `severity` column where the check defines one), or "No data available for this check.">

**Recommendations**

<one concrete FSxN-specific recommendation per Critical/High/Medium finding in this check, each labelled with its severity. Omit this block entirely if the check has no Critical/High/Medium findings.>
```

## Report rules

- Emit the **AI Disclaimer blockquote verbatim**, immediately after the header.
- One `##` section per **in-scope pillar**, in the pillar order from SKILL.md; one `###` sub-section per
  check in that pillar. Include every in-scope check even when it found nothing (render its empty-state
  row).
- The **Executive Summary** ranks findings by severity (Critical → High → Medium → Low) and must contain
  **every Critical, High, and Medium finding from every pillar**; its severity counts must reconcile
  exactly with the per-check sections.
- Render each check's **Data** as a table of the fields defined in the pillar's `references/<pillar>-checks.md`,
  including the `status` and `severity` fields for checks that define them, and the observed value(s)
  each result is based on.
- Emit a **Recommendations** block for every check with at least one Critical/High/Medium finding —
  exactly one recommendation per such finding. Skip the block for checks with only Low/Informational
  findings.
- Empty-scope precedence: if **every** in-scope check across **all** in-scope accounts/file
  systems/regions returns no resources, skip the per-pillar report and instead emit the single line
  "No FSx for NetApp ONTAP activity detected."
