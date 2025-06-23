# (Keep previous imports and constants like USER_PROMPT, AGENT_PROMPT, NEO4J_URI, etc.)
import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint  # versioni asincrone di input e print
from neo4j import AsyncDriver, AsyncGraphDatabase

# fmt: off
user_token = "[User]  > "
agent_token = "[Agent] > "
# fmt: on


### CONFIGURATION ###
bolt_port = "bolt://localhost:7687"
username = "neo4j"
pswd = "4Neo4Jay!"  # Esempio: password Neo4j (usare credenziali sicure)

# Modello LLM da utilizzare con Ollama
LLM_MODEL = "llama3.1"

### SCHEMA ###

separator = "\n\n"

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

"""  # schema selezionato

### QUERY PROMPT ###
zero_prompt = f"""
Generate the Cypher query that best answers the user query. 
The graph schema is as follows: 
{chosen_schema} 
Always output a valid Cypher query and nothing else.
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

chosen_prompt = complete_prompt

# Definition for SYSTEM_PROMPT_RESPONSE_GENERATION
sys_answer_prompt = """
You are a helpful assistant.
Respond to the user in a conversational and natural way.
Use the provided Cypher query and its output to answer the original user's question.
Explain the information found in the database.
If the query output is empty or does not seem to directly answer the question, state that the information could not be found or is inconclusive.
Do not mention the Cypher query in your response unless it's crucial for explaining an error or ambiguity.
Be concise and clear.
"""


# (The rest of your main.py script: Neo4jHandler class, LLM class, helper functions, main_rag_loop)
# ... (make sure Neo4jHandler, LLM, print_agent_response_stream,
# user_input, main_rag_loop are present as in the previous version)

# Example of how the classes and main loop would remain (simplified, ensure you have the full previous code):
class Neo4jHandler:
    """Handle interactions with the database Neo4j."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))  #
        # aprint(AGENT_PROMPT + "Neo4jHandler initialized.") # Optional: for debugging

    async def close(self) -> None:
        """
        Close the connection to the driver Neo4j.
        """
        await self._driver.close()
        # await aprint(AGENT_PROMPT + "Neo4j connection closed.")

    async def execute_query(self, query: str, params: dict | None = None) -> list[dict]:
        """
        Esegue una query Cypher e restituisce i risultati.
        """
        params = params or {}
        try:
            async with self._driver.session() as session:
                result = await session.run(query, params)
                return [record.data() async for record in result]
        except Exception as e:
            await aprint(agent_token + f"Neo4j query execution error: {e}")
            raise


class LLM:
    """Gestisce le interazioni con il modello di linguaggio Ollama."""

    def __init__(self, model: str = LLM_MODEL) -> None:
        self._client = ol.AsyncClient(host="localhost")
        self._model = model
        # aprint(AGENT_PROMPT + f"LLM initialized with model: {self._model}.")

    async def get_response_stream(self, system_prompt: str, user_query: str) -> AsyncIterator[str]:
        """Crea la risposta leggendo domanda e prompt di sistema"""
        messages = [
            ol.Message(role="system", content=system_prompt),
            ol.Message(role="user", content=user_query),
        ]
        try:
            async for chunk in await self._client.chat(self._model, messages, stream=True):
                # questo blocco è diverso da quello di B, ma sembra equivalente
                if chunk.get("message"):
                    yield chunk["message"]["content"]  # restituisce la risposta a pezzi
                elif chunk.get("done") and chunk.get("error"):
                    await aprint(agent_token + f"Ollama API error: {chunk['error']}")
                    break
        except Exception as e:
            await aprint(agent_token + f"LLM streaming error: {e}")
            yield ""

    async def get_response_full(self, system_prompt: str, user_query: str) -> str:
        """
        Crea la query Cypher in base alla domanda
        """
        response_parts = []
        try:
            async for part_stream in self.get_response_stream(system_prompt, user_query):
                # legge la risposta a pezzi e li concatena in response_parts [lista]
                response_parts.append(part_stream)
            full_response = "".join(response_parts).strip()  # diventa [Literal String]
            if "```cypher" in full_response:  # individua l'inizio del blocco di codice per la query
                # prende quel che c'è dopo ```cypher e prima di ```, cioè la query
                full_response = full_response.split("```cypher")[1].split("```")[0].strip()
            elif "```" in full_response:
                full_response = full_response.replace("```", "").strip()  # elimina altri blocchi di codice
            return full_response  # restituisce la rispsota, ossia la query Cypher formata
        except Exception as e:
            await aprint(agent_token + f"LLM full response error: {e}")
            return ""


async def gemini_print_response(response_stream: AsyncIterator[str]) -> None:
    await aprint(agent_token, end="")
    async for chunk in response_stream:  # lo prende da get_response_stream(), non da full
        await aprint(chunk, end="", flush=True)
    await aprint()


async def user_input() -> str:
    # identica tra B e G
    return await ainput(user_token)


async def main_rag_loop() -> None:
    llm_agent = LLM(model=LLM_MODEL)  # crea il modello LLM
    neo4j_handler = Neo4jHandler(bolt_port, username, pswd)  # crea l'interfaccia con neo4j
    await aprint(agent_token + "RAG System started: Ask about your smart house")  # messaggio
    try:
        while True:
            original_user_query = await user_input()  # legge la query utente
            if not original_user_query:
                continue  # se non c'è niente riprova
            if original_user_query.lower() in ["/exit", "/quit", "/goodbye", "/bye", ]:
                await aprint(agent_token + "Bye Bye!")  # comandi di chiusura
                break  # esce saltanto tutto quel che c'è dopo

            await aprint(agent_token + "Querying the database...")  # legge
            cypher_query = await llm_agent.get_response_full(
                chosen_prompt,
                original_user_query
            )  # crea la query cypher, da get_response_full

            if not cypher_query:  # se manca la query, dà errore
                await aprint(
                    agent_token + "Can't generate a query from this prompt. Please, try to rewrite it")
                continue  # nuovo tentativo
            # se invece funziona, stampa la query immessa
            await aprint(agent_token + f"Cypher query:\n{cypher_query}")

            query_results = []
            try:
                query_results = await neo4j_handler.execute_query(cypher_query)  # lancia la query sul serio
                await aprint(agent_token + f"Query results: {query_results}")  # stampa la risposta Cypher
            except Exception as e:
                await aprint(
                    agent_token + "Error occurred: "
                                  "the query could be incorrect or data could be not well-formatted.")
                continue

            await aprint(agent_token + "Formuling the answer...")  # elabora la risposta

            response_context_for_llm = (
                f"Original user query: \"{original_user_query}\"\n"
                f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )  # contesto per scrivere la risposta

            response_stream = llm_agent.get_response_stream(
                system_prompt=sys_answer_prompt,
                user_query=response_context_for_llm
            )
            await gemini_print_response(response_stream)

    except asyncio.CancelledError:
        await aprint("\n" + agent_token + "Chat interrupted. Goodbye!")
    except Exception as e:
        await aprint(agent_token + f"An error occurred in the main loop: {e}")
    finally:
        await neo4j_handler.close()
        await aprint(agent_token + "Program concluded.")


if __name__ == "__main__":
    try:
        asyncio.run(main_rag_loop())
    except KeyboardInterrupt:
        pass
