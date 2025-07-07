import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint             # versioni asincrone di input e print
from neo4j import AsyncGraphDatabase

# fmt: off
USER_PROMPT  = "[User]  "
AGENT_PROMPT = "[Agent] "
# fmt: on


class LLM:
    def __init__(
        self, model: str = "llama3.1", system: str = "You are a helpful assistant."
    ) -> None:
        self.system = system
        self._client = ol.AsyncClient("localhost")     # crea un'istanza di AsyncClient di Ollama per collegarsi al server
        self._model = model

    async def chat(self, query: str) -> AsyncIterator[str]:
        messages = (
            ol.Message(role="system", content=self.system),
            ol.Message(role="user", content=query),
        )
        async for chunk in await self._client.chat(self._model, messages, stream=True):
            yield chunk.message.content


async def print_response(agent: LLM, query: str) -> None:
    await aprint(AGENT_PROMPT, end="")
    async for chunk in agent.chat(query):
        await aprint(chunk, end="")
    await aprint()


async def user_input() -> str:
    return await ainput(USER_PROMPT)


async def main() -> None:
    agent = LLM()
    agent.system = "Always respond in a brief, condescending, sarcastic way."
    try:
        while True:
            await print_response(agent, await user_input())
    except asyncio.CancelledError:
        await aprint(" Goodbye")
        await print_response(agent, "Goodbye")


if __name__ == "__main__":
    asyncio.run(main())