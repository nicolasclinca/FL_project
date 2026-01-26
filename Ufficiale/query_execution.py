
import asyncio
from neo4j_client import Neo4jClient
from configuration import config


async def main():
    client = Neo4jClient(password='4Neo4Jay!')

    while True:
        command = input('Query > ')
        if command in config['quit_key_words']:
            break
        result = await client.launch_db_query(query=command)
        print(f'Result > {result}\n')

    await client.close()

asyncio.run(main())
