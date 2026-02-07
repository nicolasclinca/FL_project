import asyncio
import json
import logging
import datetime

from aioconsole import aprint

from embedding_model import Embedder
from retriever import DataRetriever
from language_model import LanguageModel
from neo4j_client import Neo4jClient

from configuration import config
from utilities.spinner import Spinner

# CHOOSE YOUR QUERIES
TEST_QUERIES = config['test_queries']

# Automatic script to execute the tests
INPUT_FILE = 'inputs/Queries_with_ID.json'
OUTPUT_FILE = 'outputs/automatic_results.txt'


async def test_query(neo4j_pwd: str = config['n4j_psw'],
                     llm_name: str = None, emb_name: str = None,
                     query_ids: list = None,
                     ) -> None:
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    print(f'# Test started on: {datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")}\n')

    instructions_pmt = config['question_prompt']
    answer_pmt = config['answer_prompt']

    client = Neo4jClient(password=neo4j_pwd)
    try:  # check if Neo4j is on
        await client.check_session()
    except Exception:
        return

    spinner = Spinner()
    # spinner.start(message='Please, wait')
    spinner.start(message='Processing the Full Schema: please wait')

    llm_agent = LanguageModel(
        model_name=llm_name,
        examples=config['examples'],  # cannot use previous queries
    )

    embedder = Embedder(emb_name)

    retriever = DataRetriever(
        n4j_cli=client,  # init_aqs=config['aq_tuple'],
        llm_agent=llm_agent,
        embedder=embedder,
        k_lim=config['k_lim'],
        thresh=config['thresh'],
    )
    await retriever.init_full_schema()

    with open(OUTPUT_FILE, 'w') as outfile:
        # Reset the file
        print(f"\n", file=outfile)
        print(f'Tested on: {datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")}',
              file=outfile)
        print(f'Query IDs: {query_ids}\n', file=outfile)
        print(f"LLM used: {llm_name}", file=outfile)
        print(f"Embedder used: {emb_name}", file=outfile)
        print(f'Filter limit: K = {config['k_lim']}', file=outfile)

        print('\nAuto-queries:', file=outfile)
        for aq in config['aq_tuple']:
            print(f'\t{aq}', file=outfile)

        print('\nExamples:', file=outfile)
        for example_dict in config['examples']:
            print(f'\t{example_dict["user_query"]}', file=outfile)
            print(f'\t{example_dict["cypher_query"]}\n', file=outfile)

        print('\nInstructions Prompt', file=outfile)
        print(instructions_pmt, file=outfile)

        print('\nAnswer Prompt', file=outfile)
        print(answer_pmt, file=outfile)

        print('End of the Configuration')
        print(10 * '#', '\n', file=outfile)

    # with open('./outputs/filtered_schema.txt', 'w') as filtered:
    #     # reset file
    #     print('', file=filtered)

    # Queries import
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        queries = json.load(f)
        if not isinstance(queries, list):
            await client.close()
            raise ValueError(f"Error: {INPUT_FILE} is not a list")

    testing_queries: list = []

    for aq_id in query_ids:
        if isinstance(aq_id, int):
            testing_queries.append(aq_id)
        elif isinstance(aq_id, tuple):
            for tq in range(aq_id[0], aq_id[1] + 1):
                testing_queries.append(tq)
    # print(testing_queries)

    await spinner.stop()
    count = 0
    for tq in testing_queries:
        try:
            user_question = queries[tq]['query']  # type:ignore
            expected_ans = queries[tq]['output']  # type:ignore

            count += 1

            await spinner.stop()
            total = len(testing_queries)
            print(f'\n[{count}/{total}] > {user_question} (ID: {tq}) ')

            spinner.start('Filtering the Schema')
            retriever.reset_filter()
            await retriever.filter_schema(question=user_question)
            question_pmt = instructions_pmt + retriever.transcribe_schema(filtered=True)

            await spinner.restart('Formulating the Query')
            cypher_query: str = await llm_agent.write_cypher_query(
                question=user_question, prompt_upd=question_pmt
            )

            # OLD Print the filtered schema
            # with open('./outputs/filtered_schema.txt', 'a') as filtered:
            #     print(f'User Query:\n{user_question} (ID: {tq})', file=filtered)
            #     print(retriever.transcribe_schema(filtered=True), file=filtered)
            #     print('\n' + 25 * '#', file=filtered)

            await spinner.restart('Processing Results')
            query_results = await client.launch_db_query(cypher_query)
            ans_context: str = ( # NO print
                f"Answer the user question by describing the outputs provided by Neo4j: \n"
                f"Original user question: \"{user_question}\"\n"
                # f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )
            answer: str = await llm_agent.write_answer(prompt=answer_pmt, n4j_results=ans_context)

            # QUERY-specific print
            with open(OUTPUT_FILE, 'a') as outfile:
                # print(f'\n{count}) Query ID: {tq}', file=outfile)
                # print(f'\nUser Query:\n{user_question} (ID: {tq})', file=outfile)
                print(f'\n[{count}/{total}] User Query: {user_question} (ID: {tq})', file=outfile)
                print(f'\nFiltered Schema:\n{retriever.transcribe_schema()}\n\n', file=outfile)
                print(f'\nUser Query:\n{user_question} (ID: {tq})', file=outfile)
                print(f'\nGenerated Cypher query:\n{cypher_query}', file=outfile)
                print(f'\nNeo4j outputs:\n{query_results}', file=outfile)
                print(f'\nGenerated Answer:\n{answer}', file=outfile)
                print(f'\nExpected answer:\n{expected_ans}', file=outfile)
                print('\n' + 25 * '#', file=outfile)

            await spinner.stop()

        except asyncio.CancelledError:
            await spinner.stop()
            await client.close()
            await aprint("Test Interrupted!")
            return

    await client.close()

    print(f'\nTest concluded: {datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')


# END


if __name__ == '__main__':
    asyncio.run(test_query(
        neo4j_pwd=config['n4j_psw'],
        llm_name=config['llm'],
        emb_name=config['embedder'],
        query_ids=TEST_QUERIES
    ))
