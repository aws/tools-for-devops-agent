# Before/After Examples

Paired code snippets for the Stage 2 call-site swap. Each example shows the same call before extraction and after wrapping with the LaunchDarkly AI SDK. Tools and tracking are deliberately **not** shown here — they are layered on in Stages 3 and 4. See [sdk-ai-tracker-patterns.md](sdk-ai-tracker-patterns.md) for the tracking overlay and [agent-mode-frameworks.md](agent-mode-frameworks.md) for the tool-loading pattern.

---

## Example 1: Python + OpenAI — completion mode

A typical one-shot chat app. Hardcoded model, temperature, max tokens, and system prompt.

### Before

```python
from openai import OpenAI

openai_client = OpenAI()

def answer(user_question: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
            {"role": "user", "content": user_question},
        ],
    )
    return response.choices[0].message.content
```

### After

```python
import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AICompletionConfigDefault, ModelConfig, ProviderConfig, LDMessage
from openai import OpenAI

openai_client = OpenAI()

ldclient.set_config(Config(os.environ["LD_SDK_KEY"]))
ai_client = LDAIClient(ldclient.get())

# Fallback mirrors the hardcoded values that were removed.
FALLBACK = AICompletionConfigDefault(
    enabled=True,
    model=ModelConfig(
        name="gpt-4o",
        parameters={"temperature": 0.7, "max_tokens": 2000},
    ),
    provider=ProviderConfig(name="openai"),
    messages=[LDMessage(role="system", content="You are a helpful assistant. Answer concisely.")],
)

def answer(user_id: str, user_question: str) -> str:
    context = Context.builder(user_id).kind("user").build()
    config = ai_client.completion_config("chat-assistant", context, FALLBACK)

    if not config.enabled:
        return ""  # handle disabled path

    params = config.model.parameters or {}
    response = openai_client.chat.completions.create(
        model=config.model.name,
        temperature=params.get("temperature"),
        max_tokens=params.get("max_tokens"),
        messages=[m.to_dict() for m in (config.messages or [])] + [
            {"role": "user", "content": user_question},
        ],
    )
    return response.choices[0].message.content
```

### What changed

- Model/params/prompt no longer appear as string literals — they come from `config.model.name`, `config.model.parameters`, and `config.messages`
- `LDAIClient` is initialized once at import time
- A `Context` is built per request from `user_id` (targeting happens here)
- Fallback is an `AICompletionConfigDefault` that mirrors the removed hardcoded values
- `config.enabled` is checked before calling the provider
- The provider call itself is unchanged — same `openai_client.chat.completions.create`, same return shape

---

## Example 2: Node.js + Anthropic — completion mode

Anthropic separates the system message from the messages array, so this example shows the `convertToAnthropicFormat` helper used in the relaunch guide.

### Before

```typescript
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic();

export async function answer(userQuestion: string): Promise<string> {
  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4-5',
    max_tokens: 1024,
    system: 'You are a helpful assistant. Answer concisely.',
    messages: [{ role: 'user', content: userQuestion }],
  });
  const text = response.content.find((b) => b.type === 'text');
  return text?.type === 'text' ? text.text : '';
}
```

### After

```typescript
import Anthropic from '@anthropic-ai/sdk';
import { init, LDContext } from '@launchdarkly/node-server-sdk';
import { initAi, LDAICompletionConfigDefault } from '@launchdarkly/server-sdk-ai';

const anthropic = new Anthropic();
const ldClient = init(process.env.LD_SDK_KEY!);
await ldClient.waitForInitialization({ timeout: 10 });
const aiClient = initAi(ldClient);

const FALLBACK: LDAICompletionConfigDefault = {
  enabled: true,
  model: {
    name: 'claude-sonnet-4-5',
    parameters: { max_tokens: 1024 },
  },
  provider: { name: 'anthropic' },
  messages: [
    { role: 'system', content: 'You are a helpful assistant. Answer concisely.' },
  ],
};

function convertToAnthropicFormat(ldMessages?: Array<{ role: string; content: string }>) {
  let systemMessage: string | undefined;
  const messages: Array<{ role: 'user' | 'assistant'; content: string }> = [];
  for (const msg of ldMessages ?? []) {
    if (msg.role === 'system') {
      systemMessage = msg.content;
    } else {
      messages.push({ role: msg.role as 'user' | 'assistant', content: msg.content });
    }
  }
  return { systemMessage, messages };
}

export async function answer(userId: string, userQuestion: string): Promise<string> {
  const context: LDContext = { kind: 'user', key: userId };
  const aiConfig = await aiClient.completionConfig('chat-assistant', context, FALLBACK);

  if (!aiConfig.enabled) return '';

  const { systemMessage, messages } = convertToAnthropicFormat(aiConfig.messages);
  messages.push({ role: 'user', content: userQuestion });

  const response = await anthropic.messages.create({
    model: aiConfig.model?.name ?? 'claude-sonnet-4-5',
    max_tokens: (aiConfig.model?.parameters?.max_tokens as number) ?? 1024,
    system: systemMessage,
    messages,
  });

  const text = response.content.find((b) => b.type === 'text');
  return text?.type === 'text' ? text.text : '';
}
```

### What changed

- Hardcoded model + system prompt + `max_tokens` are gone
- `initAi(ldClient)` wraps the base client once at import
- `convertToAnthropicFormat` hoists the system message out of the `LDMessage` array (since Anthropic takes `system` as a top-level param, not a role in `messages`)
- `aiConfig.enabled` is checked; the disabled path returns an empty string
- Provider call is otherwise unchanged

---

## Example 3: Python + LangGraph — agent mode

`create_agent` (in `langchain.agents`) takes a model, tools, and `system_prompt` — a natural fit for **agent mode**. The `instructions` string replaces the hardcoded `system_prompt` argument. Tools remain hardcoded for now (Stage 3 will move them into the config too).

> **API note.** Use `from langchain.agents import create_agent`. The earlier `from langgraph.prebuilt import create_react_agent` is deprecated in LangGraph 1.0 and removed in 2.0. Same return shape; the only rename you'll feel at the call site is `prompt=` → `system_prompt=`. Node.js still uses `createReactAgent` from `@langchain/langgraph/prebuilt` — no JS deprecation.

### Before

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from my_tools import search_kb, calculator

llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

agent = create_agent(
    llm,
    [search_kb, calculator],
    system_prompt=(
        "You are a technical support assistant. Use the search_kb tool to look up "
        "documentation, and the calculator tool for math. Always cite sources."
    ),
)

def run_support(user_question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": user_question}]})
    return result["messages"][-1].content
```

### After

```python
import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AIAgentConfigDefault, ModelConfig, ProviderConfig
from ldai_langchain import create_langchain_model
from langchain.agents import create_agent
from my_tools import search_kb, calculator

ldclient.set_config(Config(os.environ["LD_SDK_KEY"]))
ai_client = LDAIClient(ldclient.get())

FALLBACK = AIAgentConfigDefault(
    enabled=True,
    model=ModelConfig(name="gpt-4o", parameters={"temperature": 0.3}),
    provider=ProviderConfig(name="openai"),
    instructions=(
        "You are a technical support assistant. Use the search_kb tool to look up "
        "documentation, and the calculator tool for math. Always cite sources."
    ),
)

def run_support(user_id: str, user_question: str) -> str:
    context = Context.builder(user_id).kind("user").build()
    config = ai_client.agent_config("support-agent", context, FALLBACK)

    if not config.enabled:
        return ""

    # create_langchain_model forwards every variation parameter. Do NOT hand-roll
    # ChatOpenAI(model=...) — it drops unnamed parameters silently.
    llm = create_langchain_model(config)

    agent = create_agent(
        llm,
        [search_kb, calculator],          # Stage 3 will replace this with config.tools loader
        system_prompt=config.instructions,
    )

    result = agent.invoke({"messages": [{"role": "user", "content": user_question}]})
    return result["messages"][-1].content
```

### What changed

- `agent_config()` is called instead of `completion_config()` because the framework expects an `instructions` string
- `FALLBACK` is an `AIAgentConfigDefault` (note the different type — same fields as completion except `instructions` instead of `messages`)
- Model construction goes through `create_langchain_model(config)` from the `ldai_langchain` helper package — forwards every variation parameter. The alternative of hand-rolling `ChatOpenAI(model=config.model.name, temperature=...)` would silently drop every parameter not explicitly named.
- `create_agent(..., system_prompt=...)` reads from `config.instructions`
- Tool list is still hardcoded — Stage 3 handles that move (see [agent-mode-frameworks.md](agent-mode-frameworks.md) for the tool-factory pattern that closes over per-run config)
- **Stage 4 will add a run-scoped tracker** (mint in a `setup_run` entry node, consume in `call_model` and `finalize`) — see [agent-mode-frameworks.md § Custom `StateGraph`](agent-mode-frameworks.md) for the full architecture
- Provider-side logic (LangGraph, ReAct loop) is unchanged

---

## Rules of thumb across all three examples

1. **Nothing is added to the business logic.** The provider call, the framework call, the return shape — all unchanged. Only the *source* of model/prompt/params moves.
2. **Fallback is built from the values you removed.** Full rules at [fallback-defaults-pattern.md § Critical rules](fallback-defaults-pattern.md).
3. **Build a `Context` per request.** The context carries targeting inputs — user ID, plan tier, region, whatever the rollout is keyed on. Reuse the same context the app already uses for feature flag evaluation if one exists.
4. **Always check `config.enabled`.** Even a successful `completion_config` call can return a disabled config (if the variation is turned off in LaunchDarkly). The disabled path should not call the provider.
5. **Do not cache the config object across requests.** Call `completion_config` / `agent_config` inside the request handler so LaunchDarkly can re-evaluate targeting per call. One `LDAIClient` instance, many `completion_config` calls.
