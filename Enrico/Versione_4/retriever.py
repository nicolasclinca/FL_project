import asyncio

from neo4j_client import Neo4jClient
from language_model import LLM
from res.prompts import *
from res.auto_queries import AutoQueries as AQ


sys_classes = ('Resource', 'ObjectProperty', 'DatatypeProperty', 'Ontology',)
sys_rel_types = ('TYPE',)
sys_labels = sys_classes + sys_rel_types


def print_list(results: list, head: str = '- '):
    message = ""

    for result in results:
        result = str(result)
        if result not in sys_labels:
            message += '\n' + head + result
    return message


def print_dictionary(result: list[dict]):
    pass
    # TODO: scrivere la funzione print_dictionary

class DataRetriever:

    def __init__(self, client: Neo4jClient, llm: LLM = None):
        self.client = client
        self.filter_lm = llm

    async def close(self):
        await self.client.close()

    @staticmethod
    def select_instructions(instruction_sel: int = 0):
        if instruction_sel == 1:
            return QP.instruction_pmt_1
        else:  # == 0
            return QP.testing_instructions

    @staticmethod
    def select_examples(example_sel: int = 0) -> list[dict]:
        if example_sel == 1:
            return EL.example_list_1
        else:  # == 0
            return EL.testing_examples

    @staticmethod
    def select_answer(answer_sel: int = 0):
        if answer_sel == 1:
            return AP.answer_pmt_1
        else:  # == 0
            return AP.testing_ans_pmt

    async def prepare_schema(self, aq_tuple: tuple = None, intro : str = None):
        aq_dict = AQ.global_aq_dict
        if aq_tuple is None:  # all the possible auto queries
            aq_tuple = tuple(aq_dict.keys())

        if intro is None:
            schema = "Here's the database schema:"
        else:
            schema = intro

        for heading in aq_tuple:
            if heading not in aq_dict.keys():
                continue
            else:
                # QUERY EXECUTION
                operation = aq_dict[heading]
                schema += '\n\n' + heading
                response: list = await self.launch_auto_query(operation[AQ.query_key])

                # RESULT PROCESSING
                # TODO: forse bisogna spostare questa parte in una funzione apposita
                if operation[AQ.results_key] == 'list':
                    schema += print_list(response)
                elif operation[AQ.results_key] == 'list > dict':
                    schema += '\n**WIP**' + print_list(response) + '\n**WIP**'
                else:
                    schema += '\n' + str(response)

        return '\n' + schema

    async def launch_auto_query(self, auto_query) -> list:
        """
        Launch an automatic query to the Neo4j server.
        :param auto_query:
        :return:
        """
        async with self.client.driver.session() as session:
            if isinstance(auto_query, tuple):
                action = auto_query[0]
                params = auto_query[1:]
                return await session.execute_read(action, *params)
            else:
                return await session.execute_read(auto_query)

    async def initialize(self, auto_queries: tuple):
        question_prompt = self.select_instructions()
        question_prompt += await self.prepare_schema(aq_tuple=auto_queries)

        answer_pmt = self.select_answer()

        return question_prompt, answer_pmt

DR = DataRetriever # class identificator

if __name__ == "__main__":
    async def test():
        print("### RETRIEVER TEST ###", '\n')

        retriever = DataRetriever(Neo4jClient(password='4Neo4Jay!'))

        schema = await retriever.prepare_schema(aq_tuple=(
            # 'LABELS',
            # 'PROPERTIES',
            # 'RELATIONSHIP TYPES',
            # 'RELATIONSHIPS',
            'GLOBAL SCHEMA',
        ))
        print(schema)

        await retriever.close()

    asyncio.run(test())
