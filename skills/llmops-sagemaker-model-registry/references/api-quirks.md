# API Quirks

SageMaker read-only API responses whose obvious reading is **wrong** or misleading for a Model Registry governance review (traps §1–§2). Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs).

---

## 1. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource (LLM-AGT-004 / LLM-SM-003). Distinguish "zero measured" from "nothing reported."

## 2. An `Approved` package in the registry ≠ the deployed version is approved

- **Trap:** A model package in `ListModelPackages` with `ModelApprovalStatus: Approved` reads as "the group is governed."
- **Correct reading:** A model package in `ListModelPackages` with `ModelApprovalStatus: Approved` is only governed if the version that is actually deployed/staged is that approved version — a newer `PendingManualApproval`/`Rejected` version can be the one live. Resolve which version is deployed before clearing a group as approved (LLM-SM-REG-002).
