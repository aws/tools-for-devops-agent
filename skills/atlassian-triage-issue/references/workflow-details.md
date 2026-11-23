# Workflow details and examples

### Step 6: Provide Summary

After taking action, confirm what was done.

#### If Comment Added:

```
✅ **Comment Added Successfully**

Added details to existing issue: **PROJ-456**
https://yoursite.atlassian.net/browse/PROJ-456

**What I included:**
- Your error details
- Environment context
- User impact information

**Next Steps:**
- The assignee (@john.doe) will be notified
- Monitor PROJ-456 for updates
- If this turns out to be different, we can still create a separate ticket
```

#### If New Issue Created:

```
✅ **New Issue Created**

**PROJ-890** - Mobile Login: Connection timeout during authentication
https://yoursite.atlassian.net/browse/PROJ-890

Type: Bug | Priority: Medium | Status: Open

**What's Included:**
- Complete error details and stack trace
- Environment and reproduction steps
- User impact assessment
- References to related issues (PROJ-123, PROJ-789)

**Next Steps:**
- Issue will be reviewed during next triage meeting
- Consider setting priority based on user impact
- Assign to appropriate team member
```

---

## Edge Cases & Troubleshooting

### Multiple Potential Duplicates

If you find 3+ very similar issues:

```
🔍 **Triage Results: Multiple Possible Duplicates**

I found 3 issues that might be related:

**Most Likely Duplicate:**
**PROJ-456** - [summary] (Open, 2 days ago)
Match: 95% - Same error and component

**Also Possibly Related:**
**PROJ-234** - [summary] (Open, 1 month ago)
Match: 70% - Similar symptoms, different error

**PROJ-123** - [summary] (Resolved, 8 months ago)
Match: 60% - Related component, but was fixed

**Recommendation:**
1. Add to PROJ-456 (most similar)
2. Reference PROJ-234 in your comment (might be related)
3. Note PROJ-123 was previously fixed (possible regression)

Which issue should I add your details to? (Or create new)
```

### Unclear Project Context

If user doesn't specify which project:

```
Which Jira project should I search for similar issues?

Available projects:
- BACKEND (Backend Services)
- MOBILE (Mobile Apps)
- WEB (Web Platform)
- INFRA (Infrastructure)

Or tell me the project key directly (e.g., BACKEND, MOBILE)
```

### Insufficient Information

If the bug report lacks critical details:

```
I need more information to effectively triage this issue:

**What I have:**
- Error: "Something went wrong"

**What would help:**
- Specific error message or code
- Which part of the system (login, payment, etc.)
- What the user was trying to do
- Which environment (production, staging, mobile, web)

Can you provide any of these details?
```

### Resolved Regression

If you find a resolved issue that matches:

```
🔍 **Triage Results: Possible Regression**

This looks like it might be a regression of a previously fixed issue:

**PROJ-567** - [Same issue description]
Status: Resolved (Fixed) | Fixed: 3 months ago | Fixed by: @jane.smith
Resolution: [Brief description of fix]
https://yoursite.atlassian.net/browse/PROJ-567

**This suggests:**
- The original fix may not have fully addressed the root cause
- OR there's been a regression in recent changes
- OR this is a different issue with similar symptoms

**Recommendation:** Create a new issue and link it to PROJ-567 as "may be related to" or "regression of"

Should I create a new issue with this context?
```

### Custom Required Fields

If creating an issue fails due to required fields:

1. **Check what fields are required.** `getJiraIssueTypeMetaWithFields` is not a primary tool, so
   run it through `execute`:
```
executeRead(   # or execute(...) if your client exposes a single execute tool
  name="getJiraIssueTypeMetaWithFields",
  cloudId="...",
  inputs={"projectIdOrKey": "PROJ", "issueTypeId": "10001"}
)
```

2. **Ask user for values:**
```
This project requires additional fields to create a Bug:
- Severity: [High/Medium/Low]
- Affected Version: [Version number]

Please provide these values so I can create the issue.
```

3. **Retry with additional fields:**
```
createJiraIssue(
  ...existing parameters...,
  priority="High",
  additional_fields={
    "customfield_10001": {"value": "Production"}
  }
)
```

---

## Tips for Effective Triage

### For Search:

**Do:**
✅ Use multiple search queries with different angles
✅ Include both open and resolved issues in search
✅ Search for error signatures and symptoms separately
✅ Look at recent issues first (last 30-90 days)
✅ Check for patterns (multiple reports of same thing)

**Don't:**
❌ Search with entire error messages (too specific)
❌ Only search open issues (miss fix history)
❌ Ignore resolved issues (miss regressions)
❌ Use too many keywords (reduces matches)

### For Issue Creation:

**Do:**
✅ Write clear, specific summaries with component names
✅ Include complete error messages in code blocks
✅ Add environment and impact details
✅ Reference related issues found during search
✅ Use "Bug" issue type for actual bugs

**Don't:**
❌ Create vague summaries like "Error in production"
❌ Paste entire stack traces in summary (use description)
❌ Skip reproduction steps
❌ Forget to mention user impact
❌ Hard-code issue type without checking availability

### For Duplicate Assessment:

**High Confidence Duplicates:**
- Exact same error + same component + recent (< 30 days)
- Same root cause identified

**Likely Different Issues:**
- Different error signatures
- Different components/systems
- Significantly different contexts

**When Unsure:**
- Present both options to user
- Lean toward creating new issue (can be closed as duplicate later)
- Linking issues is better than hiding information

---

## Examples

### Example 1: Clear Duplicate Found

**User Input:**
```
Triage this error: "Connection timeout error when users try to login on iOS app"
```

**Process:**
1. Extract: "Connection timeout", "login", "iOS"
2. Search: Find PROJ-456 (open, 2 days ago) with exact same error
3. Analyze: 95% match - same error, component, symptom
4. Present: Show PROJ-456 as duplicate, recommend adding comment
5. Execute: User confirms, add comment with iOS-specific details
6. Confirm: Comment added to PROJ-456

**Output:**
```
✅ Comment added to PROJ-456

Your iOS-specific error details have been added to the existing issue.
The assignee will be notified.
```

### Example 2: New Issue with Related Context

**User Input:**
```
Error: NullPointerException in PaymentProcessor.processRefund() at line 245
Stack trace: [full stack trace]
```

**Process:**
1. Extract: "NullPointerException", "PaymentProcessor", "processRefund", "line 245"
2. Search: Find PROJ-789 (resolved, 3 weeks ago) about payment errors, but different line
3. Analyze: Related component but different specific error
4. Present: No duplicates, found related issue, recommend new ticket
5. Execute: User confirms, create new Bug with context
6. Confirm: PROJ-890 created

**Output:**
```
✅ New Issue Created

PROJ-890 - Payment API: NullPointerException in refund processing
https://yoursite.atlassian.net/browse/PROJ-890

References related issue PROJ-789 for context.
```

### Example 3: Possible Regression

**User Input:**
```
Users can't upload files larger than 5MB, getting "Upload failed" error
```

**Process:**
1. Extract: "Upload failed", "5MB", "file upload"
2. Search: Find PROJ-234 (resolved 2 months ago) - exact same issue
3. Analyze: Was fixed but now happening again
4. Present: Possible regression, recommend new issue linked to old one
5. Execute: Create new issue, link to PROJ-234 as "may be caused by"
6. Confirm: PROJ-891 created with regression context

**Output:**
```
✅ New Issue Created (Possible Regression)

PROJ-891 - File Upload: Upload failed for files >5MB (Regression?)
https://yoursite.atlassian.net/browse/PROJ-891

This may be a regression of PROJ-234, which was resolved 2 months ago.
Issue includes reference to original fix for investigation.
```

---

## When NOT to Use This Skill

This skill is for **triaging bugs and errors only**. Do NOT use for:

❌ Feature requests (use atlassian-spec-to-backlog)
❌ General task creation (use atlassian-capture-tasks-from-meeting-notes)
❌ Searching for information (use atlassian-search-company-knowledge)
❌ Generating status reports (use atlassian-generate-status-report)

**Use this skill specifically for:**
✅ "Is this a duplicate bug?"
✅ "Triage this error message"
✅ "Has this been reported before?"
✅ "Create a bug ticket for this"

---

## Quick Reference

**Primary workflow:** Extract → Search → Analyze → Present → Execute → Confirm

**Search tool:** `searchJiraIssuesUsingJql(cloudId, jql, fields, maxResults)`

**Action tools:**
- `addOrEditJiraIssueComment(cloudId, issueIdOrKey, commentBody)` - Add to existing
- `createJiraIssue(cloudId, projectKey, issueType, summary, description)` - Create new

**Issue type:** Always prefer "Bug" for error reports, check with
`executeRead(name="listJiraProjectIssueTypesMetadata", ...)` (not a primary tool)

**Remember:**
- Multiple searches catch more duplicates
- Present findings before acting
- Include error details and context
- Reference related issues
- Use "Bug" issue type when available

---
