import asyncio
from collections.abc import AsyncIterator
import ollama as ol
from aioconsole import aprint, ainput

# SYMBOLS
user_symb = "[User]  > "
agent_sym = "[Agent] > "
query_sym = "[Query] > "
neo4j_sym = "[Neo4j] > "
error_sym = "[Error] > "


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

    def __init__(self, model_name: str = None, sys_prompt: str = None,
                 examples: list[dict] = None, temperature: float = 0.0,

                 history_upd_flag: bool = False) -> None:
        """
        Initialize the LLM Agent
        :args model_name: the name of the model
        :args sys_prompt: the system prompt
        :args examples: the examples passed to the model
        :arg temperature: temperature used to generate the response
        :arg embedder_name: the name of the embedding model
        :arg history_upd_flag: whether to update the history with the new chat answers
        """

        self.llm_cli = ol.AsyncClient("localhost")
        self.temperature: float = temperature
        self.upd_history: bool = history_upd_flag

        if sys_prompt is None:
            sys_prompt = "You are a helpful assistant."
        self.sys_prompt: str = sys_prompt

        # Language model
        self.model_name: str = model_name

        self.chat_history = self.init_history(examples=examples)

    def check_installation(self):
        llm_name = self.model_name
        error: bool = False

        installed_models = []
        for model in ol.list()['models']:
            installed_models.append(model['model'])

        if llm_name not in installed_models:
            print(f'{llm_name} is not installed')
            error = True

        if error:
            print(f'Installed models are:\n{installed_models}\n')

        return not error

    def init_history(self, examples: list[dict] = None) -> list[ol.Message]:
        """
        Initialize the chat history using the examples
        :param examples: list with the examples
        :return: list with the message history
        """

        # System initial message → always added
        chat_history = [
            ol.Message(role="system", content=self.sys_prompt),
        ]

        # Adding examples
        if examples is not None:
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
                self.model_name, messages,
                stream=True,
                options={'temperature': self.temperature}
            )
            async for chunk in response:
                yield chunk.message.content

        except Exception as err:
            await aprint(agent_sym + f"LLM streaming error: {err}")
            yield ""

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
        if self.model_name in think_tag_models:
            _, think = response.split('<think>', 1)
            _, final = think.split('</think>', 1)
            return final
        else:
            return response  # no split

    async def write_answer(self, prompt: str, n4j_results: str) -> str:
        """
        Write the final answer and return it as a string, without directly printing it.
        :param prompt: the LLM prompt; it should contain the question and the Neo4j outputs
        :param n4j_results: the Neo4j outputs, in Cypher format
        :return: the natural language answer with the outputs explaination
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

if __name__ == "__main__":
    pass