---
title: Go Server SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly Go server-side SDK
---

# Go (Server) — SDK detail

- Official docs: [Go SDK reference](https://launchdarkly.com/docs/sdk/server-side/go)
- API reference: [`LDClient`, `MakeClient`](https://pkg.go.dev/github.com/launchdarkly/go-server-sdk/v7)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (Go Server)

The [Initialize the client](https://launchdarkly.com/docs/sdk/server-side/go#initialize-the-client) chapter shows **`MakeClient`** / **`MakeCustomClient`** (and optional **`ldcontext`** + **`NewScopedClient`** for a scoped client). It does **not** use **`Initialized()`** in that section. The **`error`** from **`MakeClient`** is what signals construction-time failure (see the “Best practices for error handling” callout in those docs). If you need to branch on “fully ready” after the timeout window, use **[`Initialized`](https://pkg.go.dev/github.com/launchdarkly/go-server-sdk/v7#LDClient.Initialized)** or **[Monitoring SDK status](https://launchdarkly.com/docs/sdk/features/monitoring#go)**—read **[`MakeClient`](https://pkg.go.dev/github.com/launchdarkly/go-server-sdk/v7#MakeClient)** for how the **timeout** interacts with returning before the client has finished connecting.

**Includes:** Minimal onboarding sample aligned with **“Go SDK, using LDClient and default configuration”** in the docs. For **`MakeCustomClient`**, **`ldcontext`**, **`LDScopedClient`**, or the **observability** plugin, follow the same page’s larger examples.

```go
package main

import (
	"fmt"
	"os"
	"time"

	ld "github.com/launchdarkly/go-server-sdk/v7"
)

func main() {
	ldClient, err := ld.MakeClient(os.Getenv("LAUNCHDARKLY_SDK_KEY"), 5*time.Second)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to create LaunchDarkly client: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("LaunchDarkly client created.")

	// For onboarding purposes only we flush events as soon as
	// possible so we quickly detect your connection.
	// You don't have to do this in practice because events are automatically flushed.
	ldClient.Flush()
}
```
