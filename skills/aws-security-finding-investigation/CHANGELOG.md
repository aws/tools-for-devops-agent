# Changelog

## [1.0.0] - 2026-11-09

### Added

- Initial release: read-only investigation of AWS security findings from GuardDuty, Security
  Hub, CloudTrail-based alarms, and AWS Config rules.
- Six-step workflow following the detect, analyze, contain, eradicate and recover phases of the
  AWS Security Incident Response Guide and NIST SP 800-61:
  triage, investigate, determine, then recommended containment, eradication and recovery, and a
  report with a self-check.
- Seven investigation modes with signals, evidence to collect, and common misreadings:
  credential misuse, root activity, privilege escalation and persistence, defense evasion,
  exposure changes, data access, and compute compromise or destructive activity.
- Suggested P1 to P4 triage criteria adapted from the AWS incident response playbook samples,
  with the inputs a person confirms (business impact, data sensitivity).
- Read-only CloudTrail, S3 data event, AWS Config, and VPC Flow Logs queries, with coverage
  checks before results are read.
- Response catalog with exact AWS CLI commands, impact, undo, and approver for each action;
  evidence preservation always comes first and no command is run by the agent.
- Output by agent type: a report for chat, and the investigation's root cause, key findings,
  gaps and evidence sections for Incident RCA.
- Fallbacks when a read is denied: the CloudTrail event for the same fact, reported as such.
  Extra read permissions in the skill policies template (`EnableAwsSecurityFindingInvestigation`).
- CloudTrail management events through `lookup_cloudtrail_events`, with an error-handling table
  that separates runtime refusals from IAM gaps.
- S3 object reads counted only from data events delivered to CloudWatch Logs; otherwise Unknown.
- GuardDuty brute-force `ResourceRole` and the AWS compromised-key quarantine policy.
- Persistence and root rows of the triage table are this skill's own judgement; the rest follows
  the AWS incident response playbook samples.
- Containment for IAM Identity Center permission set roles (`AWSReservedSSO_*`), which IAM
  can't edit: a deny on `identitystore:userId`, removed assignments, ended sessions.
- `StartLogging` (and CloudTrail Lake ingestion events) in the logging checks, so a restarted
  trail closes the gap instead of leaving it open-ended.
- Evaluations in two kinds: chat questions about pasted records, and questions about real
  resources in the account (including a second Region); trigger queries include neighbouring
  skills that should not trigger.

### Changed before submission

- After the subject-matter expert review: session revocation is written after the source credential
  is cut off, uses a time about 30 seconds after now, and the deny is kept at least 36 hours for a
  user and for the role's `MaxSessionDuration` for a role; chained roles and roles in other accounts
  are revoked in the account that owns them; root temporary credentials are not limited by policy;
  flow log and data event coverage checks read the traffic type and the read/write type; more
  eradication rows (group membership, existing role and group policies, SAML providers, MFA
  devices, shared snapshots and images) and defense evasion events; a write command, the
  management account and identity source order for IAM Identity Center; and a verify step that
  checks the revoked sessions.
- Response commands come from `references/response-actions.md`. A command for an action the file
  does not list is labelled as not from the skill's command list, to check before running it.
- `ConsoleLogin` Regions follow the sign-in endpoint: root in us-east-1, us-east-2 or us-west-2; IAM user
  through the global endpoint in us-east-1, or in us-east-2, eu-north-1 or ap-southeast-2 with an
  account alias cookie; Regional endpoint in its own Region. Query a multi-Region trail once, or each
  Region, and name the Regions checked.
- The CloudTrail path depends on where the agent runs: in investigations (and their subagents)
  `use_aws` refuses CloudTrail operations, so events come from `lookup_cloudtrail_events` and trail
  settings from AWS Config and the logging events; in chat, `use_aws` CloudTrail calls work.
  Tests on 2026-11-08 and 2026-11-09 saw both behaviours. A refused call whose fact a fallback
  supplied is no longer listed as a gap.
- Security group connection tracking: untracked flows are TCP or UDP only, and connections
  through NAT gateways, Network Load Balancers, Global Accelerator and interface endpoints are
  always tracked.
- Reputation lookups send only public IP addresses and domains to a tool the organization
  approved, never account IDs, ARNs, key IDs or internal names.
- AWS Config history of a trail: `supplementaryConfiguration.isLogging` as of that item; the
  event selectors themselves are not in it.
- Cases that asked "according to the skill" were rewritten as scenarios, so a run without the
  skill can answer them too.
- The description asks the agent to load the skill for pasted records too, and names the
  questions users ask about containment and evidence counts, because chat runs often answered
  without loading it. It also names S3 object-read questions, "did anyone get in?" and
  SSHBruteForce, which chat runs answered without the skill.
- Every investigation finding starts with its state and suggested priority, because the
  investigation summary is built from the recorded findings and runs that kept the priority in
  their notes lost it. An exposure with no evidence of use still gets a state and a priority.
- A "can we close it?" answer lists the three Benign conditions: the approval source, the logs
  that must have been recording, and nothing else unusual. A note claiming approval is called a
  suspicious artifact.
