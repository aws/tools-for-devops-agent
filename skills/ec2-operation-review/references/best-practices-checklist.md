# EC2 Best-Practices Checklist

Each item maps to a Well-Architected pillar. The **Signal** column is the exact
API field or metric that decides the finding. Severity is a starting point —
raise it one level for production-tagged resources, lower it one level for
sandbox/dev.

## 1. Security

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| IMDSv2 enforced | `MetadataOptions.HttpTokens != "required"` | Instance allows IMDSv1; enforce `HttpTokens=required` to mitigate SSRF credential theft | HIGH |
| IMDS hop limit sane | `HttpPutResponseHopLimit > 2` on non-container host | Reduce hop limit to 1–2 to limit token reach | LOW |
| No unrestricted SSH | SG ingress `0.0.0.0/0` or `::/0` on port 22 | Public SSH exposure; restrict to known CIDRs or use SSM Session Manager | CRITICAL |
| No unrestricted RDP | SG ingress `0.0.0.0/0` on port 3389 | Public RDP exposure; restrict or use Fleet Manager / SSM | CRITICAL |
| No unrestricted DB/admin ports | SG ingress `0.0.0.0/0` on 3306/5432/1433/6379/9200/27017 etc. | Sensitive port open to internet | CRITICAL |
| EBS volumes encrypted | `Volume.Encrypted == false` | Data at rest unencrypted; enable default EBS encryption + re-create from encrypted snapshot | HIGH |
| IAM instance profile scoped | Attached role policy contains `"*"` action/resource | Over-privileged instance role; scope to least privilege | HIGH |
| Instance profile present for API access | No `IamInstanceProfile` but app calls AWS | Likely long-lived keys on disk; attach a role instead | MEDIUM |
| No public IP unless required | `PublicIpAddress` set on a backend/private tier | Reduce attack surface; move behind NAT / private subnet | MEDIUM |
| AMI reasonably current | AMI creation date > 180 days | Stale base image; rebuild from a patched AMI | MEDIUM |
| SSM managed for patching | Not in `ssm.DescribeInstanceInformation` | No managed patch path; install SSM agent + Patch Manager | MEDIUM |

## 2. Reliability

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| ASG spans multiple AZs | ASG `AvailabilityZones` count < 2 | Single-AZ ASG; add subnets in ≥2 AZs | HIGH |
| ASG health check type | `HealthCheckType == "EC2"` for an ELB-fronted ASG | EC2-only checks miss app failures; use `ELB` health checks | MEDIUM |
| ASG min capacity for HA | `MinSize < 2` for a stateless prod service | No redundancy; raise min to ≥2 across AZs | MEDIUM |
| Recent EBS snapshot / backup | Newest snapshot for volume > 7 days old, no DLM/AWS Backup plan | No recent recovery point; enable AWS Backup or a DLM policy | HIGH |
| Instance status checks passing | `InstanceStatus`/`SystemStatus != "ok"` | Impaired instance; investigate and consider Auto Recovery | CRITICAL |
| Auto Recovery configured | No `recover` CloudWatch action on system-status-check failure | Add Auto Recovery for hardware-failure resilience | LOW |
| Termination protection on critical hosts | `DisableApiTermination == false` on a stateful/prod host | Accidental termination risk; enable protection | LOW |
| Spot interruption handling | Spot instance with no interruption handler / rebalance | Ungraceful Spot reclaim; handle interruption notices | MEDIUM |

## 3. Performance Efficiency

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| CPU not saturated | `CPUUtilization` p95 > 90% sustained | Undersized; scale up or out | HIGH |
| T-family credit balance healthy | `CPUCreditBalance` trending to 0 (standard mode) | Throttled burst instance; move to unlimited or a fixed-perf family | MEDIUM |
| Unlimited-mode cost surprise | `CPUSurplusCreditsCharged > 0` sustained | Paying surplus credits; right-size to M/C family | MEDIUM |
| EBS not throughput-bound | `VolumeThroughputPercentage`/`VolumeQueueLength` high | I/O bound; raise IOPS/throughput or move to gp3/io2 | MEDIUM |
| EbsOptimized on EBS-heavy hosts | `EbsOptimized == false` on io-heavy instance | Network/EBS contention; enable EBS optimization | LOW |
| Current-generation instance | Previous-gen family (m4, c4, t2, r4, etc.) | Better price/perf available; migrate to current gen | MEDIUM |
| Graviton candidacy | x86 workload with no arch constraint | Evaluate Graviton (m7g/c7g/r7g) for price/performance | LOW |
| gp2 → gp3 | Volume `VolumeType == "gp2"` | gp3 is cheaper with baseline 3000 IOPS; migrate | LOW |

## 4. Cost Optimization

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Idle instance | `CPUUtilization` max < 5% and network near-zero for 14 days | Idle instance still billing; stop or terminate | MEDIUM |
| Right-sizing candidate | p95 CPU < 40% and memory (if available) < 40% sustained | Overprovisioned; downsize one step and re-measure | MEDIUM |
| Stopped instance with EBS | Instance `stopped` but volumes retained long-term | EBS still bills while stopped; snapshot + delete if unneeded | LOW |
| Unattached EBS volume | `Volume.State == "available"` | Orphaned volume billing; snapshot and delete | MEDIUM |
| Idle Elastic IP | `Address.AssociationId` empty | Unattached EIP incurs charge; release if unused | LOW |
| Commitment coverage | Steady-state on-demand usage, no SP/RI coverage | Missing Savings Plans / RI discount; evaluate commitment | MEDIUM |
| Spot candidacy | Fault-tolerant/batch workload on on-demand | Evaluate Spot for interruptible workloads | LOW |

## 5. Operational Excellence

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Required tags present | Missing `Name`, `Environment`, `Owner`, or cost-allocation tags | Untagged resource; apply tagging standard | LOW |
| Alarm coverage | No CloudWatch alarm for `StatusCheckFailed` / CPU | No proactive alerting; add alarms (see thresholds ref) | MEDIUM |
| Detailed monitoring | `Monitoring.State == "disabled"` | 5-min granularity limits diagnosis; enable detailed monitoring | LOW |
| No pending scheduled events | `ec2.DescribeInstanceStatus` returns scheduled events | Pending maintenance/retirement; plan the change | MEDIUM |
| Launch template (not config) | ASG uses a launch configuration | Launch configurations are deprecated; migrate to launch templates | LOW |
| SSM agent managed | Not registered in SSM | No automation/inventory path; enable SSM | LOW |
