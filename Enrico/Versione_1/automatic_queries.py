### PREFIXES ###
home = "http://swot.sisinflab.poliba.it/home#"


### GENERIC QUERIES ###

async def devices_query(tx):
    result = await tx.run(f"""
        MATCH (n:owl__Class) 
        WHERE NOT(n.uri STARTS WITH "bnode:")
        RETURN DISTINCT replace(toString(n.uri), "{home}", "") AS class
        ORDER BY class;
        """)
    text = ""
    sep = "\n"
    async for record in result:
        text = text + str(record['class']) + sep
    return text


def devices_map(tx):
    result = tx.run(f"""
    MATCH (res:Resource)-[:ns0__located_in]->(room:ns0__Room) 
    RETURN DISTINCT replace(toString(res.uri), "{home}", "") AS obj, 
    replace(toString(room.uri), "{home}", "") AS room; 
    """)
    text = "Devices' allocations in Rooms: "
    sep = "\n"
    for record in result:
        text = text + sep + f"{record['obj']} is in {record['room']}" + sep
    return text
