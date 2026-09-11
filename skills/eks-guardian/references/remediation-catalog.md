# EKS Guardian — Remediation Catalog

Actionable remediation commands for each finding category. Use these as guidance when fixing issues identified in an EKS Guardian assessment.

> **Note**: These commands are provided as starting points. Always review and adapt for your environment before applying.

---

## Security

### Enable Private Endpoint / Disable Public Endpoint

```hcl
# Terraform
resource "aws_eks_cluster" "this" {
  # ...
  vpc_config {
    endpoint_private_access = true
    endpoint_public_access  = false
  }
}
```

```bash
# AWS CLI
aws eks update-cluster-config \
  --name <cluster-name> \
  --resources-vpc-config endpointPublicAccess=false,endpointPrivateAccess=true
```

### Enable Control Plane Logging (All 5 Types)

```hcl
# Terraform
resource "aws_eks_cluster" "this" {
  # ...
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}
```

```bash
# AWS CLI
aws eks update-cluster-config \
  --name <cluster-name> \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'
```

### Enable KMS Envelope Encryption for Secrets

```hcl
# Terraform
resource "aws_eks_cluster" "this" {
  # ...
  encryption_config {
    provider {
      key_arn = aws_kms_key.eks_secrets.arn
    }
    resources = ["secrets"]
  }
}
```

### Enforce IMDSv2 on Node Groups

```hcl
# Terraform (managed node group)
resource "aws_eks_node_group" "this" {
  # ...
  launch_template {
    id      = aws_launch_template.eks_nodes.id
    version = aws_launch_template.eks_nodes.latest_version
  }
}

resource "aws_launch_template" "eks_nodes" {
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
}
```

### Enforce Pod Security Standards

```bash
# kubectl — label namespace to enforce restricted PSS
kubectl label namespace <namespace> \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted
```

### Apply Default-Deny Network Policy

```yaml
# kubectl apply -f default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: <namespace>
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### Remove system:anonymous ClusterRoleBinding

```bash
kubectl delete clusterrolebinding <binding-name-with-anonymous>
```

### Migrate from aws-auth to Access Entries

```bash
# Create access entry for each principal in aws-auth
aws eks create-access-entry \
  --cluster-name <cluster-name> \
  --principal-arn <iam-role-arn> \
  --type STANDARD

# Associate access policy
aws eks associate-access-policy \
  --cluster-name <cluster-name> \
  --principal-arn <iam-role-arn> \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy \
  --access-scope type=cluster
```

### Enable ECR Scan-on-Push

```hcl
# Terraform
resource "aws_ecr_repository" "this" {
  name = "<repo-name>"
  image_scanning_configuration {
    scan_on_push = true
  }
  image_tag_mutability = "IMMUTABLE"
}
```

```bash
# AWS CLI
aws ecr put-image-scanning-configuration \
  --repository-name <repo-name> \
  --image-scanning-configuration scanOnPush=true
```

---

## Reliability

### Add Liveness/Readiness Probes

```yaml
# Add to deployment spec.containers[]
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3
```

### Add PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: <app-name>-pdb
  namespace: <namespace>
spec:
  minAvailable: "50%"
  selector:
    matchLabels:
      app: <app-name>
```

### Add TopologySpreadConstraints

```yaml
# Add to deployment spec
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: <app-name>
```

### Set Resource Requests and Limits

```yaml
# Add to spec.containers[]
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

### Add Graceful Shutdown

```yaml
# Add to spec
terminationGracePeriodSeconds: 60
# Add to spec.containers[]
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 15"]
```

---

## Networking

### Enable VPC CNI Prefix Delegation

```bash
kubectl set env daemonset/aws-node -n kube-system \
  ENABLE_PREFIX_DELEGATION=true \
  WARM_PREFIX_TARGET=1
```

### Scale CoreDNS

```bash
# Scale replicas
kubectl scale deployment coredns -n kube-system --replicas=<desired>

# Or use HPA
kubectl autoscale deployment coredns -n kube-system \
  --min=2 --max=10 --cpu-percent=70
```

### Create VPC Endpoints

```hcl
# Terraform — example for ECR
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id             = var.vpc_id
  service_name       = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type  = "Interface"
  subnet_ids         = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id             = var.vpc_id
  service_name       = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type  = "Interface"
  subnet_ids         = var.private_subnet_ids
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id       = var.vpc_id
  service_name = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids
}
```

### Enable VPC Flow Logs

```hcl
# Terraform
resource "aws_flow_log" "vpc" {
  vpc_id               = var.vpc_id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flow_logs.arn
  iam_role_arn         = aws_iam_role.flow_logs.arn
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/aws/vpc/flow-logs/${var.vpc_id}"
  retention_in_days = 30
}
```

---

## Scalability

### Create HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: <app-name>-hpa
  namespace: <namespace>
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: <app-name>
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## Karpenter

### Configure Consolidation

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 30s
  limits:
    cpu: "100"
    memory: "400Gi"
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64", "arm64"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["m5.large", "m5.xlarge", "m6i.large", "m6i.xlarge", "m6g.large", "m6g.xlarge"]
```

### EC2NodeClass with IMDSv2

```yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2023
  metadataOptions:
    httpEndpoint: enabled
    httpProtocolIPv6: disabled
    httpPutResponseHopLimit: 1
    httpTokens: required
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 100Gi
        volumeType: gp3
        encrypted: true
        deleteOnTermination: true
```

---

## Cost Optimization

### Migrate gp2 to gp3 StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

```bash
# Remove default annotation from gp2
kubectl annotate storageclass gp2 storageclass.kubernetes.io/is-default-class-
```

### Clean Up Idle Resources

```bash
# Find 0-replica deployments
kubectl get deployments -A -o json | jq -r '.items[] | select(.spec.replicas == 0) | "\(.metadata.namespace)/\(.metadata.name)"'

# Find unbound PVCs
kubectl get pvc -A -o json | jq -r '.items[] | select(.status.phase != "Bound") | "\(.metadata.namespace)/\(.metadata.name)"'
```

---

## Cluster Upgrades

### Check Deprecated API Usage

```bash
# Install and run kubent (kube-no-trouble)
kubectl krew install deprecations
kubectl deprecations

# Or use pluto
pluto detect-all-in-cluster
```

### Update EKS Cluster Version

```bash
# Update control plane
aws eks update-cluster-version \
  --name <cluster-name> \
  --kubernetes-version <target-version>

# Update managed node groups (after control plane is ready)
aws eks update-nodegroup-version \
  --cluster-name <cluster-name> \
  --nodegroup-name <nodegroup-name>

# Update add-ons
aws eks update-addon \
  --cluster-name <cluster-name> \
  --addon-name <addon-name> \
  --addon-version <compatible-version>
```

---

## Risk Levels

Each remediation carries an inherent risk level:

| Risk | Description | Examples |
|------|-------------|----------|
| 🟢 LOW | Read-only or additive, no disruption | Add labels, create NetworkPolicy, enable logging |
| 🟡 MEDIUM | May cause brief disruption or require rolling restart | Scale CoreDNS, update VPC CNI env vars, add probes |
| 🔴 HIGH | Potential for downtime or breaking changes | Disable public endpoint, upgrade cluster version, change auth mode |

Always test in a non-production environment first. For HIGH risk remediations, ensure PDBs are in place and perform during maintenance windows.
