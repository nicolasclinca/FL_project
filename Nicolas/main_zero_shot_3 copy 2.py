import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint             # versioni asincrone di input e print
from neo4j import AsyncDriver, AsyncGraphDatabase


# fmt: off
USER_PROMPT  = "[User] > "
AGENT_PROMPT = "[Agent] > "
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

Node labels:

- Label: Room
    Description: Represents a room in the house (e.g., ‘Living_room’, ‘Bedroom’, etc.). 
    A room is also described by the NamedIndividual label.
    Properties: no direct properties.
    
- Label: Class
    Description: Nodes representing the classes of the devices.
    
    Classes:
    These are the specific classes from your domain, which are represented as separate 'Class' nodes in the graph. 
    The URI of these class nodes will be like "http://swot.sisinflab.poliba.it/home#Air_conditioner".
    - Device
    - Appliance (subclass of Device) 
    - Togglable_device (subclass of Device) 
    - Settable_device (subclass of Device) 
    - Sensor (subclass of Device) 
    - Light (subclass of Togglable_device) 
    - Dimmable_light (subclass of Light and Settable_device) 
    - Air_conditioner (subclass of Appliance and Settable_device)
    - Coffee_machine (subclass of Appliance) 
    - Oven (subclass of Appliance and Settable_device) 
    - Robot_vacuum (subclass of Appliance)
    - Television (subclass of Appliance)
    - Washing_machine (subclass of Appliance) 
    - Boolean_sensor (subclass of Sensor) 
    - Categorical_sensor (subclass of Sensor) 
    - Numeric_sensor (subclass of Sensor) 
    - Brightness_sensor (subclass of Categorical_sensor) 
    - Humidity_sensor (subclass of Numeric_sensor) 
    - Occupancy_sensor (subclass of Boolean_sensor) 
    - Smoke_sensor (subclass of Boolean_sensor) 
    - Temperature_sensor (subclass of Numeric_sensor) 
                    
- Label: NamedIndividual
    Description: nodes representing individual devices (e.g., ‘Air_conditioner_1’, ‘Humidity_sensor_1’, etc.). This label describe the rooms also.  
    All specific individual instances (e.g., devices, sensors, except for rooms) in the graph have URIs that end with an underscore followed by a number
    (e.g., `Air_conditioner_1`, `Temperature_sensor_2`, `Living_room`).
    Individuals with number of devices:
    - Air_conditioner (2)
    - Bathroom
    - Bedroom
    - Brightness_sensor (1)
    - Ceiling_light (5)
    - Coffee_machine (1)
    - Humidity_sensor (1)
    - Kitchen
    - Lamp (3)
    - Living_room
    - Occupancy_sensor (5)
    - Oven (1)
    - Robot_vacuum (1)
    - Smoke_sensor (1)
    - Study
    - Television (1)
    - Temperature_sensor (1)
    - Washing_machine (1)
    
    
- Label: DatatypeProperty
    Description: each invidividual (marked with label NamedIndividual), except rooms, can have one or more of these properties:
    - value (for Sensor instances, indicating the sensed value):
        - true
        - false
        - 20
        - 40
        - “low”
    - state (for Toggable_device instances):
        - “on”
        - “off”
    - unit (indicating the unit for 'setting' or 'value'):
        - “C”
        - “percent”
    - setting (for Settable_device instances):
        - “20”
        - “50”
        - “180”
        - “16”
        
- Label: ObjectProperty
    Description: represents connections between entities, in particular between rooms and individual devices.
    - located_in: connects Device/Sensor instance -> Room instance. Represents where a device/sensor is located.
    - contains: connects Room instance -> Device/Sensor instance. Represents what a room contains.


- RELATIONSHIP TYPES 
    - ()-[:rest]->()
    - ()-[:first]->(Resource:Class)
    - (Resource:NamedIndividual:Room)-[:contains]->(Resource:NamedIndividual)
    - (Resource:NamedIndividual)-[:type]->(Resource:Class)
    - (Resource:Class)-[:subClassOf]->(Resource:Class)
    - (Resource:NamedIndividual)-[:located_in]->(Resource:NamedIndividual:Room)
    - (Resource:Class)-[:intersectionOf]->(Resource)
    - The Resource label is optional.
    
          
- Rules for Cypher Query Generation
  - **WHEN QUERYING FOR A SPECIFIC INDIVIDUAL INSTANCE (e.g., "Lamp 1", "Kitchen"), FOLLOW THESE STEPS RIGOROUSLY:**
    1.  **DO NOT** attempt to use a 'name' property. It does not exist.
    2. All individuals (except rooms) URIs end with `_{number}` (e.g., `Air_conditioner_1`, `Temperature_sensor_2`, `Living_room`). 
        When a user refers to a specific instance by its common name (e.g., "Lamp 1", "Living Room"), you **MUST** construct the full `uri` using this pattern.
    3.  Construct the full `uri` for the instance by combining `http://swot.sisinflab.poliba.it/home#` with the specific instance identifier (e.g., `Lamp_1`). Remember this identifier always ends with `_{number}`.
    4.  Use a `WHERE n.uri = "full_instance_uri"` clause for precise matching.
  - In MATCH clause, you must use one of the node labels: Room, NamedIndividual, Class
  - Use `WHERE` with eventually `CONTAINS` clauses for filtering properties or URIs.
  - Use `RETURN` to specify the desired output.
  - To count entities, use `COUNT()`.
  - To get distinct values, use `DISTINCT`.
  - Do not use classes to generate queries.
"""

ALTRO = """

"""

EXAMPLE = """
Example Cypher Queries based on this schema:
- To find if "Lamp_1" is on:
  MATCH (d) WHERE d.uri ENDS WITH "Lamp_1" RETURN d.state AS state
- To find the temperature setting of "Air_conditioner_1":
  MATCH (d) WHERE d.uri ENDS WITH "Air_conditioner_1" RETURN d.setting AS setting, d.unit AS unit
- To find what room "Lamp_1" is in:
  MATCH (d)-[:located_in]->(r:Room) WHERE d.uri ENDS WITH "#Lamp_1" RETURN r.uri AS room_uri
- To list all devices in the "Kitchen":
  MATCH (r:Room)-[:contains]->(d) WHERE r.uri ENDS WITH "#Kitchen" RETURN d.uri AS device_uri, labels(d) AS types
- To get the value of "Occupancy_sensor_3":
  MATCH (s) WHERE s.uri ENDS WITH "Occupancy_sensor_3" RETURN s.value AS value
"""

SYSTEM_PROMPT_CYPHER_GENERATION = f"""
Generate the Cypher query that best answers the user query. The graph schema is as follows: {NEO4J_GRAPH_SCHEMA}+{EXAMPLE}. 
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
    await aprint(AGENT_PROMPT + "Sistema RAG avviato. Chiedimi qualcosa...")
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