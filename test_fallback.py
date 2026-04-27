import asyncio
from azathoth.providers.registry import register
from azathoth.providers.base import ProviderUnavailable
from azathoth.config import get_config

class Fake503:
    name = "gemini"
    _model = "fake-503"
    supports_native_tools = False
    async def generate(self, *a, **k):
        raise ProviderUnavailable("503 UNAVAILABLE")

class FakeOllama:
    name = "ollama"
    _model = "fake-ollama"
    supports_native_tools = False
    async def generate(self, *a, **k):
        from azathoth.providers.base import LLMResponse
        return LLMResponse(text="Ollama says hello!", tool_calls=[], provider_name="ollama", model="fake-ollama")

register("gemini", lambda: Fake503())
register("ollama", lambda: FakeOllama())

from azathoth.core.llm import generate
async def main():
    print(await generate("sys", "user"))

asyncio.run(main())
