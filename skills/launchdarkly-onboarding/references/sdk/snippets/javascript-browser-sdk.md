---
title: JavaScript Browser SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly JavaScript client-side (browser) SDK
---

# JavaScript (Browser) — SDK detail

- Official docs: [JavaScript SDK reference](https://launchdarkly.com/docs/sdk/client-side/javascript)
- API reference: [Browser client (`@launchdarkly/js-client-sdk`)](https://launchdarkly.github.io/js-core/packages/sdk/browser/docs/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (JavaScript Browser)

Use **`@launchdarkly/js-client-sdk`**: **`createClient`**, **`start()`**, then **`waitForInitialization({ timeout })`**. Always pass a **timeout** (the docs recommend **1–5 seconds**); without one, connectivity issues can block your app. In v4, `waitForInitialization` **always settles** with a **status** (`complete`, `failed`, or `timeout`)—handle each path ([Use promises to determine when the client is ready](https://launchdarkly.com/docs/sdk/client-side/javascript)).

**Client-side ID and env vars:** Use the **Client-side ID** from **Project settings > Environments** (not a server SDK key). Bundler prefixes: [Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration).

Use this in an ES module context that supports top-level `await`, or wrap in an `async` function.

**Includes:** Copy-paste onboarding sample below. After `status === 'complete'`, replace the flush/log block with your own logic (the docs’ `handleInitializedClient` is only an illustration).

```javascript
import { createClient } from '@launchdarkly/js-client-sdk';

const clientSideID = import.meta.env.VITE_LAUNCHDARKLY_CLIENT_SIDE_ID;

// A "context" is a data object representing users, devices, organizations, and
// other entities. You'll need this later, but you can ignore it for now.
const context = {
  kind: 'user',
  key: 'EXAMPLE_CONTEXT_KEY',
};

const client = createClient(clientSideID, context);
client.start();

const result = await client.waitForInitialization({ timeout: 5 });

if (result.status === 'complete') {
  await client.flush();
  console.log('SDK successfully initialized!');
} else if (result.status === 'failed') {
  console.error('LaunchDarkly initialization failed:', result.error);
} else if (result.status === 'timeout') {
  console.error(
    'LaunchDarkly initialization timed out; the client keeps retrying in the background.',
  );
}
```

For Create React App, replace `import.meta.env.VITE_LAUNCHDARKLY_CLIENT_SIDE_ID` with `process.env.REACT_APP_LAUNCHDARKLY_CLIENT_SIDE_ID`. For Next.js, use `process.env.NEXT_PUBLIC_LAUNCHDARKLY_CLIENT_SIDE_ID`.
