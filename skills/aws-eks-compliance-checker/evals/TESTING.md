# Testing record

Results from `devops-agent skill-eval` 0.1.0, with judge `us.anthropic.claude-sonnet-5` in us-east-1. They are committed under `evals/structure/` (v2), `evals/best-practices/v2/`, and `evals/functional/v6/`. Structure and best-practices ran on 2026-11-18 and functional on 2026-11-19.

## Test cluster

The three `eks-compliance-live-*` cases and the manual runs below used a temporary cluster built for this purpose and deleted afterwards. It ran EKS 1.37 with two AL2023 `t3.medium` managed nodes, and had these deliberate settings:

- Public endpoint open to `0.0.0.0/0`, only the `api` log type, no KMS `encryptionConfig`, nodes in public subnets, unencrypted node volumes, and `API_AND_CONFIG_MAP` with an `aws-auth` `mapUsers` entry in `system:masters`.
- Namespace `team-a`: a privileged pod, a `hostNetwork` pod, and a Deployment reading a Secret through an env var, with no NetworkPolicy.
- Namespace `default`: one Deployment.
- RBAC: a `*`/`*`/`*` ClusterRole bound to group `contractors`, and `cluster-admin` bound to group `ops-team`.
- Namespace `secure-ns` as the compliant control: PSA `restricted`, default-deny NetworkPolicy, and a hardened pod.

An answer key for all 50 CIS controls and the nine AWS-n checks was written from direct reads before any agent ran.

## Results

These runs were made after the rename to `aws-eks-compliance-checker`, against a fresh build of the same test cluster.

| Tier | Result |
|---|---|
| structure | 12/12 (100%) |
| best-practices | 100% / 100% / 100%, consistency 100% (14 passed, 3 skipped as not applicable: no `assets/`) |
| functional | 11 cases × 3 iterations; 63/63 iterations ran (the negative smoke test runs with the skill only) |
| manual full check, `AmazonEKSAdminViewPolicy` | 59/59 statuses match the answer key |

| Case | Skill loaded | Expected output (with / without) | Assertions (with / without) |
|---|---|---|---|
| `eks-compliance-smoke-test` (should not trigger) | correctly not loaded 3/3 | n/a | n/a |
| `eks-compliance-cis-542-restricted-cidr` | 3/3 | 3/3 / 0/3 | 12/12 / 6/12 |
| `eks-compliance-audit-log-api-only` | 3/3 | 3/3 / 0/3 | 12/12 / 6/12 |
| `eks-compliance-denied-read` | 3/3 | 3/3 / 0/3 | 9/9 / 6/9 |
| `eks-compliance-section3-not-covered` | 3/3 | 3/3 / 3/3 | 9/9 / 6/9 |
| `eks-compliance-no-invented-cve` | 3/3 | 3/3 / 0/3 | 12/12 / 8/12 |
| `eks-compliance-auth-mode-configmap` | 3/3 | 3/3 / 3/3 | 9/9 / 9/9 |
| `eks-compliance-cis-only-scope` | 3/3 | 3/3 / 0/3 | 9/9 / 0/9 |
| `eks-compliance-live-cis-aws-controls` (live cluster) | 3/3 | 3/3 / 0/3 | 18/18 / 0/18 |
| `eks-compliance-live-rbac-workloads` (live cluster) | 3/3 | 3/3 / 0/3 | 15/15 / 12/15 |
| `eks-compliance-live-pci-crosswalk` (live cluster) | 3/3 | 3/3 / 2/3 | 15/15 / 10/15 |

With the skill uploaded, 30/30 expected outputs and 120/120 assertions passed, against 8/30 and 63/120 without it.

## How to read this

- **The harness grants `AmazonAIOpsAssistantPolicy`, not `AmazonEKSAdminViewPolicy`.** That policy denies listing ClusterRoles, ClusterRoleBindings, and Roles, so in the live cases the skill reports CIS 4.1.1 and 4.1.3 as `Not assessed` with the Forbidden error, which is the expected behaviour. The full RBAC grading was checked in the manual run instead.
- **Manual full check.** A separate agent space was given `AmazonEKSAdminViewPolicy` and asked for the full benchmark plus the PCI DSS crosswalk. During development, the first run matched 58 of 59 statuses and exposed the rule defects fixed below. After the fixes and the rename, the check matched all 59, rendered the PCI DSS 1.4.4, 10.2.1, and 12.3.4 rows with `Security Hub EKS.1/EKS.8/EKS.2` basis, and included the disclaimer.
- **Defects the live cluster exposed, fixed before the committed runs:**
  - CIS 4.3.1 treated the `aws-eks-nodeagent` container as proof of network policy. The container is present even when `--enable-network-policy=false`, so the rule now reads the flag.
  - CIS 5.5.1 required IAM roles and graded an IAM user as a failure, which is stricter than the benchmark. It now passes any IAM principal and recommends roles.
  - AWS-6 had no answer for clusters whose images are not in the account's ECR. It now reports `Not assessed` and names the registries.
  - `upgradePolicy.supportType=EXTENDED` on a standard-support version could be misread as extended support. AWS-2 is decided from `versionStatus`, and a gotcha says so.
  - The crosswalk basis now names the Security Hub control (`Security Hub EKS.1`), not just `Security Hub`.
  - The Inspector coverage read now pages through `nextToken`.
  - The access probes no longer use `get --raw /version` and `auth can-i --list`, which the read-only `use_kubectl` interface rejects.
- **Cases that barely separate the two sides.** `auth-mode-configmap` passes without the skill, because any model flags a `system:masters` user mapping. `section3-not-covered` passes on expected output without it, because any model declines to run a Job in a read-only review. The skill adds the `Not covered` status and the kube-bench `eks-1.8.0` recommendation.
- **Prompt wording.** Five scenario prompts (`cis-542-restricted-cidr`, `audit-log-api-only`, `denied-read`, `section3-not-covered`, `auth-mode-configmap`) now open with "Run an EKS compliance check…" instead of "During an EKS compliance check…". In runs on 2026-11-18 the agent often answered the old wording from general knowledge without reading the skill. The expected outputs and assertions are unchanged.
- **Runs discarded before the committed one.** Functional runs v2 to v5 on 2026-11-18 were not kept. In each, 5 to 14 of the 63 runs failed with the DevOps Agent tool-service errors `Missing required context: remote_toolbox` or `TOOLBOX_UNAVAILABLE ... (bind_wait_timeout)`. Also, at 17:01 UTC an account cleanup automation scaled the test node group to zero at shift end, which removed the bare test pods; the node group's Auto Scaling group was then exempted and the pods re-applied. The committed v6 run had no tool-service errors, ran with at most 6 agent spaces at a time, and checked that the test pods were present before starting.
- **Redaction.** The real account ID was replaced with `123456789012`, node public IPs with `198.51.100.x`, and subnet, VPC, security group, launch template, ENI, volume, node group, and agent role identifiers with placeholders. The EKS ECR registry account `602401143452` is AWS-owned and allowlisted.
