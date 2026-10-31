# Prometheus / AMP Investigation

This skill tells the AWS DevOps Agent when to reach for the
[aws-prometheus-mcp MCP server](https://github.com/aws/tools-for-devops-agent/tree/main/mcp/aws-prometheus-mcp)
and in what order to use its tools, so an incident whose signal lives in
Prometheus or Amazon Managed Service for Prometheus (AMP) leads to a consistent,
bounded investigation instead of guessed metric names and unbounded queries.

## ⚠️ Important Notice

This skill is sample code, not intended for production use without additional
review and testing. Validate in a non-production environment first. It is
read-only: it drives metric discovery and PromQL query tools and takes no action
on your Prometheus/AMP workspace.

## Purpose

The MCP server exposes five read-only tools but does not tell the agent when to
use them or in what order. This skill supplies the activation trigger and the
investigation sequence: discover the workspace and confirm which metrics exist
before querying, choose RED (services) or USE (resources) deliberately, compare
the incident window against a historical baseline, and keep every PromQL query
bounded in time, step, and cardinality.

The order matters. Querying a guessed metric name produces an empty or wrong
result that is easy to misread; a single incident-window value without a baseline
is not evidence; and an unbounded or high-cardinality query is the main way a
Prometheus investigation goes wrong.

## Key Capabilities

- Recognize when an incident's signal is in Prometheus/AMP rather than CloudWatch
- Enforce discover-before-query: workspace and metric-name confirmation before any
  PromQL
- Apply RED for request-driven services and USE for nodes/pods/containers, mapped
  to the standard EKS/Kubernetes metric sources
- Baseline the incident window against a prior cycle with PromQL `offset`
- Keep queries bounded (time range, step size, aggregation, counter `rate()`)
- Report the exact PromQL, the observed value, the baseline delta, and the
  coverage boundary

## Prerequisites

- The `aws-prometheus-mcp` MCP server registered in your Agent Space with its
  tools allowlisted. The server and its deployment instructions are in this
  repository at [`mcp/aws-prometheus-mcp/`](https://github.com/aws/tools-for-devops-agent/tree/main/mcp/aws-prometheus-mcp)
- An existing Amazon Managed Service for Prometheus workspace supplied to the
  server (the server does not create one)
- No additional DevOps Agent role permissions; the agent calls the MCP server,
  which holds the read-only AMP permissions

## Limitations

- Guidance only. Without the MCP server registered and allowlisted, none of the
  tools it references are callable
- Metric availability depends entirely on the customer's scrape configuration; the
  skill reports what exists rather than assuming a standard metric set
- All referenced tools are read-only; the skill neither writes nor remote-writes to
  the workspace
- PromQL evaluation is bounded by the workspace's own query limits; rejected or
  truncated queries must be narrowed, not retried unchanged

## Agent Types

- **Chat tasks** - conversational metric investigation and PromQL querying
- **Incident RCA** - automated investigation where a failure's signal is in
  Prometheus/AMP

## Uploading to AWS DevOps Agent

Register the MCP server first. The skill references its tools by name, and trigger
behavior cannot be validated until those tools are present in the Agent Space.

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, import this skill directly from the repository. In the DevOps
Agent web app, go to Settings → Add Skill → Import from repository, then point to
the `skills/prometheus-amp-investigation` directory.

**Option B: Upload as a zip file**

1. Zip the directory, including only allowed extensions:

   ```bash
   cd skills
   zip -r prometheus-amp-investigation.zip prometheus-amp-investigation/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, go to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the zip file.
5. Select the agent types: **Chat tasks** and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See
[Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

### Chat

- "Our checkout service error rate spiked at 14:00; the metrics are in our AMP workspace, not CloudWatch."
- "Which pods are being CPU-throttled right now according to Prometheus?"
- "Compare p99 latency for the orders API this hour against the same hour yesterday."
- "Is the HPA for the web deployment actually scaling? Check kube-state-metrics."

### Investigation

- "An EKS workload started returning 5xx after a deploy; root cause from Prometheus signals."
- "Node saturation suspected on the data-plane nodes last night; confirm from node-exporter."
- "Throughput dropped on the ingestion service; find where in the request path from RED metrics."

## Learn More

- [aws-prometheus-mcp MCP server](https://github.com/aws/tools-for-devops-agent/blob/main/mcp/aws-prometheus-mcp/README.md)
- [Call flow](https://github.com/aws/tools-for-devops-agent/blob/main/mcp/aws-prometheus-mcp/docs/CALL_FLOW.md)
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
