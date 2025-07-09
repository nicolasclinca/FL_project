import asyncio
from collections.abc import AsyncIterator
import ollama as ol
from aioconsole import aprint, ainput

user_token = "[User]  > "
agent_token = "[Agent] > "
query_token = "[Query] > "
neo4j_token = "[Neo4j] > "


async def print_response(response: AsyncIterator[str]) -> None:
    """
    Asynchronous print of a generic response; requires an AsyncIterator to work
    :param response: the iterator to print
    :type response: AsyncIterator[str]
    :return: nothing, it prints directly on the console
    """
    await aprint(agent_token, end="")
    async for chunk in response:
        await aprint(chunk, end="")
    await aprint()


async def async_conversion(text: str, delay: float = 0.1):
    words = text.split()
    for word in words:
        yield word
        await asyncio.sleep(delay)


async def slow_print(text: str, delay: float = 0.1):
    iterator: AsyncIterator[str] = async_conversion(text=text, delay=delay)
    async for word in iterator:
        await aprint(word, end=' ', flush=True)
    await aprint()  # Nuova riga alla fine


async def user_input() -> str:
    return await ainput(user_token)


class LLM:  # B-ver.
    def __init__(self, model: str = "llama3.1", sys_prompt: str = None) -> None:
        if sys_prompt is None:
            sys_prompt = "You are a helpful assistant."
        self.sys_prompt = sys_prompt
        self.client = ol.AsyncClient("localhost")
        self.model = model

    async def launch_chat(self, query: str, prompt_upd: str = None) -> AsyncIterator[str]:
        if prompt_upd is not None:  # system prompt update
            self.sys_prompt = prompt_upd

        messages = (
            ol.Message(role="system", content=self.sys_prompt),
            ol.Message(role="user", content=query),
        )
        try:  # Launch the chat
            async for chunk in await self.client.chat(self.model, messages, stream=True):
                yield chunk.message.content

        except Exception as err:
            await aprint(agent_token + f"LLM streaming error: {err}")
            yield ""

    async def write_cypher_query(self, user_query: str, prompt_upd: str = None) -> str:
        """
        Writes the Ollama response containing the cypher query and extracts it from the text, returning the string
        :param user_query: user question
        :type user_query: str
        :param prompt_upd: the system prompt to pass to Ollama in order to get the best response
        :type prompt_upd: str
        :return: a string containing only the extracted cypher query
        :rtype: str
        """
        stream_list = []
        iterator = self.launch_chat(query=user_query, prompt_upd=prompt_upd)
        try:
            async for stream_chunk in iterator:
                stream_list.append(stream_chunk)
            cypher_query = "".join(stream_list).strip()  # : Literal_String
            if "```cypher" in cypher_query:
                cypher_query = cypher_query.split("```cypher")[1].split("```")[0].strip()
            elif "```" in cypher_query:
                cypher_query = cypher_query.replace("```", "").strip()
            return cypher_query
        except Exception as err:
            await aprint(agent_token + f"LLM full response error: {err}")
            return ""

    async def write_answer(self, prompt: str, context: str) -> str:
        """
        Write the answer and return it as a string, without directly printing it.
        :param prompt:
        :type prompt:
        :param context:
        :type context:
        :return:
        :rtype:
        """
        iterator: AsyncIterator[str] = self.launch_chat(query=context, prompt_upd=prompt)
        stream_list = []
        try:
            async for chunk in iterator:
                stream_list.append(chunk)
            answer = "".join(stream_list).strip()
            return answer

        except Exception as err:
            await aprint(agent_token + f"LLM full response error: {err}")
            return ""

    async def print_answer(self, ans_pmt: str, context: str) -> None:
        """
        Gets answer prompt and context to elaborate and print an answer
        :param ans_pmt:
        :type ans_pmt:
        :param context:
        :type context:
        :return: nothing
        """
        await aprint(agent_token, end="")
        iterator: AsyncIterator[str] = self.launch_chat(query=context, prompt_upd=ans_pmt)

        async for chunk in iterator:  # per ogni pezzo di risposta
            await aprint(chunk, end="")  # stampa il pezzo
        await aprint()
