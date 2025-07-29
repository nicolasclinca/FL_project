import asyncio

from neo4j_client import Neo4jClient
from res.prompts import *
from res.auto_queries import AQ

query_key = 'query'
results_key = 'results'

sys_classes = ('Resource', 'ObjectProperty', 'DatatypeProperty', 'Ontology')
sys_rel_types = ('intersectionOf', 'rest', 'first', 'type')
sys_labels = sys_classes + sys_rel_types

def select_instructions():
    return QP.instruction_test


def select_examples(example_sel: int = 0):
    if example_sel == 1:
        return Exm.example_1
    else:  # == 0
        return ""


def select_answer():
    return AP.answer_prompt


def print_list(results: list, head: str = '- '):
    message = ""

    for result in results:
        result = str(result)
        if result not in sys_labels:
            message += '\n' + head + result
    return message


class InfoRetriever:

    def __init__(self, client: Neo4jClient):
        self.client = client

    async def close(self):
        await self.client.close()

    async def prepare_schema(self, aq_dict: dict = None):
        if aq_dict is None:
            return ""

        schema = "Here's the database schema:"
        for heading in aq_dict.keys():

            # QUERY EXECUTION
            operation = aq_dict[heading]
            schema += '\n\n' + heading
            response: list = await self.launch_auto_query(operation[query_key])

            # RESULT PROCESSING
            if operation[results_key] == 'list':
                schema += print_list(response)
            elif operation[results_key] == 'list > dict':
                schema += '\n**WIP**' + print_list(response)
            else:
                schema += '\n' + str(response)

        return '\n' + schema

    async def launch_auto_query(self, auto_query):
        async with self.client.driver.session() as session:
            if isinstance(auto_query, tuple):
                action = auto_query[0]
                params = auto_query[1:]
                return await session.execute_read(action, *params)
            else:  # solo funzione
                return await session.execute_read(auto_query)


if __name__ == "__main__":
    async def test():
        print("### RETRIEVER TEST ###", '\n')

        retriever = InfoRetriever(Neo4jClient(password='4Neo4Jay!'))
        dictionary = {
            'LABELS': {
                query_key: AQ.get_labels,
                results_key: 'list',
            },
            'PROPERTIES': {
                query_key: AQ.get_prop_keys,
                results_key: 'list',
            },
            # 'RELATIONSHIPS': {
            #     query_key: AQ.get_relationships,
            #     results_key: 'list > dict',
            # },
            'RELTYPES': {
                query_key: AQ.get_rel_types,
                results_key: 'list',
            },
        }
        schema = await retriever.prepare_schema(dictionary)
        print(schema)
        await retriever.close()


    asyncio.run(test())
