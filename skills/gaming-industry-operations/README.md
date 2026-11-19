# Gaming Industry Skill (`gaming-industry-operations`)

A games-industry operations skill for AWS DevOps Agent, grounded in the
[Games Industry Lens — AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/games-industry-lens/games-industry-lens.html)
(publication date December 9, 2025).

## Purpose

Games fail in ways generic cloud reviews and investigations miss: a fleet that scales
in while players are mid-match, a matchmaker whose latency rules exclude the only
Region with capacity, a login storm that throttles Cognito and DynamoDB at season
launch, packet loss on game servers that look healthy on CPU because they hit an EC2
network allowance, Spot interruptions on the ranked-mode fleet. This skill gives the
agent the lens's 78 best practices and the games-specific failure modes so it can:

- run a **read-only, graded review** of a game workload and produce a prioritized,
  player-impact-ranked remediation plan, including launch and in-game event readiness;
- bring **games context to incident triage and RCA**: player-impact framing, a
  symptom → cause → evidence map, and prevention advice that cites the lens.

## Key capabilities

- Grades **all 78 lens best practices** by their published IDs across the six pillars:
  Operational excellence (GAMEOPS, 12), Security (GAMESEC, 25), Reliability
  (GAMEREL, 6), Performance efficiency (GAMEPERF, 24), Cost optimization
  (GAMECOST, 7) and Sustainability (GAMESUS, 4), with PASS / FAIL / N/A verdicts and
  the lens's own risk levels.
- Recognizes the lens scenarios from observed resources: real-time game hosting on
  Amazon GameLift, EC2, EKS or ECS; container and serverless game backends; cloud
  game development (CI/CD, virtual workstations); game analytics pipelines.
- Launch and in-game event readiness: pre-scaling, quotas, load testing, deployment
  safety, matchmaking validation, DDoS protection, status page and AWS Countdown.
- Incident symptom map for login storms, matchmaking failures and placement
  capacity, mid-match disconnects, regional lag, launch meltdowns, cheating and
  account-takeover waves, and post-event cost spikes, each with the CloudWatch
  metrics and API reads that confirm or rule out the cause.
- Reuse-first: folds in `service-quota-check`, `aws-health-events`,
  `aws-eks-operations-review`, `ecs-operation-review`, `rds-operation-review`,
  `storage-s3-resiliency-expertise` and `support-cases` when they are installed.

## Prerequisites

- An AWS DevOps Agent Agent Space with the AWS account(s) that host the game
  associated.
- The DevOps Agent role with the `AIDevOpsAgentAccessPolicy` managed policy. The
  reads this skill uses (`gamelift:Describe*`/`List*`, `globalaccelerator`,
  `cognito-idp`, `cognito-identity`, `shield`, `wafv2`, `cloudfront`, `dynamodb`,
  `autoscaling`, `ec2`, `eks`, `ecs`, `lambda`, `elasticache`, `rds`, `route53`,
  `cloudwatch`, `logs`, `synthetics`, `kinesis`, `ce`, `servicequotas`, `health`,
  `guardduty`, `securityhub`, `iam` read-only) are already granted by that policy;
  **no custom IAM policy is required.** Reads the policy may not include
  (AWS Organizations, AWS Control Tower, AWS Compute Optimizer) degrade to N/A with a
  reason rather than failing the review.
- Optional companion skills listed above for deeper per-service grading.
- For `aws-health-events` and `support-cases` companions, a Business or Enterprise
  Support plan.

## Limitations

- Read-only: the skill proposes remediations and never changes fleets, scaling
  settings, quotas, rule sets, player accounts or any other resource.
- Several lens practices are organizational (Live Ops objectives, reuse testing,
  threat modeling, ban policy). When the evidence is not in the account or the
  conversation they are graded **N/A — Interview needed**, with the question to ask.
- Third-party observability and security tools (Datadog, Grafana, Splunk, New Relic
  and similar) cannot be inspected from AWS; their coverage is **N/A pending manual
  confirmation**, never an automatic PASS or FAIL.
- Custom (non-GameLift) matchmakers and game-server managers are assessed from the
  resources they run on and the team's description; their internal logic is not
  visible to the agent.
- Terraform or other non-CloudFormation IaC state cannot be read; the deployment
  strategy is confirmed with the team.
- The lens is a supplement to the AWS Well-Architected Framework; this skill grades
  the games-specific practices, not the base framework's full question set.

## Agent types

This skill is used by the following agent types (selected in the Operator Web App at
upload time):

- **Chat tasks** — games workload reviews, launch/event readiness, single-area
  audits and best-practice questions.
- **Incident triage** — recognizes a games incident, frames player impact and
  separates AWS impairment from the studio's own change and from demand or external
  causes.
- **Incident RCA** — works the symptom → cause → evidence map and cites the lens
  best practice for prevention.

Select **All agents** instead if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, you can import this skill directly from the repository. In the
DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point
to the `skills/gaming-industry-operations` directory. See
[Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills)
for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the
> GitHub connection setup requires admin rights on the organization. Instead, connect
> your personal GitHub account and select any repository from it during the connection
> setup. Once a GitHub connection is established, you can import skills from any
> public repository, including this one, even if it wasn't selected during the
> connection setup.

**Option B: Upload as a zip file**

1. Zip the `gaming-industry-operations/` directory (only including allowed extensions):
   ```bash
   cd skills
   zip -r gaming-industry-operations.zip gaming-industry-operations/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```
2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `gaming-industry-operations.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks**, **Incident triage** and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills — useful for
CI/CD pipelines or automation workflows. Assign the skill to the `CHAT`,
`INCIDENT_TRIAGE` and `INCIDENT_RCA` agent types. See
[Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end)
for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills)
in the AWS DevOps Agent User Guide.

## How to use this skill

**Chat — full review**

> Review our multiplayer shooter's AWS environment against the Games Industry Lens.
> Game servers run on GameLift Spot fleets in us-east-1, eu-west-1 and ap-northeast-1
> with FlexMatch; the backend is API Gateway + Lambda + DynamoDB with Cognito. We
> expect 300k CCU at peak.

**Chat — launch readiness**

> Season 2 launches in three weeks and marketing projects 4x our current CCU. Are we
> ready? Check pre-scaling, quotas, matchmaking, DDoS protection and our deployment
> plan.

**Chat — single area**

> Audit our matchmaking setup: rule sets, latency policies, queue destinations and
> the alarms we have on wait time.

**Chat — one pillar**

> Run only the Security pillar of the Games Industry Lens on our studio's production
> account.

**Incident triage / RCA (automatic when the skill is assigned to those agent types)**

Alarm or ticket: "Players in EU report being kicked from matches since 19:40 UTC".
The agent frames player impact (session interruptions, CCU drop, affected game
Region), checks AWS Health, the change timeline and demand context, then works the
disconnect symptom map: Spot interruptions, unprotected scale-in or deployment, server
process crashes, EC2 network allowances, DDoS, ISP routing — and reports the root
cause with the lens best practice to prevent recurrence.

## Package layout

```
gaming-industry-operations/
├── SKILL.md                              # Workflows, runtime contract, critical rules
├── README.md
├── CHANGELOG.md
├── .skilleval.yaml
├── references/
│   ├── games-lens-best-practices.md      # All 78 lens checks: risk, verify, PASS criteria
│   ├── architecture-scenarios.md         # Lens scenarios, vocabulary, hosting trade-offs
│   ├── incident-symptom-map.md           # Symptoms → causes → evidence → lens BP
│   ├── discovery.md                      # Ordered read-only discovery and applicability gates
│   └── report-format.md                  # Review report and incident context block contracts
└── evals/
    └── evals.json                        # Eval definitions (positive and negative cases)
```

## Maintainer

`nilendu7980` (author of record in `SKILL.md`). Open an issue in this repository for
bugs, lens updates (check the lens
[document revisions](https://docs.aws.amazon.com/wellarchitected/latest/games-industry-lens/document-revisions.html))
or new games failure modes to add to the symptom map.

## Non-production disclaimer

> ⚠ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
