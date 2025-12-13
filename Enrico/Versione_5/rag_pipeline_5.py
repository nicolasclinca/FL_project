import logging

from neo4j.exceptions import Neo4jError

from retriever import DataRetriever
from resources.spinner import Spinner
from resources.prompts import EL
from configuration import aq_tuple

from language_model import *
from neo4j_client import Neo4jClient


async def main(auto_queries: tuple,
               spin_delay: float, spin_mode: int,
               save_prompts: int = 1,
               neo4j_pw: str = None,
               filtering: bool = True,
               llm_temp: float = 0.0,
               llm_name: str = None,
               embed_name: str = None,
               k_lim: int = 10) -> None:
    # INITIALIZATION #

    logging.getLogger("neo4j").setLevel(logging.ERROR)  # disable warnings

    # NEO4J CLIENT
    client = Neo4jClient(password=neo4j_pw)
    try:  # check if Neo4j is on
        await client.check_session()
    except Exception:
        return

    # SPINNER
    spinner = Spinner(delay=spin_delay, mode=spin_mode)  # animated spinner
    spinner.start(agent_sym + "Preparing the System")

    # LLM
    exit_commands = ("#", "bye", "bye bye", "close", "esc", "exit", "goodbye", "quit")
    agent = LanguageModel(
        model_name=llm_name,
        embedder_name=embed_name,
        examples=EL.example_list_2,
        history_upd_flag=True,
        temperature=llm_temp,
    )  # LLM creation

    # DATA RETRIEVER: it prepares the schema and the prompts
    retriever = DataRetriever(
        client=client, required_aq=auto_queries,
        agent=agent, k_lim=k_lim,
    )
    instructions_pmt, answer_pmt = await retriever.init_prompts()
    await retriever.init_global_schema()

    # PROMPT PRINTING
    with open('results/prompts_file', 'w') as pmt_file:
        print('', file=pmt_file)  # always reset to blank file

    # Initialization is concluded
    await spinner.stop()
    print('# Chatbot Started #', '\n')
    await asyprint(
        agent_sym, f"Welcome from {agent.model} and {agent.embedder}. "
        # f"Please, enter your question or write 'bye' to quit"
    )

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
                await asyprint(agent_sym, "You're quitting: bye bye")
                break

            # Start querying the database
            spinner.start(agent_sym + "Formulating the query. It can take a while")

            # Filtering phase
            retriever.reset_filter()
            if filtering:
                await retriever.filter_schema(question=user_question)
            question_pmt = instructions_pmt + retriever.write_schema(filtered=True)

            if save_prompts >= 1:
                with open('results/prompts_file', 'a') as pmt_file:
                    print('\n### CONFIGURATION DATA ###', file=pmt_file)
                    print(f'\tQuestion: {user_question}', file=pmt_file)
                    print(f'\tLanguage Model: {agent.model}', file=pmt_file)
                    print(f'\tEmbedding Model: {agent.embedder}', file=pmt_file)
                    print(f'\n### QUESTION PROMPT ###\n{question_pmt}', file=pmt_file)
                    print(f'\n### ANSWER PROMPT ###\n{answer_pmt}', file=pmt_file)

            cypher_query: str = await agent.write_cypher_query(
                question=user_question, prompt_upd=question_pmt
            )

            # No query generated
            if not cypher_query:
                await asyprint(agent_sym, "Error: can't generate a query from this prompt")
                continue  # next while iteration (new user question)

            # Query successfully generated
            await spinner.stop()
            await asyprint(query_sym, cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await client.launch_db_query(cypher_query)  # pass the query to the Neo4j client
                await aprint(neo4j_sym, f"{query_results}")  # print the Cypher answer

            except Neo4jError as err:
                query_results = []
                await spinner.stop()
                await asyprint(neo4j_sym, f"Error occurred in neo4j! {err}")
                continue  # -> next user question

            finally:
                if save_prompts >= 2:  # Print the chat history
                    with open('results/prompts_file', 'a') as pmt_file:
                        print('\n### CHAT HISTORY ###', '\n', file=pmt_file)
                        for message in agent.chat_history:
                            print('\n' + message['content'], file=pmt_file)

            # RESULTS READING #
            spinner.start(agent_sym + "Formulating the answer")

            ans_context: str = (
                f"Comment the results of the Cypher query, in natural language: \n"
                f"Original user question: \"{user_question}\"\n"
                # f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )

            answer: str = await agent.write_answer(prompt=answer_pmt, n4j_results=ans_context)

            if save_prompts >= 1:
                with open('results/prompts_file', 'a') as pmt_file:
                    print('\n' + 25 * '#' + '\n', file=pmt_file)

            await spinner.stop()
            await asyprint(agent_sym, answer)

            print()  # new line
        # END while


    except asyncio.CancelledError:
        await spinner.stop()
        await asyprint("\n" + agent_sym, "You've interrupted the chat: goodbye!")

    except Exception as err:
        await aprint(agent_sym + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await client.close()
        await aprint("\n", "# Session concluded #")


if __name__ == "__main__":
    asyncio.run(main(
        auto_queries=aq_tuple,
        save_prompts=1,  # 0 per niente, 1 per i prompt, 2 per prompt e cronologia
        spin_mode=1,  # 0 per ... and 1 for /
        spin_delay=0.3,  # durata di un fotogramma dell'animazione del cursore
        neo4j_pw='4Neo4Jay!',  # password del client Neo4j -> se è None, la chiede come input()
        llm_temp=0.0,  # model temperature
        llm_name='llama3.1',  # 'codellama:7b',  # 'qwen3:8b',  # 'llama3.1',
        embed_name='nomic-embed-text',  # "embeddinggemma", 'nomic-embed-text',
        filtering=True,
        k_lim=5,  # number of examples
    ))
