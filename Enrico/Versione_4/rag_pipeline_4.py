from neo4j.exceptions import Neo4jError

from retriever import DataRetriever
from resources.cursor import Cursor
from resources.prompts import EL

from language_model import *
from neo4j_client import Neo4jClient


async def main(auto_queries: tuple,
               spin_delay: float, spin_mode: int,
               save_prompts: bool,
               neo4j_pw: str = None) -> None:
    # INITIALIZATION
    cursor = Cursor(delay=spin_delay, mode=spin_mode)  # animated cursor
    cursor.set_message(agent_sym + "Preparing the System")
    cursor.start()

    client = Neo4jClient(password=neo4j_pw)  # neo4j client

    retriever = DataRetriever(client, required_aq=auto_queries)
    instructions_pmt, answer_pmt = await retriever.init_prompts()
    await retriever.init_global_schema()

    exit_commands = ["#", "bye", "bye bye", "close", "esc", "exit", "goodbye", "quit"]
    agent = LLM(
        sys_prompt=instructions_pmt, model='codellama:7b',
        examples=EL.testing_examples, upd_history=False
    )  # LLM creation

    # PROMPT PRINTING
    with open('results/prompts_file', 'w') as pmt_file:
        print('', file=pmt_file)  # blank file

        # print(f'### INSTRUCTION PROMPT ###\n{instructions_pmt}\n\n', file=pmt_file)
        print(f'### ANSWER PROMPT ###\n{answer_pmt}\n\n', file=pmt_file)

    # Initialization is concluded
    await cursor.stop()
    print('# Chatbot Started #', '\n')
    await awrite(agent_sym, f"Welcome from {agent.model}. Enter your question")

    # Question processing
    try:
        while True:
            user_question = await user_input()
            if not user_question:
                continue

            # Close Session
            if user_question.lower() in exit_commands:
                await cursor.stop()
                await awrite(agent_sym, "You're quitting: bye bye")
                break

            # Start querying the database
            cursor.set_message(agent_sym + "Formulating the query")
            cursor.start()

            # Filtering phase
            retriever.reset_filter()
            retriever.filter_schema(question=user_question)
            question_pmt = instructions_pmt + retriever.write_schema()
            if save_prompts:
                with open('results/prompts_file', 'a') as pmt_file:
                    print('# QUESTION PROMPT', question_pmt, file=pmt_file)

            cypher_query: str = await agent.write_cypher_query(user_query=user_question, prompt_upd=question_pmt)

            # No query generated
            if not cypher_query:
                await awrite(agent_sym, "Error: can't generate a query from this prompt")
                continue  # next while iteration (new user question)

            # Query successfully generated
            await cursor.stop()
            await awrite(query_sym, cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await client.launch_query(cypher_query)  # pass the query to the Neo4j client
                await aprint(neo4j_sym, f"{query_results}")  # print the Cypher answer

            except Neo4jError as err:
                query_results = []
                await cursor.stop()
                await awrite(neo4j_sym, f"Error occurred in neo4j! {err}")
                continue  # -> next user question

            finally:
                if save_prompts:
                    with open('results/prompts_file', 'a') as pmt_file:
                        print('\n### CHAT HISTORY ###', '\n', file=pmt_file)
                        for message in agent.chat_history:
                            print(message['content'], file=pmt_file)

            # RESULTS READING #
            cursor.set_message(agent_sym + "Formulating the answer")
            cursor.start()

            ans_context: str = (
                f"Comment the results of the Cypher query, in natural language: \n"
                #f"Original user query: \"{user_question}\"\n"
                # f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )

            answer: str = await agent.write_answer(prompt=answer_pmt, n4j_results=ans_context)

            await cursor.stop()
            await awrite(agent_sym, answer)

            print()  # new line

        # END while


    except asyncio.CancelledError:
        await cursor.stop()
        await awrite("\n" + agent_sym, "You've interrupted the chat: goodbye!")

    except Exception as err:
        await aprint(agent_sym + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await client.close()
        await aprint("\n", "# Session concluded #")


if __name__ == "__main__":
    asyncio.run(main(
        auto_queries=(
            # 'LABELS',
            # 'PROPERTIES',
            'RELATIONSHIP TYPES',
            # 'RELATIONSHIPS',
            # 'GLOBAL SCHEMA',
            'NAMES', 'LABELS',
        ),
        save_prompts=True,  # stampa i prompt di sistema prima di avviare la chat
        spin_mode=1,  # 0 per ... and 1 for /
        spin_delay=0.3,  # durata di un fotogramma dell'animazione del cursore
        neo4j_pw='4Neo4Jay!',  # password del client Neo4j -> se è None, la chiede come input()
    ))
