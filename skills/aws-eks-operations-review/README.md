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

## Uploading to AWS DevOps Agent

Complete the [EKS access setup](#important-eks-access-setup) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill is built for on-demand reviews and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-eks-operations-review`, or filter by AWS service **Amazon EKS**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust thresholds in `references/runtime/metrics-thresholds.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-eks-operations-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-eks-operations-review.zip
   zip -r aws-eks-operations-review.zip aws-eks-operations-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-eks-operations-review.zip | tail -1   # expect 75 files
   ```

2. Check that the zip has this structure:

   ```text
   aws-eks-operations-review.zip
   └── aws-eks-operations-review/
       ├── SKILL.md                          # required: frontmatter with name and description
       └── references/
           ├── runtime/                      # 11 files: manifests, gates, guards, QA, report contract, overlays
           ├── pillars/                      # 9 files: canonical pillar definitions
           ├── remediations/                 # 27 files: FAIL-only index and shards
           ├── control-plane-health/         # 11 files: source detection, query shards, thresholds
           ├── decision-trees/               # 3 files
           ├── docs/                         # 5 files: operator background
           ├── kubectl-discovery-commands.md
           ├── kubectl-discovery-commands-deep-dive.md
           ├── aws-api-checks.md
           ├── upgrade-readiness.md
           ├── windows-workloads.md
           ├── hybrid-nodes.md
           ├── aiml-workloads.md
           └── k8s-deprecated-apis.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-eks-operations-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

The shared `operations-review-report-format` skill is optional either way. `references/runtime/report-contract.md` is the complete EKS fallback.

## Runtime architecture

`SKILL.md` is an S0–S8 state machine. `references/runtime/` contains the ordered discovery manifest, bounded inventory schema, router, cluster gates, grading guards, exact check manifest, telemetry thresholds, common-check crosswalk, QA gate, and final-response contract. `references/pillars/` owns canonical predicates for nine pillars; root reference files own AX and gated Upgrade/Windows/Hybrid/AI-ML definitions. `references/remediations/index.md` dispatches known FAIL IDs to small shards. `references/control-plane-health/` contains staged CP query/source/threshold/procedure/remediation files. `references/docs/` contains operator/background material and is not normal runtime authority.

Canonical coverage: 49 discovery areas; 288 core checks (41 Operations, 26 Resilience, 46 Security, 30 Scalability, 19 Performance, 26 Observability, 33 Networking, 33 Cost, 20 Control Plane, 14 AWS API); 81 gated checks (35 Upgrade, 18 Windows, 12 Hybrid, 16 AI/ML). Control Plane scorecard IDs are CP1–CP11, CP-M1–CP-M6, and CPM1–CPM3; CP1–CP25 in query shards are query IDs only; Cluster Insights is AX1.

## Optional overlays

These views run only when the user asks for them. Guardrails for vulnerability claims (version lag is a version gap; a CVE is named only when a retrieved Inspector finding or AWS security bulletin contains it) apply to every review, through guard FP13 in `references/runtime/grading-guards.md`. They are derived from the graded ledger and never add checks, change verdicts or severity, or alter the eight-section report. Activation, inputs, and rules live in `references/runtime/overlays.md`. This skill does not map findings to compliance frameworks such as CIS, NIST 800-53, or PCI DSS.

| Overlay | Ask for it with | Output |
|---|---|---|
| Historical delta | Paste a previous report from this skill and ask "what changed" | §1 New / Regressed / Persisting / Resolved / Unverified, matched by finding fingerprint. The prior report is used from the conversation only. |
| Comparison, drift, fleet | Paste reports from earlier reviews and ask to "compare dev and prod" or "check for drift" | A separate `EKS Fleet Comparison` with drift classes on parity checks. It compares reports: at most one cluster is reviewed live in the conversation, and every other cluster comes from a report you supply, so review each cluster in its own conversation first. |

Example prompts:

- "Here is last month's review of `prod-cluster`. Re-run the review and show what changed."
- "Here are last week's reviews of `dev-cluster` and `staging-cluster`. Review `prod-cluster` now and compare all three for configuration drift."

## Package layout

```text
aws-eks-operations-review/
├── SKILL.md
└── references/
    ├── runtime/                 # manifests, gates, guards, QA, report contract, overlays
    ├── pillars/                 # nine canonical pillar definitions
    ├── remediations/            # generated FAIL-only index and size-capped (≤12 KiB) shards
    ├── control-plane-health/    # source detection, four query shards, thresholds/playbooks
    ├── decision-trees/          # signal-triggered diagnostics
    ├── docs/                    # JIT background; consolidated operator-guides.md
    ├── kubectl-discovery-commands*.md
    └── aws-api-checks.md, upgrade-readiness.md, windows-workloads.md,
        hybrid-nodes.md, aiml-workloads.md, k8s-deprecated-apis.md
```

## Maintainer-only validation

AWS DevOps Agent does **not** run shell or Python scripts. Everything under `evals/` is local development tooling, is excluded from the uploaded ZIP, and is never referenced by `SKILL.md` at runtime. A maintainer may regenerate the two derived indexes after changing canonical definitions or shard declarations:

```bash
python3 evals/generate-runtime-indexes.py --write
```

A maintainer may then run the existing consistency check before upload:

```bash
bash evals/check-consistency.sh
```

The consistency check invokes the generator in `--check` mode, validates every canonical row schema, runs deterministic routing/gate/QA/shard contract probes, checks local links and package exclusions, and enforces an upload payload of at most 100 regular files. `check-consistency.sh` prints the remaining headroom. These commands are not skill steps. To build and upload the zip, see [Option B](#option-b-upload-as-a-zip-file-customizable).

## Contributing a check

1. Add the stable ID row to its canonical definition using one of the validated table schemas; never reuse/renumber IDs or use C-series for Cost.
2. Add a complete remediation block to the pillar's numbered shard and include the ID in that shard's `Canonical IDs` declaration; the generator writes the direct index route. A shard must stay ≤12 KiB (and declare ≥4 IDs) — if it would exceed the cap, start a new `<pillar>-NN.md` shard rather than growing it.
3. Run `python3 evals/generate-runtime-indexes.py --write` to regenerate `references/runtime/check-manifest.md` and `references/remediations/index.md`; do not edit either generated file manually.
4. If a count changed, update the corresponding QA count and affected runtime crosswalk/count text, then update `CHANGELOG.md`.
5. Run the local maintainer consistency check and inspect the archive contents. The generated manifest—not a blank worksheet or a human operator guide—owns membership.

## Validation status

`evals/TESTING.md` records model and non-production live validation. Do not claim those results until the suites/live review are actually run. Re-run all target models after frontmatter or workflow changes.
