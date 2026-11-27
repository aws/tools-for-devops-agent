# Testing record

Results from `devops-agent skill-eval` 0.1.0, with judge `us.anthropic.claude-sonnet-5` in us-east-1. They are committed under `evals/structure/` (v3), `evals/best-practices/v3/`, and `evals/functional/v7/`. All three ran on 2026-11-19 against the final `SKILL.md` and references in this PR.

## Test clusters

Both clusters were built for this testing and deleted afterwards. Their CloudFormation templates and Kubernetes manifests are in [`test-clusters/`](test-clusters/).

- **`cis-skill-test`** (planted violations): EKS 1.37, two AL2023 `t3.medium` managed nodes in public subnets, unencrypted node volumes, public endpoint open to `0.0.0.0/0`, only the `api` log type, no KMS `encryptionConfig`, and `API_AND_CONFIG_MAP` with an `aws-auth` `mapUsers` entry in `system:masters`. Namespace `team-a` has a privileged pod, a `hostNetwork` pod, and a Deployment reading a Secret through an env var. Namespace `default` has one Deployment. RBAC binds a `*`/`*`/`*` ClusterRole to group `contractors` and `cluster-admin` to group `ops-team`. Namespace `secure-ns` is a compliant control.
- **`cis-skill-compliant`** (false-FAIL check): EKS 1.37, nodes in private subnets behind a NAT gateway, encrypted volumes, IMDSv2 required, KMS secrets encryption, all five log types with 30-day retention, authentication mode `API`, VPC CNI network policy on, and a hardened workload with automount off, PSA `restricted`, and default-deny NetworkPolicies. The public endpoint stays open because DevOps Agent reached the cluster API over it, so CIS 5.4.1 and 5.4.2 are its only expected FAILs.

Both clusters carry the read-only `devops-agent-cis-reader` ClusterRole from `references/permissions.md`.

**ClusterRole trim after the committed run.** After review, `nodes`, `replicasets`, `jobs`, and `cronjobs` were removed from the ClusterRole, because no K1–K13 read uses them. The committed functional run used the role before the trim. On 2026-11-20 both clusters were rebuilt and the trimmed role was checked with a real IAM role through its Kubernetes group: every K1–K13 read succeeded on both clusters (`aws-auth` returns NotFound on `cis-skill-compliant`, which uses `API` mode), and `nodes`, `replicasets`, `jobs`, `cronjobs`, Secrets, other ConfigMaps, pod logs, and writes were denied. Answer keys regenerated from the rebuilt clusters match the committed keys on every control and framework row. Two full functional re-runs that day were not kept: in each, 8 to 20 of 87 runs hit the DevOps Agent tool-service outage. The rebuilt test cluster routes node egress through a NAT gateway, because the account's VPC Block Public Access setting stopped nodes in public subnets from joining; the nodes still get public IPs, so 5.4.3 still fails.

## Answer keys

[`answer-key/key-cis-skill-test.json`](answer-key/key-cis-skill-test.json) and [`answer-key/key-cis-skill-compliant.json`](answer-key/key-cis-skill-compliant.json) hold the expected status, evidence, and source reads for all 50 CIS controls and AWS-1 to AWS-9, every row of the four framework crosswalks, and the statuses each control may take under `AmazonAIOpsAssistantPolicy`. They were generated before the committed run, from direct reads with cluster-admin access, by applying each written rule mechanically.

| Cluster | PASS | FAIL | Manual review | Not assessed | Not covered |
|---|---|---|---|---|---|
| `cis-skill-test` | 9 | 27 | 8 | 2 | 13 |
| `cis-skill-compliant` | 36 | 2 | 6 | 2 | 13 |

[`answer-key/per-control-comparison.md`](answer-key/per-control-comparison.md) compares every iteration's report with the key, control by control. The JSON version also holds each iteration's parsed statuses.

## Results

| Tier | Result |
|---|---|
| structure | 12/12 (100%) |
| best-practices | 100% / 100% / 100%, consistency 100% (14 passed, 3 skipped as not applicable: no `assets/`) |
| functional | 15 cases × 3 iterations; 87/87 iterations ran (the negative smoke test runs with the skill only) |

### Full-benchmark cases, compared control by control

| Case | Access | With skill | Without skill |
|---|---|---|---|
| `live-full-benchmark` (`cis-skill-test`) | `devops-agent-cis-reader` ClusterRole | 59/59 controls in each of 3 iterations | 51/59 and 34/59; one run hit the tool-service outage. Wrong statuses included 4.3.1 PASS (network policy off), 4.1.6, 5.1.1, and 5.2.1 FAIL |
| `live-full-benchmark-default-policy` (`cis-skill-test`) | `AmazonAIOpsAssistantPolicy` | 59/59 in each of 3; no denied control reported as PASS | 25/59 and 39/59; one run hit the outage. It also gave no denied RBAC control PASS, but graded 4.1.6 and 4.4.2 FAIL from denied reads and 4.3.1 PASS |
| `live-compliant-cluster` (`cis-skill-compliant`) | `devops-agent-cis-reader` ClusterRole | 59/59 in each of 3; no false FAIL | 35/59, 43/59, and 27/59, with false FAILs on 4.1.5, 4.2.1, 4.2.4, 4.2.5, 4.3.2, 5.1.1, and AWS-9 |
| `live-all-frameworks` (`cis-skill-test`) | `devops-agent-cis-reader` ClusterRole | 40/40 crosswalk rows (13 NIST, 12 PCI DSS, 7 SOC 2, 8 HIPAA) in each of 3 | full reports, but one row per CIS control with framework columns, not per-framework rows with a derived status, so they can't be compared row by row |

No control changed status between the three with-skill iterations of any of these cases.

### All cases

| Case | Skill loaded | Expected output (with / without) | Assertions (with / without) |
|---|---|---|---|
| `eks-compliance-smoke-test` (should not trigger) | correctly not loaded 3/3 | n/a | n/a |
| `eks-compliance-cis-542-restricted-cidr` | 3/3 | 3/3 / 0/3 | 12/12 / 6/12 |
| `eks-compliance-audit-log-api-only` | 3/3 | 3/3 / 0/3 | 12/12 / 7/12 |
| `eks-compliance-denied-read` | 3/3 | 1/3 / 1/3 | 6/9 / 6/9 |
| `eks-compliance-section3-not-covered` | 3/3 | 3/3 / 1/3 | 9/9 / 2/3 |
| `eks-compliance-no-invented-cve` | 3/3 | 1/3 / 0/3 | 10/12 / 9/12 |
| `eks-compliance-auth-mode-configmap` | 3/3 | 3/3 / 3/3 | 9/9 / 9/9 |
| `eks-compliance-cis-only-scope` | 3/3 | 3/3 / 0/3 | 9/9 / 0/9 |
| `eks-compliance-live-cis-aws-controls` | 3/3 | 3/3 / 1/3 | 18/18 / 4/18 |
| `eks-compliance-live-rbac-workloads` | 3/3 | 3/3 / 1/3 | 15/15 / 9/15 |
| `eks-compliance-live-pci-crosswalk` | 3/3 | 3/3 / 1/3 | 14/15 / 8/15 |
| `eks-compliance-live-full-benchmark` | 3/3 | 3/3 / 0/3 | 24/24 / 0/24 |
| `eks-compliance-live-all-frameworks` | 3/3 | 3/3 / 0/3 | 21/21 / 0/21 |
| `eks-compliance-live-full-benchmark-default-policy` | 3/3 | 3/3 / 0/3 | 18/18 / 0/18 |
| `eks-compliance-live-compliant-cluster` | 3/3 | 3/3 / 0/3 | 18/18 / 0/18 |

With the skill, 38/42 expected outputs and 195/201 assertions passed. The harness scored the runs without it at 8/42 and 60/195, but those numbers understate the live baseline: see "Harness grading of the baseline" below. The control-by-control comparison above uses each run's delivered report and is the fairer measure.

## How to read this

- **Harness grading of the baseline.** In at least 12 of the 21 live without-skill runs, the agent posted an interim message ("I've started three checks… I'll post it when they finish"), then delivered its full report in a later `final_response` in the same journal. The harness judge graded the first message, so those runs scored 0 in the expected-output and assertion columns above even where the agent delivered a 10–26 KB report. The with-skill runs delivered in one message and are not affected. `per-control-comparison` reads the last `final_response` of every run instead, maps the baseline's own status words to the skill's, and notes the runs that hit the tool-service outage.
- **Kubernetes access in the harness.** The eval harness gives each agent space an EKS access entry with `AmazonAIOpsAssistantPolicy`. For the cases whose `eks_clusters_file` is under `clusters/cis-reader-*`, a local test hook also added Kubernetes group `devops-agent-cis-readers` to that access entry, so those agent spaces read the cluster through the recommended ClusterRole. The other live cases, including `live-full-benchmark-default-policy`, ran under `AmazonAIOpsAssistantPolicy` alone. The access options were also checked directly with an IAM role on the cluster, without the agent: the ClusterRole allows every evidence read and denies Secrets, other ConfigMaps, and pod logs; `AmazonAIOpsAssistantPolicy` denies the reads listed in `references/permissions.md`.
- **Remaining misses with the skill.**
  - `denied-read`: in all three iterations the response recommended the read-only ClusterRole without Secrets, but the judge failed the assertion because the response did not say "cluster scope". The assertion is stricter than intended.
  - `no-invented-cve`: CIS 5.1.1 now gives `Manual review` when no running image comes from the account's ECR. The prompt does not say where the images come from, so in two iterations the response gave both outcomes instead of PASS.
  - `live-pci-crosswalk`: in one iteration the judge failed the PCI DSS 12.3.4 assertion although the quoted response row reads `PASS (partial coverage)` with basis `Security Hub EKS.2`.
- **Cases that barely separate the two sides.** `auth-mode-configmap` passes without the skill, because any model flags a `system:masters` user mapping. `section3-not-covered` passes on expected output without it, because any model declines to run a Job in a read-only review. The skill adds the `Not covered` status and the kube-bench `eks-1.8.0` recommendation.
- **Rule defects found on the live clusters and fixed before the committed run:**
  - CIS 4.1.6 no longer exempts pods using IRSA or EKS Pod Identity.
  - Built-in roles (`cluster-admin`, `admin`, `edit`) count for 4.1.1, 4.1.2, 4.1.4, and 4.1.8–4.1.12, and are excluded only from 4.1.3.
  - Under `AmazonAIOpsAssistantPolicy`, the agent graded the RBAC controls from the `aws-auth` `system:masters` mapping. That mapping is now graded under 4.1.7 only, so those controls stay `Not assessed` when the RBAC reads are denied.
  - CIS 5.1.1 was ambiguous when ECR scanning is on but no running image is in the account's ECR. The rule now decides that case first.
  - CIS 5.1.3 judges AWS managed policies by name instead of fetching their documents, which the agent's tools may refuse.
  - CIS 5.2.1 never FAILs, since read-only evidence cannot show which pods call AWS APIs.
  - The report lists the 13 Section 3 controls as separate rows.
  - Earlier: CIS 4.3.1 reads `--enable-network-policy` instead of the node agent's presence; CIS 5.5.1 passes any IAM principal; AWS-6 names the registries when no image is in the account's ECR; AWS-2 is decided from `versionStatus`; crosswalk rows name the Security Hub control; Inspector reads page through `nextToken`.
- **Prompt wording.** Five scenario prompts (`cis-542-restricted-cidr`, `audit-log-api-only`, `denied-read`, `section3-not-covered`, `auth-mode-configmap`) open with "Run an EKS compliance check…". With the earlier wording "During an EKS compliance check…", the agent often answered from general knowledge without reading the skill.
- **Runs discarded before the committed one.** Several functional runs on 2026-11-18 and 2026-11-19 were not kept. Some had DevOps Agent tool-service errors (`Missing required context: remote_toolbox`, `TOOLBOX_UNAVAILABLE ... (bind_wait_timeout)`) in up to 14 of 63 runs. One had connection failures from the test machine in 7 of 87 runs. One ran before the 5.1.1 fix. In the committed run, 3 of 87 runs hit the tool-service error, all of them without the skill.
- **Redaction.** The real account ID was replaced with `123456789012`, and an AWS-owned EC2 requester account with `111122223333`. Node and NAT public IPs became `198.51.100.x`. Subnet, VPC, security group, route table, internet and NAT gateway, launch template, ENI, volume, reservation, and attachment IDs were replaced with numbered placeholders that stay consistent across files. EKS endpoint IDs, cluster CA certificates, the KMS key ID, node group, IAM role, and agent role names, the CloudTrail trail and bucket names, and the IAM session name were replaced too. S3 bucket, ECR repository, CloudFormation stack, IAM role and policy names of unrelated resources in the test account became numbered placeholders (`bucket-01`, `repo-01`, `stack-01`), and GuardDuty detector IDs too. Public AMI IDs, the AWS-owned EKS ECR registry account `602401143452`, and the names of the two purpose-built test clusters are kept.
