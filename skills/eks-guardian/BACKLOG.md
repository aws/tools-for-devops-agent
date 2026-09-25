# EKS Guardian — Backlog

Future capabilities planned for the EKS Guardian skill.

## v1.1 — Remediation Tools (MCP Server)

- [ ] Connect EKS Guardian remediation MCP server to the DevOps Agent Space
- [ ] Enable Terraform-based auto-fix for findings (VPC flow logs, control plane logging, ECR immutable tags, network policies, HPAs, pod security patches, resource limits)
- [ ] Add `terraform plan` preview before applying changes
- [ ] Add rollback capability for applied remediations
- [ ] Skill instructions updated to offer remediation after assessment

## v1.2 — Jira/Ticketing Integration

- [ ] Create Jira bugs automatically from CRITICAL/HIGH findings
- [ ] AI-enriched Jira descriptions with context from the assessment
- [ ] Link findings to existing Jira epics/projects
- [ ] Track remediation status via ticket updates

## v1.3 — Multi-Account Cross-Cluster Comparison

> Note: Same-account multi-cluster comparison, drift detection, delta/trend analysis, and
> compliance mapping shipped in v1.0.0 (SKILL.md Steps 7, 8, 11, 12, 22). Remaining work below.

- [ ] Cross-account fleet-wide report (aggregate view)
- [ ] Identify common issues across the fleet at scale (10+ clusters)

## v1.4 — Persistent Finding Storage

- [ ] Store findings in DynamoDB for historical tracking
- [ ] Finding status lifecycle (open → in-progress → resolved → regressed)
- [ ] Drift detection: alert when a previously-fixed finding reappears
- [ ] API for querying historical findings

## v1.5 — Scheduled Reviews

- [ ] Proactive/scheduled reviews (weekly, monthly)
- [ ] Automated report generation and delivery (email/Slack)
- [ ] Delta reports: only show changes since last review
- [ ] SLA tracking: flag overdue CRITICAL/HIGH findings

## v1.6 — Live Dashboard

- [ ] Real-time web dashboard for findings
- [ ] Cluster health overview with drill-down
- [ ] Remediation status tracking
- [ ] Integration with CloudWatch dashboards

## Ideas (Unscheduled)

- [ ] Custom check authoring: let users define their own best-practice rules
- [ ] Cost savings calculator: estimate $ impact of cost optimization findings
- [ ] Slack/Teams notifications for new CRITICAL findings
- [ ] Integration with AWS Security Hub for centralized finding aggregation
