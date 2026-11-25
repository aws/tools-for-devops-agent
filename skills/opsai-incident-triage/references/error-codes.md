# Step 5b — the error-code enumeration, and the check-id it maps to

Produce this table before Step 6, one row per **distinct** `errorCode` actually observed —
never one row per error class:

| `errorCode` | Class | What it means — and what it does NOT mean | check-id | Remediation owner |
|---|---|---|---|---|
| `ValidationException` | 4xx | Malformed request, unsupported parameter, context too long, or a **model id that does not exist**. Not an entitlement problem. | LLM-INV-011 | caller's request shape / model id |
| `ResourceNotFoundException` | 4xx | The named resource (model, agent, alias, KB) **does not resolve in this region**. Distinct from being entitled-but-denied. | LLM-INV-003 | `bedrock-configuration` (model/alias lifecycle) |
| `AccessDeniedException` | 4xx | The model or action **exists** but the caller is **not entitled** — IAM, SCP, or model access not granted. Never a service fault. | LLM-INV-004 | `bedrock-configuration` (access) |
| `ThrottlingException` | 4xx (429) | Quota or capacity pressure. Check backoff before quota. On the `bedrock` binding it is counted in `InvocationThrottles`, **not** in `InvocationClientErrors` or `InvocationServerErrors`, so reconcile it against the THROTTLES slot. | LLM-INV-007 | quota/backoff |
| `ModelNotReadyException` | 4xx (429) | The model is not ready to serve inference requests; the AWS SDK retries it automatically, up to 5 times ([Converse errors](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)). Provider-side readiness, not the caller's request shape, despite the 4xx status. | LLM-INV-005 | retry/backoff |
| `ServiceUnavailableException` / `InternalServerException` | 5xx | Service-side transient. | LLM-INV-007 | retry/backoff/failover |

Three distinctions are load-bearing and must survive into the output, because each one changes the
fix handed to the user:

- **Does not exist** (`ValidationException` on a malformed or unknown model id) versus **exists but
  not entitled** (`AccessDeniedException`) versus **does not resolve here** (`ResourceNotFoundException`).
  These three are distinguished by **reading the code**, never by reasoning about the id. A bad model
  id in a `Converse` call returns `ValidationException`, not `ResourceNotFoundException`.
- **Each row names its calling principal.** The same code under two roles is two rows with two
  owners; the metric cannot tell you who called, and only CloudTrail `userIdentity` can.
- Each observed code gets **its own cause sentence and its own remediation**. Two codes sharing one
  remediation is a reportable contradiction, not a simplification.
- The 4xx/5xx **class** is an input to Step 6 only. It is never the answer to "what errors are you
  seeing" — codes are.
