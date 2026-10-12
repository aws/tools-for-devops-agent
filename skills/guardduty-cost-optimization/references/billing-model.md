# Amazon GuardDuty Billing Model

Reference for how GuardDuty charges accrue. Load this when you need the exact metric,
unit, and pricing basis for a protection plan, or when reasoning about the two
non-obvious billing interactions below.

Sources:
- [Monitoring GuardDuty usage and estimating costs](https://docs.aws.amazon.com/guardduty/latest/ug/monitoring_costs.html)
- [GuardDuty pricing](https://aws.amazon.com/guardduty/pricing/)

## What is billed

GuardDuty is pay-as-you-go, **per protection plan**, priced on the volume of data each
plan analyzes. There are no upfront costs and no per-detector fee — cost is driven
entirely by analyzed volume. Each plan meters on its own unit:

| Protection Plan | Data Source | Metric (namespace `AWS/GuardDuty`) | Unit | Priced on |
|-----------------|-------------|------------------------------------|------|-----------|
| Foundational Threat Detection | CloudTrailEvents | AnalyzedCount | Count | Management events analyzed |
| Foundational Threat Detection | VPCFlowLogDNSLogEvents | AnalyzedBytes | Bytes | VPC flow + DNS log volume |
| S3 Protection | S3DataEvents | AnalyzedCount | Count | S3 data events analyzed |
| EKS Protection | KubernetesAuditLogs | AnalyzedCount | Count | EKS audit log events |
| Runtime Monitoring | RuntimeMonitoringEC2 / EKS / Fargate | MonitoredVcpuHours | vCPU-Hours | vCPU hours monitored |
| Malware Protection for EC2 | MalwareProtectionEBS / OnDemandEBS* | ScannedBytes | Bytes | EBS data scanned |
| RDS Protection | RDS / RDSLimitless / AuroraScaleout | MonitoredAcuHours / MonitoredVcpuHours | ACU/vCPU-Hours | RDS/Aurora capacity monitored |
| Lambda Protection | LambdaNetworkLogs | AnalyzedBytes | Bytes | Lambda network log volume |
| AI Protection | AIDataEvents | AnalyzedBytes | Bytes | AI data events analyzed |

Malware Protection for S3 meters separately under the `AWS/GuardDuty/MalwareProtection`
namespace (`CompletedScanBytes`, `CompletedScanCount`, etc.).

## Two critical billing behaviors

- **Runtime Monitoring offsets VPC Flow Log charges.** For instances actively
  monitored by the Runtime Monitoring agent, GuardDuty does **not** charge for VPC
  Flow Logs processing on those instances. Enabling Runtime Monitoring *decreases*
  `VPCFlowLogDNSLogEvents` usage; disabling it restores the charge. The two line items
  trade against each other — always size the net effect, not either alone.
- **Service-log configuration does not reduce GuardDuty cost.** Filtering or disabling
  your own VPC Flow Logs, CloudTrail, or S3 data event logging does **not** reduce
  what GuardDuty analyzes — GuardDuty ingests from independent internal sources. The
  only cost lever is the GuardDuty **protection-plan** configuration itself.

## Unit conversions

Convert byte metrics to GB/TB when sizing to match pricing units:
- 1 GB = 1,073,741,824 bytes
- 1 TB = 1,099,511,627,776 bytes
