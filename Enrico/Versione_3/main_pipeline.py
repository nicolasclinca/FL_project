import asyncio
from collections.abc import AsyncIterator
from aioconsole import aprint

from res.auto_queries import *
from res.spinner import Spinner

from initialization import initialize
from language_model import *
from neo4j_handler import Neo4jHandler


async def main(schema_sel: str, prompt_sel: str, ans_sel: str,
               spin_delay: float, spin_mode: int,
               schema_queries: list = None,  # per aumentare lo schema
               ans_queries: list = None,  # per aumentare il comando per la risposta
               cont_queries: list = None,  # per aumentare il contesto della risposta
               print_prompt: bool = False, ) -> None:
    exit_commands = ["//", "##", "bye", "bye bye", "close", "exit", "goodbye", "quit"]
    handler = Neo4jHandler(password="4Neo4Jay!")
    spinner = Spinner(delay=spin_delay, mode=spin_mode)  # cursore animato

    query_prompt, answer_prompt = await initialize(
        handler=handler, selectors=(schema_sel, prompt_sel, ans_sel),
        auto_queries=schema_queries, answer_queries=ans_queries,
    )

    print('\n# Session Started #\n')

    # Stampa dei prompt
    if print_prompt:
        print(f'### QUERY PROMPT ###\n{query_prompt}\n ### FINE DEL PROMPT ###\n')
        print(f'### ANSWER PROMPT ###\n{answer_prompt}\n ### FINE DEL PROMPT ###\n')
        # non ho ancora messo un print di answer_context

    agent = LLM(sys_prompt=query_prompt)  # LLM creation
    await slow_print(agent_token + "Welcome: ask about your smart house")

    # Question processing
    try:
        while True:
            user_query = await user_input()
            if not user_query:
                continue

            # Close Session
            if user_query.lower() in exit_commands:
                await spinner.stop()
                await slow_print(agent_token + "You're quitting: bye bye")
                break

            # Start querying the database
            spinner.set_message(agent_token + "Formulating the query")
            spinner.start()

            cypher_query: str = await agent.write_cypher_query(user_query=user_query, prompt_upd=query_prompt)

            # No query generated
            if not cypher_query:
                await aprint(
                    agent_token + "Can't generate a query from this prompt. Please, try to rewrite it")
                continue  # While loop

            # Query successfully generated
            await spinner.stop()
            await aprint(query_token + cypher_query)

            # NEO4J OPERATIONS #
            try:
                query_results = await handler.launch_query(cypher_query)  # pass query to handler
                await aprint(neo4j_token + f"{query_results}")  # print Cypher answer

            except Exception as err:
                query_results = []
                await spinner.stop()
                await aprint(neo4j_token + "Error occurred: incorrect data or query")
                # continue  # -> prossima query utente

            # RESULTS READING #
            spinner.set_message(agent_token + "Formuling the answer")
            spinner.start()

            answer_prompt: str = await handler.augment_prompt(auto_queries=ans_queries, chat_msg=answer_prompt)

            ans_context: str = (
                f"Original user query: \"{user_query}\"\n"
                #f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )
            ans_context: str = await handler.augment_prompt(auto_queries=cont_queries, chat_msg=ans_context)

            answer: str = await agent.write_answer(prompt=answer_prompt, context=ans_context)

            await spinner.stop()
            await slow_print(agent_token + answer)


    except asyncio.CancelledError:
        await spinner.stop()
        await slow_print("\n" + agent_token + "You've interrupted the chat: goodbye!")

    except Exception as err:
        await aprint(agent_token + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await handler.close()
        await aprint("\n# Session concluded #")


if __name__ == "__main__":

    all_init_queries = [get_properties, get_relationships, ]
    all_answer_queries = [devices_list, devices_map, ]

    asyncio.run(main(
        schema_sel='',  # H.ouse, G.raph, E.xamples,
        prompt_sel='i',  # I.nstructions, E.xamples,
        ans_sel='1',  # 0 or 1
        schema_queries=[get_properties, get_relationships], # per integrare il query_prompt
        ans_queries=[], # per integrare l'answer_prompt
        cont_queries=[devices_map, devices_list], # per integrare l'answer_context
        print_prompt=False,  # stampa i prompt di sistema prima di avviare la chat
        spin_mode=1,  # 0 for ... and 1 for /
        spin_delay=0.5,
    ))
