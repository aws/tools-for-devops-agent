# Vornik

Steps to take before you connect. [Vornik](https://vornik.io) is an agent harness you run yourself. Its companion MCP endpoint gives an investigation your incident memory (`recall`) and the procedures an operator approved. If you allow it, it also gives a write path (`remember`) and follow-up work in a sandboxed container on your models. You run Vornik yourself, and the agent calls your Vornik directly. Vornik sends nothing to its vendor.

> This is sample configuration, not intended for production use without additional review and testing. Validate it in a non-production environment first.

## Mint a key for the agent

On the Vornik host, give the agent its own project and a key. The key's scopes decide which tools the connection lists. The read-only profile follows AWS's advice to allowlist read-only tools:

```bash
vornikctl init project --template companion devops-agent --config-dir "$HOME/.config/vornik/configs"
vornikctl config reload
vornikctl companion grant --project=devops-agent --client=aws-devops-agent \
  --label="agent-space/<name>" --memory-read --skill-read --no-delegate --expires=<YYYY-MM-DD>
```

This key lists `recall`, `recent_memory`, `memory_list`, `list_scopes`, `skill_search`, `skill_get`, `skill_list`, `whoami` and `report_problem`. On a Vornik-hosted instance, choose **Connect AWS DevOps Agent** on the console's **Connect your companion** page instead. For write-back and delegation, see the [Vornik guide](https://docs.vornik.io/guides/aws-devops-agent/). The grant prints the key, `sk-vornik-…`, once.

## Reach Vornik

Vornik's daemon serves plain HTTP on its own port, so put TLS in front of it.

- **In your VPC:** create a [private connection](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-to-privately-hosted-tools.html) to the TLS endpoint, with its port in the port ranges, and select it when you connect. If the certificate comes from a private certificate authority, add that authority's certificate to the private connection.
- **Over the internet:** Vornik's installer can put Caddy in front of the daemon (`VORNIK_PUBLIC_HOSTNAME=<name>`). Allow port 443 only from the DevOps Agent IP addresses on the [security page](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security.html).

Expose only the TLS port: the daemon's own port (8080 by default) serves plain HTTP, so keep it on loopback or close it in the firewall. Without a valid key, the endpoint answers 401.

## Fill in the connection form

| Field | Value | Example |
| --- | --- | --- |
| **Vornik host name** | Host name in the certificate | `vornik.internal.example.com` |
| **Vornik HTTPS port** | Port TLS listens on | `443` |
| **Vornik companion key** | The `sk-vornik-…` key from the grant | |

When you connect, AWS DevOps Agent lists the tools, so a wrong key fails the connection. In the Agent Space, allowlist the tools your key's profile lists.

## Try it

In the Agent Space chat:

> Before you investigate, use the Vornik tools to recall what we know about past incidents on the `checkout` service, and list any approved procedures for it.

The agent calls `recall` and `skill_search` and cites what they return.

## Rotate or revoke

Mint a new key, enter it in the connection, then run `vornikctl key revoke <keyID> -p devops-agent` for the old one (`vornikctl companion keys -p devops-agent` lists the IDs).

## Support

Vornik issues: <https://github.com/EaseIT-cz/vornik/issues>. Guide: <https://docs.vornik.io/guides/aws-devops-agent/>.
