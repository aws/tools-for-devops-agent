# Decision tree: OOMKilled containers

Use this when discovery finds `pods_oomkilled > 0`. Do NOT conclude "memory leak" without
walking this tree.

## Entry point

`kubectl describe pod <oomkilled-pod>` → read last termination state, restart count, and events.
Cross-reference with Container Insights `pod_memory_utilization` 7-day trend if available.

## Branches

### Branch 1 — Memory limit set too low

**Signal:** Container consistently uses near 100% of its memory limit before being killed.
Container Insights shows `pod_memory_utilization` near limit with flat (not growing) usage.
**Evidence required:** Pod memory limit vs. steady-state usage, startup peak, no upward trend.
**Conclusion:** The limit doesn't accommodate the application's legitimate working set.
**Fix:** Increase memory limit (and request) to accommodate peak + headroom (~20%).
**NOT:** "Memory leak" — usage is stable, just above the configured limit.

### Branch 2 — Legitimate burst (spike on specific events)

**Signal:** OOMKill correlates with specific operations (batch processing, cache warming, report generation).
**Evidence required:** OOMKill timestamps correlate with workload events; memory returns to baseline after restart.
**Conclusion:** The application has legitimate memory spikes during certain operations.
**Fix:** Increase limit for burst headroom, implement memory-aware batching, or use VPA.
**NOT:** "Memory leak" — it's a known burst pattern.

### Branch 3 — Application memory growth (potential leak)

**Signal:** Container Insights shows `pod_memory_utilization` **steadily increasing** over days/weeks
until OOMKill, then drops after restart and starts growing again (sawtooth pattern).
**Evidence required:** Multi-day memory trend showing consistent growth; pattern repeats after restarts.
**Conclusion:** Likely application memory leak — the application accumulates memory over time.
**Fix:** Application-level investigation (heap dumps, profiling); as a band-aid, increase limits or set
restart policies (but this doesn't fix the root cause).
**THIS is the only branch that supports a "memory leak" conclusion**, and it requires time-series evidence.

### Branch 4 — Sidecar memory not accounted for

**Signal:** Pod has multiple containers; the OOMKilled container's limit seems adequate for its own
workload, but the pod's total memory exceeds node/cgroup limits.
**Evidence required:** All container memory usage in the pod, sidecar resource consumption.
**Conclusion:** Sidecar containers (Istio proxy, log agent, X-Ray daemon) consume significant memory
that wasn't included in capacity planning.
**Fix:** Set explicit requests/limits on sidecars; account for sidecar overhead in pod sizing.
**NOT:** "Application memory leak" — the app is fine; sidecars are the hidden consumer.

### Branch 5 — Node memory pressure (kernel OOM, not container limit)

**Signal:** OOMKill happens at a pod level (not container), `nodes_memorypressure > 0`, node events
show "evicting pod due to memory pressure."
**Evidence required:** Node-level memory utilization, `MemoryPressure` condition, eviction events.
**Conclusion:** The node ran out of memory and the kernel OOM-killer or kubelet evicted the pod. This
is different from a container exceeding its own limit.
**Fix:** Increase node capacity, reduce pod density, set appropriate kubelet-reserved/system-reserved,
or add memory-based autoscaling.
**NOT:** "Container memory limit too low" — the container didn't exceed its limit; the node is overwhelmed.

### Branch 6 — Eviction due to ephemeral-storage pressure

**Signal:** Pod terminated with `Evicted` and reason `The node was low on resource: ephemeral-storage`.
**Evidence required:** Node `ephemeral-storage` condition, pod ephemeral-storage usage.
**Conclusion:** Disk pressure caused eviction, not memory. Sometimes confused with OOMKill.
**NOT:** "OOMKilled" — this is a storage issue, not memory.

### Branch 7 — JVM / runtime behavior

**Signal:** Java/Node.js/Go application with GC behavior; memory grows to near-limit then GCs.
**Evidence required:** Language runtime GC logs, heap settings (e.g. `-Xmx` vs container limit).
**Conclusion:** The runtime is configured to use more memory than the container allows. Common with
JVM where `-Xmx` is set close to the container limit without accounting for non-heap memory.
**Fix:** Set `-Xmx` to ~75% of container limit (leave room for non-heap), or use container-aware
GC flags (`-XX:MaxRAMPercentage`).
**NOT:** "Memory leak" — it's a configuration mismatch between runtime and container.

## Summary decision matrix

| Pattern | Root cause | Evidence needed | Severity |
|---------|-----------|-----------------|----------|
| Flat usage near limit → kill | Limit too low | Steady-state usage vs. limit | Medium |
| Spike correlates with events | Legitimate burst | Event correlation | Medium |
| Sawtooth growth over days | Likely leak | Multi-day time series | High |
| Multi-container pod | Sidecar overhead | Per-container usage | Medium |
| Node MemoryPressure + eviction | Node capacity | Node conditions | High |
| Disk eviction misclassified | Storage pressure | Eviction reason | Medium |
| JVM/runtime near limit | Heap misconfiguration | GC logs, -Xmx vs limit | Medium |

## Key rule

**A "memory leak" conclusion requires Branch 3 evidence: a sustained, repeating growth pattern
over multiple days visible in time-series data.** A single OOMKill, a spike during batch processing,
or usage near the configured limit does NOT constitute evidence of a leak.
