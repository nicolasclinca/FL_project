import asyncio

from neo4j import AsyncGraphDatabase


class AutoQueries:

    @staticmethod
    async def get_labels(tx):
        records = await tx.run(f"""
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN COLLECT(DISTINCT label) AS labels
        """)
        record = await records.single()
        return record.get('labels')

    @staticmethod
    async def get_rel_types(tx):
        records = await tx.run(f"""
        MATCH ()-[r]->()
        RETURN COLLECT(DISTINCT type(r)) AS relTypes
        """)
        record = await records.single()
        return record.get('relTypes')

    @staticmethod
    async def get_prop_keys(tx):
        records = await tx.run(f"""
                MATCH (n)
                UNWIND keys(n) AS key
                RETURN COLLECT(DISTINCT key) AS propKeys
                """)
        record = await records.single()
        return record.get('propKeys')

    @staticmethod
    async def get_global_schema(tx):
        records = await tx.run("""
        MATCH (s)-[r]->(o)
        WHERE NOT s.uri STARTS WITH 'bnode://'   
            AND NOT o.uri STARTS WITH 'bnode://'   
            AND NOT type(r) IN ['SCO', 'SPO', 'RDF_TYPE', 'RDFS_SUBCLASS_OF', 'OWL_OBJECT_PROPERTY'] 
        RETURN s, r, o;
        """)
        results = []
        async for record in records:
            results.append(record['s'])
        return type(results[0])


AQ = AutoQueries

if __name__ == "__main__":

    async def aq_test(functions: list):
        uri = 'bolt://localhost:7687'
        auth = ("neo4j", "4Neo4Jay!")
        driver = AsyncGraphDatabase.driver(uri, auth=auth)

        async with driver.session() as session:
            for function in functions:
                if isinstance(function, tuple):
                    action = function[0]
                    params = function[1:]
                    print(await session.execute_read(action, *params))
                else:  # solo funzione
                    print(await session.execute_read(function))

        await driver.close()

    aq_list = [
        # AQ.get_labels,
        # AQ.get_rel_types,
        # AQ.get_prop_keys
        AQ.get_global_schema,
    ]
    asyncio.run(aq_test(aq_list))
