import asyncio
from neo4j import AsyncGraphDatabase


class AutoQueries:

    @staticmethod
    async def get_labels(tx):
        records = await tx.run(f"""
        MATCH (n)
        WHERE NOT '_GraphConfig' IN labels(n)
        UNWIND labels(n) AS label
        RETURN COLLECT(DISTINCT label) AS labels
        """)
        record = await records.single()
        return record.get('labels')

    @staticmethod
    async def get_prop_keys(tx):
        records = await tx.run(f"""
                   MATCH (n)
                   WHERE NOT '_GraphConfig' IN labels(n)
                   UNWIND keys(n) AS key
                   RETURN COLLECT(DISTINCT key) AS propKeys
                   """)
        record = await records.single()
        return record.get('propKeys')

    @staticmethod
    async def get_rel_types(tx):
        records = await tx.run(f"""
        MATCH ()-[r]->()
        RETURN COLLECT(DISTINCT type(r)) AS relTypes
        """)
        record = await records.single()
        return record.get('relTypes')

    @staticmethod
    async def get_relationships(tx):
        records = await tx.run("""
            MATCH (n)-[r]->(m) 
            WITH DISTINCT labels(n) AS fromNodeLabels, type(r) AS relationshipType, labels(m) AS toNodeLabels
            RETURN collect({
                from: fromNodeLabels,
                rel_type: relationshipType,
                to: toNodeLabels
            }) AS relationships
            """)

        record = await records.single()
        return record.get('relationships')

    @staticmethod
    async def get_global_schema(tx):
        records = await tx.run("""
        MATCH (s)-[r]->(o)
        WHERE NOT s.uri STARTS WITH 'bnode://'   
            AND NOT o.uri STARTS WITH 'bnode://'   
            AND NOT type(r) IN ['SCO', 'SPO', 'RDF_TYPE', 'RDFS_SUBCLASS_OF', 'OWL_OBJECT_PROPERTY'] 
        RETURN DISTINCT (s), (r), (o);
        """)
        results = []
        async for record in records:
            results.append(record['s'])
        return results


    query_key = 'query'
    results_key = 'results'

    global_aq_dict = {
        'LABELS': {
            query_key: get_labels,
            results_key: 'list',
        },
        'PROPERTIES': {
            query_key: get_prop_keys,
            results_key: 'list',
        },
        'RELATIONSHIPS': {
            query_key: get_relationships,
            results_key: 'list > dict',
        },
        'RELATIONSHIP TYPES': {
            query_key: get_rel_types,
            results_key: 'list',
        },
        'GLOBAL SCHEMA': {
            query_key: get_global_schema,
            results_key: 'list > dict',
        },
    }  # all possible Auto_queries

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
        (AQ.get_labels),
        (AQ.get_rel_types),
        (AQ.get_prop_keys),
        (AQ.get_relationships),
        # AQ.get_global_schema,
    ]
    asyncio.run(aq_test(aq_list))
