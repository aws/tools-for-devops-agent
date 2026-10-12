# Control Plane customer-facing finding copy

Load this reference only after a Control Plane FAIL is known and the mapped remediation playbook has been selected. It defines response wording, not a continuous-monitoring or delivery workflow. The review renders findings directly in the final response and creates no runtime files.

## Language rules

- Never use internal incident severity numbers. Use the descriptive label.
- Never expose internal tool names, employee aliases, credentials, Secret values, or PII.
- Every claim cites the observed metric/query, source, and time window.
- State managed-service boundaries precisely; do not claim direct access to etcd members or control-plane hosts.
- Keep the first sentence plain and actionable: what is wrong, why it matters, and whether action is required.

## Descriptive labels

| Internal tier | Customer-facing label |
|---|---|
| Critical | Action required — control plane impaired |
| High | Action required — control plane saturation risk |
| Medium | Attention — operational hygiene |
| Informational | Healthy — informational |

Informational signals are not FAIL findings.

## Finding response block

```text
### {check_id} — {title}
**Impact label:** {customer_facing_label}
**Observed evidence:** {value, source, query/metric, UTC window}
**Why it matters:** {cluster-specific impact}
**Likely contributing condition:** {only when evidence and decision tree support it}
**Recommended action:**
1. {least-disruptive step}
2. {verification step}
3. {escalation step only if the condition remains}
**Confidence:** {high | medium | low, with source-agreement reason}
**References:** {authoritative AWS/Kubernetes links}
```

## Evidence wording examples

- etcd: “Evidence from `apiserver_storage_size_bytes` is consistent with managed persistence pressure.”
- APF: distinguish privileged-tier throttling from expected `workload-low` protection.
- API latency: name the verb/resource and percentile; do not average histogram instances incorrectly.
- Scheduler: unschedulable pods are a workload/scheduling signal, not proof that the scheduler is broken.
- Eviction: identify the blocking PDB/finalizer evidence before asserting cause.

## Delivery boundary

This skill only returns the review response. It does not page, post to chat, create tickets, schedule scans, maintain mute state, diff prior runs, or send connector payloads. Those are separate user-configured automation capabilities.