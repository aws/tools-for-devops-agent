---
title: Edge SDKs (Cloudflare, Vercel, Fastly, Akamai)
description: Where to find LaunchDarkly edge platform SDK documentation and packages
---

# Edge SDKs — SDK detail

Edge SDKs use an **SDK Key**. Use the platform-specific reference for constraints (e.g. KV, environment, bundling).

| Platform | Detect pattern | Official docs | Package / repo |
|----------|----------------|---------------|----------------|
| Akamai EdgeWorkers | `bundle.json`, `edgeworkers` | [Akamai SDK reference](https://launchdarkly.com/docs/sdk/edge/akamai) | [js-core / akamai-edgekv](https://github.com/launchdarkly/js-core/tree/main/packages/sdk/akamai-edgekv) · [API docs](https://launchdarkly.github.io/js-core/packages/sdk/akamai-edgekv/docs) |
| Cloudflare Workers | `wrangler.toml`, `@cloudflare/workers-types` | [Cloudflare SDK reference](https://launchdarkly.com/docs/sdk/edge/cloudflare) | [js-core / cloudflare](https://github.com/launchdarkly/js-core/tree/main/packages/sdk/cloudflare) · [API docs](https://launchdarkly.github.io/js-core/packages/sdk/cloudflare/docs/) |
| Fastly Compute | Fastly config, `@fastly/js-compute` (typical) | [Fastly SDK reference](https://launchdarkly.com/docs/sdk/edge/fastly) | [js-core / fastly](https://github.com/launchdarkly/js-core/tree/main/packages/sdk/fastly) · [API docs](https://launchdarkly.github.io/js-core/packages/sdk/fastly/docs/) |
| Vercel Edge | `vercel.json` with edge functions, `@vercel/edge` | [Vercel SDK reference](https://launchdarkly.com/docs/sdk/edge/vercel) | [js-core / vercel](https://github.com/launchdarkly/js-core/tree/main/packages/sdk/vercel) · [API docs](https://launchdarkly.github.io/js-core/packages/sdk/vercel/docs/) |

**Recipe index:** [SDK Recipes](../recipes.md) — Edge SDKs

There are no bundled onboarding code samples in this repo for edge SDKs; follow each platform’s official reference.