# AWS Performance Efficiency Review

A skill for AWS DevOps Agent that finds where an application spends its time, which resource limits it, and what to change. It follows the request path across dependencies, uses the RED and USE methods to locate the bottleneck, tests each candidate cause by timing, scope, history and magnitude before naming it, ranks the fix that removes the cause above the one that adds capacity, and maps every finding to the Performance Efficiency pillar of the AWS Well-Architected Framework.

> **Disclaimer:** This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

## What it does

**Starts from the goal, not the graph.** In a chat review it first reads what it can (an existing SLO, alarms) and then asks at most three questions in one message: the performance target, the expected peak or growth, and the constraints. Every recommendation is then sized against that target with explicit arithmetic (required concurrency = rate x per-request duration) and kept inside the constraints. In an incident investigation it never asks; it states its defaults in an Assumptions line.

**Follows the request path, whatever the entry point.** A load balancer, an API, a queue, a stream, a schedule or a batch job. It orders the hops from the entry point to the deepest dependency from the Agent Space topology, Application Signals and X-Ray, falling back to configuration (target groups, event source mappings, endpoint variables) and marking inferred hops as such. For asynchronous work it maps producer, queue or stream, consumer fleet and what the consumers call.

**Measures before it explains.** Rate, errors and p50, p90, p99 duration at every hop (RED), each hop's share of end-to-end time and its change against a baseline window. For queues and streams RED is arrival rate, completion rate, backlog and age. Averages are never used alone; like is compared with like (same percentile, same period, matched rate), and the baseline is re-taken when rate, request shape or configuration changed inside the history.

**Finds the constraining resource (USE).** Utilization, saturation and errors on CPU, memory, IOPS, network, connections, concurrency and capacity units of the suspect hop, broken down by operation, member, Availability Zone, revision and caller, with outliers picked against peers rather than a fixed threshold. A limit at its maximum behind a slow dependency is reported as a consequence, not a cause, unless it saturated first.

**Hunts the limits that look like headroom.** Burst credits, baseline throughput allowances, provisioned limits that sit below the instance ceiling, the memory setting that is really the CPU setting, concurrency caps, visibility timeouts shorter than the work, token and request quotas, Provisioned Throughput. Each is checked against the real limit, not the resource's nominal size.

**Tests every cause before naming it.** Competing explanations are ruled in or out by timing, scope, history and magnitude. A cause is **Confirmed** only with two independent signals whose onset and size account for the symptom in numbers, **Likely** with one signal or a failed read, otherwise **Unconfirmed** and never listed as a cause. A peer running the same code is used as a control twin; a change shared by healthy and degraded peers is ruled out as the sole cause; a configuration change is never invented.

**Checks for self-inflicted load first.** Before recommending capacity it compares originating requests with the attempts a dependency actually received; retries, abandoned calls and timeouts shorter than the dependency's p99 are proven by magnitude and fixed at the caller. The fix that removes the cause always ranks above the one that masks it, cutting business load is never a ranked fix, and raising a consumer's cap triggers a downstream capacity check.

**Uses the account's own advisors as hypotheses, not verdicts.** Compute Optimizer right-sizing and Trusted Advisor performance checks are read for resources on the path; a flag is confirmed or dismissed with the workload's own metrics, and off-path findings are reported separately as cost items.

**Covers AI and ML hops like any other hop.** A model invocation, an inference endpoint, a GPU cluster or an agent runtime is measured from its caller with the same rules: arriving rate including throttles, latency percentiles, output tokens per second to separate a slower model from a longer answer, quotas and provisioned units as hidden limits. When the evidence puts the bottleneck inside the model, the training job or the agent runtime, the report names the dedicated repository skill as the next step.

**Treats missing telemetry as a finding.** Every source on the path that could not be read, whether the capability is off, the call was denied or the namespace is empty, is a row in a Telemetry gaps table: what to enable, what the review could then measure, the cost direction with the pricing page, and the permission change needed.

**Reports in one shape every time.** Assumptions, Summary with verdict and labelled cause, Request path, Bottleneck with evidence and arithmetic, Hypotheses considered, Findings each citing the metric and the call that returned it, Recommendations ranked with cost direction, verification metric and Well-Architected PERF best-practice ID, Telemetry gaps, Next review. No account IDs, ARNs, IP addresses or principal names appear anywhere in the answer.

Service-specific metric names, thresholds and deep checks (databases, compute, storage, caches, queues, load balancers, API gateways, NAT, Bedrock, SageMaker AI, AgentCore, GPU on EKS) live in the `references/` files and are applied when the path reaches that service.

The skill only reads. It does not change resources, run code, or connect to databases.

## Agent types

- **Chat tasks:** performance reviews, right-sizing questions, "will this scale for the peak".
- **Incident RCA:** investigations where the symptom is latency, timeouts, throttling, backlog or saturation.

Select **All agents** at upload if a custom agent should also load this skill.

## Prerequisites

### 1. An Agent Space with the application's accounts

An existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the accounts that run the application configured as cloud sources.

### 2. IAM permissions for the Agent Space role

The skill is **read-only**: it never calls `Create*`, `Update*`, `Delete*`, `Put*` or any data-plane API. The managed policy `AIDevOpsAgentAccessPolicy` already covers CloudWatch metrics and logs, X-Ray, Application Signals, Database Insights (`pi`), CloudTrail lookup, Service Quotas and the describe APIs of the services on the path. Twelve read actions must be added:

- `compute-optimizer:GetEnrollmentStatus`, `GetEC2InstanceRecommendations`, `GetAutoScalingGroupRecommendations`, `GetEBSVolumeRecommendations`, `GetLambdaFunctionRecommendations`, `GetECSServiceRecommendations`, `GetRDSDatabaseRecommendations` (right-sizing input)
- `lambda:GetFunctionConcurrency` (reserved concurrency for the Lambda deep check)
- `trustedadvisor:ListChecks`, `ListRecommendations`, `GetRecommendation`, `ListRecommendationResources` (performance-pillar checks; data is returned only on a Business Support+, Enterprise Support or Unified Operations plan, otherwise the skill reports Trusted Advisor as unavailable)

Deploy them with the `EnableAwsPerformanceEfficiencyReview` parameter of the shared template [cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), one stack per Agent Space role:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies-<role-suffix> \
  --parameter-overrides ExistingRoleName=<DevOpsAgentRole-AgentSpace-XXXX> \
      EnableAwsPerformanceEfficiencyReview=true \
  --capabilities CAPABILITY_NAMED_IAM --region <region>
```

Set the template's other `Enable*` parameters to `false` unless you also want those skills' policies. The skill still runs without the twelve actions: a denied call is reported as a telemetry gap with the missing permission named, and the Compute Optimizer, reserved-concurrency and Trusted Advisor inputs are skipped.

### 3. Telemetry on the request path (recommended)

The review is most complete with CloudWatch Application Signals or AWS X-Ray on the services in the path, Database Insights on RDS and Aurora, the CloudWatch agent publishing memory on EC2, Container Insights on ECS and EKS, Lambda Insights on CPU-bound functions, Compute Optimizer opted in, and for AI hops Bedrock model invocation logging, SageMaker AI detailed observability, Accelerated Compute Insights on GPU clusters and AgentCore observability. Without them the skill still runs and lists each missing source in the report's Telemetry gaps table with the cost direction and the change needed.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

Package from inside the skill directory so `SKILL.md` sits at the archive root, excluding development-only files:

```bash
cd skills/aws-performance-efficiency-review
zip -r ../aws-performance-efficiency-review.zip . -x 'README.md' 'CHANGELOG.md' 'evals/*'
```

Then in the Agent Space Operator Web App:

1. Open **Skills**, then **Add skill**, then **Upload skill**.
2. Drop `aws-performance-efficiency-review.zip`.
3. Select agent types **Chat tasks** and **Incident RCA** (or **All agents**).
4. Review the validation result, then **Upload**.

Or with the DevOps Agent CLI: `devops-agent skills upload-skill --skill-dir skills/aws-performance-efficiency-review --agent-space-id <id> --agent-types "CHAT,INCIDENT_RCA"`.

## Example prompts

Chat:

- "Run a performance review of the orders service for the last 14 days."
- "Where does the latency in the inventory API come from?"
- "Are the instances behind the web load balancer right-sized?"
- "Will the payment service handle three times today's peak traffic?"

Investigation:

- "p99 latency on the orders API went above 2 seconds at 14:00 UTC. Find the cause."
- "Requests to the inventory service started timing out after this morning's deployment."

## Skill contents

```
aws-performance-efficiency-review/
├── SKILL.md                          # Workflow the agent follows: intake, path, RED, USE, differential, report
├── references/
│   ├── metrics-by-service.md         # Metric names, dimensions, statistics and deep checks per service
│   ├── bottleneck-patterns.md        # Starting thresholds and symptom-to-cause patterns
│   ├── hidden-limits.md              # Limits that look like headroom: credits, burst, allowances, caps, quotas
│   ├── logs-and-statistics.md        # Logs Insights patterns; baselines, SLOs, async RED, Little's law
│   ├── diagnosis-rules.md            # Confidence labels, differential, magnitude arithmetic, twins, masking fixes
│   ├── report-and-delegation.md      # Report template, hygiene, sub-agent task text
│   ├── well-architected-mapping.md   # PERF01 to PERF05 best-practice IDs
│   └── telemetry-sources.md          # Capability to enable per telemetry gap, with cost direction and permissions
├── evals/                            # skill-eval cases and results (development only, not published)
├── README.md
└── CHANGELOG.md
```

## Further reading

The methods behind the analysis rules, and the two AWS facts the rules lean on most:

- Brendan Gregg, the USE method: https://www.brendangregg.com/usemethod.html
- Tom Wilkie, the RED method: https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/
- Google SRE book, service level objectives and error budgets: https://sre.google/sre-book/service-level-objectives/
- Amazon Builders' Library, timeouts, retries and backoff with jitter: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- Amazon Builders' Library, avoiding insurmountable queue backlogs: https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/
- Lambda memory sets the CPU share (1,769 MB is one vCPU): https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html
- Lambda `Duration` excludes initialization time: https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html

Per-service metric names and limits are taken from the AWS documentation for that service; the pricing pages cited in telemetry gaps are listed in `references/telemetry-sources.md`.
