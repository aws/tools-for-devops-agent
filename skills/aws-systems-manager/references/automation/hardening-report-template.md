# Report template

Use this structure for the hardening report. Keep every section, in this order. Write "None" under a section with nothing to report.

```markdown
## Runbook hardening report: <document name>
Format: <YAML | JSON>   Schema: 0.3   Steps: <n>   Parameters: <n>

| Severity | Found | Applied | Proposed | Flagged |
|---|---|---|---|---|

### Applied fixes
- <parameter or step>: <change> (source: <page>)

### Proposed fixes
PROPOSED FIX: <title>
ISSUE: <what is wrong and why>
BEFORE: <excerpt>
AFTER: <excerpt>
SOURCE: <page>

### Flagged for redesign
- <issue>, <what a redesign must address>

### Checks with no findings
- <check numbers>

### Not covered by this review
- The IAM policy of the assume role
- Any Command document the runbook calls, beyond how parameters are passed to it

### Hardened document
<the complete document with applied and proposed fixes, same format as the input>
```
