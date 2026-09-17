# AWS EKS Operations Review — Custom Agent

**Version: 1.0.0** (see [`CHANGELOG.md`](https://github.com/aws/tools-for-devops-agent/blob/main/custom-agents/aws-eks-operations-review/CHANGELOG.md)) | Requires skill version 1.9.3+ (see [`skills/aws-eks-operations-review/`](https://github.com/aws/tools-for-devops-agent/tree/main/skills/aws-eks-operations-review))

## Purpose

This custom agent is an orchestrator for the [`aws-eks-operations-review`](https://github.com/aws/tools-for-devops-agent/tree/main/skills/aws-eks-operations-review) skill. It runs a full read-only operations review of one Amazon EKS cluster and publishes the result as **multiple artifacts — one Summary plus one per pillar** rather than a single large report.

The multi-artifact split is the agent's central design decision. A full review spans 49 discovery areas and roughly 288 graded rows, and assembling that into one cumulative artifact means many sequential `create_or_update_artifact` calls whose payload grows with each call — the failure mode that produces render stalls and half-written reports. Splitting by pillar keeps each artifact small enough that most complete in one or two calls, makes every completed pillar a standalone deliverable, and removes cross-pillar accumulation risk entirely.

## Key Capabilities

- Grades one EKS cluster across nine pillars — Operations, Resilience, Security, Scalability, Performance, Observability, Networking, Cost, Control Plane — plus AWS API and Cluster Insights rows
- Publishes a Summary artifact (executive summary, cluster snapshot, prioritized action plan, Critical/High findings index, coverage line) and one artifact per graded pillar (that pillar's full scorecard plus its detailed findings)
- Grades every row against an observed result; a row that cannot be assessed stays in the report as N/A with the exact reason rather than being dropped or guessed
- Produces detailed, actionable remediation per finding — ordered steps naming the specific resource and field, validation, rollback, effort, and an authoritative documentation link
- Delegates all heavy work to subagents (discovery, telemetry, per-pillar grading, remediation prose, QA, rendering) so the orchestrator never holds raw payloads
- Enforces a QA coverage gate before any artifact is rendered, and verifies each artifact by reading it back afterward
- Treats wall-clock time as a constraint, degrading gracefully to declared-partial coverage instead of stalling with nothing rendered

## Important behavior notes

**Fixed scope.** The system prompt as published targets cluster `retail-store-demo` in `us-east-1` and does not enumerate clusters. Change the cluster name and region in the prompt's Workflow step 1 before using it against your own cluster, or the run will stop when it cannot find that cluster.

**Read-only.** `use_kubectl` is limited to `get`, `describe`, `logs`, `version`, `config current-context`, `cluster-info`, `top`, and `get --raw`. Kubernetes Secret values are never fetched. Remediations are proposals for human approval — the agent performs no mutations.

**Degraded runs are reported, not hidden.** If the runtime budget forces the agent to skip a pillar or compact its findings, it names what was skipped and why, in both the Summary artifact and the final report.

## Prerequisites

- An AWS DevOps Agent space
- IAM permissions for EKS read APIs (`eks:DescribeCluster`, `eks:ListNodegroups`, `eks:DescribeNodegroup`, `eks:ListAddons`, `eks:DescribeAddon`, `eks:ListInsights`, `eks:DescribeInsight`), CloudWatch metrics and Logs Insights reads, EC2 describe APIs, and CloudTrail lookup
- **EKS access configured in DevOps Agent** so the agent can run read-only `kubectl` against the cluster — see [Important: EKS access setup](#important-eks-access-setup-in-devops-agent) below. Without this the agent cannot discover any Kubernetes object and the review is almost entirely N/A.
- Kubernetes read access for the agent's identity on the target cluster — granted through the EKS access entry below. For the underlying verb and resource list, see the skill's [`references/docs/minimum-rbac.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aws-eks-operations-review/references/docs/minimum-rbac.md)
- The [aws-eks-operations-review skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/aws-eks-operations-review) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even though the skill's README instructs to choose specific agent types
- If your cluster's metrics and logs live outside CloudWatch — Grafana, Prometheus, Loki, or another observability platform — see [Optional: third-party MCP tools](#optional-third-party-mcp-tools-environment-dependent). Without that setup the telemetry-dependent rows are marked N/A rather than graded.

### Important: EKS access setup in DevOps Agent

**This is the single most common reason a run produces an empty-looking review.** `use_kubectl` reaches your cluster through an EKS **access entry** granted to your Agent Space's IAM role. Until that entry exists, every one of the 49 discovery areas returns `n/a` with a permission error, and the review completes honestly but almost entirely unassessed — scorecards full of N/A rows rather than findings. Follow [AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html) in the DevOps Agent user guide, once per cluster you intend to review.

The short version:

1. **Check the cluster's authentication mode includes the EKS API.** On the cluster's **Access** tab in the Amazon EKS console, the authentication mode must include EKS API. If it does not, switch to a mode that does before continuing. (This agent's Security pillar also grades this setting — a cluster still on `API_AND_CONFIG_MAP` will be flagged, which is expected and separate from access setup.)
2. **Find your Agent Space's primary cloud source IAM role ARN.** In your Agent Space: **Capabilities → Cloud → Primary Source → Edit**.
3. **Create an IAM access entry** on the cluster's **Access** tab, using that role ARN as the IAM principal.
4. **Attach an access policy** and set the access scope — see the policy guidance below.
5. **Verify** by asking the agent something simple about the cluster, such as listing pods in a namespace, before running a full review.

#### Policy choice — use `AmazonEKSAdminViewPolicy` for complete discovery

The AWS documentation's default is `AmazonAIOpsAssistantPolicy`, which is sufficient for typical incident investigation. **An operations review is broader than an investigation.** The 49 discovery areas walk the whole cluster object graph — namespaces, workloads, RBAC ClusterRoles and bindings, admission webhook configurations, CRDs, StorageClasses, PodDisruptionBudgets, NetworkPolicies, ResourceQuotas, LimitRanges, ServiceAccounts, and more. Object kinds the access policy does not cover come back as permission denials, which the agent correctly records as N/A with the exact reason rather than guessing — so the gap shows up as a review with real coverage holes.

**For all Kubernetes objects to be discovered, attach the AWS managed `AmazonEKSAdminViewPolicy` access policy**, with the access scope set to **Cluster**.

- **Scope must be Cluster, not namespace-limited.** The review is cluster-wide by definition. Namespace-scoped access silently reduces coverage: cluster-scoped objects such as ClusterRoles, webhook configurations, StorageClasses, and CRDs become invisible, and pillars like Security and Networking lose most of their evidence.
- **Read-only either way.** `AmazonEKSAdminViewPolicy` grants view access only. It cannot create, modify, or delete cluster resources, and the agent's own contract forbids mutation regardless of what the policy permits.

**One security note worth raising with whoever approves the access entry:** `AmazonEKSAdminViewPolicy` grants read access to *all* Kubernetes objects, and that includes Secrets. This agent never fetches Secret values — the skill and system prompt both prohibit it, and Secret checks are graded on existence, type, and metadata only. But the IAM grant is broader than what the agent uses, so the decision should be made deliberately rather than by default. If your organization will not permit it, use `AmazonAIOpsAssistantPolicy` instead and accept that some rows will be N/A for lack of access; the review remains valid, just less complete.

If the agent cannot reach the cluster at all, confirm the access entry uses the exact IAM role ARN from the Agent Space dialog and that an access policy is actually attached — a per-cluster step that is easy to miss when connecting several clusters to one Agent Space.

## Creating the Agent

1. In the DevOps Agent web app, go to the "Agents" page.
2. In the "Custom Agents" section, click "Create agent".
3. In the dialog, click "Form".
4. Fill out the form:
   - **Name** — `aws-eks-operations-review` (lowercase letters, numbers, hyphens only).
   - **System prompt** — copy the content of `SYSTEM_PROMPT.md` from this directory and paste it in. If your target cluster is not `retail-store-demo` in `us-east-1`, edit Workflow step 1 before saving.
   - **Skills** — select the skill listed in [Skills to add](#skills-to-add) below.
5. Click "Create agent".
6. Assign the tools and memory stores as described in the two sections below. Tools and memory stores are configured through Chat, not the Form.

### Skills to add

Select this in the "Skills" drop-down of the creation form:

| Skill | Why it's needed |
|-------|-----------------|
| `aws-eks-operations-review` | The authoritative source for the S0–S8 state machine, 49 discovery areas, check manifest, pillar definitions, thresholds, gates, grading guards, QA checklist, remediation shards, and report contract. The system prompt orchestrates this skill and grades nothing from memory — without it the agent has no check definitions at all. |

### Tools to add

Tools are assigned through Chat. On the newly created agent's page, click "Edit", then select "Chat". Once DevOps Agent finishes loading the agent's context, paste the request below, then confirm every tool appears under "Tools" on the agent's page afterward.

```text
Add the following tools to this custom agent: use_aws, use_kubectl, query_cloudwatch_logs,
create_or_update_artifact, list_artifacts, verify_aws_claim, lookup_cloudtrail_events,
get_topology_map, list_resources, list_resources_by_type, get_resource_edges,
explore_cloud_resource_topology, get_cloud_resource_topology, get_full_topology,
get_account_cloudformation_stacks, get_trace_overview, get_trace_summaries, get_trace_by_id,
trusted_advisor_get_recommendation_details, trusted_advisor_list_recommendations,
get_skill_resource, get_skill_resource_manifest
```

What each group is for:

| Tool | Used for |
|------|----------|
| `get_skill_resource_manifest`, `get_skill_resource` | Loading the skill's references just-in-time, state by state. Required — the agent cannot start without these. |
| `use_kubectl` | The 49 discovery areas, one command per call, read verbs only |
| `use_aws` | EKS describe/list APIs, CloudWatch metrics, EC2 health, and the AWS API / Cluster Insights rows |
| `query_cloudwatch_logs` | Control-plane Logs Insights queries (CP01–CP25) and log-pattern telemetry signals |
| `create_or_update_artifact`, `list_artifacts` | Publishing the Summary and pillar artifacts. `list_artifacts` is required by the prompt's re-run behavior, which checks for an existing title match before creating an artifact so re-runs update rather than duplicate. |
| `verify_aws_claim` | Confirming a threshold, quota, or recommended target value before prescribing it in a remediation |
| `lookup_cloudtrail_events` | Telemetry signals, and identifying when a misconfiguration was introduced for a finding's root-cause section |
| `get_topology_map`, `list_resources`, `list_resources_by_type`, `get_resource_edges`, `explore_cloud_resource_topology`, `get_cloud_resource_topology`, `get_full_topology`, `get_account_cloudformation_stacks` | Context gathering, related-resource discovery, and establishing the blast radius of a finding |
| `get_trace_overview`, `get_trace_summaries`, `get_trace_by_id` | Correlating latency findings where traces exist |
| `trusted_advisor_list_recommendations`, `trusted_advisor_get_recommendation_details` | Surfacing relevant EKS/EC2 advisor findings as Cost and Operations evidence |

### Memory stores to add

Memory stores are also assigned through Chat. In the same Chat session used for tools (or a new one), paste:

```text
Add the understanding-agent-space, tool-use-best-practices, and chat-tool-use-best-practices
memory stores to this custom agent.
```

| Memory store | Why it's needed |
|--------------|-----------------|
| `understanding-agent-space` | Agent Space context — how artifacts, skills, and capability providers behave in the space the agent runs in |
| `tool-use-best-practices` | General tool-use guidance, relevant because this agent makes long sequences of read and render calls |
| `chat-tool-use-best-practices` | Tool-use guidance for chat-initiated runs, used when the agent is invoked interactively rather than on a schedule |

### Optional: third-party MCP tools (environment-dependent)

The tool list above is deliberately AWS-native. As published, the agent treats **CloudWatch metrics and CloudWatch Logs as the only telemetry sources** — Evidence & Accuracy rule 3 in the system prompt verifies a namespace with `list-metrics` (or a log group, stream, ingestion delay, filters, and window for Logs Insights) and then marks the dependent row N/A with the paired observability-visibility FAIL.

**That is correct behavior only if CloudWatch is actually where your cluster's telemetry lives.** Many EKS environments send metrics and logs somewhere else — Amazon Managed Grafana, self-managed Grafana, Prometheus, Loki, or a third-party observability platform. On those clusters the agent will produce a run full of N/A rows for signals that are in fact perfectly observable, just not where it looked. The review is still honest, but far less useful than it should be.

If your telemetry lives outside CloudWatch, all three of these steps are required — doing only some of them makes things worse, not better:

1. **Connect the MCP server.** Register it as an account-level capability provider and connect it to your Agent Space, following that server's own deployment instructions.
2. **Assign its tools through Chat.** MCP tools cannot be assigned through the Form. Use the same Chat-based flow as the [Tools to add](#tools-to-add) section, naming the specific tools and the MCP server they come from, then confirm they appear under "Tools" on the agent's page.
3. **Update the system prompt to actually use them.** This is the step that is easy to skip and the one that matters most. Assigning tools without telling the prompt when to reach for them leaves the agent marking rows N/A while holding the tool that would have answered them.

For step 3, extend Evidence & Accuracy rule 3 with a fallback policy. Adapt the names to your own server and tools — the shape matters more than the specifics:

```text
Fallback before N/A. When a metric or log signal cannot be satisfied from CloudWatch
(namespace or dimensions absent, log type disabled, or Logs Insights returns nothing
after source/stream/delay/filter/window verification), attempt <your source> before
marking the dependent row N/A:
  - Discover the datasource, then query the metric or log stream for this cluster.
  - Cite the datasource (name and UID or endpoint) in the evidence of every row that
    used the fallback, alongside the query and the result.
  - Only mark N/A after both CloudWatch and <your source> were tried and returned
    nothing, and document both attempts in the N/A reason.
The observability-visibility FAIL still applies when a required telemetry source is
genuinely absent — a successful fallback removes the N/A, not the finding that
CloudWatch coverage is missing.
```

Two cautions:

- **Do not reference a tool in the prompt that is not assigned.** The agent will attempt it, fail, and burn budget on retries. Prompt and assigned tools must match in both directions.
- **Keep the read-only posture.** Assign only read and query tools from the third-party server. The agent's contract is that it never mutates anything, and a writable tool in its hands breaks that guarantee regardless of what the prompt says.

The same pattern applies to any other capability your environment needs — a cost or FinOps MCP server for the Cost pillar, a service-desk server for cross-referencing findings against tickets. Assign the tools, then extend the relevant prompt section to say when and how to use them and how to cite what they return.

## Executing the Agent

You can execute the custom agent on-demand from the custom agent page, on a schedule, or through chat. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) for more information. You can also run it with a custom prompt — for example, naming a single pillar to review instead of the full nine.

Once finished, the artifacts are persisted on the **Artifacts** page in the DevOps Agent web app. Expect one Summary artifact plus one artifact per graded pillar, each titled `EKS Operations Review — <cluster> — <Summary | Pillar Name>`. Start with the Summary: it carries the executive summary, the prioritized action plan, the Critical/High findings index across every pillar, and the coverage line naming each pillar artifact produced.

## Related

- [aws-eks-operations-review skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/aws-eks-operations-review) — the authoritative check definitions, thresholds, gates, and report contract this agent executes
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
