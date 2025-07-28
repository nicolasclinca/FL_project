import asyncio

from neo4j_client import Neo4jClient
from res.prompts import *
from res.auto_queries import AQ


def select_instructions():
    return QP.instruction_test


def select_examples(example_sel: int = 0):
    if example_sel == 1:
        return EP.example_1
    else: # == 0
        return ""


def select_answer():
    return AP.answer_prompt


class InfoRetriever:

    def __init__(self, client: Neo4jClient):
        self.client = client


    async def close(self):
        await self.client.close()


    async def prepare_schema(self):
        schema = self.client.launch_auto_queries([
            # AQ.get_labels,
            # AQ.get_prop_keys,
            # AQ.get_rel_types,

        ])
        schema_str = ""
        async for s in schema:
            # print(s)
            schema_str += '\n' + str(s)
        return schema_str + '\n'

    async def initialize(self, aq_sel='nq', exm_sel=0,):
        answer_pmt = select_answer()

        question_pmt = select_instructions()
        question_pmt += select_examples(exm_sel)

        schema = await self.prepare_schema()
        question_pmt += "# SCHEMA \n" + schema

        return question_pmt, answer_pmt


if __name__ == "__main__":

    async def test():
        print("### RETRIEVER TEST ###", '\n')

        retriever = InfoRetriever(Neo4jClient(password='4Neo4Jay!'))
        await retriever.prepare_schema()
        await retriever.close()


    asyncio.run(test())
