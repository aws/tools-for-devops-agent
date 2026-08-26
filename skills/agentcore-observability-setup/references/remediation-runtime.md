# Remediation — AgentCore Runtime Agents

Copy-pasteable remediation for gaps found on the runtime path. All steps are applied by the
customer; the skill only generates them.

---

## 1. Enable CloudWatch Transaction Search (account prerequisite)

Without Transaction Search, spans are not delivered to CloudWatch Logs — traces never appear.

**Console:** CloudWatch → Application Signals (APM) → Transaction search → **Enable Transaction
Search** → select **ingest spans as structured logs** → Save.

**Effect:** X-Ray trace segments are ingested into CloudWatch Logs so AgentCore can deliver spans.

---

## 2. Code-level instrumentation (ADOT SDK)

Add to `requirements.txt`:

```
aws-opentelemetry-distro>=0.10.0
boto3
```

Use `aws-opentelemetry-distro>=0.18.0` if you want spans delivered to the agent's **own** log group
(unified span destination) rather than the shared `aws/spans` group.

Launch the agent with auto-instrumentation:

```bash
opentelemetry-instrument python my_agent.py
```

Containerized:

```dockerfile
CMD ["opentelemetry-instrument", "python", "main.py"]
```

Ensure the framework emits traces (e.g. configure the Strands tracer, or add the matching
auto-instrumentor such as `opentelemetry-instrumentation-langchain`). Supported instrumentation
libraries: OpenInference, Openllmetry, OpenLit, Traceloop.

---

## 3. Span destination (unified vs shared)

Set on the agent runtime environment:

- Opt in to the agent's own log group: `UNIFIED_TRACES_DESTINATION_ENABLED=true`
- Opt out (use shared `aws/spans`): `UNIFIED_TRACES_DESTINATION_ENABLED=false`

Requires ADOT ≥ 0.18.0; earlier versions ignore this and use `aws/spans`.

---

## 4. X-Ray resource policy on the agent log group (unified destination)

When delivering spans to the agent's own log group, the agent execution role needs
`logs:PutResourcePolicy`, and a CloudWatch Logs resource policy must allow X-Ray to write:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowXRayToPutSpans",
      "Effect": "Allow",
      "Principal": { "Service": "xray.amazonaws.com" },
      "Action": "logs:PutLogEvents",
      "Resource": "arn:aws:logs:<region>:<account-id>:log-group:/aws/bedrock-agentcore/runtimes/<agent-id>-<endpoint>:*"
    }
  ]
}
```

---

## 5. Session-id propagation

Set the session-id header when invoking the runtime so ADOT stamps `session_id` on downstream
telemetry:

```
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: <session-id>
```

For W3C cross-service correlation, propagate `traceparent`.

---

## Third-party observability platforms

To route telemetry to a non-AWS platform, set `DISABLE_ADOT_OBSERVABILITY=true` on the runtime.
This unsets the default ADOT environment. Note: this intentionally disables AWS-side observability —
flag it if the customer expects CloudWatch data.
