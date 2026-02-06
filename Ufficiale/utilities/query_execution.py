
import asyncio
from Ufficiale.neo4j_client import Neo4jClient
from Ufficiale.configuration import config


async def main():
    client = Neo4jClient(password=config['n4j_psw'])

    while True:
        command = input('Query > ')
        if command in config['quit_key_words']:
            break
        result = await client.launch_db_query(query=command)
        print(f'Result > {result}\n')

    await client.close()

asyncio.run(main())
