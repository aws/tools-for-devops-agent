# AWS Security Posture Review — Custom Agent

> **English summary.** A read-only security posture review custom agent for AWS DevOps Agent. The lead agent dispatches 11 sub-agents, one per domain (baseline services, GuardDuty / Access Analyzer, network exposure, network controls, storage, S3 buckets, compute, containers, IAM, change attribution, WAF), each writing its own Markdown artifact; the lead agent then writes an overview artifact that indexes them. Every finding carries the resource ID, Region, the API evidence it came from and a severity; anything the agent could not read is listed explicitly as "not verified" instead of being guessed. Read-only is enforced by the tool allowlist (11 read tools, no `use_kubectl`) and by an IAM policy that contains only Describe / Get / List actions. The system prompt, the report and this README are written in Chinese.

## Purpose

在 AWS DevOps Agent 上对一个 AWS 账号做一次**只读**的安全态势审查，结果写成 12 份 Markdown Artifact（1 份总览 + 11 个分册），在 DevOps Agent Web App 的 Artifacts 页直接看。每条发现都带资源 ID、区域、API 证据和严重度；查不到的项显式写「未核实（原因）」，不推测、不编造。

适合安全、运维团队定期（或按需）给账号做一次有证据可追溯的安全盘点。

## Key Capabilities

- 一次运行覆盖 11 个领域，每个领域一个分册 Artifact，总览 Artifact 汇总高 / 中 / 低严重度并链接各分册
- 主 agent 只做调度和索引，分册正文全部由采集数据的子 agent 自己写，避免转述失真
- 每条发现固定格式：资源 ID、区域、本轮真实调用过的 API 返回、严重度、怎么改（控制台步骤）
- 每个分册带「检查范围」（查了多少资源）和「本节未核实项」（没查到的项和原因）
- 支持单册模式：任务描述只点名某个领域时，只出对应分册，不写总览
- 支持「不得改动」资源列表：对列出的资源照常审查，但「怎么改」第一步写「先与资源负责人确认」
- 只读边界有两层：custom agent 的工具白名单（11 个读类工具，不给 `use_kubectl` 和任何写类工具）+ IAM 策略全部为 Describe / Get / List

### 12 份 Artifact

标题统一为 `AWS Security Posture Review - <账号ID> - <YYYY-MM-DD>`，分册再加 ` - Part <n> <英文节名>`。

| 分册 | 查什么 |
|---|---|
| 总览 | §0 范围与方法、§1 矩阵 + 高 / 中 / 低严重度汇总表、§9 阅读指引、§10 不可用项与未核实项、分册索引 |
| Part 2A Baseline | 每个启用区域 GuardDuty / Security Hub / Config / Inspector / Macie / Access Analyzer 是否开通；CloudTrail 多区域、校验、加密 |
| Part 2B GuardDuty and Access Analyzer | GuardDuty 现有 finding、Access Analyzer 外部访问 finding，按资源归类 |
| Part 3A Network Exposure | 对公网开放的安全组及 ENI 挂载、公网子网与路由、NACL |
| Part 3B Network Controls | Network Firewall、VPC 对等与 TGW、VPC Endpoint、负载均衡监听、API Gateway、Route 53、CloudFront、Flow Logs |
| Part 4 Storage | EBS 卷与快照加密及共享、KMS、RDS / DynamoDB / ElastiCache / EFS / Backup、Secrets Manager |
| Part 4B S3 Buckets | 每个桶的公开访问拦截、桶策略、ACL 与 Object Ownership、版本控制、访问日志、复制 |
| Part 5 Compute | EC2 公网实例与 IMDS、Lambda（含 Function URL）、ECR、SNS / SQS / EventBridge 资源策略 |
| Part 5B Containers | EKS 控制面端点、审计日志、版本、节点组；ECS 任务定义特权容器与明文密钥 |
| Part 6 IAM | 用户与 MFA、角色信任策略（外部账号）、宽泛权限与权限提升路径、OIDC、SSO |
| Part 7 Attribution | 高严重度发现最近一次被改成当前状态的 CloudTrail 事件（谁、何时、从哪里） |
| Part 8 WAF | 每个 Web ACL 的规则动作、托管规则组 Count / Block、日志与挂载资源 |

每个分册的结构固定：本节风险表 -> 怎么改（控制台步骤）-> 检查范围 -> 本节未核实项。

## Prerequisites

- 一个 AWS DevOps Agent Agent Space，目标账号已作为 cloud source 接入
- Agent Space 角色上的 AWS 托管策略 `AIDevOpsAgentAccessPolicy`（建 Agent Space 选 Auto-create 时已附）
- **需要额外的只读 IAM 权限。** 托管策略没覆盖的 36 个 Describe / Get / List 动作要以内联策略加到 Agent Space 角色上，原文见本目录 [`iam-extra-readonly-policy.json`](./iam-extra-readonly-policy.json)。不加的话对应检查项在报告里标「未核实」，agent 仍能跑完。
  - 加法：IAM -> Roles -> 打开 Agent Space 角色（默认名 `DevOpsAgentRole-AgentSpace-<后缀>`）-> Permissions -> Add permissions -> Create inline policy -> JSON -> 粘贴全文 -> Next -> 名字填 `SecurityReviewExtraReadOnly` -> Create policy
  - 撤回：删除该内联策略即可

| 领域 | 动作 | 不加会怎样 |
|---|---|---|
| IAM | `ListAccessKeys` `GetAccessKeyLastUsed` `GetCredentialReport` `GenerateCredentialReport` `GetAccountPasswordPolicy` `GetAccountSummary` `ListMFADevices` `ListGroups` `ListAttachedGroupPolicies` `ListGroupPolicies` `ListAttachedUserPolicies` `ListUserPolicies` `ListInstanceProfiles` `ListSAMLProviders` `ListGroupsForUser` `ListPolicies` `ListServiceSpecificCredentials` | root MFA、密码策略、访问密钥年龄、用户直挂策略查不了 |
| S3 / EC2 | `s3:GetAccountPublicAccessBlock` `s3:GetReplicationConfiguration` `ec2:GetEbsEncryptionByDefault` | 账号级公开访问拦截、桶复制、EBS 默认加密查不了 |
| EFS | `DescribeFileSystems` `DescribeFileSystemPolicy` `DescribeMountTargets` `DescribeMountTargetSecurityGroups` `DescribeAccessPoints` `DescribeBackupPolicy` | EFS 整节未核实 |
| Trusted Advisor | `trustedadvisor:ListRecommendations` `ListRecommendationResources` `GetRecommendation`；`support:DescribeTrustedAdvisorChecks` `DescribeTrustedAdvisorCheckResult` `DescribeTrustedAdvisorCheckSummaries` | 无 TA 交叉来源。只在账号为 Business Support 及以上时有效 |
| 其他 | `sso:DescribePermissionSet` `inspector2:BatchGetAccountStatus` `guardduty:GetFindingsStatistics` `access-analyzer:GetFinding` | 对应项未核实 |

- 可选：AWS 托管策略 `CloudWatchReadOnlyAccess`，用于 Flow Logs 和日志查询
- 本 agent 不依赖任何 skill 或 memory store

## Creating the Agent

1. 在 DevOps Agent Web App 左下角打开 **Agents** 菜单
2. 点右侧 **Create agent**，在弹出的菜单里选 **Form**（最左边的选项）
3. **Name** 填 `aws-security-posture-review`
4. 把本目录 `SYSTEM_PROMPT.md` 的全文复制进 **System prompt** 字段（上限 50,000 字符，本文件 49,936）
5. **Skills** 和 **Memory stores** 都不选，点 **Create agent**
6. 配工具：在新建 agent 的页面点 **Edit**，在弹出窗口选 **Chat**，等 DevOps Agent 问你要改什么，然后发：

   ```
   Set the tools of aws-security-posture-review to exactly these 11 and remove any other:
   use_aws, create_or_update_artifact, verify_aws_claim, lookup_cloudtrail_events,
   query_cloudwatch_logs, list_resources, list_resources_by_type, list_resource_details,
   list_resource_history, get_topology_map, get_resource_edges
   ```

7. 回到 agent 页面核对 **Tools** 正好是这 11 个（`use_aws` 加 10 个平台读工具），**没有 use_kubectl**。工具白名单是只读的硬边界，少一个会有检查项变「未核实」，多一个写类工具就破坏了只读承诺

## Executing the Agent

按官方 [Executing custom agents](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) 从 agent 页面 **Run Now** 旁的下拉选 **Run with prompt**，也可以配 schedule 定期跑。任务描述写法：

| 要什么 | 任务描述 |
|---|---|
| 整轮 12 份 | `目标账号 123456789012，主区域 us-east-1。严格只读。` |
| 只看一块 | 上面那句 + `帮我做 IAM 分析`（或 `只做 Part 6 IAM`） |
| 有不能动的资源 | 再加 `以下资源标为不得改动：<资源名或 ID 列表>` |

单册对照：IAM / 用户 / 角色 / 密钥 / MFA / SSO -> Part 6；S3 / 桶 -> Part 4B；EKS / ECS / 容器 -> Part 5B；EC2 / Lambda / ECR / SNS / SQS -> Part 5；EBS / RDS / KMS / 快照 / Secrets / 备份 / EFS / DynamoDB / ElastiCache -> Part 4；安全组 / 公网暴露 / NACL -> Part 3A；网络防火墙 / 负载均衡 / API Gateway / CloudFront / Route 53 / Flow Log / VPC Endpoint -> Part 3B；WAF -> Part 8；GuardDuty / Access Analyzer -> Part 2B；基线 / CloudTrail / Config / Security Hub / Inspector / Macie -> Part 2A；变更归因 / 谁改的 -> Part 7（依赖整轮的高严重度发现，单投意义不大）。

跑完后结果在 Web App 的 **Artifacts** 页，总览里的分册链接可直接点开。同一个 custom agent 一次只跑一个任务，再投的会排队。

### 审查其他账号

agent 只能读已接入 Agent Space 的账号。要审别的账号，先在 Agent Space -> Capabilities -> Cloud -> Secondary sources 把它接进来（一个账号一个角色，角色上同样要加 `AIDevOpsAgentAccessPolicy` + 控制台生成的 inline policy + `iam-extra-readonly-policy.json`），再在任务描述里写该账号 ID。官方步骤见 [Connecting multiple AWS Accounts](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-connecting-multiple-aws-accounts.html)。

## Known Limitations

- 以下三项角色有权限也查不到，报告里标「未核实」：`iam:GenerateCredentialReport`（账号里从未生成过凭证报告时读不到）、`sso-admin:DescribePermissionSet` 等（改读本账号的 `AWSReservedSSO_*` 落地角色）、账号级 S3 公开访问拦截
- Trusted Advisor 交叉来源只在 Business Support 及以上套餐可用
- 平台的 MCP 工具会话偶发中断时，整轮会提前结束，总览 §0 会列出「本轮未完成」的分册；用单册模式补那几册即可
- 资源很多时（如数百个 IAM 角色）部分检查按 prompt 里的规则缩小范围，各分册「检查范围」写明查了多少
- 一个任务只审一个账号，多账号就投多个任务，串行执行

## Disclaimer

本 custom agent 是示例代码（sample code），未经额外审查和测试不应直接用于生产环境。请先在非生产环境验证其行为，并按你所在组织的安全策略审查 IAM 权限和工具配置。它只读不写，但报告中的「怎么改」步骤由人执行前应逐条核对。

## Related

- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
- [Creating a custom agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-creating-a-custom-agent.html)
- [AIDevOpsAgentAccessPolicy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html)
