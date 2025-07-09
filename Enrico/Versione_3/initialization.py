
from typing import Any
from neo4j_handler import Neo4jHandler
from res.prompts import *

### DATABASE SCHEMA ###

def select_schema(selector: str = 'ghe'):
    selector = list(selector.upper())
    schema = f""""""

    if "H" in selector:
        schema += house_schema
    if "G" in selector:
        schema += graph_schema
    if "E" in selector:
        schema += example_schema

    return schema


### QUERY PROMPT ###

def select_prompt(selector: str = 'ie', schema: str = ""):
    selector = list(selector.upper())
    prompt = zero_prompt + schema  # base case

    if "I" in selector:
        prompt += instruction_prompt
    if "E" in selector:
        prompt += example_prompt

    return prompt


def select_answer(selector: str = "0"):
    selector = list(selector.upper())
    if "0" in selector:  # simple
        return answer_0
    elif "1" in selector:
        return answer_1
    else:
        # answer prompt più complessi
        return answer_0


### INIT FUNCTION ###

async def initialize(handler: Neo4jHandler,
                     selectors: tuple[str,str,str] = None,
                     auto_queries: list[Any] = None,
                     answer_queries: list[Any] = None) -> tuple[str,str]:
    """
    Initialize the system
    :param handler: handler of the Neo4j database
    :param selectors: tuple of selectors, to initialize schema and prompts
    :param auto_queries: automatic queries to augment the query prompt
    :param answer_queries: automatic queries to augment the answer prompt
    :return:
    :rtype:
    """
    if selectors is None:
        selectors = ('ghe', 'ei', 's') # default mode

    schema = select_schema(selectors[0])
    schema += await handler.augment_prompt(auto_queries=auto_queries, chat_msg=schema)

    query_prompt = select_prompt(selector=selectors[1], schema=schema)

    ans_prompt = select_answer(selector=selectors[2])
    ans_prompt += await handler.augment_prompt(auto_queries=answer_queries, chat_msg=ans_prompt)

    return query_prompt, ans_prompt


