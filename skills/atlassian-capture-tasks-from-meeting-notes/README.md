# atlassian-capture-tasks-from-meeting-notes

Turn meeting action items into Jira tasks with resolved assignees.

## Prerequisites and setup

Connect the `atlassian` connector to an authorized Atlassian Cloud site, enable the
tools needed for this workflow, and install this skill. It uses the customer's
Atlassian permissions and tool approvals. No additional AWS IAM permissions or
infrastructure are required by this skill.

Read operations search or fetch authorized Atlassian data. Any Jira creation,
commenting or Confluence publication described by the workflow requires the user's
explicit request and review of the proposed change. Tool availability depends on
authentication, scopes, product access and organization policies.

## Example

Ask: "Review these meeting notes and propose follow-up Jira tasks in project DEMO."

## Source and maintenance

Adapted from [Atlassian's v2 skill](https://github.com/atlassian/atlassian-mcp-server/tree/352a02b05189e2a958a973867cc6eca365cb8fc3/skills/capture-tasks-from-meeting-notes) at commit `352a02b05189e2a958a973867cc6eca365cb8fc3`.
Upstream is Apache-2.0 licensed; see [its license](https://github.com/atlassian/atlassian-mcp-server/blob/352a02b05189e2a958a973867cc6eca365cb8fc3/LICENSE).
The AWS adaptation adds product-prefixed identity, publishing metadata, tool-routing
guidance, approval and data-handling rules, and on-demand references. It excludes
all archived `skills/v1/` material and executable helpers. Maintainer: `sbourkeatlassian`.

This is sample guidance. Validate it with non-production data before production use
and review the enabled tool permissions and approval settings.
