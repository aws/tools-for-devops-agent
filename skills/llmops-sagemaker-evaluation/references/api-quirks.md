# API Quirks

SageMaker read-only API responses whose obvious reading is **wrong** or misleading for a SageMaker-side evaluation review (traps §1–§2). Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs).

---

## 1. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource (LLM-AGT-004 / LLM-SM-003). Distinguish "zero measured" from "nothing reported." When reading the `LLMOps/Evaluation` custom-metric presence for EVAL-003, absent datapoints mean the scores were never published, not a measured zero.

## 2. A SageMaker-side eval runs as a recipe-driven training job

- **Trap:** An evaluation request reads as this skill's to catalogue regardless of which service runs it.
- **Correct reading:** A SageMaker-side eval runs as a recipe-driven training job — confirm the request is SageMaker-side before cataloguing it. A Bedrock-native `CreateEvaluationJob` is out of scope and routes to `llmops-quality-evaluation` (LLM-SM-EVAL-004); do not diagnose it here.
