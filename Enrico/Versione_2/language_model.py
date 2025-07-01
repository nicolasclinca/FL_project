from collections.abc import AsyncIterator
import ollama as ol
from aioconsole import aprint

user_token =  "[User]  > "
agent_token = "[Agent] > "


async def print_answer(answer: AsyncIterator[str]) -> None:
    await aprint(agent_token, end="")
    async for chunk in answer:
        await aprint(chunk, end="")
    await aprint()


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
        # da G. get_response_full
        stream_list = []
        try:
            async for stream_chunk in self.launch_chat(query=user_query, prompt_upd=prompt_upd):
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
