import asyncio
from collections.abc import AsyncIterator
import ollama as ol
import numpy as np
from aioconsole import aprint, ainput
from configuration import avail_llm_models, avail_embedders

# SYMBOLS
user_symb = "[User]  > "
agent_sym = "[Agent] > "
query_sym = "[Query] > "
neo4j_sym = "[Neo4j] > "


async def async_conversion(text: str, delay: float = 0.1) -> AsyncIterator[str]:
    """
    Convert a text string in an AsyncIterator, in order to have an async writing
    :param text: the text to be converted
    :param delay: delay time between two printed words
    :return: the asynchronous iterator
    :rtype: AsyncIterator[str]
    """
    words = text.split()
    for word in words:
        yield word
        await asyncio.sleep(delay)


async def asyprint(symbol: str, text: str, delay: float = 0.1, line_len: int = 25) -> None:
    """
    Asynchronous Print: write the answers word by word
    :param symbol: the initial symbol: it identifies the answer source
    :param text: the text to be written
    :param delay: delay time between two printed words
    :param line_len: maximum length (in words) of a single line, before an automatic newline
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


class LanguageModel:  # B-ver.
    # from configuration.py
    models = avail_llm_models
    embedders = avail_embedders

    def __init__(self, model_name: str = None, sys_prompt: str = None,
                 examples: list[dict] = None, temperature: float = 0.0,
                 history_upd_flag: bool = True,
                 embedder_name: str = None) -> None:
        """
        Initialize the LLM Agent
        :args model_name: the name of the model
        :args sys_prompt: the system prompt
        :args examples: the examples passed to the model
        :arg temperature: the model temperature
        :arg history_upd_flag: if True, the chat history is updated at every new prompt
        :arg embedder_name: the name of the embedding model
        """

        self.llm_cli = ol.AsyncClient("localhost")
        self.temperature: float = temperature
        self.upd_history: bool = history_upd_flag

        if sys_prompt is None:
            sys_prompt = "You are a helpful assistant."
        self.sys_prompt: str = sys_prompt

        # Language model
        if model_name not in LanguageModel.models:
            print(f"The '{model_name}' embedding model is not available. '{LanguageModel.models[0]}' selected. ")
            model_name = LanguageModel.models[0]
        self.model: str = model_name

        self.chat_history = self.init_history(examples=examples)

        # Embedding Model
        if embedder_name not in LanguageModel.embedders:
            # language model
            print(f"The '{embedder_name}' embedding model is not available. '{LanguageModel.embedders[0]}' selected. ")
            embedder_name = LanguageModel.embedders[0]
        self.embedder = embedder_name

    def init_history(self, examples: list[dict] = None) -> list[ol.Message]:
        """
        Initialize the chat history using the examples
        :param examples: list with the examples
        :return: list with the message history
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
        ]

        if self.upd_history:
            self.chat_history = messages

        try:  # Launch the chat
            response: AsyncIterator[ol.ChatResponse] = await self.llm_cli.chat(
                self.model, messages,
                stream=True,
                options={'temperature': self.temperature}
            )
            async for chunk in response:
                yield chunk.message.content

        except Exception as err:
            await aprint(agent_sym + f"LLM streaming error: {err}")
            yield ""

    async def get_embedding(self, text: str) -> np.ndarray:
        """
        Create the embedding of the given text
        """
        response = await self.llm_cli.embeddings(model=self.embedder, prompt=text)
        return np.array(response['embedding'])

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        # FIXME: controllare che sia corretta
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))  # type: ignore

    async def write_cypher_query(self, question: str, prompt_upd: str = None):
        """
        Get the user question and write the Cypher query
        """
        stream_list = []
        iterator = self.launch_chat(query=question, prompt_upd=prompt_upd)

        try:
            async for stream_chunk in iterator:
                stream_list.append(stream_chunk)

            cypher_query = "".join(stream_list).strip()  # : Literal_String
            return self.complete_response(cypher_query)

        except Exception as err:
            await aprint(agent_sym + f"Error while writing query: {err}")
            return ""

    def complete_response(self, response: str):
        """
        Complete the response to a query: for example, it deletes the <think> paragraph in Qwen
        """
        think_tag_models = ('qwen3:8b', 'phi4-mini-reasoning')
        if self.model in think_tag_models:
            _, think = response.split('<think>', 1)
            # TODO: potremmo salvare think in un file a parte
            _, final = think.split('</think>', 1)
            return final
        else:
            return response  # no split

    async def write_answer(self, prompt: str, n4j_results: str) -> str:
        """
        Write the answer and return it as a string, without directly printing it.
        :param prompt:
        :param n4j_results:
        :return:
        """
        iterator: AsyncIterator[str] = self.launch_chat(query=n4j_results, prompt_upd=prompt)
        stream_list = []
        try:
            async for chunk in iterator:
                stream_list.append(chunk)
            answer = "".join(stream_list).strip()
            return self.complete_response(answer)

        except Exception as err:
            await aprint(agent_sym + f"LLM full response error: {err}")
            return ""
