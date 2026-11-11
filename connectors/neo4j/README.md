# Neo4j

Steps to take before you connect. You run the official [Neo4j MCP server](https://github.com/neo4j/mcp) next to your self-managed Neo4j, and the agent reaches it over HTTPS. You need a Neo4j admin user for the setup and access to the VPC where Neo4j runs.

## Check your Neo4j

- Neo4j 2026.x Enterprise Edition. The read-only user below needs a custom role, and custom roles are an Enterprise feature.
- The database is named `neo4j`. The connector always connects to that database. For a database with another name, add the MCP server as your own MCP server instead of using this connector.
- APOC is installed in the version that matches the server, for example with `NEO4J_PLUGINS=["apoc"]` in the Docker image or the Helm chart. The MCP server won't start a session without it.

## Create a read-only user

The agent's credential is a Neo4j native user with a single diagnostics role. Never use an admin user: the MCP server's read-only mode still allows `TERMINATE TRANSACTION`, and an admin user can end other users' transactions with it.

As an admin, run this against the `system` database:

```cypher
CREATE ROLE devops_agent_diag IF NOT EXISTS;
GRANT SHOW TRANSACTION (*) ON DATABASE * TO devops_agent_diag;
GRANT SHOW SETTING * ON DBMS TO devops_agent_diag;
GRANT SHOW INDEX ON DATABASE * TO devops_agent_diag;
GRANT SHOW CONSTRAINT ON DATABASE * TO devops_agent_diag;
DENY LOAD ON ALL DATA TO devops_agent_diag;
CREATE USER devops_agent IF NOT EXISTS SET PASSWORD '<password>' CHANGE NOT REQUIRED;
GRANT ROLE devops_agent_diag TO devops_agent;
```

With this role the agent sees running transactions, settings, indexes, constraints and the APOC version. It can't read graph data, so `get-schema` returns nothing, and `LOAD CSV` is denied. `SHOW SETTINGS` masks secret values.

To rotate the password, run `ALTER USER devops_agent SET PASSWORD '<new password>' CHANGE NOT REQUIRED;` and enter the new value in the connection. To revoke access, run `ALTER USER devops_agent SET STATUS SUSPENDED;` or `DROP USER devops_agent;`.

## Run the MCP server

Run `neo4j/mcp` v2.1.0 or later in the same VPC as Neo4j, in HTTP mode with TLS and read-only mode. For example, with the `neo4j/mcp:v2.1.0` image:

```text
--transport-mode http --http-host 0.0.0.0 --http-port 8443
--http-tls-enabled true --http-tls-cert-file /tls/server.crt --http-tls-key-file /tls/server.key
--http-allowed-uris <neo4j-host>:7687 --read-only true --telemetry false
```

- `--http-allowed-uris` lists the Bolt `host:port` entries the server may connect to. A request for any other address gets HTTP 400.
- Telemetry is on by default. `--telemetry false` turns it off.
- The image runs as user 65532 and has no shell, so mount the certificate and key files readable by that user.
- The certificate must match the host name you enter in the connection form. A Common Name is limited to 64 characters, so put a longer load balancer name in the Subject Alternative Name.

## Reach the server

If the server isn't reachable from the internet on port 443, create a [private connection](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-to-privately-hosted-tools.html) to it, with its port in the port ranges, and select it when you connect. If the certificate comes from a private certificate authority, add that authority's certificate to the private connection. When the server's address can change, as a Fargate task's does, put it behind an internal Network Load Balancer and connect to the load balancer.

## Fill in the connection form

| Field | Value | Example |
| --- | --- | --- |
| **Neo4j MCP server host** | Host name of the MCP server or its load balancer | `neo4j-mcp.internal.example.com` |
| **Neo4j MCP server port** | Port the server listens on | `8443` |
| **Neo4j user and password (base64 of user:password)** | Output of `printf '%s' 'devops_agent:<password>' \| base64` | |
| **Neo4j Bolt URI** | Bolt URI of the Neo4j server, with its scheme: `bolt://` or `neo4j://`, or `bolt+s://` or `neo4j+s://` when Bolt uses TLS. Its host and port must be in `--http-allowed-uris` | `bolt://neo4j.internal.example.com:7687` |

When you connect, AWS DevOps Agent calls the server to list its tools, so a wrong password fails the connection with `Unable to access tools from the MCP server`.

## Choose the tools

Keep `read-cypher` enabled. The `neo4j-support-specialist` skill runs only its own listed read-only queries through it. You can turn off `get-schema`, which returns nothing for this user. The server doesn't offer `write-cypher` in read-only mode, or `list-gds-procedures` when Graph Data Science isn't installed.

While the `neo4j` database is stopped, the server can't start a session. Investigations that start then don't get the tool and work from logs.
