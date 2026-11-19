# AWS EKS Compliance Checker

> ⚠ This skill is sample code, not intended for production use without additional review and
> testing. Users should validate in a non-production environment first.

## Purpose

Grades one Amazon EKS cluster against the CIS Amazon EKS Benchmark v1.8.0 and maps the results to NIST SP 800-53 Rev. 5, PCI DSS v4.0.1, SOC 2, and HIPAA. Each control gets a status backed by the evidence that decided it, so a platform or security team can answer an auditor's "show me" questions without assembling the evidence by hand. The skill is read-only and the report is technical evidence, not a certification or attestation.

## Key Capabilities

- Grades all 50 CIS Amazon EKS Benchmark v1.8.0 controls with PASS, FAIL, Manual review, Not assessed, or Not covered. Control IDs, titles, and Automated/Manual types follow the kube-bench `eks-1.8.0` profile.
- Collects its own evidence through `use_kubectl` (RBAC, service accounts, pod security settings, NetworkPolicies, `aws-auth`) and `use_aws` (cluster configuration, node groups, IAM node roles, Amazon Inspector, Amazon GuardDuty, AWS CloudTrail, AWS Backup).
- Adds nine supplementary AWS checks that the frameworks need and the CIS benchmark does not grade. Three of them follow Security Hub EKS controls EKS.2, EKS.8, and EKS.9.
- Maps results to NIST 800-53, PCI DSS, SOC 2, and HIPAA only when asked. Rows that AWS publishes as Security Hub *Related requirements* are labelled `Security Hub`; the rest are labelled `Indicative` for auditor confirmation.
- Never treats missing evidence as a pass, never reads Secret values, and never names a CVE that a retrieved Inspector finding does not contain.
- Reads Kubernetes support status from the EKS API at runtime instead of a hardcoded version list.

## Prerequisites

- An AWS DevOps Agent Space with the target account connected as a cloud source.
- AWS permissions: every read is covered by the `AIDevOpsAgentAccessPolicy` managed policy. No extra policy from [`devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml) is needed.
- Kubernetes access: an EKS access entry for the Agent Space's primary cloud source IAM role with `AmazonEKSAdminViewPolicy` at **Cluster** scope, following [AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html). The policy allows reading Secrets; this skill never does. With `AmazonAIOpsAssistantPolicy` instead, listing ClusterRoles, ClusterRoleBindings, and Roles is denied, so the RBAC controls (CIS 4.1.1–4.1.4 and 4.1.8–4.1.12) report `Not assessed`.
- For the vulnerability controls (CIS 5.1.1, AWS-6): Amazon Inspector ECR scanning. For AWS-4: Amazon GuardDuty EKS protection. Without them those checks report FAIL or Not assessed, not an error.

## Limitations

- CIS Section 3 (13 worker-node file and kubelet controls) needs host access and is reported as Not covered, with a recommendation to run kube-bench on the nodes. The skill never runs kube-bench or any pod itself.
- Several CIS controls are Manual in the benchmark and need human judgement (for example 4.5.1 namespaces as boundaries, 5.1.4 approved registries). The skill gathers the evidence and states the question instead of guessing.
- Framework mappings show technical evidence for part of a control. Procedural, administrative, and physical requirements are out of scope.
- One cluster per review. Review several clusters one after another.
- For a general best-practices review across reliability, cost, scalability, and operations, use [aws-eks-operations-review](../aws-eks-operations-review/). For upgrade planning, use [eks-upgrade-readiness](../eks-upgrade-readiness/).

## Agent Types

This skill is used by the following agent type:

- **Chat tasks** — on-demand compliance assessments and audit evidence requests

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/aws-eks-compliance-checker` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

**Option B: Upload as a zip file**

1. Zip the `aws-eks-compliance-checker/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r aws-eks-compliance-checker.zip aws-eks-compliance-checker/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `aws-eks-compliance-checker.zip` file (max 6 MB).
5. Select the agent type **Chat tasks**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage the skill programmatically, assigning it to the `CHAT` agent type. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

### Chat tasks

- "Run a CIS Amazon EKS Benchmark assessment of `prod-cluster` in us-east-1."
- "Is `payments-cluster` compliant with PCI DSS? Give me the control-level evidence."
- "Map `prod-cluster` to NIST 800-53 and SOC 2 for our audit next month."
- "Which CIS EKS controls does `dev-cluster` fail, and what are the offending resources?"

## Related

- [aws-eks-operations-review](../aws-eks-operations-review/) — graded best-practices review across nine pillars, with vulnerability posture, delta, and fleet drift overlays.
- [eks-upgrade-readiness](../eks-upgrade-readiness/) — pre-upgrade assessment.
- [aws-eks-healthdashboard](../aws-eks-healthdashboard/) — point-in-time health snapshot.
