import asyncio
from collections.abc import AsyncIterator

from spinner import Spinner
from aioconsole import ainput, aprint

from initialization import simple_init, init_1
from language_model import agent_token, user_token, print_answer, LLM
from neo4j_handler import Neo4jHandler


async def user_input() -> str:
    return await ainput(user_token)


async def main(initializator: int, print_prompt: bool,
               schema_sel: str, prompt_sel: str, ans_sel: str,
               spin_delay: float, spin_mode: int) -> None:

    exit_commands = ["//", "##", "bye", "close", "exit", "goodbye", "quit"]

    handler = Neo4jHandler(password="4Neo4Jay!")

    spinner = Spinner(delay=spin_delay, mode=spin_mode) # spinning cursor

    if initializator == 1:
        sys_prompt, answer_prompt = await init_1(
            handler=handler, schema_sel=schema_sel,
            prompt_sel=prompt_sel, ans_sel=ans_sel,
        )
    else: ## == 0
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

            spinner.set_message(agent_token + "Formulating the query")
            spinner.start()
            try:
                cypher_query = await agent.write_cypher_query(user_query=user_query, prompt_upd=sys_prompt)
            finally:
                await spinner.stop()

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

            spinner.set_message(agent_token + "Formuling the answer")
            spinner.start()

            answer_context = (
                f"Original user query: \"{user_query}\"\n"
                #f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )

            answer: AsyncIterator[str] = agent.launch_chat(query=answer_context, prompt_upd=answer_prompt)
            await spinner.stop()

            await print_answer(answer)

            # stampa istantanea
            # answer = await agent.write_answer(context=answer_context, prompt=answer_prompt)
            # await aprint(agent_token + answer)



    except asyncio.CancelledError:
        await aprint("\n" + agent_token + "Chat interrupted. Goodbye!")

    except Exception as err:
        await aprint(agent_token + f"An error occurred in the main loop: {err}")

    finally:  # Normal conclusion
        await handler.close()
        await aprint("\nSession successfully concluded.")


if __name__ == "__main__":
    asyncio.run(main(
        initializator=1,  # Select the init function in initialization.py
        schema_sel='',  # H.ouse, G.raph, E.xamples,
        prompt_sel='',  # I.nstructions, E.xamples,
        ans_sel='s',  # S.imple
        print_prompt=True, # stampa il prompt di sistema prima di avviare la chat
        spin_mode=0, # ... or /
        spin_delay=0.5, # animation duration in seconds
    ))
