import asyncio
import sys
import time

from aioconsole import ainput, aprint

from initialization import simple_init, complex_init
from Enrico.Versione_1.language_model import LLM, user_token, agent_token
from Enrico.Versione_1.neo4j_handler import Neo4jHandler


async def user_input() -> str:
    return await ainput(user_token)


async def main(complex_mode: bool, schema_sel='', prompt_sel='ie', ans_sel='s', print_prompt=False) -> None:
    exit_commands = ["//", "##", "bye", "close", "exit", "goodbye", "quit"]

    handler = Neo4jHandler(password="4Neo4Jay!")

    if complex_mode:
        sys_prompt, answer_prompt = await complex_init(handler, schema_sel, prompt_sel, ans_sel)
    else:
        sys_prompt, answer_prompt = simple_init(schema_sel='ghe', prompt_sel='ie', ans_sel='s')

    # Stampa del prompt
    if print_prompt:
        print(f'### SYSTEM PROMPT ###\n{sys_prompt}\n ### FINE DEL PROMPT ###\n')

    # rendere dinamico anche answer_prompt


    agent = LLM(sys_prompt=sys_prompt)
    await aprint(agent_token + "System started: Ask about your smart house")

    # Question processing
    try:
        while True:

            user_query = await user_input()
            if not user_query:
                continue

            # Close Session
            if user_query.lower() in exit_commands:
                await aprint(agent_token + "Bye Bye!")
                break

            # Start querying the database
            await aprint(agent_token + "Formulating the query...")
            # Inserire cursore animato ?
            cypher_query = await agent.write_cypher_query(user_query=user_query, prompt_upd=sys_prompt)

            # No query generated
            if not cypher_query:
                await aprint(
                    agent_token + "Can't generate a query from this prompt. Please, try to rewrite it")
                continue  # the While loop

            # Query successfully generated
            await aprint(agent_token + f"Cypher query:\n\t\t  {cypher_query}")

            # Query elaboration
            query_results = []
            try:
                query_results = await handler.launch_query(cypher_query)  # lancia la query sul serio
                await aprint(agent_token + f"Query results: {query_results}")  # stampa la risposta Cypher

            except Exception as err:
                await aprint(
                    agent_token + "Error occurred: incorrect data or query")
                continue

            await aprint(agent_token + "Formuling the answer...")

            answer_context = (
                f"Original user query: \"{user_query}\"\n"
                #f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )

            answer = agent.launch_chat(query=answer_context, prompt_upd=answer_prompt)
            await agent.print_answer(answer)


    except asyncio.CancelledError:
        await aprint("\n" + agent_token + "Chat interrupted. Goodbye!")

    except Exception as err:
        await aprint(agent_token + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await handler.close()
        await aprint("\nSession successfully concluded.")


if __name__ == "__main__":
    asyncio.run(main(
        complex_mode=True,
        schema_sel='',
        prompt_sel='ie',
        ans_sel='s',
        print_prompt=False
    ))
