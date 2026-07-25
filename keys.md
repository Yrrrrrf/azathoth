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
