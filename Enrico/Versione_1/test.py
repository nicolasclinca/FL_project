import itertools
import sys
from collections import defaultdict

from neo4j import GraphDatabase, AsyncGraphDatabase, AsyncResult
import asyncio

uri = 'bolt://localhost:7687'
auth = ("neo4j", "4Neo4Jay!")
home = "http://swot.sisinflab.poliba.it/home#"
driver = AsyncGraphDatabase.driver(uri, auth=auth)


async def get_classes(tx):
    results: AsyncResult = await tx.run(f"""
    MATCH (n:owl__Class) 
    WHERE NOT(n.uri STARTS WITH "bnode:")
    RETURN DISTINCT replace(toString(n.uri), "{home}", "") AS class
    ORDER BY class;
    """)
    res_list = []
    async for record in results:
        res_list.append(record.data()['class'])
    return res_list


async def get_properties(tx) -> str:
    labels: AsyncResult = await tx.run("CALL db.labels()") # YIELD *

    properties = defaultdict(set)
    schema = ("\nPROPERTIES SCHEMA\n"
              "Class : (Properties) \n ")

    ### Dictionary
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

        props = ", ".join(sorted(properties[label])) or "no properties"
        schema += f"{class_name} : ({props})\n"

    return schema

async def get_relationships(tx) -> str:
    schema = ("RELATIONSHIPS SCHEMA\n"
              "(node)-[relationship]->(node)")

    rel_types = await tx.run("CALL db.relationshipTypes()") # YIELD *
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
            schema += f"- ({from_label})-[:{rel_type} {{{props}}}]->({to_label})\n"

    return schema


async def main_execute(functions: list):
    async with driver.session() as session:
        for function in functions:
            print(type(function))
            print(await session.execute_read(function))
    await driver.close()

# asyncio.run(main_execute([get_properties, get_relationships]))

### TEST DEL CURSORE ###

class Spinner:
    def __init__(self, message="Please, wait", delay=0.1, mode:int = 0):
        if mode == 1:
            self.cursor = itertools.cycle(['-', '\\', '|', '/'])
        else: # mode==0
            self.cursor = itertools.cycle([
                '.   ',
                '..  ',
                '... '])

        self.message = message
        self.delay = delay
        self.running = False
        self.spinner_task = None

    async def spin(self):
        while self.running:
            char = next(self.cursor)
            sys.stdout.write(f"\r{self.message} {char}")
            sys.stdout.flush()
            await asyncio.sleep(self.delay)

    def set_message(self, message: str):
        self.message = message

    def start(self):
        self.running = True
        self.spinner_task = asyncio.create_task(self.spin())

    async def stop(self):
        self.running = False
        if self.spinner_task:
            await self.spinner_task # Assicurati che la task dello spinner si fermi
        # Pulisce la riga
        sys.stdout.write("\r" + " " * (len(self.message) + 3) + "\r") # 3 per lo spazio e il carattere dello spinner
        sys.stdout.flush()

async def long_running_task():
    """Simula una funzione asincrona che impiega del tempo."""
    await asyncio.sleep(7) # Simula un'operazione che dura 7 secondi
    return "Ecco la risposta definitiva!"

async def main():
    spinner = Spinner(message="Formulating the Answer", delay=0.1)

    spinner.start()
    try:
        result = await long_running_task()
    finally:
        await spinner.stop() # Assicurati che lo spinner si fermi anche in caso di eccezioni

    print(result)

if __name__ == "__main__":
    asyncio.run(main())



