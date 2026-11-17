# API Quirks

SageMaker read-only API responses whose obvious reading is **wrong** or misleading for a batch transform / offline-scoring review (traps §1–§2). Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs).

---

## 1. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource (LLM-AGT-004 / LLM-SM-003). Distinguish "zero measured" from "nothing reported."

## 2. A transform job `Completed` ≠ every record scored

- **Trap:** A transform job `TransformJobStatus: Completed` reads as "every record was scored."
- **Correct reading:** A transform job `TransformJobStatus: Completed` is not proof every record was scored — the output `.out` object count can be short of the input record count (partial/failed records). Reconcile output against input with `ListObjectsV2`; treat `Completed` as "ran to the end", not "scored everything" (LLM-SM-BATCH-003).
