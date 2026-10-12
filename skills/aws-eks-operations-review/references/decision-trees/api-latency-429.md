# Decision tree: API latency and HTTP 429 (throttling)

Use this when CP2/CP3 show elevated LIST latency, CP7/CP8 show 5xx, or CP13 shows 429s.
Do NOT conclude "the control plane needs more capacity" without walking this tree.

## Entry point

Identify which signal fired:
- High LIST latency (CP2 avg > 1s, CP3 max > 20s)
- HTTP 429 responses (CP7/CP13)
- HTTP 5xx responses (CP8)

## Branches

### Branch 1 — Noisy client (single caller dominating)

**Signal:** CP5/CP6 show one `userAgent` generating > 30% of total LIST or overall API volume.
**Evidence required:** Per-user-agent request count, the caller's identity (controller, CI tool, custom operator).
**Conclusion:** A single client is saturating the API. Fix the client (reduce polling frequency, add informers/caches, use watches instead of LIST).
**NOT:** "The control plane needs more capacity" — the capacity is fine; one client is abusing it.

### Branch 2 — Excessive LIST / unbounded queries

**Signal:** CP4 shows high LIST latency on specific resources (pods, secrets, configmaps).
**Evidence required:** Which resources are being LISTed, whether `limit`/`continue` pagination is used, response sizes (CP-M3).
**Conclusion:** Clients are doing unbounded LIST (no `limit` parameter) against large collections. Fix: add pagination, use watches, or scope to namespaces.
**NOT:** "etcd is slow" — the requests are too large.

### Branch 3 — API Priority and Fairness queueing

**Signal:** 429s concentrated in specific priority levels (CP13, `apiserver_flowcontrol_rejected_requests_total`).
**Evidence required:** Which priority level is rejecting (`system`, `leader-election`, `workload-high`, `workload-low`), queue depth, executing seats vs. nominal limit.
**Conclusion depends on priority level:**
- `workload-low` 429s → **Expected behavior** (APF protecting the cluster). Informational.
- `workload-high` 429s > 1% → **Client impact**. Identify the dominant caller; redistribute shares or fix the caller.
- `system` or `leader-election` 429s → **Critical**. Control-plane controllers are being throttled. Investigate what's consuming the seats (Branch 1 or Branch 4).

### Branch 4 — Admission webhook latency

**Signal:** CP-M4 shows `apiserver_admission_webhook_admission_duration_seconds` p99 > 1s.
**Evidence required:** Which webhook(s) are slow, their endpoint health, serial vs. parallel invocation.
**Conclusion:** Webhooks in the request path add latency to every API call. A single slow webhook (or an unreachable endpoint with a long timeout) makes the entire API feel slow.
**NOT:** "API server is overloaded" — the API server is fine; a webhook is holding up the response.
**Fix:** Reduce webhook timeout, fix the webhook endpoint, narrow the webhook's `rules` to reduce invocations, or switch `failurePolicy: Ignore` if appropriate.

### Branch 5 — Authentication / authorization retries

**Signal:** CP19 shows high 403 counts; CP9 shows elevated 4xx.
**Evidence required:** Which principals are being denied, whether they're retrying rapidly.
**Conclusion:** A controller or workload lost its permissions and is retry-looping against the API, generating load.
**NOT:** "API server throttling" — the load is artificial from a broken auth config.
**Fix:** Restore the RBAC binding or access entry, then the retry storm stops.

### Branch 6 — Controller retry storms

**Signal:** KCM workqueue_depth growing, high retry counts, one controller's QPS approaching 18–20.
**Evidence required:** CP14 (per-controller latency), workqueue metrics, controller logs.
**Conclusion:** A controller is failing to reconcile and retrying at its maximum QPS. This generates sustained API load that looks like saturation.
**NOT:** "Add API capacity" — fix the controller's reconciliation failure (often a missing resource, RBAC change, or upstream dependency).

### Branch 7 — Managed persistence pressure (etcd)

**Signal:** CP2/CP3 LIST latency high AND `apiserver_storage_size_bytes` > 6 GB (or `etcd_request_duration_seconds` p99 > 1s from CP-M5).
**Evidence required:** etcd size, write rate (CP10), growth rate, dominant resource types.
**Conclusion:** The managed etcd is under size/write pressure, causing slow reads. This is the legitimate "control-plane capacity" scenario.
**Fix:** Reduce object churn (clean up Events, CRDs, old Secrets), consider Provisioned Control Plane for the 16 GB tier, or reduce object count.
**Language:** "Evidence is consistent with managed persistence pressure" — never "the etcd disk is slow" (we don't have host access).

### Branch 8 — Actual control-plane capacity limitation

**Signal:** All of the above are ruled out; sustained 5xx (CP8), healthz failures (CP12), and the cluster is genuinely at scale limits.
**Evidence required:** This is the **only** branch that supports recommending Provisioned Control Plane or a capacity increase. It requires:
- Ruling out noisy clients (Branch 1)
- Ruling out unbounded LISTs (Branch 2)
- Ruling out webhook latency (Branch 4)
- Ruling out retry storms (Branch 6)
- Evidence of genuine saturation: `apiserver_current_inflight_requests` near ceiling, 5xx correlated with load, no single-caller explanation.
**Conclusion:** The cluster has legitimately outgrown Standard control-plane capacity.
**Fix:** Evaluate Provisioned Control Plane (XL/2XL/4XL) or architectural changes (split into multiple clusters, reduce API surface).

## Decision priority

Work through branches in this order (most common → least common):
1. Noisy client (Branch 1) — eliminates >50% of cases
2. Webhook latency (Branch 4) — the silent killer
3. Unbounded LIST (Branch 2)
4. APF queueing (Branch 3) — identify the priority level
5. Auth retries / controller storms (Branch 5/6)
6. etcd pressure (Branch 7)
7. Genuine capacity (Branch 8) — only after ruling out 1–6

## Disallowed conclusions

- "Upgrade to Provisioned Control Plane" before ruling out Branches 1–6.
- "The EKS control plane is slow" without specifying which component (API server? etcd? webhook?).
- "etcd is broken" — we never have direct etcd access; say "persistence pressure indicated by..."
- "APF is misconfigured" when 429s are only in `workload-low` (that's correct behavior).
