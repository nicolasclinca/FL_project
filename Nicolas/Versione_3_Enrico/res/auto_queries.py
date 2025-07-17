import asyncio

from neo4j import AsyncResult, AsyncGraphDatabase
from collections import defaultdict

### PREFIXES ###
home = "http://swot.sisinflab.poliba.it/home#"
owl = "owl__"
ns0 = "ns0__"
rdf = "rdf__"
rdfs = "rdfs__"
removable_pref = [owl, ns0, rdf, rdfs]

nl = "\n"  #new line


def remove_prefix(schema: str, prefixes: list[str] = None):
    if prefixes is None:
        prefixes = removable_pref
    for pref in prefixes:
        schema = schema.replace(pref, "")
    return schema


### DOMAIN-BASES QUERIES ###
class DomainQueries:

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    async def get_named_ind(tx, parametro):
        results = await tx.run(f"""
            MATCH (n:owl__NamedIndividual) 
            RETURN DISTINCT replace(toString(n.uri), "{home}", "") as Object 
            ORDER BY Object;
            """)
        text = f"\n{parametro}\n"
        async for record in results:
            text += nl + record['Object']
        return text


### GENERAL QUERIES ###

class GeneralQueries:

    @staticmethod
    async def get_properties(tx) -> str:
        """
        Write the properties' schema
        """
        labels: AsyncResult = await tx.run("CALL db.labels()")  # YIELD *

        properties = defaultdict(set)
        schema = ("""\n\nPROPERTIES SCHEMA
        \nClass : (Properties) \n""")

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
        # return remove_prefix(schema)

    @staticmethod
    async def get_classes_rel(tx, limit: int = 0) -> str:
        schema = ("""
        \nRELATIONSHIPS SCHEMA 
        \n(node)-[relationship]->(node)\n""")

        rel_types = await tx.run("CALL db.relationshipTypes()")  # YIELD *
        rel_props = defaultdict(set)
        rel_directions = defaultdict(set)

        if limit == 0:
            limit = ""
        else:
            limit = f"LIMIT {limit}"

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
            {limit}
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

    @staticmethod
    async def show_relations(tx) -> str:
        results = await tx.run(f"""
            CALL db.relationshipTypes() 
            YIELD relationshipType 
            RETURN relationshipType as rel
            """)
        text = "RELATIONS:"
        async for record in results:
            text += nl + record['rel']
        return text

    @staticmethod
    async def show_properties(tx) -> str:
        results = await tx.run("""
        CALL db.propertyKeys() 
        YIELD propertyKey 
        RETURN propertyKey as prop
        """)
        text = "PROPERTIES"
        async for record in results:
            text += nl + record['prop']
        return text

    @staticmethod
    async def show_labels(tx) -> str:
        results = await tx.run(f"""
        CALL db.labels() 
        YIELD label  
        RETURN label
        """)
        text = "LABELS:"
        async for record in results:
            text += nl + record['label']
        return text


### TEST FUNCTION

async def test_queries(functions: list):
    """
    Funzione di test -> da eliminare in vista della consegna
    """
    uri = 'bolt://localhost:7687'
    auth = ("neo4j", "4Neo4Jay!")
    driver = AsyncGraphDatabase.driver(uri, auth=auth)

    async with driver.session() as session:
        for function in functions:
            if isinstance(function, tuple):
                action = function[0]
                params = function[1:]
                print(await session.execute_read(action, *params))
            else: # solo funzione
                print(await session.execute_read(function))

    await driver.close()

# Definite sempre
DQ = DomainQueries
GQ = GeneralQueries

general_queries = [GQ.get_properties, GQ.get_classes_rel,
                   GQ.show_relations, GQ.show_properties, GQ.show_labels]
domain_queries = [DQ.devices_map, DQ.devices_list, DQ.get_named_ind, ]

if __name__ == "__main__":  # Solo se eseguito direttamente
    print("### TEST DELLE QUERY AUTOMATICHE ###\n")
    asyncio.run(test_queries([
        GQ.show_labels,
        (DQ.get_named_ind, "IL PROSSIMO NON È LECITO")
    ]))
