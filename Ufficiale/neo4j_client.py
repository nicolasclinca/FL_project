from aioconsole import aprint
from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable, CypherSyntaxError

from language_model import error_sym


class Neo4jClient:
    """Client for the Neo4j server"""

    def __init__(self, uri: str = None, user: str = None, password: str = None) -> None:
        """
        Neo4jClient constructor
        :param uri: Neo4j server URI
        :param user: Neo4j user name
        :param password: Neo4j password
        """
        if uri is None:
            uri = "bolt://localhost:7687"
        if user is None:
            user = "neo4j"
        if password is None:
            password = input('Please, insert your Neo4j password into configuration.py; or write it here'
                             '\n[Password]:')#.strip()

        self.driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self) -> None:
        await self.driver.close()

    async def launch_db_query(self, query: str, params: dict | None = None) -> list[dict]:
        """
        Launches a query to the Neo4j database
        :param query: Neo4j query
        :param params: Neo4j query parameters
        """
        params = params or {}
        try:
            async with self.driver.session() as session:
                # query = LiteralString(query)
                result = await session.run(query, params)  # type: ignore
                return [record.data() async for record in result]  # query outputs
        except CypherSyntaxError:
            await aprint(error_sym, f"Cypher Syntax Error")
            return []

    async def check_session(self) -> None:
        """
        Check if the Neo4j server is running
        """
        try:
            async with self.driver.session() as sesh:
                await sesh.run('RETURN 1')

        except AuthError:
            print("/!\\ Wrong Neo4j Authetication: check your password "
              "in: inputs > configuration.py > config['n4j_psw']"
              "\n(Be sure username and URI are correct too)")
            raise
        except ServiceUnavailable:
            print(f"/!\\ The Neo4j Server is not active")
            raise
        except Exception as err:
            print(f"Neo4j Starting Error:\n\n{(err)}\n\n")
            raise


if __name__ == "__main__":
    pass
    # import asyncio
    #
    #
    # async def main():
    #     client = Neo4jClient(password='4Neo4Jay!')
    #     print(await client.launch_db_query(query='MATCH (n:NamedIndividual) RETURN n '))
    #     await client.close()
    #
    #
    # asyncio.run(main())
