
from aioconsole import aprint
from collections import defaultdict
from neo4j import AsyncGraphDatabase, AsyncDriver

from Enrico.Versione_1.language_model import agent_token
from Enrico.Versione_1.automatic_queries import *


class Neo4jHandler:
    """Handle interactions with the database Neo4j."""

    def __init__(self, uri: str = None, user: str = None, password: str = None) -> None:
        """Create an asynchronous driver for the Neo4j Database"""
        if uri is None:
            uri = "bolt://localhost:7687"
        if user is None:
            user = "neo4j"
        if password is None:
            password = "neo4j"

        self.driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self) -> None:
        """Close the connection """
        await self.driver.close()

    async def launch_query(self, query: str, params: dict | None = None) -> list[dict]:
        """
        Execute a Cypher query and return the results.
        """
        params = params or {}
        try:
            async with self.driver.session() as session:
                # query = LiteralString(query)
                result = await session.run(query, params)
                return [record.data() async for record in result]  # query results
        except Exception as err:
            await aprint(agent_token + f"Neo4j query execution error: {err}")
            raise

    async def augment_schema(self, init_queries: list, schema: str = "") -> str:
        async with self.driver.session() as session:
            for query in init_queries:
                schema += await session.execute_read(query)
        # await self.close() # in teoria il driver va chiuso solo dopo la pipeline
        return schema
