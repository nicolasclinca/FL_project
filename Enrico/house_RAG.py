import asyncio
import ollama as ol
from collections.abc import AsyncIterator
from aioconsole import ainput, aprint
from neo4j import AsyncDriver, AsyncGraphDatabase

from Enrico.prove_schema import devices_map

user_token = "[User]  > "
agent_token = "[Agent] > "
bolt_port = "bolt://localhost:7687"
username = "neo4j"
pswd = "4Neo4Jay!"
LLM_MODEL = "llama3.1"


class Neo4jHandler:
    """
    Handle interactions with the database Neo4j.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        with self._driver.session() as session:
            self.schema = f"""{session.execute_read(devices_map)}"""
            print(session.execute_read(devices_map))

    async def close(self) -> None:
        """
        Close the connection to the driver Neo4j.
        """
        await self._driver.close()

    async def execute_query(self, query: str, params: dict | None = None) -> list[dict]:
        """
        Executes the Cypher query and gets the results
        """
        params = params or {}
        try:
            async with self._driver.session() as session:
                result = await session.run(query, params)
                return [record.data() async for record in result]
        except Exception as e:
            await aprint(agent_token + f"Neo4j query execution error: {e}")
            raise


class LLM:
    """Gestisce le interazioni con il modello di linguaggio Ollama."""

    def __init__(self, model: str = LLM_MODEL) -> None:
        self._client = ol.AsyncClient(host="localhost")
        self._model = model

    async def get_response_stream(self, system_prompt: str, user_query: str) -> AsyncIterator[str]:
        messages = [
            ol.Message(role="system", content=system_prompt),
            ol.Message(role="user", content=user_query),
        ]
        try:
            async for chunk in await self._client.chat(self._model, messages, stream=True):
                if chunk.get("message"):
                    yield chunk["message"]["content"]
                elif chunk.get("done") and chunk.get("error"):
                    await aprint(agent_token + f"Ollama API error: {chunk['error']}")
                    break
        except Exception as e:
            await aprint(agent_token + f"LLM streaming error: {e}")
            yield ""

    async def get_response_full(self, system_prompt: str, user_query: str) -> str:
        response_parts = []
        try:
            async for part_stream in self.get_response_stream(system_prompt, user_query):
                response_parts.append(part_stream)
            full_response = "".join(response_parts).strip()
            if "```cypher" in full_response:
                full_response = full_response.split("```cypher")[1].split("```")[0].strip()
            elif "```" in full_response:
                full_response = full_response.replace("```", "").strip()
            return full_response
        except Exception as e:
            await aprint(agent_token + f"LLM full response error: {e}")
            return ""


async def print_agent_response_stream(response_stream: AsyncIterator[str]) -> None:
    await aprint(agent_token, end="")
    async for chunk in response_stream:
        await aprint(chunk, end="", flush=True)
    await aprint()


async def user_input() -> str:
    return await ainput(user_token)


def choose_prompt(schema, prompt_id=0):
    """
    Select the best prompt to use based on the schema
    """
    if prompt_id == 0: # zero shot
        return f"""
            Generate the Cypher query that best answers the user query. 
            The graph schema is as follows: 
            {schema} 
            Always output a valid Cypher query and nothing else.
            """
    elif prompt_id == 1: # few shot
        pass

    return None

sys_answer_prompt = """
You are a helpful assistant.
Respond to the user in a conversational and natural way.
Use the provided Cypher query and its output to answer the original user's question.
Explain the information found in the database.
If the query output is empty or does not seem to directly answer the question, state that the information could not be found or is inconclusive.
Do not mention the Cypher query in your response unless it's crucial for explaining an error or ambiguity.
Be concise and clear.
"""


async def main_rag_loop() -> None:
    llm_agent = LLM(model=LLM_MODEL)
    neo4j_handler = Neo4jHandler(bolt_port, username, pswd)
    await aprint(agent_token + "RAG System started: Ask about your smart house")
    try:
        while True:
            original_user_query = await user_input()
            if not original_user_query:
                continue
            if original_user_query.lower() in ["/bye", "/close", "/exit", "/goodbye", "/quit", ]:
                await aprint(agent_token + "Bye Bye!")
                break

            await aprint(agent_token + "Querying the database...")
            cypher_query = await llm_agent.get_response_full(
                chosen_prompt,
                original_user_query
            )

            if not cypher_query:
                await aprint(
                    agent_token + "Can't generate a query from this prompt. Please, try to rewrite it")
                continue
            await aprint(agent_token + f"Cypher query:\n{cypher_query}")

            query_results = []
            try:
                query_results = await neo4j_handler.execute_query(cypher_query)
                await aprint(agent_token + f"Query results: {query_results}")
            except Exception as e:
                await aprint(agent_token +
                             "Error occurred: the query could be incorrect or data could be not well-formatted.")
                continue

            await aprint(agent_token + "Formuling the answer...")
            response_context_for_llm = (
                f"Original user query: \"{original_user_query}\"\n"
                f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )
            response_stream = llm_agent.get_response_stream(
                sys_answer_prompt,  # Defined in your previous full script
                response_context_for_llm
            )
            await print_agent_response_stream(response_stream)

    except asyncio.CancelledError:
        await aprint("\n" + agent_token + "Chat interrupted. Goodbye!")
    except Exception as e:
        await aprint(agent_token + f"An error occurred in the main loop: {e}")
    finally:
        await neo4j_handler.close()
        await aprint(agent_token + "Program concluded.")


if __name__ == "__main__":
    try:
        asyncio.run(main_rag_loop())
    except KeyboardInterrupt:
        pass
