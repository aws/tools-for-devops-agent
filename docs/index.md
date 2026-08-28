---
hide:
  - navigation
  - toc
---

<div class="hero">
  <div class="hero-image">
    <img src="assets/devops-agent-icon.svg" alt="AWS DevOps Agent">
  </div>
  <h1>AWS DevOps Agent Tools</h1>
  <p class="hero-subtitle">Open-source skills, custom agents, MCP servers, and infrastructure templates that extend AWS DevOps Agent for incident response, root cause analysis, and operational reviews.</p>
  <div class="hero-buttons">
    <a href="getting-started/" class="md-button md-button--primary">Get Started</a>
    <a href="skills/" class="md-button">Browse Skills</a>
    <a href="custom-agents/" class="md-button">Browse Custom Agents</a>
    <a href="mcp-servers/" class="md-button">Browse MCP Servers</a>
  </div>
</div>

<div class="features">
  <div class="feature">
    <h3>🔍 Skills</h3>
    <p>Structured instruction sets that teach the agent how to investigate incidents, perform operational reviews, and follow best practices for specific AWS services.</p>
  </div>
  <div class="feature">
    <h3>🤖 Custom Agents</h3>
    <p>Ready-to-use custom agent configurations that combine skills and tools into purpose-built workflows like scheduled health reports.</p>
  </div>
  <div class="feature">
    <h3>🔧 MCP Servers</h3>
    <p>Deployable MCP servers that give the agent custom tools for deep infrastructure diagnostics — node log collection, DNS resolution probing, database health checks, and more.</p>
  </div>
</div>

---

## What's in This Repository?

This repository provides open-source tools that extend [AWS DevOps Agent](https://aws.amazon.com/devops-agent/) beyond its built-in capabilities:

- **Skills** — Structured instruction sets that teach the agent how to investigate specific operational scenarios. Skills follow the open [Agent Skills specification](https://agentskills.io/home) and the [DevOps Agent skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) guidance, and can be uploaded to your Agent Space.
- **Custom Agents** — Pre-built agent configurations with system prompts and tool assignments for specific operational workflows (e.g., generating periodic health reports). Custom agents follow the [AGENTS.md specification](https://agents.md/) and the [DevOps Agent custom agents guidance](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html).
- **MCP Servers** — Deployable [Model Context Protocol](https://modelcontextprotocol.io) servers that extend DevOps Agent with custom tools for infrastructure diagnostics, database health checks, and more. Each server is deployed to your AWS account and registered with your Agent Space.
- **CloudFormation Templates** — Infrastructure-as-code for provisioning IAM permissions and resources that skills require.

### What Can Skills Do?

Skills enable DevOps Agent to:

- **Specialize** with investigation procedures, best practices, and organizational knowledge specific to your infrastructure
- **Automatically load** relevant instructions during investigations, eliminating repetitive guidance
- **Compose** multiple skills for end-to-end investigation workflows
- **Guide** the agent in using your custom MCP server tools effectively for infrastructure-specific workflows

### What Can Custom Agents Do?

Custom agents are user-defined AI agents that automate operational tasks specific to your infrastructure. You define a system prompt, assign tools and skills, and run them on demand or on a schedule. Common use cases include:

- **Operational reporting** — Generate daily or weekly health summaries, deployment reports, or compliance audits across your infrastructure
- **Configuration auditing** — Periodically check resource configurations against your organization's standards and produce findings
- **Trend analysis** — Analyze metrics, error patterns, or cost trends over time and surface actionable insights
- **Multi-step workflows** — Orchestrate sequences of tool calls across multiple integrations to complete complex operational procedures
- **Cross-tool correlation** — Combine data from observability platforms, CI/CD pipelines, and AWS services to answer complex operational questions

### What Can MCP Servers Do?

MCP ([Model Context Protocol](https://modelcontextprotocol.io)) is an open standard for connecting AI applications to external systems. MCP servers give DevOps Agent the ability to interact with your infrastructure through custom tools. Use cases include:

- **Deep infrastructure diagnostics** — Collect and analyze node-level logs, DNS resolution behavior, or database internals that aren't accessible through standard AWS APIs
- **Safe, scoped access** — Each server enforces its own security model with IAM scoping, allowlists, and read-only constraints so the agent operates within well-defined boundaries
- **Standardized integration** — Build once using the MCP specification and register with DevOps Agent via a secure endpoint — no custom client code needed
- **Composable with skills** — Pair MCP servers with skills that guide the agent on when and how to use the tools effectively

## Learn More

- [Getting Started](getting-started.md) — how to deploy skills and custom agents to your Agent Space
- [Writing your own skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) — official AWS documentation
- [Creating custom agents](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html) — official AWS documentation
- [Agent Skills specification](https://agentskills.io/home) — the open standard these skills follow
- [AGENTS.md specification](https://agents.md/) — the open standard for custom agent definitions
- [Model Context Protocol](https://modelcontextprotocol.io) — the open specification for MCP servers
- [Agent Skill Eval](https://github.com/aws-samples/sample-agent-skill-eval) — evaluation framework for testing skills
