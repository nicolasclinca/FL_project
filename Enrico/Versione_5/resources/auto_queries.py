import random
from collections import defaultdict
from Enrico.Versione_5.configuration import sys_labels


class AutoQueries:

    @staticmethod
    async def get_names(tx):
        records = await tx.run(f"""
               MATCH (n:NamedIndividual) 
               RETURN COLLECT(n.name) as names
               """)
        record = await records.single()
        return record.get('names')

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
    async def props_per_type(tx):
        return await tx.run(f"""
           CALL db.schema.nodeTypeProperties()
           """)

    @staticmethod
    async def props_per_label(tx):
        records = await AQ.props_per_type(tx)

        nodes_props = defaultdict(set)
        async for record in records:
            for node_label in record['nodeLabels']:
                prop_name = record['propertyName']
                if prop_name not in sys_labels:
                    nodes_props[node_label].add(prop_name)

        return [nodes_props]  # list containing only the dictionary

    @staticmethod
    async def examples_per_label(tx, limits: tuple[int, int], name: str = 'name') -> list[dict]:
        records = await AQ.props_per_type(tx)
        query_lim, print_lim = limits

        examples_dict: dict = {}
        async for record in records:
            for node_label in record['nodeLabels']:
                exmp_query = (
                    f"MATCH (n:`{node_label}`) "
                    f"WHERE n.{name} IS NOT NULL "
                    f"RETURN n.{name} AS exmp_name LIMIT {query_lim} "
                )
                exmp_result = await tx.run(exmp_query)
                exmp_list: list = []
                async for exm_rec in exmp_result:

                    exmp_list.append(exm_rec['exmp_name'])
                    random.shuffle(exmp_list)
                    exmp_list = exmp_list[:print_lim]

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
    async def get_classes(tx):
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
        'NAMES': {
            func_key: get_names,
            results_key: 'list',
            head_key: 'These are values for the \'name\' property',
            text_key: None,
            filter_key: 'dense',  # 'lexical',
        },
        'PROPS_PER_LABEL': {
            func_key: props_per_label,
            results_key: 'dict > group',
            head_key: 'Each label has these properties',
            text_key: 'Label: `#` has ONLY these properties: ',
            filter_key: None, #'node_props_filtering',
        },
        'EXAMPLES_PER_LABEL': {
            func_key: (examples_per_label, (50, 50), 'name'),
            results_key: 'dict > group',
            head_key: 'Examples per Label',
            text_key: 'Examples for `#` -> ',
            filter_key: 'dense-2'
        },
        'RELATIONSHIPS VISUAL': {
            func_key: (relationships_visual, 0),
            results_key: 'list',
            head_key: "These are the relationship types per labels",
            text_key: '',
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
