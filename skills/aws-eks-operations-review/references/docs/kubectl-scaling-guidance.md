# kubectl scaling guidance (large clusters)

- **Do not** fetch `kubectl get pods -A -o json` on clusters with thousands of pods — it can pressure the API server and blow context. Instead:
  - Use `kubectl get pods -A -o wide` or field-selectors for status counts (`--field-selector=status.phase=Pending`).
  - Scope per namespace and iterate.
  - For pod-spec detail (probes, requests, securityContext), sample representative namespaces rather than the whole cluster.
- Pace calls: run areas sequentially. Confirm with the user before a broad sweep on production.
- Cap detail: when an area returns hundreds of items, summarize counts and inspect a bounded sample (the original tool capped detailed views at 30–50 items).

