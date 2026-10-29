---
title: Node.js Server SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly Node.js server-side SDK
---

# Node.js (Server) — SDK detail

- Official docs: [Node.js SDK reference (server-side)](https://launchdarkly.com/docs/sdk/server-side/node-js)
- API reference: [SDK API docs](https://launchdarkly.github.io/js-core/packages/sdk/server-node/docs/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (Node.js Server)

**Includes:** Patterns below follow the **Get started**, **Initialize the client**, **Evaluate a context**, and **Promises and async** sections of the [Node.js server-side SDK reference](https://launchdarkly.com/docs/sdk/server-side/node-js). Use **one** initialization strategy (`waitForInitialization` **or** the `ready` event—not both at once unless you know why).

### Singleton client

`LDClient` must be a **singleton** per LaunchDarkly environment—do not create a new client per request. Use your real SDK key from env vars, not a literal in source.

```javascript
import { init } from '@launchdarkly/node-server-sdk';

const client = init(process.env.LAUNCHDARKLY_SDK_KEY);
```

### Wait for initialization (startup)

Run this **once** during process startup—for example before your HTTP server accepts connections, inside whatever async bootstrap your framework provides. The public docs use `{ timeout: 10 }` (seconds); adjust as needed.

**Promise style** (from [Promises and async](https://launchdarkly.com/docs/sdk/server-side/node-js)):

```javascript
client
  .waitForInitialization({ timeout: 5 })
  .then(() => {
    // Initialization complete — safe to evaluate flags and/or start serving traffic.
  })
  .catch((err) => {
    // Timeout or initialization failed
  });
```

**Async/await** (same topic—must live inside an `async` function your app already uses for startup):

```javascript
try {
  await client.waitForInitialization({ timeout: 5 });
  // Initialization complete
} catch (err) {
  // Timeout or initialization failed
}
```

**Alternative:** the docs also document a `ready` event and callback-style `client.variation(..., (err, value) => { ... })` under **Evaluate a context**—use that form if it fits your codebase better.

### Evaluate a flag (when handling work)

The docs state that in production you should invoke `variation` **as needed** (not only once at import). Use `await` inside an `async` route handler, service method, job, etc.

```javascript
const context = {
  kind: 'user',
  key: 'example-user-key',
  name: 'Example User',
};

const showFeature = await client.variation('example-flag-key', context, false);
```

For a boolean flag you may use `boolVariation` if you prefer; the official getting-started examples use `variation` with a boolean default.
