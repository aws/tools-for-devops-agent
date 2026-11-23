# Workflow details and examples

## Edge Cases & Troubleshooting

### Multiple Specs or Pages

**If user references multiple Confluence pages:**
- Process each separately, or ask which to prioritize
- Consider creating separate Epics for distinct features
- "I see you've provided 3 spec pages. Should I create separate Epics for each, or would you like me to focus on one first?"

### Existing Epic

**If user wants to add tickets to an existing Epic:**
- Skip Epic creation (Step 5)
- Ask for the existing Epic key: "What's the Epic key you'd like to add tickets to? (e.g., PROJ-100)"
- Proceed with Step 6 using the provided Epic key

### Custom Required Fields

**If ticket creation fails due to required fields:**
1. Use `getJiraIssueTypeMetaWithFields` to identify what fields are required. It is not a primary
   tool, so run it through `execute`:
   ```
   executeRead(   # or execute(...) if your client exposes a single execute tool
     name="getJiraIssueTypeMetaWithFields",
     cloudId="...",
     inputs={"projectIdOrKey": "PROJ", "issueTypeId": "10001"}
   )
   ```

2. Ask user for values: "This project requires a 'Priority' field. What priority should I use? (e.g., High, Medium, Low)"

3. Pass native parameters directly — `priority` is a top-level string, not an
   `additional_fields` entry. Reserve `additional_fields` for custom fields:
   ```
   priority="High",
   additional_fields={"customfield_10001": {"value": "Production"}}
   ```

### Large Specifications

**For specs that would generate 15+ tickets:**
- Present the full breakdown to user
- Ask: "This spec would create 18 tickets. Should I create all of them, or would you like to adjust the scope?"
- Offer to create a subset first: "I can create the first 10 tickets now and wait for your feedback before creating the rest."

### Subtasks vs Tasks

**Some projects use "Subtask" issue types:**
- If metadata shows "Subtask" is available, you can use it for more granular work
- Subtasks link to parent tasks (not Epics directly)
- Structure: Epic → Task → Subtasks

### Ambiguous Specifications

**If the Confluence page lacks detail:**
- Create fewer, broader tickets
- Note in ticket descriptions: "Detailed requirements need to be defined during refinement"
- Ask user: "The spec is light on implementation details. Should I create high-level tickets that can be refined later?"

### Failed API Calls

**If `createJiraIssue` fails:**
1. Check the error message for specific issues (permissions, required fields, invalid values)
2. Use `executeRead(name="listJiraProjectIssueTypesMetadata", ...)` to verify issue type availability
3. Inform user: "I encountered an error creating tickets: [error message]. This might be due to project permissions or required fields."

---

## Tips for High-Quality Breakdowns

### Be Specific
- ❌ "Do frontend work"
- ✅ "Create login form UI with email/password inputs and validation"

### Include Technical Context
- Mention specific technologies when clear from spec
- Reference components, services, or modules
- Note integration points

### Logical Grouping
- Related work stays in the same ticket
- Don't split artificially: "Build user profile page" includes both UI and API integration
- Do split when different specialties: Separate backend API task from frontend UI task if worked on by different people

### Avoid Duplication
- Don't create redundant tickets for the same functionality
- If multiple features need the same infrastructure, create one infrastructure ticket they all depend on

### Explicit Testing
- Include testing as part of feature tasks ("Implement X with unit tests")
- OR create separate testing tasks for complex features ("Write integration tests for authentication flow")

### Documentation Tasks
- For user-facing features: Include "Update user documentation" or "Create help articles"
- For developer tools: Include "Update API documentation" or "Write integration guide"

### Dependencies
- Note prerequisites in ticket descriptions
- Use "Depends on" or "Blocks" relationships in Jira if available
- Sequence tickets logically (infrastructure → implementation → testing)

---

## Examples of Good Breakdowns

### Example 1: New Feature - Search Functionality

**Epic:** Product Search and Filtering

**Tickets:**
1. [Task] Design search index schema and data structure
2. [Task] Implement backend search API with Elasticsearch
3. [Story] Build search input and results UI components
4. [Story] Add advanced filtering (price, category, ratings)
5. [Story] Implement search suggestions and autocomplete
6. [Task] Optimize search performance and add caching
7. [Task] Write search integration tests and documentation

### Example 2: Bug Fix - Performance Issue

**Epic:** Resolve Dashboard Load Time Issues

**Tickets:**
1. [Task] Profile and identify performance bottlenecks
2. [Bug] Optimize database queries with indexes and caching
3. [Bug] Implement lazy loading for dashboard widgets
4. [Bug] Add pagination to large data tables
5. [Task] Set up performance monitoring and alerts

### Example 3: Infrastructure - CI/CD Pipeline

**Epic:** Automated Deployment Pipeline

**Tickets:**
1. [Task] Set up GitHub Actions workflow configuration
2. [Task] Implement automated testing in CI pipeline
3. [Task] Configure staging environment deployment
4. [Task] Implement blue-green production deployment
5. [Task] Add deployment rollback mechanism
6. [Task] Create deployment runbook and documentation


---
