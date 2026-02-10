
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
    async def relationships_names(tx, c_lim: int = 0):
        records = await tx.run(f"""
                   CALL db.relationshipTypes();
                   """)
        relations = set()

        c = 0
        async for record in records:
            name = record["relationshipType"]
            if name in sys_labels:
                continue
            relations.add(name)
            c += 1
            if c == c_lim != 0:
                return list(relations)
        return list(relations)


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
    results_format = 'results'  # how to format the outputs
    text_heading = 'heading'  # heading to introduce this piece of data to LLM
    filter_mode = 'filter_mode'  # how to filter data to pass to the LLM

    global_aq_dict = {
        'NAMES': {
            function: get_names,
            results_format: 'list',
            text_heading: "Use these values for the 'name' property",
        },
        'LABELS': {
            function: labels_names,
            results_format: 'list',
            text_heading: "These are the class labels: ",  # *don't invent other labels*
        },
        'OBJECT PROPERTIES': {
            function: object_properties,
            results_format: 'list > dict',
            text_heading: "Here's some property values",
        },
        'RELATIONSHIPS NAMES': {
            function: relationships_names,
            results_format: 'list',
            text_heading: "These are the relationships: *don't invent other relationships*",
        }
    }  # all possible Auto_queries


AQ = AutoQueries

if __name__ == "__main__":
    pass
