---
title: React Web SDK — SDK detail
description: Root-level React onboarding sample and links for the LaunchDarkly React Web SDK
---

# React (Web) — SDK detail

- Official docs: [React SDK reference](https://launchdarkly.com/docs/sdk/client-side/react) · [React Web SDK reference](https://launchdarkly.com/docs/sdk/client-side/react/react-web)
- API reference: [React Web SDK (`launchdarkly-react-client-sdk`)](https://launchdarkly.github.io/react-client-sdk/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (React Web)

**Initialization:** Prefer **`asyncWithLDProvider`** so the tree mounts after the underlying JavaScript client is ready (avoids startup flag flicker). Pass **`timeout`** in **seconds** (docs recommend **1–5**); it is forwarded to `waitForInitialization` on the JS client ([Configuration options](https://launchdarkly.com/docs/sdk/client-side/react/react-web)). **`withLDProvider`** is an alternative if you accept initializing after the first mount.

**Credentials:** **Client-side ID** from **Project settings > Environments** (not a server SDK key). Bundler env prefixes: [Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration).

**Includes:** Copy-paste sample for a Vite-style client entry (e.g. `main.tsx`). Requires **React 16.8+** (`asyncWithLDProvider` uses hooks).

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { asyncWithLDProvider } from 'launchdarkly-react-client-sdk';

function App() {
  return <div>Let your feature flags fly!</div>;
}

// A "context" is a data object representing users, devices, organizations, and other entities.
const context = {
  kind: 'user',
  key: 'EXAMPLE_CONTEXT_KEY',
  email: 'user@example.com',
};

const clientSideID = import.meta.env.VITE_LAUNCHDARKLY_CLIENT_SIDE_ID?.trim();
if (!clientSideID) {
  throw new Error(
    'LaunchDarkly: missing client-side ID. Set VITE_LAUNCHDARKLY_CLIENT_SIDE_ID (Vite), REACT_APP_LAUNCHDARKLY_CLIENT_SIDE_ID (CRA), or NEXT_PUBLIC_LAUNCHDARKLY_CLIENT_SIDE_ID (Next.js client).',
  );
}

void (async () => {
  const LDProvider = await asyncWithLDProvider({
    clientSideID,
    context,
    timeout: 5,
  });

  const rootEl = document.getElementById('root');
  if (!rootEl) {
    throw new Error('LaunchDarkly bootstrap: #root element not found');
  }

  createRoot(rootEl).render(
    <StrictMode>
      <LDProvider>
        <App />
      </LDProvider>
    </StrictMode>,
  );
})();
```

For Create React App, read the ID from `process.env.REACT_APP_LAUNCHDARKLY_CLIENT_SIDE_ID` instead of `import.meta.env.VITE_…`. For Next.js client bundles, use `process.env.NEXT_PUBLIC_LAUNCHDARKLY_CLIENT_SIDE_ID` in a client entry (`'use client'` as required).
