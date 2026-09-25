# Report Format

Use this structure for chat responses and for the investigation root-cause summary.

```markdown
# GPU Training Cluster Investigation: <cluster or workload> (<account>/<region>)

**Impact window:** <start UTC> to <end UTC> (<source: user-provided | assumed last 24h>)
**Orchestrator:** <HyperPod Slurm | HyperPod EKS | Self-managed EC2 | EKS>
**Verdict:** <one sentence: primary branch, affected node(s), and trigger, labelled Proven or Hypothesis>
**Node verdicts:** <node: REPLACE | REBOOT | LEAVE ALONE | MONITOR | NOT OBSERVABLE, one line each>
**Confidence:** <High | Medium | Low>, <one-line basis>

## Timeline (UTC)

| Time | Source | Node / resource | Event |
|------|--------|-----------------|-------|
| ... | HMA log / Health / EC2 status / CloudTrail / Capacity Block / FSx metric | ... | ... |

## Node capability and fabric

| Node | Instance type | GPUs | EFA attached / max | NVSwitch (per reference table) | Fabric Manager | NCCL transport |
|------|---------------|------|--------------------|--------------------------------|----------------|----------------|
| i-... | p5.48xlarge | 8 | 32 / 32 | Yes | Started | Not observable (no NCCL lines shipped) |

## GPU error log coverage

| Node | Log source | Stream first / last event | Live across window | Kernel lines ever | Xids in window | Status |
|------|------------|---------------------------|--------------------|-------------------|----------------|--------|
| i-... | /aws/parallelcluster/.../system-messages | 09-23 16:19 / 09-23 16:24 | No | 2,666 | n/a | Not observable after 09-23 16:24 |
| i-... | customer kernel group | 09-23 16:24 / now | Yes | 404 | 0 | Measured |
| i-... (HyperPod) | HMA detections | no stream (expected when healthy) | Log group live | n/a | 0 | No HMA detections |

## Root cause

- **Branch:** <A hardware | B capacity lifecycle | C storage | D network | E cluster change | F application>
- **Evidence:** <timestamped signals on the affected nodes that precede the failure>
- **Why not the others:** see branch table

## Branch assessment

| Branch | Status | Evidence |
|--------|--------|----------|
| A GPU / node hardware | Root cause / Contributing / Ruled out / Not assessed / UNVERIFIED | ... |
| B Capacity lifecycle | ... | ... |
| C Storage (FSx for Lustre) | ... | ... |
| D Network (EFA / NCCL) | ... | ... |
| E Cluster change | ... | ... |
| F Application | ... | ... |

## Cluster state at investigation time

| Instance group | Type | Current / Target | Nodes not Running |
|----------------|------|------------------|-------------------|

NodeRecovery: <Automatic | None>. OnStartDeepHealthChecks: <list | none>.

## Recommended operator actions (not executed)

1. <action tied to the root-cause branch, with the exact CLI or console step and a doc link>
2. ...

## Visibility gaps

- <signals that could not be read through AWS APIs and what to collect, e.g. NCCL_DEBUG=INFO logs>
- <any query marked UNVERIFIED and why>
```

## Pre-flight report (Mode P)

```markdown
# GPU Cluster Pre-flight: <cluster> (<account>/<region>), planned run <N> h from <start UTC>

**Ready:** <Yes | Yes with risks | No>. <one sentence on the blocking item, if any>

| # | Check | Result | Evidence | Operator action |
|---|-------|--------|----------|-----------------|
| P1 | Reserved capacity outlasts the run | PASS / RISK / FAIL / UNVERIFIED / Needs input | ... | ... |
| ... | ... | ... | ... | ... |
```

Rules:

- Confidence is **High** only when the root-cause signal is on the affected node, precedes
  the failure, and no other branch has competing evidence.
- Every row in the branch table must have a status. An empty row is not allowed.
- Do not include training data, checkpoint contents, or model details.
- The headline must not say "hardware error" unless a node verdict is REPLACE or REBOOT on
  hardware grounds.
- Every cause is labelled `Proven` or `Hypothesis (to validate)` with the confirming
  measurement.
