import asyncio
import json
import logging

from aioconsole import aprint

from Enrico.Versione_6.resources.spinner import Spinner
from retriever import DataRetriever
from configuration import config
from language_model import LanguageModel
from neo4j_client import Neo4jClient
from resources.prompts import EL

# Automatic script to execute the tests
INPUT_FILE = 'resources/main_queries.json'
OUTPUT_FILE = './results/test_results.txt'


async def test_query(neo4j_pwd: str = '4Neo4Jay!',
                     llm_name: str = None, emb_name: str = None,
                     start: int = 0, term: int = None) -> None:
    logging.getLogger("neo4j").setLevel(logging.ERROR)

    instructions_pmt = config['question_prompt']
    answer_pmt = config['answer_prompt']

    client = Neo4jClient(password=neo4j_pwd)
    try:  # check if Neo4j is on
        await client.check_session()
    except Exception:
        return

    spinner = Spinner(delay=config['spin_delay'])
    spinner.set_message(message='Please, wait... ')

    llm_agent = LanguageModel(
        model_name=llm_name,
        embedder_name=emb_name,
        examples=EL.example_list,
        history_upd_flag=False,  # cannot use previous queries
    )

    retriever = DataRetriever(
        client=client, init_aqs=config['aq_tuple'],
        llm_agent=llm_agent, k_lim=config['k_lim'],
    )
    await retriever.init_full_schema()

    with open(OUTPUT_FILE, 'w') as outfile:
        # Reset the file
        print('', file=outfile)

    # Queries import
    queries: list = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        queries = json.load(f)
        if not isinstance(queries, list):
            await client.close()
            raise ValueError(f"Error: {INPUT_FILE} is not a list")

    for q in range(start, term):  # for cycle on the queries

        try:
            user_question = queries[q]['query']
            expected_ans = queries[q]['output']

            print(f'\n[{q+1}/{term}] > ' + user_question)

            await spinner.restart('Processing Schema...')
            retriever.reset_filter()
            await retriever.filter_schema(question=user_question)
            question_pmt = instructions_pmt + retriever.write_schema(filtered=True)

            await spinner.restart('Processing Query...')
            cypher_query: str = await llm_agent.write_cypher_query(
                question=user_question, prompt_upd=question_pmt
            )

            await spinner.restart('Processing Results...')
            query_results = await client.launch_db_query(cypher_query)
            ans_context: str = (
                f"Answer the user question by describing the results provided by Neo4j: \n"
                f"Original user question: \"{user_question}\"\n"
                # f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )
            answer: str = await llm_agent.write_answer(prompt=answer_pmt, n4j_results=ans_context)

            with open(OUTPUT_FILE, 'a') as outfile:
                print(f'\n{q+1}) User Query:\n{user_question}', file=outfile)
                print(f'\nCypher query:\n{cypher_query}', file=outfile)
                print(f'\nNeo4j results:\n{query_results}', file=outfile)
                print(f'\nAnswer:\n{answer}', file=outfile)
                print(f'\nExpected answer:\n{expected_ans}', file=outfile)
                print('\n' + 25 * '#', file=outfile)

            await spinner.stop()

        except asyncio.CancelledError:
            await spinner.stop()
            await client.close()
            await aprint("Test Interrupted!")
            return

    await client.close()
# END


if __name__ == '__main__':
    asyncio.run(test_query(
        neo4j_pwd=config['n4j_psw'],
        llm_name=config['llm'],
        emb_name=config['embd'],
        start=0, term=3,
    ))
