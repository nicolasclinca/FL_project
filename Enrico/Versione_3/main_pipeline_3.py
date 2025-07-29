
from res.auto_queries import GeneralQueries
from res.cursor import Cursor

from initialization import initialize
from language_model import *
from neo4j_client import Neo4jClient


async def main(schema_sel: str, prompt_sel: str, ans_sel: str,
               spin_delay: float, spin_mode: int,
               schema_queries: list = None,  # per aumentare lo schema
               ans_queries: list = None,  # per aumentare il prompt per la risposta
               cont_queries: list = None,  # per aumentare il prompt della risposta
               print_prompt: bool = False,
               neo4j_pw: str = None) -> None:


    exit_commands = ["#", "bye", "bye bye", "close", "exit", "goodbye", "quit"]
    n4j_cli = Neo4jClient(password=neo4j_pw)
    cursor = Cursor(delay=spin_delay, mode=spin_mode)  # cursore animato

    query_prompt, answer_prompt = await initialize(
        n4j_cli=n4j_cli, selectors=(schema_sel, prompt_sel, ans_sel),
        auto_queries=schema_queries, answer_queries=ans_queries,
    )

    print('\n# Chatbot Started #\n')

    # Stampa dei prompt
    if print_prompt:
        print(f'### QUERY PROMPT ###\n{query_prompt}\n ### FINE DEL PROMPT ###\n')
        print(f'### ANSWER PROMPT ###\n{answer_prompt}\n ### FINE DEL PROMPT ###\n')
        # non ho ancora messo un print di answer_context

    agent = LLM(sys_prompt=query_prompt)  # LLM creation
    await awrite(agent_token + "Welcome: ask about your knowledge graph database")

    # Question processing
    try:
        while True:
            user_query = await user_input()
            if not user_query:
                continue

            # Close Session
            if user_query.lower() in exit_commands:
                await cursor.stop()
                await awrite(agent_token + "You're quitting: bye bye")
                break

            # Start querying the database
            cursor.set_message(agent_token + "Formulating the query")
            cursor.start()

            cypher_query: str = await agent.write_cypher_query(user_query=user_query, prompt_upd=query_prompt)

            # No query generated
            if not cypher_query:
                await aprint(
                    agent_token + "Can't generate a query from this prompt. Please, try to rewrite it")
                continue  # next while iteration (new user query)

            # Query successfully generated
            await cursor.stop()
            await awrite(query_token + cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await n4j_cli.launch_query(cypher_query)  # pass the query to the Neo4j n4j_cli
                await aprint(neo4j_token + f"{query_results}")  # print the Cypher answer

            except Exception as err:
                query_results = []
                await cursor.stop()
                await aprint(neo4j_token + "Error occurred: incorrect data or query")
                # continue  # -> prossima query utente

            # RESULTS READING #
            cursor.set_message(agent_token + "Formuling the answer")
            cursor.start()

            answer_prompt: str = await n4j_cli.augment_prompt(auto_queries=ans_queries, chat_msg=answer_prompt)

            ans_context: str = (
                f"Original user query: \"{user_query}\"\n"
                #f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )
            # NON LECITO (aumento contesto)
            ans_context: str = await n4j_cli.augment_prompt(auto_queries=cont_queries, chat_msg=ans_context)

            answer: str = await agent.write_answer(prompt=answer_prompt, context=ans_context)

            await cursor.stop()
            await awrite(agent_token + answer)


    except asyncio.CancelledError:
        await cursor.stop()
        await awrite("\n" + agent_token + "You've interrupted the chat: goodbye!")

    except Exception as err:
        await aprint(agent_token + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await n4j_cli.close()
        await aprint("\n# Session concluded #")


if __name__ == "__main__":
    GQ = GeneralQueries # Class: General Queries

    asyncio.run(main(
        schema_sel='',  # H.ouse, G.raph, E.xamples,
        prompt_sel='i0',  # I.nstructions (I0 o I1), E.xamples,
        ans_sel='a1',  # A0 or A1
        schema_queries=[GQ.get_properties, GQ.get_classes_rel],  # per integrare il query_prompt
        ans_queries=[],  # per integrare l'answer_prompt -> NON LECITO (forse)
        cont_queries=[],  # per integrare l'answer_context -> NON LECITO (sicuramente)
        print_prompt=True,  # stampa i prompt di sistema prima di avviare la chat
        spin_mode=0,  # 0 for ... and 1 for /
        spin_delay=0.5,  # durata di un fotogramma dell'animazione
        neo4j_pw=None,  # password del client Neo4j -> se è None, la chiede come input()
    ))

