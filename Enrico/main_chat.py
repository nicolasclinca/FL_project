import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint             # versioni asincrone di input e print
from neo4j import AsyncGraphDatabase

# fmt: off
user_token = "[User]  > "
agent_token = "[Agent] > "
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
    await aprint(agent_token, end="")
    async for chunk in agent.chat(query):
        await aprint(chunk, end="")
    await aprint()


async def user_input() -> str:
    return await ainput(user_token)


async def main() -> None:
    agent = LLM()
    personalities = [
        "Always respond in a brief, condescending, sarcastic way.",
        "Always respond in a brief, gentle, syntetic way."
    ]
    agent.system = personalities[1]
    try:
        while True:
            complete_query = await user_input()
            await print_response(agent, complete_query)
            if complete_query.lower() in ["/exit", "/quit", "/goodbye", "/bye",]:
                # await aprint(agent_token + "Bye Bye!")
                break
    except asyncio.CancelledError:
        await aprint("Goodbye")
        await print_response(agent, "Goodbye")


if __name__ == "__main__":
    asyncio.run(main())
