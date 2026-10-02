# AWS EKS Operations Review skill

> ⚠️ This skill is sample code, not intended for production use without additional review and
> testing. Users should validate in a non-production environment first.

Read-only EKS best-practices review for AWS DevOps Agent. It uses the MCP tool `use_kubectl` for Kubernetes discovery, attempts 49 areas, grades selected canonical checks as PASS/FAIL/N/A, loads only FAIL remediations, runs a hard QA gate, and returns the complete Markdown report directly in the response. Tool results remain transient in conversation: nothing is written to Amazon S3, an inventory/state/report file, or a checkpoint. It never mutates resources. Customer-account reads use audited read-only agent access, never local AWS CLI/boto3 credentials.

## Important: EKS access setup

`use_kubectl` reaches a cluster through an EKS **access entry** granted to your Agent Space's IAM role. Until that entry exists, all 49 discovery areas return `n/a` with a permission error and the review completes almost entirely unassessed. Configure it once per cluster, following [AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html):

1. Confirm the cluster's authentication mode includes the EKS API (cluster **Access** tab in the Amazon EKS console).
2. Copy your Agent Space's primary cloud source IAM role ARN from **Capabilities → Cloud → Primary Source → Edit**.
3. Create an IAM access entry on the cluster's **Access** tab using that role ARN as the principal.
4. Attach an access policy with access scope **Cluster**.

**For all Kubernetes objects to be discovered, attach the AWS managed `AmazonEKSAdminViewPolicy` access policy.** The documented default, `AmazonAIOpsAssistantPolicy`, suits incident investigation, but this review walks the full cluster object graph — RBAC roles and bindings, admission webhook configurations, CRDs, StorageClasses, PodDisruptionBudgets, NetworkPolicies, ResourceQuotas, ServiceAccounts — and any object kind the policy does not cover is recorded as N/A for lack of access rather than graded. Namespace-scoped access has the same effect on cluster-scoped objects, so use the Cluster scope.

`AmazonEKSAdminViewPolicy` is view-only, but it does grant read access to all objects including Secrets. This skill never fetches Secret values — Secret checks are graded on existence, type, and metadata only — so the grant is broader than the skill uses and should be approved deliberately. Where that is not acceptable, use `AmazonAIOpsAssistantPolicy` and expect some rows to be N/A.

## Runtime architecture

`SKILL.md` is an S0–S8 state machine. `references/runtime/` contains the ordered discovery manifest, bounded inventory schema, router, cluster gates, grading guards, exact check manifest, telemetry thresholds, common-check crosswalk, QA gate, and final-response contract. `references/pillars/` owns canonical predicates for nine pillars; root reference files own AX and gated Upgrade/Windows/Hybrid/AI-ML definitions. `references/remediations/index.md` dispatches known FAIL IDs to small shards. `references/control-plane-health/` contains staged CP query/source/threshold/procedure/remediation files. `references/docs/` contains operator/background material and is not normal runtime authority.

Canonical coverage: 49 discovery areas; 288 core checks (41 Operations, 26 Resilience, 46 Security, 30 Scalability, 19 Performance, 26 Observability, 33 Networking, 33 Cost, 20 Control Plane, 14 AWS API); 81 gated checks (35 Upgrade, 18 Windows, 12 Hybrid, 16 AI/ML). Control Plane scorecard IDs are CP1–CP11, CP-M1–CP-M6, and CPM1–CPM3; CP1–CP25 in query shards are query IDs only; Cluster Insights is AX1.

## Package layout

```text
aws-eks-operations-review/
├── SKILL.md
└── references/
    ├── runtime/                 # manifests, gates, guards, QA, report contract
    ├── pillars/                 # nine canonical pillar definitions
    ├── remediations/            # generated FAIL-only index and 4–8-ID shards
    ├── control-plane-health/    # source detection, four query shards, thresholds/playbooks
    ├── decision-trees/          # signal-triggered diagnostics
    ├── docs/                    # JIT background; consolidated operator-guides.md
    ├── kubectl-discovery-commands*.md
    └── aws-api-checks.md, upgrade-readiness.md, windows-workloads.md,
        hybrid-nodes.md, aiml-workloads.md, k8s-deprecated-apis.md
```

## Maintainer-only validation and packaging

AWS DevOps Agent does **not** run shell or Python scripts. Everything under `evals/` is local development tooling, is excluded from the uploaded ZIP, and is never referenced by `SKILL.md` at runtime. A maintainer may regenerate the two derived indexes after changing canonical definitions or shard declarations:

```bash
python3 evals/generate-runtime-indexes.py --write
```

A maintainer may then run the existing consistency check before upload:

```bash
bash evals/check-consistency.sh
```

The consistency check invokes the generator in `--check` mode, validates every canonical row schema, runs deterministic routing/gate/QA/shard contract probes, checks local links and package exclusions, and enforces an upload payload of at most 100 regular files. These commands are not skill steps.

Build from the parent directory and remove the old archive first so deleted entries cannot remain:

```bash
rm -f aws-eks-operations-review.zip
zip -r aws-eks-operations-review.zip aws-eks-operations-review/ \
  -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' \
  -x '*/.git/*' '*/evals/*' '*/.skilleval.yaml' '*/CHANGELOG.md' \
     '*/README.md' '*/EKS_SKILL_OPTIMIZATION_REPORT.md' '*.DS_Store'
```

Upload constraints: root entry `aws-eks-operations-review/SKILL.md`, ZIP ≤6 MB and ≤100 regular files, no `scripts/`, eval files, README, changelog, optimization report, `.DS_Store`, TSV, or runtime sidecars. The intended payload currently contains exactly 100 files. In the Agent Space Operator Web App choose **Skills → Add skill → Upload skill**, select On-demand/Evaluation (or Generic), review validation, and upload. The shared `operations-review-report-format` skill is optional; `references/runtime/report-contract.md` is the complete EKS fallback/adapter.

## Contributing a check

1. Add the stable ID row to its canonical definition using one of the validated table schemas; never reuse/renumber IDs or use C-series for Cost.
2. Add a complete remediation block to a 4–8-ID numbered shard and include the ID in that shard's `Canonical IDs` declaration; the generator writes the direct index route.
3. Run `python3 evals/generate-runtime-indexes.py --write` to regenerate `references/runtime/check-manifest.md` and `references/remediations/index.md`; do not edit either generated file manually.
4. If a count changed, update the corresponding QA count and affected runtime crosswalk/count text, then update `CHANGELOG.md`.
5. Run the local maintainer consistency check and inspect the archive contents. The generated manifest—not a blank worksheet or a human operator guide—owns membership.

## Validation status

`evals/TESTING.md` records model and non-production live validation. Do not claim those results until the suites/live review are actually run. Re-run all target models after frontmatter or workflow changes.
