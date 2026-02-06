
import random

from configuration import sys_labels


class AutoQueries:

    @staticmethod
    async def get_names(tx):
        """
        Retrieves the 'name' property of all nodes labeled as NamedIndividual.
        """
        records = await tx.run(f"""
               MATCH (n:NamedIndividual) 
               RETURN COLLECT(n.name) as names
               """)
        record = await records.single()
        return record.get('names')

    @staticmethod
    async def get_properties(tx, indiv_name: str) -> dict:
        """
        Given a NamedIndividual name, get its properties values.
        Filters out system properties defined in sys_labels.
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
    async def object_properties(tx, schema: dict = None, c_lim: int = 3, randomizer: bool = False) -> list:
        """
        Given the (full or filtered) schema, extract property values from some objects.
        It uses the 'NAMES' list from the schema to fetch properties for the first c_lim individuals.
        """
        if schema is None:
            # print('schema is null')
            return []  # nothing

        names: list = schema['NAMES'].copy()
        if c_lim > len(names):
            c_lim = len(names)

        if not isinstance(names, list):
            return []  # nothing

        objs_prop: list = []  # list of dictionaries
        if randomizer:
            random.shuffle(names)

        c = 0
        for pair in names:
            c += 1
            objs_prop.append(await AQ.get_properties(tx, pair[0]))

            if c == c_lim:
                break

        return objs_prop

    @staticmethod
    async def relationships_visual(tx, c_lim: int = 0):
        """
        Get the relationship connections between node labels using db.schema.visualization().
        Returns a list of strings representing relationships like (:LabelA)-[:REL_TYPE]->(:LabelB).
        filter_mode >= 1 filters out self-loops (relationships where start and end labels are the same).
        """
        records = await tx.run(f"""
           CALL db.schema.visualization()
           """)
        relations = set()  # set guarantees unique values

        c = 0
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

                relations.add(f"(:{start_labels[0]})-[:{rel_type}]->(:{end_labels[0]})")
                c += 1
                if c == c_lim != 0:
                    return list(relations)

        return list(relations)  # list

    @staticmethod
    async def labels_names(tx):
        """
        Retrieves all node labels present in the database, excluding system labels.
        """
        records = await tx.run(f"""
            CALL db.labels()
            """)
        labels: list = []
        async for record in records:
            if record['label'].lower() not in sys_labels:
                labels.append(record['label'])
        return labels

    ###################

    function = 'function'  # get the real function
    results_key = 'results'  # how to format the outputs
    heading = 'heading'  # heading to introduce this piece of data to LLM
    filter_mode = 'filter_mode'  # how to filter data to pass to the LLM

    global_aq_dict = {
        'NAMES': {
            function: get_names,
            results_key: 'list',
            heading: "Use these values for the 'name' property",
            filter_mode: 'dense-klim',  # -klim  -thresh
        },
        'LABELS': {
            function: labels_names,
            results_key: 'list',
            heading: "These are the class labels: ",  # *don't invent other labels*
            filter_mode: 'dense-thresh',
        },
        'OBJECT PROPERTIES': {
            function: object_properties,
            results_key: 'list > dict',
            heading: "Here's some property values",
            filter_mode: 'launch',
        },
        'RELATIONSHIPS VISUAL': {
            function: relationships_visual,
            results_key: 'list',
            heading: "These are the relationships: *don't invent other relationships*",
            filter_mode: 'dense-klim',
        },
    }  # all possible Auto_queries


AQ = AutoQueries

if __name__ == "__main__":
    pass
