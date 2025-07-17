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

Node labels:

- Label: ns0__Room
    Description: Represents a room in the house (e.g., ‘Living_room’, ‘Bedroom’, etc.). 
    A room is also described by the owl__NamedIndividual label.
    Properties: no direct properties.
    
- Label: owl__Class
    Description: Nodes representing the classes of the devices.
    
    Classes:
    - Device: Base label for all devices.
        - Togglable_device (subclass of Device): Has a 'ns0__state' property (string, e.g., "on", "off").
            - Light (subclass of Togglable_device): Represents all lights.
                - Dimmable_light (subclass of Light and Settable_device): Also has 'ns0__setting' (number, brightness percentage) and 'ns0__unit' ("percent"). 
            - Appliance (subclass of Togglable_device): Represents household appliances.
                - Air_conditioner (subclass of Appliance and Settable_device): Has 'ns0__state', 'ns0__setting' (number, temperature), and 'ns0__unit' ("C"). 
                - Coffee_machine (subclass of Appliance): Has 'ns0__state'.
                - Oven (subclass of Appliance and ns0__Settable_device): Has 'ns0__state', 'ns0__setting' (number, temperature), and 'ns0__unit' ("C").
                - Robot_vacuum (subclass of Appliance): Has 'ns0__state'. 
                - Television (subclass of Appliance): Has 'ns0__state'.
                - Washing_machine (subclass of Appliance): Has 'ns0__state'.
        - Settable_device (subclass of Device): Has 'ns0__setting' (varying type) and 'ns0__unit' (string) properties.
        - Sensor (subclass of Device): Has a 'ns0__value' property (varying type) and possibly 'ns0__unit'.
            - Boolean_sensor (subclass of Sensor): 'ns0__value' is boolean (true/false).
                - Occupancy_sensor
                - Smoke_sensor
            - Categorical_sensor (subclass of Sensor): 'ns0__value' is a string category.
                - Brightness_sensor: 'ns0__value' (string, e.g., "low").
            - Numeric_sensor (subclass of Sensor): 'ns0__value' is numeric.
                - Humidity_sensor: 'ns0__value' (number), 'ns0__unit' ("percent"). 
                - Temperature_sensor: 'ns0__value' (number), 'ns0__unit' ("C"). 
                
- Label: owl__NamedIndividual
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
    
    
- Label: owl__DatatypeProperty
    Description: each invidividual (marked with label owl__NamedIndividual), except rooms, can have one or more of these properties:
    - ns0__value (for Sensor instances, indicating the sensed value):
        - true
        - false
        - 20
        - 40
        - “low”
    - ns0__state (for Toggable_device instances):
        - “on”
        - “off”
    - ns0__unit (indicating the unit for 'ns0__setting' or 'ns0__value'):
        - “C”
        - “percent”
    - ns0__setting (for Settable_device instances):
        - “20”
        - “50”
        - “180”
        - “16”
        
- Label: owl__ObjectProperty
    Description: represents connections between entities, in particular between rooms and individual devices.
    - ns0__located_in: connects Device/Sensor instance -> ns0__Room instance. Represents where a device/sensor is located.
    - ns0__contains: connects ns0__Room instance -> Device/Sensor instance. Represents what a room contains.
    
    
- Properties of Nodes:
  - For all instance nodes:
      - uri (String): This is the **CRUCIAL AND ONLY UNIQUE IDENTIFIER** for every individual instance (e.g., "http://swot.sisinflab.poliba.it/home#Air_conditioner_1").
      - **ABSOLUTELY CRITICAL RULE FOR INSTANCE IDENTIFICATION:**
          * **Individual instances (devices, sensors, rooms) in the graph **DO NOT** have a 'name' property.**
          * Their specific identifier is **ALWAYS** embedded in the `uri` property.
          * All individuals (except rooms) URIs end with `_{number}` (e.g., `Air_conditioner_1`, `Temperature_sensor_2`, `Living_room`). When a user refers to a specific instance by its common name (e.g., "Lamp 1", "Living Room"), you **MUST** construct the full `uri` using this pattern.
  - In MATCH clause, you must use one of the node labels: ns0__Room, owl__NamedIndividual, owl__Class.
  
      
- Rules for Cypher Query Generation
  - **WHEN QUERYING FOR A SPECIFIC INDIVIDUAL INSTANCE (e.g., "Lamp 1", "Kitchen"), FOLLOW THESE STEPS RIGOROUSLY:**
    1.  **DO NOT** attempt to use a 'name' property. It does not exist.
    2.  Construct the full `uri` for the instance by combining `http://swot.sisinflab.poliba.it/home#` with the specific instance identifier (e.g., `Lamp_1`). Remember this identifier always ends with `_{number}`.
    3.  Use a `WHERE n.uri = "full_instance_uri"` clause for precise matching.
  - Use `WHERE` with eventually `CONTAINS` clauses for filtering properties or URIs.
  - Use `RETURN` to specify the desired output.
  - To count entities, use `COUNT()`.
  - To get distinct values, use `DISTINCT`.
  - Do not use classes to generate queries.
"""

ALTRO = """
=== RELATIONSHIP TYPES ===
- (Resource)-[:rdf__rest {no properties}]->(Resource)
- (Resource)-[:rdf__first {no properties}]->(Resource:owl__Class)
- (Resource:owl__NamedIndividual:ns0__Room)-[:ns0__contains {no properties}]->(Resource:owl__NamedIndividual)
- (Resource:owl__NamedIndividual)-[:rdf__type {no properties}]->(Resource:owl__Class)
- (Resource:owl__Class)-[:rdfs__subClassOf {no properties}]->(Resource:owl__Class)
- (Resource:owl__NamedIndividual)-[:ns0__located_in {no properties}]->(Resource:owl__NamedIndividual:ns0__Room)
- (Resource:owl__Class)-[:owl__intersectionOf {no properties}]->(Resource)
- The Resource label is optional.
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
    """Gestisce le interazioni"""
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