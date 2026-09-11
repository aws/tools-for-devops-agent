# Security Network Nodes remediations — shard 04

Canonical IDs: `S33,S34,S35,S36,S37,S38,S39`

### S33 — Admission webhook timeout & reinvocation bounded
**Why it matters:** A slow/hung webhook with a high `timeoutSeconds` blocks every matching API request for that duration — worst with `failurePolicy: Fail` (S17). `reinvocationPolicy: IfNeeded` re-runs mutating webhooks after later mutations, compounding latency.
**Steps:** Set a tight `timeoutSeconds` (≤10s), scope webhooks narrowly (S16/Sc19), and drop unnecessary `reinvocationPolicy: IfNeeded`.
**References:**
- [Kubernetes — Dynamic Admission Control (timeouts, reinvocation)](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)

### S34 — Webhook CA-bundle certificate validity
**Why it matters:** An expired webhook CA silently breaks TLS to the backend: with `failurePolicy: Fail` it blocks **all** matching API calls (can wedge the cluster); with `Ignore` it silently skips validation (security bypass).
**Steps:** Decode each `clientConfig.caBundle` (base64 → `openssl x509 -noout -enddate`) and flag expired / <30-day certs; rotate via cert-manager or the controller's own rotation.
**References:**
- [Kubernetes — Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)

### S35 — Secrets Store CSI rotation enabled
**Why it matters:** A secret synced once and never rotated is barely better than a static Secret — a rotated backend secret won't reach pods until the mount refreshes.
**Steps:** Enable the CSI driver's rotation reconciler (`--enable-secret-rotation=true`) and set a sane `--rotation-poll-interval`. **N/A** if Secrets Store CSI isn't in use.
**References:**
- [Secrets Store CSI Driver — Secret auto rotation](https://secrets-store-csi-driver.sigs.k8s.io/topics/secret-auto-rotation)

### S36 — VPC CNI dedicated IAM role (not node role)
**Why it matters:** By default `aws-node` inherits the node instance role, so any pod that can reach IMDS gets the CNI's networking permissions — a least-privilege gap. EKS strongly recommends a dedicated role.
**Steps:** Attach `AmazonEKS_CNI_Policy` to a dedicated IRSA / Pod-Identity role for the `aws-node` service account, remove it from the node role, and restrict IMDS (S28).
**References:**
- [EKS Best Practices — VPC CNI (use separate IAM role)](https://docs.aws.amazon.com/eks/latest/best-practices/vpc-cni.html)

### S37 — GuardDuty EKS Protection enabled + no active findings *(AWS-API)*
**Why it matters:** GuardDuty EKS Protection detects runtime threats (credential exfiltration, privilege escalation, crypto mining, container escape) using audit logs and eBPF. Without it, active attacks go undetected.
**Steps:**
1. Enable EKS Audit Log Monitoring: GuardDuty console → EKS Protection → enable.
2. Enable EKS Runtime Monitoring: GuardDuty console → EKS Runtime Monitoring → enable + deploy the GuardDuty agent (managed or self-managed add-on).
3. Investigate active HIGH/CRITICAL findings: `aws guardduty list-findings` filtered to `Kubernetes:*` types for this cluster's account/region.
4. For each finding: follow the GuardDuty remediation guidance (isolate compromised pod, rotate credentials, patch vulnerability).
**References:**
- [GuardDuty EKS Protection](https://docs.aws.amazon.com/guardduty/latest/ug/kubernetes-protection.html)
- [GuardDuty EKS Runtime Monitoring](https://docs.aws.amazon.com/guardduty/latest/ug/eks-protection-runtime-monitoring.html)

### S38 — Inspector container image scanning *(AWS-API)*
**Why it matters:** Running container images with known Critical/High CVEs represents active exploitation risk. Inspector continuously scans ECR images and produces actionable findings.
**Steps:**
1. Enable Inspector ECR scanning: Inspector console → Settings → enable Amazon ECR scanning.
2. Check findings: `aws inspector2 list-findings --filter-criteria '{"resourceType":[{"comparison":"EQUALS","value":"AWS_ECR_CONTAINER_IMAGE"}]}'`
3. For CRITICAL/HIGH CVEs in images currently running in the cluster: rebuild base images with patched packages, push updated tags, redeploy.
4. Enable ECR immutable tags (SM5) to prevent tag overwriting after scan.
**References:**
- [Inspector container scanning](https://docs.aws.amazon.com/inspector/latest/user/scanning-ecr.html)
- [EKS Best Practices — Image Security](https://docs.aws.amazon.com/eks/latest/best-practices/image-security.html)

### S39 — Security Hub EKS controls passing *(AWS-API)*
**Why it matters:** Security Hub evaluates EKS resources against the AWS Foundational Security Best Practices standard. FAILED controls indicate compliance gaps that may trigger audit findings.
**Steps:**
1. Enable Security Hub with the AWS Foundational Security Best Practices standard.
2. Check EKS controls: `aws securityhub get-findings --filters '{"ProductName":[{"Value":"Security Hub","Comparison":"EQUALS"}],"ResourceType":[{"Value":"AwsEks*","Comparison":"PREFIX"}]}'`
3. Key EKS controls: [EKS.1] endpoint not publicly accessible, [EKS.2] supported Kubernetes version, [EKS.3] encrypted Kubernetes secrets, [EKS.8] audit logging enabled.
4. For each FAILED control: follow the Security Hub remediation steps to resolve.
**References:**
- [Security Hub EKS controls](https://docs.aws.amazon.com/securityhub/latest/userguide/eks-controls.html)
