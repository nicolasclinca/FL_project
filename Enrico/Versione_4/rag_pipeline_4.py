from neo4j.exceptions import Neo4jError

from retriever import DataRetriever
from resources.spinner import Spinner
from resources.prompts import EL
from configuration import aq_tuple

from language_model import *
from neo4j_client import Neo4jClient


async def main(auto_queries: tuple,
               spin_delay: float, spin_mode: int,
               save_prompts: bool,
               neo4j_pw: str = None,
               filtering: bool = True,
               llm_temp: float = 0.0,
               llm_model: str = None) -> None:
    # INITIALIZATION #
    # CURSOR
    spinner = Spinner(delay=spin_delay, mode=spin_mode)  # animated spinner
    spinner.start(agent_sym + "Preparing the System")

    # NEO4J CLIENT
    client = Neo4jClient(password=neo4j_pw)

    # DATA RETRIEVER: it prepares the schema and the prompts
    retriever = DataRetriever(client, required_aq=auto_queries)
    instructions_pmt, answer_pmt = await retriever.init_prompts()
    await retriever.init_global_schema()

    # LLM
    exit_commands = ["#", "bye", "bye bye", "close", "esc", "exit", "goodbye", "quit"]
    agent = LLM(
        sys_prompt=instructions_pmt, model=llm_model,
        examples=EL.example_list_2, upd_history=True,
        temperature=llm_temp,
    )  # LLM creation

    # PROMPT PRINTING
    with open('results/prompts_file', 'w') as pmt_file:
        print('', file=pmt_file)  # reset to blank file
        if save_prompts:
            print(f'### ANSWER PROMPT ###\n{answer_pmt}', file=pmt_file)

    # Initialization is concluded
    await spinner.stop()
    print('# Chatbot Started #', '\n')
    await awrite(agent_sym, f"Welcome from {agent.model}. Enter your question")

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
                await awrite(agent_sym, "You're quitting: bye bye")
                break

            # Start querying the database
            spinner.start(agent_sym + "Formulating the query")

            # Filtering phase
            retriever.reset_filter()
            if filtering:
                await retriever.filter_schema(question=user_question)
            question_pmt = instructions_pmt + retriever.write_schema(filtered=True)
            if save_prompts:
                with open('results/prompts_file', 'a') as pmt_file:
                    print('\n', '# QUESTION PROMPT', question_pmt, file=pmt_file)

            # cypher_query: str = await agent.write_cypher_query(
            #     user_query=user_question, prompt_upd=question_pmt
            # )

            cypher_query: str = await agent.new_write_cypher_query(
                question=user_question, prompt_upd=question_pmt
            )

            # No query generated
            if not cypher_query:
                await awrite(agent_sym, "Error: can't generate a query from this prompt")
                continue  # next while iteration (new user question)

            # Query successfully generated
            await spinner.stop()
            await awrite(query_sym, cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await client.launch_query(cypher_query)  # pass the query to the Neo4j client
                await aprint(neo4j_sym, f"{query_results}")  # print the Cypher answer

            except Neo4jError as err:
                query_results = []
                await spinner.stop()
                await awrite(neo4j_sym, f"Error occurred in neo4j! {err}")
                continue  # -> next user question

            finally:
                if save_prompts:
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

            await spinner.stop()
            await awrite(agent_sym, answer)

            print()  # new line

        # END while


    except asyncio.CancelledError:
        await spinner.stop()
        await awrite("\n" + agent_sym, "You've interrupted the chat: goodbye!")

    except Exception as err:
        await aprint(agent_sym + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await client.close()
        await aprint("\n", "# Session concluded #")


if __name__ == "__main__":
    asyncio.run(main(
        auto_queries=aq_tuple,
        save_prompts=True,  # stampa i prompt di sistema prima di avviare la chat
        spin_mode=1,  # 0 per ... and 1 for /
        spin_delay=0.3,  # durata di un fotogramma dell'animazione del cursore
        neo4j_pw='4Neo4Jay!',  # password del client Neo4j -> se è None, la chiede come input()
        llm_temp=0.4,
        llm_model='qwen3:4b',  # 'llama3.1'
        filtering=False,
    ))
