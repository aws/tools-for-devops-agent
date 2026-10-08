# DevOps Agent alarm investigations

Forwards **one** Amazon CloudWatch alarm to an AWS DevOps Agent generic webhook, so the
alarm opens an investigation. **One stack = one alarm** — deploy it again per alarm.

No Lambda and no code: an Amazon EventBridge rule scoped to the alarm ARN matches
`CloudWatch Alarm State Change` with `state.value = ALARM`, an input transformer builds
the incident payload, and an EventBridge API destination POSTs it. The API key lives in an
EventBridge connection, which sends it as `Authorization: Bearer <key>`. An IAM role grants
the rule `events:InvokeApiDestination` on that one destination.

The payload carries only the alarm ARN and the raised state — no alarm name, reason, or
metric data. DevOps Agent enriches from the ARN.

## Before you deploy

The webhook is created in the console (there is no `CreateWebhook` API) and its API key is
shown only once, so it must exist first:

1. Create the Agent Space.
2. Console → **Capabilities → Agent Space Webhook → Generate webhook**, authentication type
   **API key**. Copy the URL and the key — the key is not retrievable later.
3. Deploy this stack with that URL, that key, and the alarm ARN.

Lost the key? Rotate the webhook from the Capabilities tab; rotation keeps the URL and
issues a new key. Update the stack afterwards — the connection re-reads the key only when
the stack is updated.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WebhookUrl` | *(required)* | HTTPS URL of the generic webhook. |
| `WebhookApiKey` | *(required)* | The API key from webhook creation. `NoEcho`, so it is masked in stack events and `describe-stacks`. |
| `AlarmArn` | *(required)* | ARN of the single alarm to forward. |
| `InvocationRateLimitPerSecond` | `300` | Cap on webhook invocations per second — 300 is the per-destination quota, so the stack adds no throttling. Lower it only to deliberately rate-limit the webhook. |
| `DevOpsAgentAlarmIntegrationTag` | *(stack name)* | Value of the `DevOpsAgent` tag on the rule and role. Identification and cost allocation only; does not affect routing. |

## Deploy

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-alarm-investigations/devops-agent-alarm-investigations.yaml \
  --stack-name devops-agent-alarm-investigations-<alarm-name> \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      WebhookUrl="https://<your-webhook-url>" \
      WebhookApiKey="<your-webhook-api-key>" \
      AlarmArn="arn:aws:cloudwatch:<region>:<account>:alarm:<alarm-name>"
```

## Notes

- **Cross-Region and cross-account alarms.** Deploy this stack once, in the DevOps Agent's
  account and Region, and set `AlarmArn` to the alarm's real (possibly remote) ARN. Remote
  alarms reach it via ordinary
  [bus-to-bus forwarding](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-cross-account.html):
  a rule in the alarm's own Region/account targeting the agent Region's default bus, plus —
  cross-account only — a resource policy on the agent bus allowing `PutEvents` from the
  source account. The forwarded event still carries the alarm ARN in `resources`, so this
  stack's rule matches it.
- **Region availability.** API destinations to public HTTPS endpoints are not available in
  every Region — check
  [API destinations as targets](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-api-destinations.html#eb-api-destination-regions).
- **Deduplication.** `incidentId` is the EventBridge event id, constant across retries, so
  redeliveries reuse it instead of opening duplicates. Control flapping at the alarm's
  datapoints-to-alarm setting.
- **Delivery.** Up to 32 retry attempts over 8 hours; API destinations require a response
  within 5 seconds. `MaximumEventAgeInSeconds` stops retries once an event is older than
  the window, so a late redelivery cannot open a stale investigation.
- **Monitoring.** There is no log group. The rule publishes `InvocationAttempts`,
  `SuccessfulInvocationAttempts`, `RetryInvocationAttempts` and `FailedInvocations` in
  `AWS/Events` by `RuleName`. Alarm on `FailedInvocations`; add a dead-letter queue to the
  target to inspect events that never landed.
- **Keeping the key in your own secret.** Replace `ApiKeyValue` with
  `'{{resolve:secretsmanager:MyWebhookSecret}}'` and drop the `WebhookApiKey` parameter, so
  the key never passes through a stack parameter. Same rotation caveat as above.
- **API key versus HMAC.** The webhook also supports HMAC, but EventBridge connections
  support only Basic, API key, and OAuth and cannot sign per request — HMAC would need a
  signing Lambda in between. This template takes the API key path to stay code-free.
