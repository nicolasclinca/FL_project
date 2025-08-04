import asyncio
from collections import defaultdict
# from Enrico.Versione_4.retriever import sys_labels

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
    async def get_names(tx):
        records = await tx.run(f"""
               MATCH (n:NamedIndividual) 
               RETURN COLLECT(n.name) as names
               """)
        record = await records.single()
        return record.get('names')

    @staticmethod
    async def node_type_properties(tx):
        return await tx.run(f"""
           CALL db.schema.nodeTypeProperties()
           """)


    @staticmethod
    async def props_per_label(tx):
        records = await AQ.node_type_properties(tx)

        nodes_props = defaultdict(set)
        async for record in records:
            for node_label in record['nodeLabels']:
                nodes_props[node_label].add(record['propertyName'])

        return [nodes_props] # list containing only the dictionary

    @staticmethod
    async def examples_per_label(tx, name: str = 'name', lim: int = 5):
        records = await AQ.node_type_properties(tx)

        examples_dict: dict = {}
        for node_label in records['nodeLabels']:
            exmp_query = (
                f"MATCH (n:`{node_label}`) "
                f"WHERE n.{name} IS NOT NULL "
                f"RETURN n.{name} AS exmp_name LIMIT {lim}"
            )
            exmp_result = await tx.run(exmp_query)
            exmp_list = [record['exmp_name'] async for record in exmp_result]

            if exmp_list:
                examples_dict[node_label] = exmp_list

        return [examples_dict]


    @staticmethod
    async def get_global(tx):
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
    head_key = 'heading'
    filter_key = 'filtering'
    text_key = 'text'

    global_aq_dict = {
        'LABELS': {
            query_key: get_labels,
            results_key: 'list',
            head_key: 'Use only these Labels',
            text_key: None,
            filter_key: None,
        },
        'PROPERTIES': {
            query_key: get_prop_keys,
            results_key: 'list',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'RELATIONSHIPS': {
            query_key: get_relationships,
            results_key: 'list > dict',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'RELATIONSHIP TYPES': {
            query_key: get_rel_types,
            results_key: 'list',
            head_key: 'These are the relationship types',
            text_key: None,
            filter_key: None,
        },
        'NAMES': {
            query_key: get_names,
            results_key: 'list',
            head_key: 'These are values for the \'name\' property',
            text_key: None,
            filter_key: 'lexical',
        },
        'GLOBAL SCHEMA': {
            query_key: get_global,
            results_key: 'list > dict',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'PROPS_PER_LABEL': {
            query_key: props_per_label,
            results_key: 'dict > group',
            head_key: 'Properties per label',
            text_key: 'Label: `#` has properties: ',
            filter_key: None,
        },
        'EXAMPLES_PER_LABEL': {
            query_key: props_per_label,
            results_key: 'dict > group',
            head_key: 'Examples per Label',
            text_key: 'Example for `#` -> ',
            filter_key: None,
        }
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
        # AQ.get_labels,
        # AQ.get_rel_types,
        # AQ.get_prop_keys,
        # AQ.get_relationships,
        # AQ.get_global_schema,
        AQ.props_per_label,
    ]
    asyncio.run(aq_test(aq_list))
