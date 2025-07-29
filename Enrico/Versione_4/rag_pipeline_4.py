from neo4j.exceptions import Neo4jError

from retriever import InfoRetriever
from res.auto_queries import AutoQueries
from res.cursor import Cursor
from res.prompts import Examples

from language_model import *
from neo4j_client import Neo4jClient


async def main(schema_sel, query_sel, ans_sel,  # init selectors
               spin_delay: float, spin_mode: int,
               print_prompt: bool = False,
               neo4j_pw: str = None) -> None:

    exit_commands = ["#", "bye", "bye bye", "close", "exit", "goodbye", "quit"]

    # INITIALIZATION
    cursor = Cursor(delay=spin_delay, mode=spin_mode)  # animated cursor
    cursor.set_message(agent_sym + "Preparing the schema")
    cursor.start()

    client = Neo4jClient(password=neo4j_pw)  # neo4j client
    retriever = InfoRetriever(client)

    question_pmt, answer_pmt = await retriever # initialized prompts

    await cursor.stop()

    print('\n# Chatbot Started #\n')

    # Stampa dei prompt
    if print_prompt:
        print(f'### QUESTION PROMPT ###\n{question_pmt}\n\n')
        print(f'### ANSWER PROMPT ###\n{answer_pmt}\n\n')
        # non ho ancora messo un print di answer_context

    agent = LLM(sys_prompt=question_pmt, model='codellama:7b', examples=Examples.example_list_1)  # LLM creation
    await awrite(agent_sym, f"Welcome from {agent.model}: ask about your knowledge graph database")

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

            cypher_query: str = await agent.write_cypher_query(user_query=user_question, prompt_upd=question_pmt)

            # No query generated
            if not cypher_query:
                await awrite(agent_sym,
                             "Can't generate a query from this prompt. Please, try to rewrite it")
                continue  # next while iteration (new user question)

            # Query successfully generated
            await cursor.stop()
            await awrite(query_sym, cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await client.launch_query(cypher_query)  # pass the query to the Neo4j client
                await aprint(neo4j_sym + f"{query_results}")  # print the Cypher answer

            except Neo4jError as err:
                # query_results = [{'Error': err}]
                await cursor.stop()
                await awrite(neo4j_sym, f"Error occurred in neo4j!")
                continue  # -> next user question

            # RESULTS READING #
            cursor.set_message(agent_sym + "Formuling the answer")
            cursor.start()

            ans_context: str = (
                f"Comment the results of the Cypher query, in natural language: \n"
                #f"Original user query: \"{user_question}\"\n"
                f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )

            answer: str = await agent.write_answer(prompt=answer_pmt, n4j_results=ans_context)

            await cursor.stop()
            await awrite(agent_sym, answer)


    except asyncio.CancelledError:
        await cursor.stop()
        await awrite("\n" + agent_sym, "You've interrupted the chat: goodbye!")

    except Exception as err:
        await aprint(agent_sym + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await client.close()
        await aprint("\n# Session concluded #")


if __name__ == "__main__":
    AQ = AutoQueries  # Class: General Queries

    asyncio.run(main(
        schema_sel="cst",
        query_sel="",
        ans_sel="",
        print_prompt=True,  # stampa i prompt di sistema prima di avviare la chat
        spin_mode=0,  # 0 for ... and 1 for /
        spin_delay=0.5,  # durata di un fotogramma dell'animazione
        neo4j_pw='4Neo4Jay!',  # password del client Neo4j -> se è None, la chiede come input()
    ))
