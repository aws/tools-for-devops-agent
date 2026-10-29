---
name: launchdarkly-projects
description: Guide for setting up LaunchDarkly projects in your codebase. Helps you assess your stack, choose the right approach, and integrate project management that makes sense for your architecture.
compatibility: Requires the remotely hosted LaunchDarkly MCP server. Code that creates projects itself (scripts, IaC, admin tools) needs an API access token with projects:write permission.
metadata:
  author: launchdarkly
  version: "0.5.0"
---

# LaunchDarkly Projects Setup

You're using a skill that will guide you through setting up LaunchDarkly project management in a codebase. Your job is to explore the codebase to understand the stack and patterns, assess what approach makes sense, choose the right implementation path from the references, execute the setup, and verify it works.

## Prerequisites

- The remotely hosted LaunchDarkly MCP server configured in your environment
- An API access token with `projects:write` permission, only if you're building code that creates projects (scripts, IaC, admin tools)

## Core Principles

1. **Understand First**: Explore the codebase to understand the stack and patterns.
2. **Choose the Right Fit**: Select an approach that matches your architecture.
3. **Follow Conventions**: Respect existing code style and structure.
4. **Verify Integration**: Confirm the setup works: the agent performs checks and reports results.

## API Access

When you create or inspect a project yourself, use the LaunchDarkly MCP server tools: `create-project`, `get-project`, and `list-projects`. They authenticate via OAuth and need no token.

The MCP tools don't return server-side SDK keys, only client-side IDs and mobile keys. To get the SDK key the app needs, ask the user to copy it from **Project settings → Environments**, or, if they'd rather, to paste an API access token for this session so you can fetch it through the REST API ([Quick Start](references/quick-start.md)). Do not search environment variables, `.env` files, or agent/MCP config files for credentials.

The reference guides call the REST API because they build code that runs without the agent.

## What Are Projects?

Projects are LaunchDarkly's top-level organizational containers that hold:
- All your configs
- Feature flags and segments  
- Multiple environments (Production and Test created by default)

Think of projects as separate applications, services, or teams that need their own isolated set of configurations.

## Project Setup Workflow

### Step 1: Explore the Codebase

Before implementing anything, understand the existing architecture:

1. **Identify the tech stack:**
   - What language(s)? (Python, Node.js, Go, Java, etc.)
   - What framework(s)? (FastAPI, Express, Spring Boot, etc.)
   - Is there an existing LaunchDarkly integration?

2. **Check environment management:**
   - How are environment variables stored? (.env files, secrets manager, config files)
   - Where is configuration loaded? (startup scripts, config modules)
   - Are there existing LaunchDarkly SDK keys?

3. **Look for patterns:**
   - Are there existing API clients or service modules?
   - How is external API integration typically done?
   - Is there a CLI, scripts directory, or admin tooling?

4. **Understand the use case:**
   - Is this a new project being set up?
   - Adding to an existing LaunchDarkly integration?
   - Part of a multi-service architecture?
   - Need for project cloning across regions/teams?

### Step 2: Assess the Situation

Based on your exploration, determine the right approach:

| Scenario | Recommended Path |
|----------|------------------|
| New project, no LaunchDarkly integration | **Quick Setup** - Create the project with `create-project`, then save its SDK keys |
| Existing LaunchDarkly usage | **Add to Existing** - Create new project or use existing |
| Multiple services/microservices | **Multi-Project** - Create projects per service |
| Multi-region or multi-tenant | **Project Cloning** - Clone template project |
| Infrastructure-as-Code (IaC) setup | **Automated Setup** - Script-based creation |
| Need project management tooling | **CLI/Admin Tools** - Build project management utilities |

### Step 3: Choose Your Implementation Path

Select the reference guide that matches your stack and use case:

**By Language/Stack:**
- [Python Implementation](references/python-setup.md) - For Python applications (FastAPI, Django, Flask)
- [Node.js/TypeScript Implementation](references/nodejs-setup.md) - For Node.js/Express/NestJS applications
- [Go Implementation](references/go-setup.md) - For Go services
- [Multi-Language Setup](references/multi-language-setup.md) - For polyglot architectures

**By Use Case:**
- [Quick Start](references/quick-start.md) - Create first project and get SDK keys
- [Environment Configuration](references/env-config.md) - Save SDK keys to .env, secrets, or config
- [Project Cloning](references/project-cloning.md) - Clone projects for regions/teams
- [IaC/Automation](references/iac-automation.md) - Terraform, scripts, CI/CD integration
- [Admin Tooling](references/admin-tooling.md) - Build CLI or admin utilities

### Step 4: Implement the Integration

Follow the chosen reference guide to implement project management. Key considerations:

1. **API Authentication:**
   - Store API token securely
   - Follow existing secrets management patterns
   - Never commit tokens to version control

2. **Project Naming:**
   - Use consistent, descriptive names
   - Follow existing naming conventions
   - Project keys: lowercase, hyphens, start with letter

3. **SDK Key Management:**
   - Extract and store SDK keys for each environment
   - Save the key the application uses as `LD_SDK_KEY`. The Python and Node.js AI SDKs read that variable and initialize on the first AI call. They don't read `LAUNCHDARKLY_SDK_KEY`.
   - Use the same pattern as other secrets in your codebase
   - Consider separate keys for test/staging/production

4. **Error Handling:**
   - Handle existing projects gracefully (409 conflict)
   - Provide clear error messages
   - Don't fail silently

### Step 5: Verify the Setup

After creating the project, verify it works:

1. **Fetch to confirm it exists.** Call the `get-project` MCP tool and check that the project has its environments. Code without MCP access can call the REST API instead:
   ```bash
   curl -X GET "https://app.launchdarkly.com/api/v2/projects/{projectKey}?expand=environments" \
     -H "Authorization: {api_token}"
   ```
   **Do not pipe the response straight into a `.environments.items[]`-style `jq` filter.** The shape of `environments` varies by `expand` parameter — sometimes it's `{items: [...]}`, sometimes a bare array — and a hand-rolled filter will fail with `Cannot index array with string "items"`. Run `jq -e .` first to inspect the actual shape, or use `jq '.environments | if type == "object" then .items else . end'` to handle both.

2. **Test SDK integration:**
   Put the key in `.env` as `LD_SDK_KEY`, then initialize the AI SDK from the project directory. Python needs `pip install launchdarkly-server-sdk launchdarkly-ai-server python-dotenv`:
   ```python
   import asyncio
   from dotenv import load_dotenv
   from launchdarkly_ai_server import init_client, get_client, shutdown

   load_dotenv()

   async def main():
       await init_client()
       print("SDK initialized:", get_client().is_initialized())
       # shutdown() flushes pending events before closing the connection.
       await shutdown()

   asyncio.run(main())
   ```
   Node.js needs `npm install @launchdarkly/ai-node dotenv`:
   ```javascript
   import 'dotenv/config';
   import { initClient, shutdown } from '@launchdarkly/ai-node';

   // Resolves once connected; throws LDTimeoutError if the key is invalid
   await initClient();
   console.log('SDK initialized: true');
   await shutdown();
   ```
   A valid key prints `SDK initialized: True` (Python) or `true` (Node.js). With an invalid key, Python logs `HTTP error 401 (invalid SDK key)` and prints `False`, and Node.js throws `LDTimeoutError` after 10 seconds. With no key, both raise an error that asks for `LD_SDK_KEY`.

3. **Report results:**
   - ✓ Project exists and has environments
   - ✓ SDK keys are present and valid
   - ✓ SDK can initialize (or flag any issues)

## Project Key Best Practices

Project keys must follow these rules:

```
✓ Good examples:
  - "support-ai"
  - "chat-bot-v2"
  - "internal-tools"

✗ Bad examples:
  - "Support_AI"     # No uppercase or underscores
  - "123-project"    # Must start with letter  
  - "my.project"     # No dots allowed
```

**Naming Recommendations:**
- Keep keys short but descriptive
- Use team/service/purpose as naming scheme
- Be consistent across your organization

## Common Organization Patterns

### By Team
```
platform-ai       → Platform Team Agent
customer-ai       → Customer Success Team Agent
internal-ai       → Internal Tools Team Agent
```

### By Application/Service
```
mobile-ai         → Mobile App configs
web-ai            → Web App configs
api-ai            → API Service configs
```

### By Region/Deployment
```
ai-us             → US Region
ai-eu             → Europe Region
ai-apac           → Asia-Pacific Region
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Project already exists | Check if it's the right one; use it or create with different key |
| Need multiple projects | Create separately for each service/region/team |
| Shared configs across services | Use same project, separate by SDK context |
| Token lacks permissions | Request `projects:write` or use MCP server |
| Project name conflict | Keys must be unique, names can be similar |

## What NOT to Do

- Don't create projects without understanding the use case first
- Don't commit API tokens or SDK keys to version control
- Don't use production SDK keys in test/development environments
- Don't create duplicate projects unnecessarily
- Don't skip the exploration phase

## Next Steps

After setting up projects:

1. **Create configs** - Use the `launchdarkly-configs-create` skill
2. **Set up SDK Integration** - Use the `sdk-install` skill
3. **Configure Targeting** - Use the `launchdarkly-configs-targeting` skill

## Related Skills

- `launchdarkly-configs-create` - Create configs in projects
- `sdk-install` - Integrate SDK in your application
- `launchdarkly-configs-targeting` - Configure config targeting
- `launchdarkly-configs-variations` - Manage config variations

## References

- [Python Implementation](references/python-setup.md)
- [Node.js Implementation](references/nodejs-setup.md)
- [Go Implementation](references/go-setup.md)
- [Quick Start Guide](references/quick-start.md)
- [Environment Configuration](references/env-config.md)
- [Project Cloning](references/project-cloning.md)
- [IaC/Automation](references/iac-automation.md)
- [Admin Tooling](references/admin-tooling.md)
