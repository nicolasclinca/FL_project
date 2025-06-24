import asyncio
from collections.abc import AsyncIterator
from typing import LiteralString

import ollama as ol
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase, AsyncDriver

### CONFIGURATION ###

user_token = "[User]  > "
agent_token = "[Agent] > "


### Neo4j custom configuration


class Neo4jHandler:
    """Handle interactions with the database Neo4j."""

    def __init__(self, uri: str = None, user: str = None, password: str = None) -> None:
        """Create an asynchronous driver for the Neo4j Database"""
        if uri is None:
            uri = "bolt://localhost:7687"
        if user is None:
            user = "neo4j"
        if password is None:
            password = "neo4j"
        # print(f"""Uri: {uri}; User: {user}; Password: {password}""")

        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self) -> None:
        """Close the connection """
        await self._driver.close()

    async def launch_query(self, query: str, params: dict | None = None) -> list[dict]:
        """
        Execute a Cypher query and return the results.
        """
        params = params or {}
        try:
            async with self._driver.session() as session:
                # query = LiteralString(query)
                result = await session.run(query, params)
                return [record.data() async for record in result]  # query results
        except Exception as err:
            await aprint(agent_token + f"Neo4j query execution error: {err}")
            raise


class LLM:  # B-ver.
    def __init__(self, model: str = "llama3.1", sys_prompt: str = None) -> None:
        if sys_prompt is None:
            sys_prompt = "You are a helpful assistant."
        self.sys_prompt = sys_prompt
        self.client = ol.AsyncClient("localhost")
        self.model = model

    async def launch_chat(self, query: str, prompt_upd: str = None) -> AsyncIterator[str]:
        if prompt_upd is not None:  # system prompt update
            self.sys_prompt = prompt_upd

        messages = (
            ol.Message(role="system", content=self.sys_prompt),
            ol.Message(role="user", content=query),
        )
        try:  # Launch the chat
            async for chunk in await self.client.chat(self.model, messages, stream=True):
                yield chunk.message.content

        except Exception as err:
            await aprint(agent_token + f"LLM streaming error: {err}")
            yield ""

    async def write_cypher_query(self, user_query: str, prompt_upd: str = None) -> str:
        # da G.
        stream_list = []
        try:
            async for stream_chunk in self.launch_chat(query=user_query, prompt_upd=prompt_upd):
                stream_list.append(stream_chunk)
            cypher_query = "".join(stream_list).strip()  # : Literal_String
            if "```cypher" in cypher_query:
                cypher_query = cypher_query.split("```cypher")[1].split("```")[0].strip()
            elif "```" in cypher_query:
                cypher_query = cypher_query.replace("```", "").strip()
            return cypher_query
        except Exception as err:
            await aprint(agent_token + f"LLM full response error: {err}")
            return ""

    async def print_answer(self, ans_context: AsyncIterator[str]) -> None:
        """Stampa la risposta"""
        await aprint(agent_token, end="")
        async for chunk in ans_context:  # per ogni pezzo di risposta
            await aprint(chunk, end="")  # stampa il pezzo
        await aprint()  # solo una piccola attesa?


async def user_input() -> str:
    return await ainput(user_token)


async def gemini_print_response(response_stream: AsyncIterator[str]) -> None:
    await aprint(agent_token, end="")
    async for chunk in response_stream:  # lo prende da get_response_stream(), non da full
        await aprint(chunk, end="", flush=True)
    await aprint()


async def prof_print_response(agent: LLM, query: str) -> None:
    """Stampa la risposta"""
    await aprint(agent_token, end="")
    async for chunk in agent.launch_chat(query):  # per ogni pezzo di risposta
        await aprint(chunk, end="")  # stampa il pezzo
    await aprint()  # solo una piccola attesa?


def schema_initialization():
    house_schema = """
    Node Labels and their primary properties (nodes often have multiple labels due to class hierarchy):
    Note: Ontology classes are prefixed with 'ns0__'. For example, a Room is labeled :ns0__Room.
    - ns0__Room: Represents locations. Examples: "Living_room", "Kitchen", "Bedroom", "Bathroom", "Study".
    - ns0__Device: Base label for all devices.
        - ns0__Togglable_device (subclass of ns0__Device): Has a 'ns0__state' property (string, e.g., "on", "off").
            - ns0__Light (subclass of ns0__Togglable_device): Represents all lights.
                - ns0__Dimmable_light (subclass of ns0__Light and ns0__Settable_device): Also has 'ns0__setting' (number, brightness percentage) and 'ns0__unit' ("percent"). Examples: "Ceiling_light_1", "Lamp_1", "Lamp_2".
            - ns0__Appliance (subclass of ns0__Togglable_device): Represents household appliances.
                - ns0__Air_conditioner (subclass of ns0__Appliance and ns0__Settable_device): Has 'ns0__state', 'ns0__setting' (number, temperature), and 'ns0__unit' ("C"). Examples: "Air_conditioner_1", "Air_conditioner_2".
                - ns0__Coffee_machine (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Coffee_machine_1".
                - ns0__Oven (subclass of ns0__Appliance and ns0__Settable_device): Has 'ns0__state', 'ns0__setting' (number, temperature), and 'ns0__unit' ("C"). Example: "Oven_1".
                - ns0__Robot_vacuum (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Robot_vacuum_1".
                - ns0__Television (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Television_1".
                - ns0__Washing_machine (subclass of ns0__Appliance): Has 'ns0__state'. Example: "Washing_machine_1".
        - ns0__Settable_device (subclass of ns0__Device): Has 'ns0__setting' (varying type) and 'ns0__unit' (string) properties.
        - ns0__Sensor (subclass of ns0__Device): Has a 'ns0__value' property (varying type) and possibly 'ns0__unit'.
            - ns0__Boolean_sensor (subclass of ns0__Sensor): 'ns0__value' is boolean (true/false).
                - ns0__Occupancy_sensor: Examples: "Occupancy_sensor_1" through "Occupancy_sensor_5".
                - ns0__Smoke_sensor: Example: "Smoke_sensor_1".
            - ns0__Categorical_sensor (subclass of ns0__Sensor): 'ns0__value' is a string category.
                - ns0__Brightness_sensor: 'ns0__value' (string, e.g., "low"). Example: "Brightness_sensor_1".
            - ns0__Numeric_sensor (subclass of ns0__Sensor): 'ns0__value' is numeric.
                - ns0__Humidity_sensor: 'ns0__value' (number), 'ns0__unit' ("percent"). Example: "Humidity_sensor_1".
                - ns0__Temperature_sensor: 'ns0__value' (number), 'ns0__unit' ("C"). Example: "Temperature_sensor_1".
    """  # schema della casa intelligente

    graph_schema = """
    Node Identification:
    - Individual entities (devices, rooms, sensors like 'Lamp_1', 'Kitchen') are nodes, each having a unique 'uri' property (e.g., "http://swot.sisinflab.poliba.it/home#Lamp_1").
    - These individual nodes are typically labeled with `:Resource` and `:owl__NamedIndividual`.
    - Some individuals, like Rooms, might also directly have their specific type label (e.g., a node for 'Kitchen' might be labeled `:ns0__Room`).
    - For other individuals (especially devices and sensors), their specific ontological type (e.g., Light, Temperature_sensor) might not be a direct label on the instance node. Their type is often defined by relationships (like `rdf:type`) to class nodes or inferred from the properties they possess.
    - The unique identifier for an entity (e.g., "Lamp_1", "Living_room") is the fragment part of its 'uri' (the part after '#').
    - To match a specific named individual like "Lamp_1", query its 'uri' property (e.g., `WHERE n.uri ENDS WITH '#Lamp_1'`). Do NOT assume specific type labels like `:ns0__Light` are present on these individual device/sensor nodes when matching them by URI.

    Relationship Types:
    - (Individual Device/Sensor)-[:ns0__located_in]->(Individual Room, e.g., node labeled :ns0__Room).
    - (Individual Room, e.g., node labeled :ns0__Room)-[:ns0__contains]->(Individual Device/Sensor).
    """  # schema con nodi e relazioni

    example_schema = """
    Common Data Properties on Nodes (as per ontology mapping):
    Note: Data properties are also prefixed with 'ns0__'.
    - 'ns0__state': For ns0__Togglable_device instances, indicates if it's "on" or "off".
    - 'ns0__setting': For ns0__Settable_device instances, the current setting value.
    - 'ns0__unit': The unit for 'ns0__setting' or 'ns0__value' (e.g., "percent", "C").
    - 'ns0__value': For ns0__Sensor instances, the sensed value.

    Example Cypher Queries based on this schema:
    - To find if "Lamp_1" is on:
      MATCH (d) WHERE d.uri ENDS WITH "#Lamp_1" RETURN d.ns0__state AS state
    - To find the temperature setting of "Air_conditioner_1":
      MATCH (d) WHERE d.uri ENDS WITH "#Air_conditioner_1" RETURN d.ns0__setting AS setting, d.ns0__unit AS unit
    - To find what room "Lamp_1" is in:
      MATCH (d)-[:ns0__located_in]->(r:ns0__Room) WHERE d.uri ENDS WITH "#Lamp_1" RETURN r.uri AS room_uri
    - To list all devices in the "Kitchen":
      MATCH (r:ns0__Room)-[:ns0__contains]->(d) WHERE r.uri ENDS WITH "#Kitchen" RETURN d.uri AS device_uri, labels(d) AS types
    - To get the value of "Occupancy_sensor_3":
      MATCH (s) WHERE s.uri ENDS WITH "#Occupancy_sensor_3" RETURN s.ns0__value AS value
    """  # schema con regole ed alcuni esempi
    # schema selection
    chosen_schema = f"""
    {house_schema}

    {graph_schema}
    
    
    """  # schema selezionato {example_schema}

    ### QUERY PROMPT ###
    zero_prompt = f"""
    Generate the Cypher query that best answers the user query. 
    The graph schema is as follows: 
    {chosen_schema} 
    """

    few_prompt = f"""
    You are an expert Cypher query generator.
    Your task is to generate a Cypher query that retrieves information from a Neo4j graph database to answer the user's question.
    The graph schema is as follows:
    {chosen_schema}
    """

    instruction_prompt = f"""
    {few_prompt}

    Instructions:
    - Only output a valid Cypher query.
    - Do not include any explanations, comments, or markdown formatting like ```cypher ... ```.
    - Ensure the query returns data that can directly answer the user's question.
    - When querying a specific named individual (e.g., "Lamp 1", "Kitchen"), match it using its `uri` property (e.g., `WHERE individual.uri ENDS WITH '#Lamp_1'`). Do NOT add specific type labels like `:ns0__Light` or `:ns0__Device` to the individual node in the MATCH pattern, as these individuals are primarily labeled `:owl__NamedIndividual`.
    - However, if you are matching a Room individual, you CAN use the `:ns0__Room` label (e.g., `(r:ns0__Room)`).
    - Data properties (like `ns0__state`, `ns0__setting`, `ns0__value`) are directly on these individual nodes. Refer to the schema to know which conceptual type has which properties. The base URI for individuals is typically 'http://swot.sisinflab.poliba.it/home'.

    """

    complete_prompt = f"""
    {instruction_prompt}

    For example:
    User query: "Is Lamp 1 on?"
    Appropriate Cypher query: MATCH (d) WHERE d.uri ENDS WITH '#Lamp_1' RETURN d.ns0__state AS state

    User query: "What is the temperature in the kitchen?"
    Appropriate Cypher query: MATCH (s)-[:ns0__located_in]->(r:ns0__Room) WHERE s.uri ENDS WITH '#Temperature_sensor_1' AND r.uri ENDS WITH '#Kitchen' RETURN s.ns0__value AS value, s.ns0__unit AS unit
    (Alternative for "temperature in the kitchen" if a specific sensor isn't named: MATCH (r:ns0__Room)-[:ns0__contains]->(s:ns0__Temperature_sensor) WHERE r.uri ENDS WITH '#Kitchen' RETURN s.ns0__value, s.ns0__unit. This assumes Temperature_sensor_1 is a :ns0__Temperature_sensor, which might be a class node or an individual with that label if import was different. For now, prioritize matching individuals by URI if named.)

    User query: "Which devices are in the living room?"
    Appropriate Cypher query: MATCH (r:ns0__Room)-[:ns0__contains]->(d) WHERE r.uri ENDS WITH '#Living_room' RETURN d.uri AS device_uri
    """

    return complete_prompt


async def main() -> None:
    exit_commands = ["//", "bye", "close", "exit", "goodbye", "quit"]

    query_prompt = schema_initialization()
    answer_prompt = """
    You are a helpful assistant.
    Respond to the user in a conversational and natural way.
    Use the provided Cypher query and its output to answer the original user's question.
    Explain the information found in the database.
    If the query output is empty or does not seem to directly answer the question, state that the information could not be found or is inconclusive.
    Do not mention the Cypher query in your response unless it's crucial for explaining an error or ambiguity.
    Be concise and clear.
    """

    agent = LLM(sys_prompt=query_prompt)
    handler = Neo4jHandler(password="4Neo4Jay!")

    await aprint(agent_token + "System started: Ask about your smart house")  # messaggio

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
            await aprint(agent_token + "Querying the database...")
            # Inserire cursore animato ?
            cypher_query = await agent.write_cypher_query(user_query=user_query)

            # No query generated
            if not cypher_query:
                await aprint(
                    agent_token + "Can't generate a query from this prompt. Please, try to rewrite it")
                continue  # the While loop

            # Query successfully generated
            await aprint(agent_token + f"Cypher query:\n\t{cypher_query}")

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
                f"Generated Cypher query: \"{cypher_query}\"\n"
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
    asyncio.run(main())
