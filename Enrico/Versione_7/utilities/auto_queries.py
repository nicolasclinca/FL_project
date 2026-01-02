from collections import defaultdict
from Ufficiale.inputs.configuration import sys_labels


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
    async def node_type_properties(tx):
        return await tx.run(f"""
           CALL db.schema.nodeTypeProperties()
           """)

    @staticmethod
    async def props_per_label(tx):
        records = await AQ.node_type_properties(tx)

        nodes_props_dict = defaultdict(set)  # empty
        async for record in records:
            for node_label in record['nodeLabels']:
                prop_name = record['propertyName']
                if prop_name not in sys_labels:
                    nodes_props_dict[node_label].add(prop_name)

        return [nodes_props_dict]  # list containing only the dictionary

    @staticmethod
    async def get_properties(tx, indiv_name: str) -> dict:
        """
        Given a NamedIndividual name, get its properties values
        """
        record = await tx.run(f"""
            MATCH (n:NamedIndividual {{name: '{indiv_name}'}}) RETURN n {{.*}} AS props
            """)
        record = await record.single()
        props_dict = record['props']
        for sys_prop in sys_labels:
            if sys_prop in props_dict.keys():
                props_dict.pop(sys_prop, None)
        return props_dict

    @staticmethod
    async def object_properties(tx, schema: dict = None, c_lim: int = 3) -> list:
        """
        Given the (full or filtered) schema, extract property values from some objects
        """
        if schema is None:
            # print('schema is null')
            return []  # nothing

        names: list = schema['NAMES']
        if not isinstance(names, list):
            return []  # nothing

        objs_prop: list = []  # list of dictionaries

        c = 0
        for name in names:
            c += 1
            objs_prop.append(await AQ.get_properties(tx, name))

            if c == c_lim:
                break

        return objs_prop

    @staticmethod
    async def relationships_visual(tx, filter_mode: int):
        """
        Get the relationship connections
        """
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
    async def class_hierarchy(tx) -> list:
        records = await tx.run(f"""
        MATCH (sub:Class) -[:SUBCLASSOF]->(sup:Class) 
        RETURN sub.name AS sbn , sup.name AS spn
        """)
        res_list = []
        async for record in records:
            # res_list.append((record['sub'], record['sup']))
            # res_list.append(f"{record['sbn']} is subclass of {record['spn']}")
            res_list.append(f"(:{record['sbn']})-[:SUBCLASSOF]->(:{record['spn']}) ")
        return res_list

    @staticmethod
    async def get_class(tx, indiv_name: str) -> list:
        records = await tx.run(f"""
            MATCH (n:NamedIndividual {{name: '{indiv_name}'}})-[:MEMBEROF]->(c:Class) RETURN c.name AS cls
            """)
        results: list = []
        async for record in records:
            results.append(record['cls'])
        print(results)
        return results

    @staticmethod
    async def get_labels(tx, indiv_name: str) -> list:
        pass

    @staticmethod
    async def object_classes(tx, schema: dict = None, c_lim: int = 3):
        if schema is None:
            # print('schema is null')
            return []  # nothing

        names: list = schema['NAMES']
        if not isinstance(names, list):
            return []  # nothing

        objs_cls: list = []  # list of dictionaries

        c = 0
        for name in names:
            c += 1
            objs_cls.append(await AQ.get_class(tx, name))

            if c == c_lim:
                break

        return objs_cls

    ###################

    function = 'function'  # get the real function
    results_key = 'results'  # how to format the outputs
    head_key = 'heading'  # heading to introduce this piece of data to LLM
    filter_key = 'filter_mode'  # how to filter data to pass to the LLM
    text_key = 'text'  # how to write this piece of data for the LLM

    global_aq_dict = {
        'NAMES': {
            function: get_names,
            results_key: 'list',
            head_key: "Use these values for the 'name' property",
            text_key: None,
            filter_key: 'dense-thresh',
        },
        'PROPS_PER_LABEL': {
            function: props_per_label,
            results_key: 'dict > group',
            head_key: 'Each label has these properties',
            text_key: 'Label: `§` has ONLY these properties: ',
            filter_key: 'dense-sort',
        },
        'RELATIONSHIPS VISUAL': {
            function: relationships_visual,
            results_key: 'list',
            head_key: "These are the relationship types per labels",
            text_key: '',
            filter_key: 'dense-sort',
        },
        'CLASS HIERARCHY': {
            function: class_hierarchy,
            results_key: 'list',
            head_key: "Use this SUBCLASSOF relationship schema",
            text_key: '',
            filter_key: 'dense-sort',
        },
        'OBJECT PROPERTIES': {
            function: object_properties,
            results_key: 'list > dict',
            head_key: "Here's some property values",
            text_key: '',
            filter_key: 'launch',
        },
        'OBJECT CLASSES': {
            function: object_classes,
            results_key: 'list > dict',
            head_key: "Here's some classes",
            text_key: '',
            filter_key: 'launch',
        },
    }  # all possible Auto_queries


AQ = AutoQueries

if __name__ == "__main__":
    pass
