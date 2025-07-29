from typing import Any
from neo4j_client import Neo4jClient
from res.prompts import (DatabaseSchema as DS,
                         QueryPrompts as QP,
                         AnswerPrompts as AP)


def convert_selector(string: str, sep: str = ",") -> list[str]:
    """
    Convert the selectors from a string to a list of strings
    :param sep:
    :type sep:
    :param string:
    :type string:
    :return:
    :rtype:
    """
    selectors: list = string.upper().split(sep=sep)

    for i in range(len(selectors)):
        selectors[i] = selectors[i].strip()

    return selectors


### DATABASE SCHEMA ###

def select_schema(selector: str):
    # Questa funzione va cambiata, perché quegli schemi non vanno bene
    schema = f""""""

    if selector is None:
        return schema # empty schema

    selector: list = convert_selector(selector)

    if "H" in selector:
        schema += DS.house_schema
    if "G" in selector:
        schema += DS.graph_schema
    if "E" in selector:
        schema += DS.example_schema

    return schema


### QUERY PROMPT ###

def select_prompt(selector: str, schema: str = ""):
    prompt = QP.zero_prompt + schema  # base case

    if selector is None:
        return prompt

    selector: list = convert_selector(selector)

    if "I0" in selector:
        prompt += QP.instruction_pmt_1
    elif 'I1' in selector:
        prompt += QP.instruction_pmt_2
    else:
        prompt += QP.testing_query

    if "E" in selector:
        prompt += QP.example_prompt

    return prompt


def select_answer(selector: str):
    selector = convert_selector(selector)
    if "A1" in selector:
        return AP.answer_pmt_2
    else: # 0
        return AP.answer_pmt_1


### INIT FUNCTION ###

async def initialize(n4j_cli: Neo4jClient,
                     selectors: tuple[str, str, str] = None,
                     auto_queries: list[Any] = None,
                     answer_queries: list[Any] = None) -> tuple[str, str]:
    """
    Initialize the system
    :param n4j_cli: handler of the Neo4j database
    :param selectors: tuple of selectors, to initialize schema and prompts
    :param auto_queries: automatic queries to augment the query prompt
    :param answer_queries: automatic queries to augment the answer prompt
    :return:
    :rtype:
    """
    if selectors is None:
        selectors = (None, None, None)  # default mode

    schema = select_schema(selectors[0])
    schema += await n4j_cli.augment_prompt(auto_queries=auto_queries, chat_msg=schema)

    query_prompt = select_prompt(selector=selectors[1], schema=schema)

    ans_prompt = select_answer(selector=selectors[2])
    ans_prompt += await n4j_cli.augment_prompt(auto_queries=answer_queries, chat_msg=ans_prompt)

    return query_prompt, ans_prompt


if __name__ == "__main__":
    pass
