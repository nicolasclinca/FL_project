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
This graph represents a smart home environment, including rooms, devices, and sensors, along with their interrelations and states.

Nodes and their properties (node labels derived from OWL classes, with 'ns0' prefix):

- Label: ns0_Room
  Description: Represents a room in the house (e.g., Living_room, Bedroom).
  Properties: No direct properties.

- Label: ns0_Air_conditioner (subclass of ns0_Appliance and ns0_Settable_device)
  Description: An air conditioning device (e.g., Air_conditioner_1, Air_conditioner_2).
  Properties:
    - setting (integer): The set value for the air conditioner (e.g., temperature).
    - state (string): The current state of the air conditioner ('on' or 'off').
    - unit (string): The unit of measurement for the setting (e.g., 'C' for Celsius).

- Label: ns0_Appliance (subclass of ns0_Togglable_device)
  Description: A generic household appliance.
  Properties: No direct properties.

- Label: ns0_Boolean_sensor (subclass of ns0_Sensor)
  Description: A sensor that returns a boolean value.
  Properties: No direct properties.

- Label: ns0_Brightness_sensor (subclass of ns0_Categorical_sensor)
  Description: A brightness sensor (e.g., Brightness_sensor_1).
  Properties:
    - value (string): The brightness level (e.g., 'low').

- Label: ns0_Categorical_sensor (subclass of ns0_Sensor)
  Description: A sensor that returns a categorical value.
  Properties: No direct properties.

- Label: ns0_Coffee_machine (subclass of ns0_Appliance)
  Description: A coffee machine (e.g., Coffee_machine_1).
  Properties:
    - state (string): The current state of the coffee machine ('on' or 'off').

- Label: ns0_Device
  Description: A generic device.
  Properties: No direct properties.

- Label: ns0_Dimmable_light (subclass of ns0_Light and ns0_Settable_device)
  Description: A dimmable light (e.g., Ceiling_light_1, Lamp_1).
  Properties:
    - setting (integer): The light intensity level.
    - state (string): The light's state ('on' or 'off').
    - unit (string): The unit of measurement for the setting (e.g., 'percent').

- Label: ns0_Humidity_sensor (subclass of ns0_Numeric_sensor)
  Description: A humidity sensor (e.g., Humidity_sensor_1).
  Properties:
    - unit (string): The unit of measurement for humidity (e.g., 'percent').
    - value (integer): The humidity value.

- Label: ns0_Light (subclass of ns0_Togglable_device)
  Description: A generic lighting device (e.g., Ceiling_light_2).
  Properties: No direct properties.

- Label: ns0_Numeric_sensor (subclass of ns0_Sensor)
  Description: A sensor that returns a numeric value.
  Properties: No direct properties.

- Label: ns0_Occupancy_sensor (subclass of ns0_Boolean_sensor)
  Description: An occupancy sensor (e.g., Occupancy_sensor_1).
  Properties:
    - value (boolean): Indicates if the room is occupied (true/false).

- Label: ns0_Oven (subclass of ns0_Appliance and ns0_Settable_device)
  Description: An oven (e.g., Oven_1).
  Properties:
    - setting (integer): The set temperature for the oven.
    - state (string): The current state of the oven ('on' or 'off').
    - unit (string): The unit of measurement for the setting (e.g., 'C' for Celsius).

- Label: ns0_Robot_vacuum (subclass of ns0_Appliance)
  Description: A robot vacuum cleaner (e.g., Robot_vacuum_1).
  Properties:
    - state (string): The current state of the robot vacuum cleaner ('on' or 'off').

- Label: ns0_Sensor (subclass of ns0_Device)
  Description: A generic sensor.
  Properties: No direct properties.

- Label: ns0_Settable_device (subclass of ns0_Device)
  Description: A device with configurable settings.
  Properties: No direct properties.

- Label: ns0_Smoke_sensor (subclass of ns0_Boolean_sensor)
  Description: A smoke sensor (e.g., Smoke_sensor_1).
  Properties:
    - value (boolean): Indicates the presence of smoke (true/false).

- Label: ns0_Television (subclass of ns0_Appliance)
  Description: A television (e.g., Television_1).
  Properties:
    - state (string): The current state of the television ('on' or 'off').

- Label: ns0_Temperature_sensor (subclass of ns0_Numeric_sensor)
  Description: A temperature sensor (e.g., Temperature_sensor_1).
  Properties:
    - unit (string): The unit of measurement for temperature (e.g., 'C' for Celsius).
    - value (integer): The temperature value.

- Label: ns0_Togglable_device (subclass of ns0_Device)
  Description: A device that can be turned on or off.
  Properties: No direct properties.

- Label: ns0_Washing_machine (subclass of ns0_Appliance)
  Description: A washing machine (e.g., Washing_machine_1).
  Properties:
    - state (string): The current state of the washing machine ('on' or 'off').


Relationships and their properties (relationship types derived from OWL Object Properties, with 'ns0' prefix):

- Relationship Type: [:ns0_located_in]
  Description: Indicates that a device is located in a room.
  Origin: Nodes representing Devices (e.g., ns0_Air_conditioner, ns0_Brightness_sensor, ...)
  Destination: Nodes with label 'ns0_Room'.
  Properties: No direct properties on the relationship.

- Relationship Type: [:ns0_contains]
  Description: Indicates that a room contains a device.
  Origin: Nodes with label 'ns0_Room'.
  Destination: Nodes representing Devices (e.g., ns0_Air_conditioner, ns0_Brightness_sensor, ...)
  Properties: No direct properties on the relationship.
"""


EXAMPLE = """
Example Cypher Queries based on this schema:
- To find if "Lamp_1" is on:
  MATCH (d) WHERE d.uri ENDS WITH "#Lamp_1" RETURN d.ns0__state AS state
- To find the temperature setting of "Air_conditioner_1":
  MATCH (d) WHERE d.uri ENDS WITH "#Air_conditioner_1" RETURN d.ns0__setting AS setting, d.ns0__unit AS unit
- To find what room "Lamp_1" is in:
  MATCH (d)-[:ns0__located_in]->(r:ns0__Room) WHERE d.uri ENDS WITH "#Lamp_1" RETURN DISTINCT replace(toString(r.uri), "http://swot.sisinflab.poliba.it/home#", "home:") AS room;
- To list all devices in the "Kitchen":
  MATCH (r:ns0__Room)-[:ns0__contains]->(d) WHERE r.uri ENDS WITH "#Kitchen" RETURN d.uri AS device_uri, labels(d) AS types
- To get the value of "Occupancy_sensor_3":
  MATCH (s) WHERE s.uri ENDS WITH "#Occupancy_sensor_3" RETURN s.ns0__value AS value
"""


SYSTEM_PROMPT_CYPHER_GENERATION = f"""
Generate the Cypher query that best answers the user query. The graph schema is as follows: {NEO4J_GRAPH_SCHEMA}. 
Always output a valid Cypher query and nothing else.
"""

SYSTEM_PROMPT_RESPONSE_GENERATION = """
Respond to the user in a conversational fashion by explaining the Cypher query output:
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
                SYSTEM_PROMPT_RESPONSE_GENERATION,
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