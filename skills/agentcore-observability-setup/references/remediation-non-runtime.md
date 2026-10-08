# Remediation — Agents Hosted Outside AgentCore Runtime

For agents on Lambda, ECS, EKS, on-prem, or another cloud. Prerequisites first: enable CloudWatch
Transaction Search (see `remediation-runtime.md` §1) and add the ADOT SDK to the code. Then create
an agent log group and set the environment variables below.

> **ADOT Collector is not supported.** Use the ADOT SDK, or on Lambda the AWS Lambda Layer for
> OpenTelemetry. Nothing else.

All steps are applied by the customer; the skill only generates them.

---

## Full OTEL environment (ECS / EKS / on-prem / multi-cloud)

**AWS environment:**

```
AWS_ACCOUNT_ID=<account id>
AWS_DEFAULT_REGION=<default region>
AWS_REGION=<region>
AWS_ACCESS_KEY_ID=<access key id>        # on-prem/multi-cloud, or IAM Roles Anywhere
AWS_SECRET_ACCESS_KEY=<secret key>       # prefer role-based creds on AWS hosts
```

**OTEL environment:**

```
AGENT_OBSERVABILITY_ENABLED=true
OTEL_PYTHON_DISTRO=aws_distro
OTEL_PYTHON_CONFIGURATOR=aws_configurator          # ADOT Python only
OTEL_RESOURCE_ATTRIBUTES=service.name=<agent-name>,aws.log.group.names=/aws/bedrock-agentcore/runtimes/<agent-id>,cloud.resource_id=<AgentEndpointArn:AgentEndpointName>
OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=/aws/bedrock-agentcore/runtimes/<agent-id>,x-aws-log-stream=runtime-logs,x-aws-metric-namespace=bedrock-agentcore
OTEL_EXPORTER_OTLP_TRACES_HEADERS=x-aws-log-group=/aws/bedrock-agentcore/runtimes/<agent-id>,x-aws-log-stream=spans   # optional: unified spans; needs ADOT >=0.18.0 + X-Ray log-group resource policy
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_EXPORTER=otlp
```

On AWS-hosted compute (ECS/EKS), use the task/pod IAM role instead of static access keys.

If `OTEL_EXPORTER_OTLP_TRACES_HEADERS` points spans at your own log group, add the X-Ray log-group
resource policy (see `remediation-runtime.md` §4).

---

## Lambda

Lambda uses the **AWS Lambda Layer for OpenTelemetry** — do **not** add `aws-opentelemetry-distro`
or run `opentelemetry-instrument`.

1. Attach the AWS Lambda Layer for OpenTelemetry to the function.
2. Set:

```
AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-instrument
```

3. Add the agent log-group / OTEL resource attributes as above. Lambda-specific extras:

```
OTEL_AWS_APPLICATION_SIGNALS_ENABLED=false   # disable Application Signals
OTEL_LOGS_EXPORTER=otlp                       # export logs over OTLP
OTEL_METRICS_EXPORTER=awsemf                  # metrics as CloudWatch EMF
```

**Verify (Tier 3):** `lambda:GetFunctionConfiguration` → Layer present, `AWS_LAMBDA_EXEC_WRAPPER`
set, OTEL/log-group vars present.

---

## ECS

Put the full OTEL environment (above) into the container definition's `environment` block; use the
task role for credentials.

**Verify (Tier 3):** `ecs:DescribeTaskDefinition` → container env carries the OTEL variable set.

---

## EKS

The OTEL environment lives in the pod spec / ConfigMap, governed by Kubernetes RBAC — **not**
verifiable via IAM. The skill verifies **telemetry arrival** (Tier 1: is the agent log group
receiving data?) and prescribes the pod/ConfigMap env below. Direct pod-env verification is out of
scope: it would require EKS Access Entries, in-cluster RBAC, and native Kubernetes API calls
(partially mutating, per-cluster), which this read-only skill does not perform.

Set the OTEL environment (above) in the pod spec or a ConfigMap referenced by the deployment.

---

## On-prem / multi-cloud

Outside the DevOps Agent's reach — **prescribe only**. Same ADOT SDK env as ECS/EKS, plus:

- Credentials: IAM access keys **or** IAM Roles Anywhere (preferred).
- Outbound HTTPS to the AWS OTLP endpoints must be allowed from the host network.
- Create the agent log group in the target AWS account/region and reference it in
  `OTEL_RESOURCE_ATTRIBUTES` / `OTEL_EXPORTER_OTLP_*_HEADERS`.
