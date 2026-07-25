# AI Provider Consoles

Quick reference for developer consoles, API key pages, docs, and base URLs.

## TL;DR

| Provider       | Console                                                              | API Keys                                                                          | Docs                                       |
| -------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------ |
| Google AI      | <https://aistudio.google.com>                                        | <https://aistudio.google.com/app/apikey>                                          | <https://ai.google.dev/gemini-api/docs>    |
| Anthropic      | <https://console.anthropic.com>                                      | <https://console.anthropic.com/settings/keys>                                     | <https://docs.claude.com>                  |
| Kimi (Moonshot, intl) | <https://platform.moonshot.ai/console>                        | <https://platform.moonshot.ai/console/api-keys>                                   | <https://platform.moonshot.ai/docs>        |
| Kimi (Moonshot, CN)   | <https://platform.moonshot.cn/console>                        | <https://platform.moonshot.cn/console/api-keys>                                   | <https://platform.moonshot.cn/docs>        |
| Qwen (intl)    | <https://modelstudio.console.alibabacloud.com>                       | <https://modelstudio.console.alibabacloud.com/?tab=model#/api-key>                | <https://www.alibabacloud.com/help/en/model-studio> |
| Qwen (CN)      | <https://bailian.console.aliyun.com>                                 | <https://bailian.console.aliyun.com/?tab=model#/api-key>                          | <https://help.aliyun.com/zh/model-studio>  |

---

## Base URLs (OpenAI-compatible)

```text
# Google (Gemini, OpenAI-compatible mode)
https://generativelanguage.googleapis.com/v1beta/openai/

# Anthropic (native; not OpenAI-shaped)
https://api.anthropic.com/v1

# Kimi / Moonshot
https://api.moonshot.ai/v1            # international
https://api.moonshot.cn/v1            # China

# Qwen / DashScope (Alibaba Model Studio)
https://dashscope-intl.aliyuncs.com/compatible-mode/v1   # Singapore
https://dashscope-us.aliyuncs.com/compatible-mode/v1     # US (Virginia)
https://dashscope.aliyuncs.com/compatible-mode/v1        # China (Beijing)
```

---

## Env var convention

```bash
export GEMINI_API_KEY="..."
export ANTHROPIC_API_KEY="sk-ant-..."
export MOONSHOT_API_KEY="sk-..."
export DASHSCOPE_API_KEY="sk-..."
```

---

## Minimal Python sanity check (OpenAI SDK, swap base_url per provider)

```python
from openai import OpenAI
import os

providers = {
    "kimi": ("https://api.moonshot.ai/v1", "MOONSHOT_API_KEY", "kimi-k2"),
    "qwen": (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_API_KEY",
        "qwen-plus",
    ),
    "google": (
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
    ),
}

for name, (url, env, model) in providers.items():
    client = OpenAI(base_url=url, api_key=os.environ[env])
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "ping"}],
    )
    print(name, "→", r.choices[0].message.content)
```

Anthropic uses its own SDK (`anthropic` package), not the OpenAI shape:

```python
import anthropic

msg = anthropic.Anthropic().messages.create(
    model="claude-opus-4-7",
    max_tokens=64,
    messages=[{"role": "user", "content": "ping"}],
)
print(msg.content[0].text)
```