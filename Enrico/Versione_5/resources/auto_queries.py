import random
from collections import defaultdict
from Enrico.Versione_5.configuration import sys_labels



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
                prop_name = record['propertyName']
                if prop_name not in sys_labels:
                    nodes_props[node_label].add(prop_name)

        return [nodes_props]  # list containing only the dictionary

    @staticmethod
    async def examples_per_label(tx, limits: tuple[int, int], name: str = 'name') -> list[dict]:
        records = await AQ.node_type_properties(tx)

        examples_dict: dict = {}
        async for record in records:
            for node_label in record['nodeLabels']:
                exmp_query = (
                    f"MATCH (n:`{node_label}`) "
                    f"WHERE n.{name} IS NOT NULL "
                    f"RETURN n.{name} AS exmp_name LIMIT {limits[0]}"
                )
                exmp_result = await tx.run(exmp_query)
                exmp_list: list = []
                async for exm_rec in exmp_result:

                    # exmp_list.append(await retriever.dense_filtering(
                    #     results=exm_rec['exmp_name'], question=question, k_lim=limits[1])
                    # )

                    exmp_list.append(exm_rec['exmp_name'])
                    # random.shuffle(exmp_list)
                    # exmp_list = exmp_list[:limits[1]]

                    if exmp_list:
                        examples_dict[node_label] = exmp_list

        return [examples_dict]

    @staticmethod
    async def relationships_visual(tx, filter_mode: int):
        # TODO: aggiungere modalità di filtraggio
        records = await tx.run(f"""
           CALL db.schema.visualization()
           """)
        relations = set()  # set guarantees unique values
        async for record in records:
            for relation in record["relationships"]:
                start_nd = relation.start_node
                end_nd = relation.end_node
                rel_type = relation.type

                start_labels: list = [label for label in start_nd.labels if label.lower() not in sys_labels]
                end_labels: list = [label for label in end_nd.labels if label.lower() not in sys_labels]

                if not start_labels or not end_labels:
                    continue

                if rel_type.lower() in sys_labels:
                    continue

                if filter_mode >= 1:
                    if start_labels[0] == end_labels[0]:
                        continue

                relations.add(f"(:{start_labels[0]})-[:{rel_type}]->(:{end_labels[0]})")

        return list(relations)  # list

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

    @staticmethod
    async def node_properties(tx, name):
        try:
            records = await tx.run(f"""
                MATCH (n:NamedIndividual {{name: '{name}'}}) 
                RETURN properties(n) as props
                """)
            record = await records.single()
            props: dict = record['props']

            for prop in sys_labels:
                if prop in props.keys():
                    props.pop(prop)

            return [props]  # list is mandatory

        except TypeError:
            return {}

        except Exception:
            print('/!\\ General Exception in Testing Auto Query /!\\')
            raise

    @staticmethod
    async def get_classes(tx):
        records = await tx.run(f"""
               MATCH (n:Class) 
               RETURN COLLECT(n.name) as names
               """)
        record = await records.single()
        return record.get('names')

    @staticmethod
    async def class_hierarchy(tx):
        records = await tx.run(f"""
                       MATCH (n:Class) 
                       RETURN COLLECT(n.name) as names
                       """)
        record = await records.single()
        return record.get('names')

    ###################

    func_key = 'function'  # get the real function
    results_key = 'results'  # how to format the results
    head_key = 'heading'  # heading to introduce this piece of data to LLM
    filter_key = 'filtering'  # how to filter data to pass to the LLM
    text_key = 'text'  # how to write this piece of data for the LLM

    global_aq_dict = {
        'LABELS': {
            func_key: get_labels,
            results_key: 'list',
            head_key: 'Use only these Labels',
            text_key: None,
            filter_key: None,
        },
        'PROPERTIES': {
            func_key: get_prop_keys,
            results_key: 'list',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'RELATIONSHIPS LIST': {
            func_key: get_relationships,
            results_key: 'list > dict',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'RELATIONSHIP TYPES': {
            func_key: get_rel_types,
            results_key: 'list',
            head_key: 'These are the relationship types',
            text_key: None,
            filter_key: None,
        },
        'NAMES': {
            func_key: get_names,
            results_key: 'list',
            head_key: 'These are values for the \'name\' property',
            text_key: None,
            filter_key: 'dense',  #'lexical',
        },
        'NODES_WITH_PROPS': {
            func_key: get_names,
            results_key: 'list',
            head_key: 'These are values for the \'name\' property',
            text_key: None,
            filter_key: 'node_props',
        },
        'GLOBAL SCHEMA': {
            func_key: get_global,
            results_key: 'list > dict',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'PROPS_PER_LABEL': {
            func_key: props_per_label,
            results_key: 'dict > group',
            head_key: 'Each label has these properties',
            text_key: 'Label: `#` has ONLY these properties: ',
            filter_key: None,
        },
        'EXAMPLES_PER_LABEL': {
            func_key: (examples_per_label, (50, 5), 'name'),
            results_key: 'dict > group',
            head_key: 'Examples per Label',
            text_key: 'Examples for `#` -> ',
            filter_key: 'dense-2' # 'dense-2',
        },
        'RELATIONSHIPS VISUAL': {
            func_key: (relationships_visual, 0),
            results_key: 'list',
            head_key: "These are the relationship types per labels",
            text_key: '',
            filter_key: None,
        },
        'NODE PROPERTIES': {
            func_key: (node_properties, 'Lamp_38'),
            results_key: 'dict',
            head_key: None,
            text_key: None,
            filter_key: None,
        },
        'CLASSES': {
            func_key: get_classes,
            results_key: 'list',
            head_key: "Here are all the available classes",
            text_key: None,
            filter_key: 'dense',
        },
    }  # all possible Auto_queries


AQ = AutoQueries

if __name__ == "__main__":
    pass
