from neo4j import GraphDatabase, AsyncGraphDatabase, AsyncResult
import asyncio

uri = 'bolt://localhost:7687'
auth = ("neo4j", "4Neo4Jay!")

driver = AsyncGraphDatabase.driver(uri, auth=auth)


async def print_classes(tx):
    results: AsyncResult = await tx.run("""
    MATCH (n:owl__Class) 
    WHERE NOT(n.uri STARTS WITH "bnode:")
    RETURN DISTINCT replace(toString(n.uri), "http://swot.sisinflab.poliba.it/home#", "") AS class
    ORDER BY class;
    """)
    async for record in results:
        return record.data()


async def main_execute(function):
    async with driver.session() as session:
        await print(session.execute_read(function))
    await driver.close()



asyncio.run(main_execute(print_classes))
