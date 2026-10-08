# Amazon Bedrock Best Practices Checklist

Organized by pillar. Maps directly to the checks in `SKILL.md` Step 4.

## Security

- [ ] **Guardrails** configured for high-volume workloads (filter hate, insult, sexual, violence, PII; block use-case-relevant denied topics)
- [ ] **Guardrail signals** healthy — `InvocationClientErrors` < 5% of `Invocations`; `InvocationsIntervened` in the 5–15% range on active guardrails
- [ ] **Model invocation logging** configured appropriately for the data-sensitivity profile (do NOT log prompt/output for production PII/PCI/HIPAA content)
- [ ] **Knowledge Base configuration** — chunk size 200–1000 tokens, sound embedding strategy, monitoring, error handling with retry logic
- [ ] **Knowledge Base data source encryption** — customer-managed KMS key when handling sensitive content
- [ ] **VPC configuration for model customization jobs** — training data not reachable from the internet; VPC Flow Logs enabled
- [ ] **IAM fine-grained access control** — agent/alias policies scoped to specific resources; resource `*` justified and documented
- [ ] **Knowledge Base logging** — KB ingestion log delivery configured; CloudTrail + CloudWatch enabled for anomaly detection
- [ ] **Prompt injection** — prompt templates hardened per prompt-engineering best practices
- [ ] **Model access** — scoped to only the essential, legally approved models (least privilege)

## Performance

- [ ] **Latency & throttling** — throttle rate low; retries use exponential backoff with jitter; smaller models and streaming used for latency-sensitive apps
- [ ] Application deployed in the same region as the Bedrock endpoint to minimize network latency
- [ ] `max_tokens` set no higher than needed; lower temperature where deterministic output suffices
- [ ] **Agent performance** — latency-optimized flow eligibility met (single KB, no enabled action groups, no follow-up questions, default orchestration template)
- [ ] **Invoked model versions** — no Legacy or End-of-Life models still receiving production traffic; upgrade plan documented
- [ ] **Data automation** — success rate > 95%, error rate < 5%, throttle rate < 1%
- [ ] **Service tier** aligned to workload (Reserved/Priority for latency-sensitive; Flex for cost-tolerant batch)

## Service Quotas

- [ ] **Model quotas** — RPM/TPM (including CRIS and Global CRIS) utilization < 75%; increases requested proactively
- [ ] **Guardrail service quotas** — ApplyGuardrail requests and text-unit consumption < 75% of quota; Classic vs Standard policy usage reviewed manually when both configured
- [ ] CloudWatch alarms set for high quota-utilization thresholds

## Cost Optimization

- [ ] **Application inference profiles** used for cost allocation / usage tracking via Cost Allocation Tags
- [ ] **Custom model distillation** evaluated for narrow, repetitive, high-volume tasks on premium large models (candidate rule: p99 latency > 3000 ms + input tokens > 1M/month + throttle rate > 5%)
- [ ] **Prompt caching** enabled and optimized (cache offload ≥ 50%) for input-heavy repeated-context workloads
- [ ] **Prompt management** used for versioning and variant testing (cost/quality tradeoffs)
- [ ] **Intelligent prompt routing** used for mixed-complexity workloads within a model family
- [ ] **Provisioned throughput** balanced against on-demand; no idle or soon-to-expire provisioned models on unused workloads
- [ ] **Batch inference** used for high-volume (> 10K/day), latency-tolerant, or scheduled workloads (up to ~50% savings); self-managed batch migrated to managed Batch Inference where models are available
- [ ] **EC2 GPU utilization** (self-managed) — no sustained under-utilization (< 40%), memory pressure (> 90%), bursty usage (CV > 0.5), or un-committed high sustained usage (> 80%)

## Resilience

- [ ] **Cross-Region Inference (CRIS)** adopted where burst resilience or data-residency matters; adoption % high (traffic routed through inference profiles, not direct base-model invocations)

## CloudWatch Alarm Coverage (recommended)

- [ ] Throttling — `InvocationThrottles` alarm per high-value model
- [ ] Latency — `InvocationLatency` p95 threshold alarm
- [ ] Server errors — `InvocationServerErrors` alarm
- [ ] Guardrail interventions — `InvocationsIntervened` trend alarm
- [ ] Quota utilization — alarm approaching RPM/TPM limits
