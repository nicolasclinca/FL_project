from neo4j import AsyncDriver

from Enrico.simple_init import select_prompt, select_schema


async def devices_query(tx):
    result = await tx.run("""
        MATCH (n:owl__Class) 
        WHERE NOT(n.uri STARTS WITH "bnode:")
        RETURN DISTINCT replace(toString(n.uri), "http://swot.sisinflab.poliba.it/home#", "") AS class
        ORDER BY class;
        """)
    text = ""
    sep = "\n"
    async for record in result:
        text = text + str(record['class']) + sep
    return text


def devices_map(tx):
    result = tx.run("""
    MATCH (res:Resource)-[:ns0__located_in]->(room:ns0__Room) 
    RETURN DISTINCT replace(toString(res.uri), "http://swot.sisinflab.poliba.it/home#", "") AS obj, 
    replace(toString(room.uri), "http://swot.sisinflab.poliba.it/home#", "") AS room; 
    """)
    text = "Devices' allocations in Rooms: "
    sep = "\n"
    for record in result:
        text = text + sep + f"{record['obj']} is in {record['room']}" + sep
    return text


async def complex_init(driver: AsyncDriver, schema_sel: str = 'ghe', prompt_sel: str = 'ie') -> str:
    schema = select_schema(schema_sel)
    async with driver.session() as session:
        schema += await session.execute_read(devices_query) # device classes
        # mappa = await session.execute_read(devices_map) # device-room map

    prompt = select_prompt(prompt_sel, schema)
    # print("##### STAMPA DEL PROMPT #####: \n" + prompt + "\n ##### FINE DEL PROMPT ##### \n\n")


    # await driver.close()
    return prompt


# complex_init(None)
