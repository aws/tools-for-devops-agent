---
title: React Native Client SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly React Native SDK
---

# React Native — SDK detail

- Official docs: [React Native SDK reference](https://launchdarkly.com/docs/sdk/client-side/react/react-native)
- API reference: [React Native SDK (`@launchdarkly/react-native-client-sdk`)](https://launchdarkly.github.io/js-core/packages/sdk/react-native/docs/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (React Native)

**Current SDK:** **`@launchdarkly/react-native-client-sdk` v10** (TypeScript, [Expo-compatible](https://launchdarkly.com/docs/sdk/client-side/react/react-native); iOS and Android only—not web). Build **`ReactNativeLDClient`** with the **mobile key**, wrap the app in **`LDProvider`**, and call **`identify(context)`** after mount (no context at construction). **`identify`** uses a **5s timeout by default**; do not strip timeouts in custom configuration.

**Install (non-Expo):** Add **`@react-native-async-storage/async-storage`**, then run **`npx pod-install`** for iOS ([Install the SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-native)).

**Mobile key:** Resolve a non-empty string at runtime (below uses Expo’s `EXPO_PUBLIC_` env). Bare React Native typically uses **react-native-config** or native build settings—never hardcode keys in source. Logical name: [Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration).

**Includes:** Copy-paste onboarding sample below.

```tsx
import { useEffect } from 'react';
import {
  AutoEnvAttributes,
  LDProvider,
  ReactNativeLDClient,
} from '@launchdarkly/react-native-client-sdk';

const mobileKey = process.env.EXPO_PUBLIC_LAUNCHDARKLY_MOBILE_KEY?.trim();
if (!mobileKey) {
  throw new Error(
    'LaunchDarkly: missing mobile key. For Expo, set EXPO_PUBLIC_LAUNCHDARKLY_MOBILE_KEY. For bare React Native, inject the key (for example react-native-config) and pass it here.',
  );
}

const ldClient = new ReactNativeLDClient(mobileKey, AutoEnvAttributes.Enabled, {
  debug: true,
  applicationInfo: {
    id: 'ld-rn-test-app',
    version: '0.0.1',
  },
});

// A "context" is a data object representing users, devices, organizations, and other entities.
const context = { kind: 'user', key: 'EXAMPLE_CONTEXT_KEY' };

const App = () => {
  useEffect(() => {
    ldClient.identify(context).catch((e: unknown) => {
      console.error('LaunchDarkly identify failed:', e);
    });
  }, []);

  return (
    <LDProvider client={ldClient}>
      <YourComponent />
    </LDProvider>
  );
};

export default App;
```

Expo requires the **`EXPO_PUBLIC_`** prefix for `process.env` in app code; other setups should substitute their own resolved string for `mobileKey`.
