from typing import Any
from neo4j import AsyncDriver, AsyncGraphDatabase


class Neo4jClient:
    """Client for the Neo4j server"""

    def __init__(self, uri: str = None, user: str = None, password: str = None) -> None:

        if uri is None:
            uri = "bolt://localhost:7687"
        if user is None:
            user = "neo4j"
        if password is None:
            password = input('Please, write your Neo4j password: ').strip()

        self.driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))


    async def close(self) -> None:
        await self.driver.close()


    async def launch_query(self, query: str, params: dict | None = None) -> list[dict]:
        params = params or {}
        try:
            async with self.driver.session() as session:
                # query = LiteralString(query)
                result = await session.run(query, params)
                return [record.data() async for record in result]  # query results
        except Exception as err:
            # await awrite(neo4j_sym, f"Neo4j query execution error: {err}", line_len=15)
            raise


    async def launch_auto_queries(self, auto_queries: list = None):
        if auto_queries is None:
            auto_queries = []

        async with self.driver.session() as session:
            for function in auto_queries:
                if isinstance(function, tuple):
                    action = function[0]
                    params = function[1:]
                    yield await session.execute_read(action, *params)
                else:
                    yield await session.execute_read(function)


if __name__ == "__main__":
    pass