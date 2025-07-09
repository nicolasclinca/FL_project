### PREFIXES ###
from neo4j import AsyncResult
from collections import defaultdict

home = "http://swot.sisinflab.poliba.it/home#"


### AUTOMATIC QUERIES ###

async def devices_list(tx):
    """
    Search for all the device nodes
    """
    result = await tx.run(f"""
        MATCH (n:owl__Class) 
        WHERE NOT(n.uri STARTS WITH "bnode:")
        RETURN DISTINCT replace(toString(n.uri), "{home}", "") AS class
        ORDER BY class;
        """)
    sep = "\n"
    text = sep + "DEVICE CLASSES"
    async for record in result:
        text = text + str(record['class']) + sep
    return text


async def devices_map(tx):
    """
    Search for devices allocation in rooms
    """
    result = await tx.run(f"""
        MATCH (res:Resource)-[:ns0__located_in]->(room:ns0__Room) 
        RETURN DISTINCT replace(toString(res.uri), "{home}", "") AS obj, 
        replace(toString(room.uri), "{home}", "") AS room; 
        """)
    text = "Devices' allocations in Rooms: "
    sep = "\n"
    async for record in result:
        text = text + sep + f"""{record['obj']} is in {record['room']}"""
    return text + sep


async def get_properties(tx) -> str:
    """
    Write the properties' schema
    """
    labels: AsyncResult = await tx.run("CALL db.labels()")  # YIELD *

    properties = defaultdict(set)
    schema = ("""\n\nPROPERTIES SCHEMA\n
    Class : (Properties) \n""")

    async for label in labels:

        class_name = label.value()

        query = f"""
        MATCH (n:`{class_name}`) 
        WITH n LIMIT 100 
        UNWIND keys(n) AS key 
        RETURN DISTINCT key
        """

        result = await tx.run(query)
        async for record in result:
            properties[label].add(record["key"])

        props = """, """.join(sorted(properties[label])) or """no properties"""
        schema += f"""{class_name} : ({props})\n"""

    return schema


async def get_relationships(tx) -> str:
    schema = ("""\nRELATIONSHIPS SCHEMA\n
    (node)-[relationship]->(node)""")

    rel_types = await tx.run("CALL db.relationshipTypes()")  # YIELD *
    rel_props = defaultdict(set)
    rel_directions = defaultdict(set)

    async for rel_type in rel_types:
        rel_type = rel_type.value()

        query = f"""
        MATCH (a)-[r:`{rel_type}`]->(b) 
        WITH r LIMIT 100 
        UNWIND keys(r) AS key 
        RETURN DISTINCT key
        """
        result = await tx.run(query)
        async for record in result:
            rel_props[rel_type].add(record["key"])

        # Tipi di nodi collegati
        query_types = f"""
        MATCH (a)-[r:`{rel_type}`]->(b) 
        RETURN DISTINCT labels(a) AS from_labels, labels(b) AS to_labels 
        LIMIT 100
        """
        result = await tx.run(query_types)
        async for record in result:
            from_labels = ":".join(record["from_labels"])
            to_labels = ":".join(record["to_labels"])
            rel_directions[rel_type].add((from_labels, to_labels))

        props = ", ".join(sorted(rel_props[rel_type])) or "no properties"
        directions = rel_directions[rel_type]
        for from_label, to_label in directions:
            schema += f"""- ({from_label})-[:{rel_type} {{{props}}}]->({to_label})\n"""

    return schema


