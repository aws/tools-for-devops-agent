---
title: Python Server SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly Python server-side SDK
---

# Python (Server) — SDK detail

- Official docs: [Python SDK reference](https://launchdarkly.com/docs/sdk/server-side/python)
- API reference: [launchdarkly-server-sdk (Read the Docs)](https://launchdarkly-python-sdk.readthedocs.io/)
- Published package: [launchdarkly-server-sdk (PyPI)](https://pypi.org/project/launchdarkly-server-sdk/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (Python Server)

Use a **current** `launchdarkly-server-sdk` release; see the [SDK releases page](https://github.com/launchdarkly/python-server-sdk/releases) and [version compatibility](https://launchdarkly.com/docs/sdk/server-side/python) (Python **3.9+** from SDK **9.12+**).

**Install** ([Install the SDK](https://launchdarkly.com/docs/sdk/server-side/python#install-the-sdk)):

```bash
pip install launchdarkly-server-sdk
```

Optional observability ([Python observability](https://launchdarkly.com/docs/sdk/observability/python)) — requires Python SDK **9.12+**:

```bash
pip install launchdarkly-observability
```

**Import** (same topic):

```python
import ldclient
from ldclient.config import Config

# Optional — launchdarkly-observability package; requires Python SDK v9.12+
# from ldobserve import ObservabilityPlugin
```

**Initialize:** Call **`ldclient.set_config(Config(...))`** once, then **`ldclient.get()`** for the singleton client ([Initialize the client](https://launchdarkly.com/docs/sdk/server-side/python#initialize-the-client)). With observability: `Config(sdk_key, plugins=[ObservabilityPlugin()])`. Worker processes that **fork** may need **`postfork()`** ([Considerations with worker-based servers](https://launchdarkly.com/docs/sdk/server-side/python#considerations-with-worker-based-servers)).

**Includes:** Minimal onboarding script. SDK key: **`LAUNCHDARKLY_SDK_KEY`** ([Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration)).

```python
import os
import sys

import ldclient
from ldclient.config import Config

if __name__ == "__main__":
    sdk_key = os.environ.get("LAUNCHDARKLY_SDK_KEY")
    if not sdk_key or not sdk_key.strip():
        print(
            "LAUNCHDARKLY_SDK_KEY is not set. Use Project settings > Environments > SDK key.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()

    if not client.is_initialized():
        print("LaunchDarkly client failed to initialize", file=sys.stderr)
        raise SystemExit(1)

    # For onboarding only — events are normally flushed in the background.
    client.flush()
    print("LaunchDarkly client ready.")
```
