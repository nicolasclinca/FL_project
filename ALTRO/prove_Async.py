import asyncio
from neo4j import AsyncGraphDatabase


# serve a collegarsi al database principale su neo4j. 
# per fare ciò, il server deve essere già attivo tramite neo4j console
# async dichiara una funzione asincrona
# await dice al programma di aspettare un'operazione che può richiedere tempo, 
# senza bloccare tutto il resto. 
# Un solo ciclo asyncio.run() è permesso
async def main():
    # creo la "porta" di accesso al database
    uri = "neo4j://localhost:7687"
    driver = AsyncGraphDatabase.driver(uri, auth=("neo4j", "Passworddineo4j1!"))
    
    #await driver.close()
    # apro la connessione attivando il driver
    async with driver:
        async with driver.session() as session:
            result = await session.run("RETURN 'Hello, Neo4j!' AS message")
            record = await result.single()
            print(record["message"])


async def saluta():
    print("Ciao")
    await interrupt()
    print("Bentornato")

async def interrupt():
    print("Pubblicità")

async def execution():
    await asyncio.gather(main(), saluta())
    print("tutto apposto")


if __name__ == "__main__":
    #asyncio.gather(main(), saluta())
    #print("tutto apposto")
    asyncio.run(execution())



