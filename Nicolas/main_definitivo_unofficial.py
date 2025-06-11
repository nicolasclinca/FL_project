import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint             # versioni asincrone di input e print
from neo4j import AsyncDriver, AsyncGraphDatabase


# fmt: off
USER_PROMPT  = "[User]  "
AGENT_PROMPT = "[Agent] "
# fmt: on


# --- Configurazione --- #
# Dettagli per la connessione a Neo4j (modificare secondo necessità)
NEO4J_URI = "bolt://localhost:7687"  # URI del server Neo4j
NEO4J_USER = "neo4j"                 # utente Neo4j
NEO4J_PASSWORD = "Passworddineo4j1!"          # password Neo4j 

# Modello LLM da utilizzare con Ollama
LLM_MODEL = "llama3.1"

# !!! IMPORTANTE !!!
# Schema del grafo Neo4j derivato dall'ontologia 'home.ttl'.
# Questo schema è cruciale per l'LLM per generare query Cypher corrette.
NEO4J_GRAPH_SCHEMA = """
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

Common Data Properties on Nodes (as per ontology mapping):
Note: Data properties are also prefixed with 'ns0__'.
- 'ns0__state': For ns0__Togglable_device instances, indicates if it's "on" or "off".
- 'ns0__setting': For ns0__Settable_device instances, the current setting value.
- 'ns0__unit': The unit for 'ns0__setting' or 'ns0__value' (e.g., "percent", "C").
- 'ns0__value': For ns0__Sensor instances, the sensed value (e.g., "true" and "false" indicating presence or not, "20", "40", "low").

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
"""

# Prompt di sistema per la generazione della query Cypher
SYSTEM_PROMPT_CYPHER_GENERATION = f"""
You are an expert Cypher query generator.
Your task is to generate a Cypher query that retrieves information from a Neo4j graph database to answer the user's question.
The graph schema is as follows:
{NEO4J_GRAPH_SCHEMA}

Instructions:
- Only output a valid Cypher query.
- Do not include any explanations, comments, or markdown formatting like ```cypher ... ```.
- Ensure the query returns data that can directly answer the user's question.
- When querying a specific named individual (e.g., "Lamp 1", "Kitchen"), match it using its `uri` property (e.g., `WHERE individual.uri ENDS WITH '#Lamp_1'`). Do NOT add specific type labels like `:ns0__Light` or `:ns0__Device` to the individual node in the MATCH pattern, as these individuals are primarily labeled `:owl__NamedIndividual`.
- However, if you are matching a Room individual, you CAN use the `:ns0__Room` label (e.g., `(r:ns0__Room)`).
- Data properties (like `ns0__state`, `ns0__setting`, `ns0__value`) are directly on these individual nodes. Refer to the schema to know which conceptual type has which properties. The base URI for individuals is typically 'http://swot.sisinflab.poliba.it/home'.

For example:
User query: "Is Lamp 1 on?"
Appropriate Cypher query: MATCH (d) WHERE d.uri ENDS WITH '#Lamp_1' RETURN d.ns0__state AS state

User query: "What is the temperature in the kitchen?"
Appropriate Cypher query: MATCH (s)-[:ns0__located_in]->(r:ns0__Room) WHERE s.uri ENDS WITH '#Temperature_sensor_1' AND r.uri ENDS WITH '#Kitchen' RETURN s.ns0__value AS value, s.ns0__unit AS unit
(Alternative for "temperature in the kitchen" if a specific sensor isn't named: MATCH (r:ns0__Room)-[:ns0__contains]->(s:ns0__Temperature_sensor) WHERE r.uri ENDS WITH '#Kitchen' RETURN s.ns0__value, s.ns0__unit. This assumes Temperature_sensor_1 is a :ns0__Temperature_sensor, which might be a class node or an individual with that label if import was different. For now, prioritize matching individuals by URI if named.)

User query: "Which devices are in the living room?"
Appropriate Cypher query: MATCH (r:ns0__Room)-[:ns0__contains]->(d) WHERE r.uri ENDS WITH '#Living_room' RETURN d.uri AS device_uri
"""
# Definition for SYSTEM_PROMPT_RESPONSE_GENERATION
SYSTEM_PROMPT_RESPONSE_GENERATION = """
You are a helpful assistant.
Respond to the user in a conversational and natural way.
Use the provided Cypher query and its output to answer the original user's question.
Explain the information found in the database.
If the query output is empty or does not seem to directly answer the question, state that the information could not be found or is inconclusive.
Do not mention the Cypher query in your response unless it's crucial for explaining an error or ambiguity.
Be concise and clear.
"""


class Neo4jHandler:
    """Gestisce le interazioni con il database Neo4j."""
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password)) 

    async def close(self) -> None:
        """Chiude la connessione al driver Neo4j."""
        await self._driver.close()
        # await aprint(AGENT_PROMPT + "Neo4j connection closed.") # Optional: for debugging

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
            await aprint(AGENT_PROMPT + f"Neo4j query execution error: {e}")
            raise


class LLM:
    """Gestisce le interazioni con il modello di linguaggio Ollama."""
    def __init__(self, model: str = LLM_MODEL) -> None:
        self._client = ol.AsyncClient(host="localhost")
        self._model = model
        # aprint(AGENT_PROMPT + f"LLM initialized with model: {self._model}.") # Optional: for debugging

    async def get_response_stream(self, system_prompt: str, user_query: str) -> AsyncIterator[str]:
        messages = [
            ol.Message(role="system", content=system_prompt),
            ol.Message(role="user", content=user_query),
        ]
        try:
            async for chunk in await self._client.chat(self._model, messages, stream=True):
                if chunk.get("message"):
                    yield chunk["message"]["content"]
                elif chunk.get("done") and chunk.get("error"):
                    await aprint(AGENT_PROMPT + f"Ollama API error: {chunk['error']}")
                    break
        except Exception as e:
            await aprint(AGENT_PROMPT + f"LLM streaming error: {e}")
            yield ""

    async def get_response_full(self, system_prompt: str, user_query: str) -> str:
        response_parts = []
        try:
            async for part_stream in self.get_response_stream(system_prompt, user_query):
                 response_parts.append(part_stream)
            full_response = "".join(response_parts).strip()
            if "```cypher" in full_response:
                full_response = full_response.split("```cypher")[1].split("```")[0].strip()
            elif "```" in full_response:
                 full_response = full_response.replace("```", "").strip()
            return full_response
        except Exception as e:
            await aprint(AGENT_PROMPT + f"LLM full response error: {e}")
            return ""


async def print_agent_response_stream(response_stream: AsyncIterator[str]) -> None:
    await aprint(AGENT_PROMPT, end="")
    async for chunk in response_stream:
        await aprint(chunk, end="", flush=True)
    await aprint()


async def user_input() -> str:
    return await ainput(USER_PROMPT)


async def main_rag_loop() -> None:
    llm_agent = LLM(model=LLM_MODEL)
    neo4j_handler = Neo4jHandler(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    await aprint(AGENT_PROMPT + "Sistema RAG avviato. Chiedimi qualcosa sulla casa intelligente!")
    try:
        while True:
            original_user_query = await user_input()
            if not original_user_query:
                continue
            if original_user_query.lower() in ["exit", "quit", "goodbye", "esci", "ciao"]:
                await aprint(AGENT_PROMPT + "Ok, alla prossima!")
                break

            await aprint(AGENT_PROMPT + "Sto pensando a come interrogare la base di conoscenza...")
            cypher_query = await llm_agent.get_response_full(
                SYSTEM_PROMPT_CYPHER_GENERATION,
                original_user_query
            )

            if not cypher_query:
                await aprint(AGENT_PROMPT + "Non sono riuscito a generare una query Cypher per la tua domanda. Prova a riformularla.")
                continue
            await aprint(AGENT_PROMPT + f"Query Cypher generata: {cypher_query}")

            query_results = []
            try:
                query_results = await neo4j_handler.execute_query(cypher_query)
                await aprint(AGENT_PROMPT + f"Risultati della query: {query_results}")
            except Exception as e:
                await aprint(AGENT_PROMPT + "Si è verificato un errore durante l'esecuzione della query su Neo4j. Potrebbe essere malformata o i dati non sono come previsto.")
                continue

            await aprint(AGENT_PROMPT + "Sto formulando una risposta...")
            response_context_for_llm = (
                f"Original user query: \"{original_user_query}\"\n"
                f"Generated Cypher query: \"{cypher_query}\"\n"
                f"Result from Neo4j: {query_results}"
            )
            response_stream = llm_agent.get_response_stream(
                SYSTEM_PROMPT_RESPONSE_GENERATION, # Defined in your previous full script
                response_context_for_llm
            )
            await print_agent_response_stream(response_stream)

    except asyncio.CancelledError:
        await aprint("\n" + AGENT_PROMPT + "Chat interrotta. Arrivederci!")
    except Exception as e:
        await aprint(AGENT_PROMPT + f"Si è verificato un errore inaspettato nel loop principale: {e}")
    finally:
        await neo4j_handler.close()
        await aprint(AGENT_PROMPT + "Programma terminato.")


if __name__ == "__main__":
    try:
        asyncio.run(main_rag_loop())
    except KeyboardInterrupt:
        pass