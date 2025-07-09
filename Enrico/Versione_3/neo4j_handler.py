from typing import Any

from aioconsole import aprint
from neo4j import AsyncDriver, AsyncGraphDatabase

from language_model import agent_token


class Neo4jHandler:
    """Gestore delle interazioni con il database Neo4j"""

    def __init__(self, uri: str = None, user: str = None, password: str = None) -> None:

        if uri is None:
            uri = "bolt://localhost:7687"
        if user is None:
            user = "neo4j"
        if password is None:
            password = "neo4j"

        self.driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self) -> None:
        await self.driver.close()

    async def launch_query(self, query: str, params: dict | None = None) -> list[dict]:
        """Lancia la query direttamente al database e ne restituisce i risultati (Linguaggio Cypher)"""
        params = params or {}
        try:
            async with self.driver.session() as session:
                #query = LiteralString(query)
                result = await session.run(query, params)
                return [record.data() async for record in result]  # query results
        except Exception as err:
            await aprint(agent_token + f"Neo4j query execution error: {err}")
            raise

    async def augment_prompt(self, auto_queries: list[Any] = None, chat_msg: str = "") -> str:
        """Lancia le query automatiche per integrare un responso già esistente con nuove informazioni.
        Il responso può essere lo schema o anche il contesto della risposta"""
        if auto_queries is None:
            auto_queries = []

        async with self.driver.session() as session:
            for query in auto_queries:
                chat_msg += await session.execute_read(query)

        return chat_msg


