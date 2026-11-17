# Metrics & Logs Reference

The CloudWatch metric set for SageMaker real-time inference endpoints.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds live in `cloudwatch-alarm-reference.md`, not here.

---

## aws/sagemaker/Endpoints — SageMaker inference metrics

Two namespaces. Invocation metrics are in `AWS/SageMaker`; instance resource metrics are in `/aws/sagemaker/Endpoints`. Dimensions: `EndpointName`, `VariantName`. Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html

Invocation metrics (`AWS/SageMaker`):

| Metric | Unit | Meaning |
|---|---|---|
| `Invocations` | Count | Requests sent to the variant |
| `InvocationsPerInstance` | Count | Invocations normalized per instance (scaling signal) |
| `ModelLatency` | Microseconds | Time the model/container took to respond |
| `OverheadLatency` | Microseconds | SageMaker overhead added to the request |
| `Invocation4XXErrors` | Count | Client errors |
| `Invocation5XXErrors` | Count | Server errors |
| `ModelSetupTime` | Microseconds | Cold-start/model load time (async/serverless) |

Instance resource metrics (`/aws/sagemaker/Endpoints`):

| Metric | Meaning |
|---|---|
| `CPUUtilization` | CPU across the container(s) |
| `MemoryUtilization` | Memory utilization |
| `DiskUtilization` | Storage volume utilization |
| `GPUUtilization` | GPU compute utilization (GPU instances) |
| `GPUMemoryUtilization` | GPU memory utilization (GPU instances) |
