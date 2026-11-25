# API Quirks

SageMaker read-only API responses whose obvious reading is **wrong** or misleading for a real-time, serverless/async or batch transform review (traps §1–§4). Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs).

---

## 1. SageMaker endpoint `InService` with `CurrentInstanceCount` = 0

- **Trap:** `DescribeEndpoint` `EndpointStatus: InService` reads as healthy and serving.
- **Correct reading:** A variant can be `InService` yet report `CurrentInstanceCount: 0` (scaled in, scale-to-zero async/serverless, or a misconfigured leftover). `InService` is control-plane state, not proof of serving capacity → check instance count and recent `Invocations`; async endpoints do not publish `Invocations`, so read the backlog metrics instead (LLM-SM-003).

## 2. `DescribeScalableTargets` empty ≠ no scaling intended

- **Trap:** An empty scalable-targets response reads as "auto-scaling is simply off, low severity."
- **Correct reading:** For a production endpoint, empty means **fixed capacity** — it cannot absorb spikes or scale in to save cost (LLM-SM-001, HIGH). Confirm it's registered under `application-autoscaling` with namespace `sagemaker`, resource id `endpoint/<name>/variant/<variant>`; a wrong resource-id lookup also returns empty and can be mistaken for "no scaling."

## 3. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource (LLM-SM-003). Distinguish "zero measured" from "nothing reported."
- **Serverless and async signals:** `ModelSetupTime` and `ApproximateBacklogSizePerInstance` are read from CloudWatch, so an absent datapoint must not be read as "no cold start" or "empty queue" (LLM-SM-SERVE-001, LLM-SM-SERVE-004).

## 4. A transform job `Completed` ≠ every record scored

- **Trap:** A transform job `TransformJobStatus: Completed` reads as "every record was scored."
- **Correct reading:** A transform job `TransformJobStatus: Completed` is not proof every record was scored — batch transform writes one `<input>.out` per input file, only when every record in that file succeeded, so the `.out` count can be short of the input **file** count ([batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)). Reconcile output files against input files with `ListObjectsV2`; treat `Completed` as "ran to the end", not "scored everything" (LLM-SM-BATCH-003).
