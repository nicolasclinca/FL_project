import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint  # versioni asincrone di input e print

#from neo4j import AsyncGraphDatabase

# fmt: off
user_token = "[User]  > "
agent_token = "[Agent] > "


# fmt: on


class LLM:
    def __init__(
            self, model: str = "llama3.1", sys_prompt: str = "You are a helpful assistant."
    ) -> None:
        self.sys_prompt = sys_prompt  # prompt di sistema
        self._client = ol.AsyncClient("localhost")  # istanza AsyncClient di Ollama per collegarsi al server
        self._model = model  # modello linguistico vero e proprio

    async def launch_chat(self, query: str) -> AsyncIterator[str]:
        messages = (
            ol.Message(role="system", content=self.sys_prompt),
            ol.Message(role="user", content=query),
        )
        async for chunk in await self._client.chat(self._model, messages, stream=True):
            yield chunk.message.content  # restituisce la risposta a pezzi


async def prof_print_response(agent: LLM, query: str) -> None:
    """Stampa la risposta"""
    await aprint(agent_token, end="")
    async for chunk in agent.launch_chat(query):  # per ogni pezzo di risposta
        await aprint(chunk, end="")  # stampa il pezzo
    await aprint()  # solo una piccola attesa?


async def user_input() -> str:
    return await ainput(user_token)


async def main() -> None:
    agent = LLM()
    personalities = {
        'Professional': "Always respond in a brief, gentle, syntetic way.",
        'Sarcastic': "Always respond in a brief, condescending, sarcastic way.",
    }
    agent.sys_prompt = personalities['Sarcastic']  # definisce il prompt
    try:
        while True:
            user_query = await user_input()
            if user_query.lower() in ["/bye", "/close", "/exit", "/goodbye", "/quit", ]:
                await aprint(agent_token + "Bye Bye!")
                break
            await prof_print_response(agent, user_query)
    except asyncio.CancelledError:
        await aprint("Goodbye")
        await prof_print_response(agent, "Goodbye")


if __name__ == "__main__":
    asyncio.run(main())
