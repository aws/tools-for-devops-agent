# Getting Started

This guide walks you through deploying skills and custom agents from this repository to your AWS DevOps Agent Space.

## Prerequisites

!!! info "Before you begin"
    - An [AWS DevOps Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) set up with your target AWS account as a cloud source
    - The skill-specific prerequisites documented on each skill's page (IAM permissions, etc.)
    - The agent-specific prerequisites documented on each custom agent's page (IAM permissions, tools, skills, etc.)
    - The server-specific prerequisites documented on each MCP server's page (deployment tools, IAM permissions, etc.)

---

## Skills

### Deploy a Skill

#### 1. Choose a Skill

Browse the [Skills Catalog](skills/index.md) and select a skill that matches your use case.

#### 2. Follow the Skill's README

Each skill's page includes prerequisites, deployment instructions, and sample prompts. Follow the instructions in the skill's README to deploy it to your Agent Space.

#### 3. Verify

In the DevOps Agent Chat, try one of the sample prompts listed on the skill's page. The agent should automatically activate the skill based on the context of your request.

### Directory Structure

Each skill follows a consistent structure based on the [Agent Skills specification](https://agentskills.io/home):

```
skills/<skill-name>/
├── SKILL.md          # Main skill instructions with frontmatter (required)
├── README.md         # Documentation, prerequisites, and upload guide
├── CHANGELOG.md      # Version history
├── evals/            # Evaluation queries and benchmarks
├── assets/           # Images, diagrams, data files (optional)
└── references/       # Supplementary reference docs (optional)
```

The `SKILL.md`, `references/`, and `assets/` directories are what AWS DevOps Agent reads at runtime. Everything else supports development, testing, and documentation.

### Writing Your Own Skills

For guidance on creating custom skills for your operational workflows, see the [AWS DevOps Agent skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html).

You can also use the skills in this repository as templates.

---

## Custom Agents

### Deploy a Custom Agent

#### 1. Choose a Custom Agent

Browse the [Custom Agents Catalog](custom-agents/index.md) and select an agent that matches your workflow.

#### 2. Follow the Agent's README

Each custom agent's page includes prerequisites, step-by-step creation instructions, and execution guidance. Follow the instructions in the agent's README to create and configure it in your Agent Space.

#### 3. Verify

Execute the custom agent on-demand from its page in the DevOps Agent web app. Check that the agent produces the expected output (report artifact, recommendations, etc.).

### Directory Structure

Each custom agent follows a consistent structure:

```
custom-agents/<agent-name>/
├── SYSTEM_PROMPT.md  # The system prompt to paste into the agent configuration
├── README.md         # Documentation, prerequisites, creation steps, execution guide
└── CHANGELOG.md      # Version history
```

The `SYSTEM_PROMPT.md` is what you paste into the DevOps Agent web app when creating the agent. The README provides the full setup walkthrough.

### Creating Your Own Custom Agents

For guidance on building custom agents for your operational workflows, see the [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html).

You can also use the agents in this repository as templates — they demonstrate how to structure a system prompt, assign tools, and compose skills into a purpose-built workflow.

---

## MCP Servers

### Deploy an MCP Server

#### 1. Choose an MCP Server

Browse the [MCP Servers Catalog](mcp-servers/index.md) and select a server that matches your diagnostic needs.

#### 2. Follow the Server's README

Each MCP server's page includes prerequisites, deployment instructions (typically using CDK or SAM), and registration steps for connecting it to your Agent Space.

#### 3. Register with DevOps Agent

After deploying the infrastructure, register the MCP server endpoint with your Agent Space. Each server's README provides the specific registration steps (endpoint URL, authentication method, and tool selection).

#### 4. Verify

In the DevOps Agent Chat, try one of the usage examples from the server's README. The agent should discover and invoke the server's tools based on the context of your request.

### Directory Structure

Each MCP server follows a project-specific structure, but typically includes:

```
mcp/<server-name>/
├── README.md         # Documentation, prerequisites, deployment, and registration guide
├── LICENSE           # License file
├── template.yaml     # SAM template (or cdk.json for CDK-based servers)
├── src/              # Server source code
├── tests/            # Unit and integration tests
└── docs/             # Architecture and design documentation (optional)
```

The deployment artifacts (SAM template or CDK app) provision the infrastructure in your AWS account. After deployment, the server exposes an MCP-compatible endpoint that DevOps Agent connects to.

### Building Your Own MCP Servers

For guidance on building MCP servers for DevOps Agent, see the [AWS DevOps Agent MCP servers documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html) and the [Model Context Protocol specification](https://modelcontextprotocol.io).

You can also use the servers in this repository as templates — they demonstrate security models, IAM scoping, tool design patterns, and registration workflows.
