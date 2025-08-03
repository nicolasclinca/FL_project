import asyncio
from collections.abc import AsyncIterator
import ollama as ol
from aioconsole import aprint, ainput


# SYMBOLS
user_symb = "[User]  > "
agent_sym = "[Agent] > "
query_sym = "[Query] > "
neo4j_sym = "[Neo4j] > "


async def async_conversion(text: str, delay: float = 0.1) -> AsyncIterator[str]:
    """
    Convert a text string in an AsyncIterator, to have an async writing
    :param text:
    :type text:
    :param delay:
    :type delay:
    :return:
    :rtype:
    """
    words = text.split()
    for word in words:
        yield word
        await asyncio.sleep(delay)


async def awrite(symbol: str, text: str, delay: float = 0.1, line_len: int = 25) -> None:
    """
    Asynchronous Writing
    :param symbol:
    :param text:
    :param delay:
    :param line_len:
    """
    tabulation = " " * (len(symbol) - 2)
    await aprint(symbol, end="")
    iterator: AsyncIterator[str] = async_conversion(text=text, delay=delay)

    count = 0
    async for word in iterator:
        count += 1

        if count % line_len == 0:
            count = 0
            await aprint(word, end="\n" + tabulation + "> ", flush=True)
        else:
            await aprint(word, end=' ', flush=True)

    await aprint()


async def user_input() -> str:
    return await ainput(user_symb)


class LLM:  # B-ver.
    models = ('llama3.1', 'codellama:7b', 'codellama:7b-python')  # possible models

    def __init__(self, model: str = None, sys_prompt: str = None,
                 examples: list[dict] = None, temperature: float = 0.0,
                 upd_history: bool = True) -> None:

        self.client = ol.AsyncClient("localhost")
        self.temperature = temperature
        self.upd_history = upd_history

        if sys_prompt is None:
            sys_prompt = "You are a helpful assistant."
        self.sys_prompt = sys_prompt

        if model not in LLM.models:
            model = LLM.models[0]  # default model
        self.model = model

        self.chat_history = self.init_history(examples=examples)

    def init_history(self, examples: list[dict] = None):
        """
        Initialize the chat history using the examples
        :param examples:
        :return:
        """
        chat_history = [
            ol.Message(role="system", content=self.sys_prompt),
        ]

        if examples is None:
            return chat_history

        for example in examples:
            chat_history.append(ol.Message(role="user", content=example["user_query"]))
            chat_history.append(ol.Message(role="assistant", content=example["cypher_query"]))

        return chat_history

    async def launch_chat(self, query: str, prompt_upd: str = None) -> AsyncIterator[str]:
        """
        Launch a chat exchange with the LLM
        """
        if prompt_upd is not None:  # system prompt update
            self.sys_prompt = prompt_upd

        messages = self.chat_history + [
            ol.Message(role="system", content=self.sys_prompt),
            ol.Message(role="user", content=query),
            # Assistant Role?
        ]

        if self.upd_history:
            self.chat_history = messages

        try:  # Launch the chat
            response = await self.client.chat(self.model, messages,
                                              stream=True, options={'temperature': self.temperature})
            async for chunk in response:
                yield chunk.message.content

        except Exception as err:
            await aprint(agent_sym + f"LLM streaming error: {err}")
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
            await aprint(agent_sym + f"Error while writing query: {err}")
            return ""

    async def write_answer(self, prompt: str, n4j_results: str) -> str:
        """
        Write the answer and return it as a string, without directly printing it.
        :param prompt:
        :type prompt:
        :param n4j_results:
        :type n4j_results:
        :return:
        :rtype:
        """
        iterator: AsyncIterator[str] = self.launch_chat(query=n4j_results, prompt_upd=prompt)
        stream_list = []
        try:
            async for chunk in iterator:
                stream_list.append(chunk)
            answer = "".join(stream_list).strip()
            return answer

        except Exception as err:
            await aprint(agent_sym + f"LLM full response error: {err}")
            return ""
