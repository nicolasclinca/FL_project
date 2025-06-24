
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase, AsyncDriver, GraphDatabase

from Enrico.Versione_1.language_model import agent_token


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
