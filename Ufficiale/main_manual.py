import logging
from pprint import pprint

from neo4j.exceptions import Neo4jError

from embedding_model import Embedder
from retriever import DataRetriever
from utilities.spinner import Spinner
from configuration import config

from language_model import *
from neo4j_client import Neo4jClient

OUTPUT_PATH = 'outputs/manual_results.txt'


async def main(save_prompts: bool = True) -> None:
    # INITIALIZATION #

    # No Logging Messages
    logging.getLogger("neo4j").setLevel(logging.ERROR)  # disable warnings

    # PROMPTS
    instructions_pmt = config['question_prompt']
    answer_pmt = config['answer_prompt']

    # NEO4J CLIENT

    try:  # check if Neo4j is on
        n4j_client = Neo4jClient(user= config['n4j_usr'],
                                 password=config['n4j_psw'],
                                 uri=config['n4j_url'])
        await n4j_client.check_session()
    except Exception:
        return

    # SPINNER
    spinner = Spinner()  # animated spinner
    spinner.start(agent_sym + "Preparing the System")

    # LARGE LANGUAGE MODEL
    exit_commands = config['quit_key_words']

    # Checking the installation of models
    llm_agent = LanguageModel(
        model_name=config['llm'],
        examples=config['examples'],
    )  # LLM creation

    # EMBEDDING MODEL
    embedder = Embedder(config['embedder'])

    # Check models installation
    if not llm_agent.check_installation() or not embedder.check_installation():
        await n4j_client.close()
        await spinner.stop()
        return

    # DATA RETRIEVER: it prepares the schema and the prompts
    retriever = DataRetriever(
        n4j_cli=n4j_client, embedder=embedder,
        k_lim=config['k_lim'], thresh=config['thresh'],
    )
    await retriever.init_full_schema()

    # PROMPT PRINTING
    with open(OUTPUT_PATH, 'w') as pmt_file:
        print('\n### CONFIGURATION DATA ###', file=pmt_file)
        print(f'\tLanguage Model: {llm_agent.model_name}', file=pmt_file)
        print(f'\tEmbedding Model: {embedder.name}', file=pmt_file)

        print('\n### EXAMPLES ###', file=pmt_file)
        for message in llm_agent.examples_list:
            print('\n' + message['content'], file=pmt_file)

    # Initialization is concluded
    await spinner.stop()

    with open("outputs/full_schema.txt", 'w') as test_file:
        print(10 * "#", "FULL SCHEMA", 10 * '#', file=test_file)
        for aq_name in retriever.full_schema.keys():
            print("\n", aq_name, file=test_file)
            pprint(retriever.full_schema[aq_name], stream=test_file)
        print('\n', file=test_file)
    # fine test

    await asyprint(
        agent_sym, f"Welcome from {llm_agent.model_name} and {embedder.name}."
        # f"Please, enter your question or write 'bye' to quit"
    )
    print()
    # SESSION STARTED
    try:
        while True:
            # Question processing
            user_question = await user_input()
            if not user_question:
                continue

            # Close Session
            if user_question.lower() in exit_commands:
                await spinner.stop()
                await asyprint(agent_sym, "You've type an exit command: bye bye")
                break

            # Start querying the database
            spinner.start(agent_sym + "Formulating the query. It can take a while")

            # Filtering phase
            retriever.reset_filter()

            await retriever.filter_schema(question=user_question)
            question_pmt = instructions_pmt + retriever.transcribe_schema(filtered=True)

            # Query generation phase
            cypher_query: str = await llm_agent.write_cypher_query(
                question=user_question, prompt_upd=question_pmt
            )

            # Saving Prompts
            if save_prompts:
                with open(OUTPUT_PATH, 'a') as pmt_file:
                    print(f"\n\n### QUESTION: {user_question}", file=pmt_file)
                    print(f'\n### QUESTION PROMPT ###\n{question_pmt}', file=pmt_file)

            # No query generated
            if not cypher_query:
                await asyprint(agent_sym, "Error: can't generate a query from this prompt")
                continue  # next user question

            # Query successfully generated
            await spinner.stop()
            await asyprint(query_sym, cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await n4j_client.launch_db_query(cypher_query)  # pass the query to the Neo4j client
                await aprint(neo4j_sym, f"{query_results}")  # print the Cypher answer

            except Neo4jError as err:
                await spinner.stop()
                await asyprint(neo4j_sym, f"Error occurred in neo4j!\n{err}\n")
                continue  # -> next user question

            # RESULTS READING #
            spinner.start(agent_sym + "Formulating the answer")

            ans_context: str = (
                f"Answer the user question by describing the outputs provided by Neo4j: \n"
                f"Original user question: \"{user_question}\"\n"
                # f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )

            answer: str = await llm_agent.write_answer(prompt=answer_pmt, n4j_results=ans_context)

            if save_prompts:
                with open(OUTPUT_PATH, 'a') as pmt_file:
                    print(f'\n### ANSWER PROMPT ###\n{answer_pmt}', file=pmt_file)
                    print('\n### CONTEXT ###\n', file=pmt_file)
                    print(ans_context, file=pmt_file)
                    print(f"\nGENERATED QUERY: {cypher_query}", file=pmt_file)
                    print('\n### ANSWER ###\n', file=pmt_file)
                    print(answer, file=pmt_file)

                    print('\n' + 25 * '#' + '\n', file=pmt_file)

            await spinner.stop()
            await asyprint(agent_sym, answer)

            print()  # new line
        # END while


    except asyncio.CancelledError:
        await spinner.stop()
        await asyprint("\n" + agent_sym, "Chat session manually abrupted!")

    except Exception as err:
        await spinner.stop()
        await asyprint(agent_sym, f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await n4j_client.close()


if __name__ == "__main__":
    asyncio.run(main(
        save_prompts=True,
    ))
