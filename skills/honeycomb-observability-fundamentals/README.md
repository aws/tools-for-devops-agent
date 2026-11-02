# Honeycomb Observability Fundamentals Skill

This skill enables the AWS DevOps Agent to answer conceptual questions about observability and Honeycomb from first principles.

## Purpose

Recommendations about instrumentation and investigation are easier to trust when they rest on first principles. The skill explains wide events, high cardinality and dimensionality, events vs metrics vs logs, and the core analysis loop.

## Key Capabilities

- Explain what observability is and how it differs from monitoring
- Explain why Honeycomb recommends wide events
- Explain high cardinality and dimensionality
- Compare events, metrics and logs
- Describe the core analysis loop

## Prerequisites

- None to answer questions. Applying the ideas to your data needs the Honeycomb connector in your Agent Space.

## Limitations

- Not for running queries or investigating a live issue. Use the Honeycomb Production Investigation skill for that.

## Agent Types

This skill is used by the following agent types:

- **Chat tasks** — questions the operator asks in chat

## Installing

When you add the Honeycomb connector, the DevOps Agent console offers this skill to install. You can also import it from this repository: in the DevOps Agent web app, go to Settings → Add Skill → Import from repository, and point to the `skills/honeycomb-observability-fundamentals` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

## How to Use This Skill

### Chat

- "Why does Honeycomb recommend wide events instead of separate metrics for each dimension?"
- "What does high cardinality mean, and why is it a problem for some tools but not Honeycomb?"
- "What is the difference between events, metrics and logs?"

## Non-production disclaimer

> ⚠️ Maintained by Honeycomb. The skill only reads from Honeycomb. Validate it in a non-production environment first.
