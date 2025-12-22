import asyncio
from collections.abc import AsyncIterator
from collections import defaultdict

import ollama as ol
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase, exceptions

# --- CONFIGURAZIONE ---
# Inserisci qui i dati di connessione per il tuo database Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "4Neo4Jay!"

# Modello Ollama da utilizzare
OLLAMA_MODEL = "llama3.1"  # codellama:7b oppure llama3.1

# Prompt per l'interfaccia utente
USER_PROMPT = "[User] > "
AGENT_PROMPT = "[Agent] > "

FEW_SHOT_EXAMPLES = [
    {
        "user_query": "Which people live in Paris?",
        "cypher_query": "MATCH (p:Person)-[:LIVES_IN]->(c:City {name: 'Paris'}) RETURN p.name"
    },
    {
        "user_query": "What is the company that Lukas is working for?",
        "cypher_query": "MATCH (p:Person {name: 'Lukas'})-[:WORKS_IN]->(c:Company) RETURN p.name"
    },
    {
        "user_query": "What is the email address of the user with username ‘alice91’?",
        "cypher_query": "MATCH (u:User {username: 'alice91'}) RETURN u.email"
    },
    {
        "user_query": "Show me all articles written by the author ‘Mario Rossi’.",
        "cypher_query": "MATCH (a:Author {name: 'Mario Rossi'})-[:WROTE]->(p:Post) RETURN p.title, p.publicationDate"
    }
]


class LLM:
    """
    Un wrapper semplificato per il client asincrono di Ollama.
    """

    def __init__(self, model: str = OLLAMA_MODEL, system: str = "You are a helpful assistant."):
        self.system = system
        self._client = ol.AsyncClient()
        self._model = model

    async def chat(self, user_query: str) -> str:
        """
        Invia una richiesta all'LLM e restituisce la risposta completa come stringa.
        """
        messages = [
            ol.Message(role="system", content=self.system),
            ol.Message(role="user", content=user_query),
        ]
        response = await self._client.chat(self._model, messages)
        return response['message']['content']

    async def stream_chat(self, user_query: str) -> AsyncIterator[str]:
        """
        Invia una richiesta all'LLM e restituisce la risposta in streaming.
        """
        messages = [
            ol.Message(role="system", content=self.system),
            ol.Message(role="user", content=user_query),
        ]
        async for chunk in await self._client.chat(self._model, messages, stream=True, options={"temperature": 0}):
            yield chunk['message']['content']


async def get_neo4j_schema(driver) -> str:  # DEPRECATED
    """
    Recupera il "vocabolario" del grafo (solo elementi in uso)
    utilizzando una singola ed efficiente query con la sintassi aggiornata.
    """
    print("[System] Retrieving in-use graph vocabulary...")

    schema_query = """
        CALL () {
            MATCH (n)
            WHERE NOT '_GraphConfig' IN labels(n)
            UNWIND labels(n) AS label
            RETURN COLLECT(DISTINCT label) AS labels
        }
        CALL () {
            MATCH ()-[r]->()
            RETURN COLLECT(DISTINCT type(r)) AS relTypes
        }
        CALL () {
            MATCH (n)
            WHERE NOT '_GraphConfig' IN labels(n)
            UNWIND keys(n) AS key
            RETURN COLLECT(DISTINCT key) AS propKeys
        }

        CALL () { 
            MATCH (n)-[r]->(m) 
            WITH DISTINCT labels(n) AS fromNodeLabels, type(r) AS relationshipType, labels(m) AS toNodeLabels
            RETURN collect({
                `from`: fromNodeLabels,
                `type`: relationshipType,
                `to`: toNodeLabels
            }) AS relationships
        }

        RETURN labels, relTypes, propKeys, relationships
        """

    try:
        async with driver.session() as session:
            result = await session.run(schema_query)
            record = await result.single()

            if not record:
                return "Graph is empty or schema could not be retrieved."

            all_labels = record.get("labels", [])
            rel_types = record.get("relTypes", [])
            prop_keys = record.get("propKeys", [])
            relationships = record.get("relationships", [])

            # PASSO 2: Recupera gli individui per ogni etichetta
            LABELS_TO_EXCLUDE = {'_GraphConfig', 'Resource'}
            labels = [l for l in all_labels if l not in LABELS_TO_EXCLUDE]
            individuals_by_label = {}
            for label in labels:
                individual_query = f"""
                MATCH (n:`{label}`)
                WHERE n.uri IS NOT NULL AND NOT n.uri STARTS WITH 'bnode://'
                WITH n.name AS individual
                RETURN COLLECT(individual) AS individuals
                """

                individual_result = await session.run(individual_query)
                record = await individual_result.single()
                if record and record["individuals"]:
                    individuals_by_label[label] = record["individuals"]

            # PASSO 3: Formatta tutto in un unico contesto per l'LLM
            formatted_context = f"""
                This is the schema of the graph database.

                ### Node Labels
                The graph contains the following node labels:
                `{all_labels}`

                ### Relationship Types
                The graph contains the following relationship types:
                `{rel_types}`


                ### Property Keys
                Nodes and relationships can have the following properties:
                `{prop_keys}`

                ** Relationships between nodes:**
                {relationships}


                ### Example Individuals by Label
                Here are some example individuals (values of the 'name' property) for some of the node labels:
            """
            for label, individuals in individuals_by_label.items():
                formatted_context += f"- `{label}`: {individuals}\n"

            return formatted_context.strip()


    except Exception as e:
        print(f"\n[FATAL ERROR] An error occurred while fetching the schema: {e}")
        return ""


async def genera_schema_strutturato(driver) -> str:
    etichette_da_ignorare = {"_GraphConfig", "Resource", "Ontology"}
    proprieta_identificativa = 'name'
    limite = 100
    schema_finale = []

    async with driver.session() as session:
        # --- 1. Ottenere Nodi e le loro Proprietà ---
        try:
            # Usiamo un defaultdict per raggruppare facilmente le proprietà per etichetta
            nodi_e_proprieta = defaultdict(set)
            risultati_nodi = await session.run("CALL db.schema.nodeTypeProperties()")

            async for record in risultati_nodi:
                for etichetta in record["nodeLabels"]:
                    nodi_e_proprieta[etichetta].add(record["propertyName"])
        except Exception as e:
            schema_finale.append(f"## Errore nel recupero dello schema dei nodi: {e}")

        etichette_valide = sorted([l for l in nodi_e_proprieta.keys() if l not in etichette_da_ignorare])

        # Formattazione della sezione dei nodi
        schema_nodi = [
            "## Schema delle Proprietà dei Nodi",
            "Di seguito sono elencati i nodi e le rispettive proprietà.\n"
        ]
        # Ordina le etichette per un output consistente
        for etichetta in sorted(nodi_e_proprieta.keys()):
            if etichetta in etichette_da_ignorare:
                continue
            proprieta = sorted(list(nodi_e_proprieta[etichetta]))
            schema_nodi.append(f"- Nodo con etichetta `:{etichetta}` ha le proprietà: `{proprieta}`.")

        schema_finale.append("\n".join(schema_nodi))

        # ---  2. Campionare Istanze per Ogni Etichetta ---
        try:
            esempi_per_etichetta:dict = {}
            for etichetta in etichette_valide:
                query_esempio = (
                    f"MATCH (n:`{etichetta}`) "
                    f"WHERE n.{proprieta_identificativa} IS NOT NULL "
                    f"RETURN n.{proprieta_identificativa} AS instance_name LIMIT {limite}"
                )
                risultati_esempi = await session.run(query_esempio)
                esempi = [record["instance_name"] async for record in risultati_esempi]
                if esempi:
                    esempi_per_etichetta[etichetta] = esempi

            # --- Formattazione Sezione 2: Esempi di Istanze ---
            if esempi_per_etichetta:
                schema_esempi = ["\n## Esempi di Istanze per Etichetta",
                                 "Per darti un'idea dei dati reali, ecco alcuni nomi di istanze per etichetta.\n"]
                for etichetta, esempi in esempi_per_etichetta.items():
                    schema_esempi.append(f"- Esempi per `:{etichetta}`: `{esempi}`")
                schema_finale.append("\n".join(schema_esempi))

        except Exception as e:
            schema_finale.append(f"## Errore nel recupero degli esempi di istanze: {e}")

        # --- 3. Ottenere i Pattern delle Relazioni ---
        try:
            # Usiamo un set per memorizzare solo i pattern di relazione unici
            relazioni_uniche = set()
            risultati_relazioni = await session.run("CALL db.schema.visualization()")

            async for record in risultati_relazioni:
                # La query restituisce una lista di oggetti relazione
                for relazione in record["relationships"]:
                    nodo_partenza = relazione.start_node
                    nodo_arrivo = relazione.end_node
                    tipo_relazione = relazione.type

                    # Filtra via le etichette da ignorare da entrambi i nodi della relazione.
                    labels_partenza_filtrate = [l for l in nodo_partenza.labels if l not in etichette_da_ignorare]
                    labels_arrivo_filtrate = [l for l in nodo_arrivo.labels if l not in etichette_da_ignorare]

                    # Se dopo il filtro non rimangono etichette, non aggiungere la relazione allo schema (improbabile ma sicuro).
                    if not labels_partenza_filtrate or not labels_arrivo_filtrate:
                        continue

                    # Prendi la prima etichetta "buona" rimasta.
                    etichetta_partenza = labels_partenza_filtrate[0]
                    etichetta_arrivo = labels_arrivo_filtrate[0]

                    pattern = f"(:{etichetta_partenza})-[:{tipo_relazione}]->(:{etichetta_arrivo})"
                    relazioni_uniche.add(pattern)

            # Formattazione della sezione delle relazioni
            schema_relazioni = [
                "\n## Schema delle Relazioni",
                "Di seguito sono elencati i pattern di relazione esistenti tra i nodi.\n"
            ]
            # Ordina i pattern per un output consistente
            for pattern in sorted(list(relazioni_uniche)):
                schema_relazioni.append(f"- {pattern}")

            schema_finale.append("\n".join(schema_relazioni))

        except Exception as e:
            schema_finale.append(f"## Errore nel recupero dello schema delle relazioni: {e}")

    return "\n\n".join(schema_finale)


async def extract_sub_schema(user_query: str, full_graph_schema: str, llm_client: ol.AsyncClient) -> str:
    """
    Passo 1: Usa l'LLM per analizzare lo schema completo e la query utente,
    restituendo solo le parti dello schema rilevanti per la query.
    """

    system_prompt = f"""
    # ROLE: Graph Schema Analyst

    ## GOAL
    You are an expert graph schema analyst. Your task is to analyze a user's question 
    and a full graph schema, and then extract a smaller, relevant subgraph schema that contains
    ONLY the elements needed to answer the question.

    ## FULL GRAPH SCHEMA
    ---
    {full_graph_schema}
    ---

    ## INSTRUCTIONS
    1.  Read the user's question carefully to understand the entities (like 'television', 'kitchen') and relationships they are asking about.
    2.  Examine the full graph schema provided.
    3.  Identify the specific Node Labels, Relationship Types, and Property Keys that are **directly relevant** to the user's question.
    4.  If a node is relevant, include its relationships to other nodes to provide context (e.g., if the user asks about a 'Device', also include the 'Room' it is 'located_in').
    5.  **CRITICAL**: You MUST NOT invent any new elements (labels, properties, relationships) that are not explicitly listed in the full schema.

    ## FINAL OUTPUT
    Produce a reduced schema that is a perfect subset of the original, maintaining the exact same formatting.
    Output ONLY the reduced schema and NOTHING ELSE.
    """

    messages = [
        ol.Message(role="system", content=system_prompt),
        ol.Message(role="user", content=user_query),
    ]

    response = await llm_client.chat(model=OLLAMA_MODEL, messages=messages, options={"temperature": 0})
    reduced_schema = response['message']['content']
    return reduced_schema


async def cypher_query_generator(user_query: str, subgraph_schema: str, llm_client: ol.AsyncClient) -> str:
    """
    Passo 2:
    """

    cypher_query_prompt = f"""
    # ROLE: Expert Neo4j Cypher Query Generator

    ## GOAL
    You are an expert Cypher query translator with deep knowledge of Neo4j graph databases. 
    Your primary function is to convert natural language questions into syntactically correct and 
    semantically efficient Cypher queries based on a provided graph schema. You must adhere 
    strictly to the schema and instructions.

    ##  RELEVANT GRAPH SCHEMA
    The following schema contains ONLY the elements you are allowed to use for the query.

    ---
    {subgraph_schema}
    ---

    ## CORE INSTRUCTIONS:
    1.  **CRITICAL**: You MUST ONLY use the node labels, relationship types, and property keys defined in the provided schema. DO NOT use any elements not listed.
    2.  **NEVER INVENT** elements. If the schema doesn't contain a concept from the user's query, you cannot answer it.
    3.  **ALWAYS** specify the node label in a MATCH clause. 
    4.  To find an individual, you MUST first specify its label, then filter by its `name` property 
    5.  Pay close attention to relationship directions `(node1)-[:REL_TYPE]->(node2)`.

    ## FINAL OUTPUT:
    Always output a valid Cypher query and **NOTHING ELSE**. Do not add explanations or markdown formatting.
    """

    messages = [
        ol.Message(role="system", content=cypher_query_prompt),
        ol.Message(role="user", content=user_query),
    ]

    for example in FEW_SHOT_EXAMPLES:
        messages.append(ol.Message(role="user", content=example["user_query"]))
        messages.append(ol.Message(role="assistant", content=example["cypher_query"]))

    messages.append(ol.Message(role="user", content=user_query))

    response = await llm_client.chat(model=OLLAMA_MODEL, messages=messages, options={"temperature": 0})
    generated_cypher = response['message']['content']

    return generated_cypher.strip().replace("```cypher", "").replace("```", "").strip()


async def run_rag_pipeline(user_query: str, graph_schema: str, neo4j_driver, llm_client: ol.AsyncClient) -> \
AsyncIterator[str]:
    """
    Esecuzione della pipeline a 2(o 3) vie
    """

    # === PASSO 1: ESTRARRE IL SOTTO-GRAFO RILEVANTE ===
    print(f"Extracting relevant subgraph from full schema...")
    relevant_schema = await extract_sub_schema(user_query, graph_schema, llm_client)
    print(f"Relevant subgraph extracted:\n---\n{relevant_schema}\n---")

    # === PASSO 2: GENERARE LA QUERY CYPHER DAL SOTTO-GRAFO ===
    print(AGENT_PROMPT + f"Generating Cypher query from relevant subgraph...")
    generated_cypher = await cypher_query_generator(user_query, relevant_schema, llm_client)
    print(AGENT_PROMPT + f"Generated Cypher: {generated_cypher}")

    # === PASSO 3: ESEGUIRE LA QUERY E GENERARE LA RISPOSTA FINALE ===
    print(AGENT_PROMPT + f"Executing query and generating final response...")
    query_results = ""
    try:
        async with neo4j_driver.session() as session:
            result = await session.run(generated_cypher)
            results_list = [str(record.data()) async for record in result]
            query_results = "\n".join(results_list)

            if not query_results:
                query_results = "The query returned no outputs."

    except exceptions.CypherSyntaxError as e:
        query_results = f"The generated Cypher query has a syntax error: {e}"
    except Exception as e:
        query_results = f"An error occurred while executing the Cypher query: {e}"

    print(AGENT_PROMPT + f"{query_results}")

    response_gen_prompt = f"""
    Respond to the user in a conversational fashion by explaining the following Cypher query output.
    The user's original question was: "{user_query}"

    The Cypher query output is:
    ---
    {query_results}
    ---
    """

    response_agent = LLM(model=OLLAMA_MODEL, system=response_gen_prompt)
    async for chunk in response_agent.stream_chat(user_query):
        yield chunk


async def main():
    """
    Funzione principale che avvia la chat loop.
    """
    try:
        # Inizializza il driver di Neo4j
        async with AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
            llm_client = ol.AsyncClient()  # Crea il client una sola volta
            graph_schema = await genera_schema_strutturato(driver)
            print(graph_schema)
            if not graph_schema:
                print("[System] Could not retrieve schema. Exiting.")
                return

            print("\n[System] Setup complete. You can now ask questions about the graph.")

            while True:
                user_query = await ainput(USER_PROMPT)
                if user_query.lower() in ["exit", "quit", "esci"]:
                    break

                await aprint(AGENT_PROMPT, end="")
                async for chunk in run_rag_pipeline(user_query, graph_schema, driver, llm_client):
                    await aprint(chunk, end="")
                await aprint()

    except asyncio.CancelledError:
        pass  # Gestisce l'uscita con Ctrl+C
    finally:
        await aprint("\nGoodbye.")


if __name__ == "__main__":
    asyncio.run(main())

"""
/home/enrico/miniconda3/envs/FL_project/bin/python /home/enrico/Programmi/PyCharm/Progetti/FormalLanguages/FL_project/Enrico/pipeline_nicolas.py 
Received notification from DBMS server: {severity: WARNING} {code: Neo.ClientNotification.Procedure.ProcedureWarning} {category: GENERIC} {title: The query used a procedure that generated a warning.} {description: The query used a procedure that generated a warning. (The field `propertyTypes` will change output format in the next major version.)} {position: line: 1, column: 1, offset: 0} for query: 'CALL db.schema.nodeTypeProperties()'
## Schema delle Proprietà dei Nodi
Di seguito sono elencati i nodi e le rispettive proprietà.

- Nodo con etichetta `:Class` ha le proprietà: `['name', 'uri']`.
- Nodo con etichetta `:DatatypeProperty` ha le proprietà: `['name', 'uri']`.
- Nodo con etichetta `:NamedIndividual` ha le proprietà: `['name', 'setting', 'state', 'unit', 'uri', 'value']`.
- Nodo con etichetta `:ObjectProperty` ha le proprietà: `['name', 'uri']`.
- Nodo con etichetta `:Room` ha le proprietà: `['name', 'uri']`.


## Esempi di Istanze per Etichetta
Per darti un'idea dei dati reali, ecco alcuni nomi di istanze per etichetta.

- Esempi per `:Class`: `['Light', 'Categorical_sensor', 'Humidity_sensor', 'Air_conditioner', 'Oven', 'Coffee_machine', 'Washing_machine', 'Room', 'Settable_device', 'Temperature_sensor', 'Numeric_sensor', 'Device', 'Occupancy_sensor', 'Brightness_sensor', 'Smoke_sensor', 'Appliance', 'Dimmable_light', 'Togglable_device', 'Robot_vacuum', 'Boolean_sensor', 'Television', 'Sensor']`
- Esempi per `:DatatypeProperty`: `['unit', 'state', 'setting', 'value']`
- Esempi per `:NamedIndividual`: `['Television_1', 'Occupancy_sensor_4', 'Occupancy_sensor_5', 'Occupancy_sensor_2', 'Washing_machine_1', 'Occupancy_sensor_3', 'Occupancy_sensor_1', 'Study', 'Temperature_sensor_1', 'Ceiling_light_3', 'Ceiling_light_2', 'Ceiling_light_5', 'Ceiling_light_4', 'Ceiling_light_1', 'Humidity_sensor_1', 'Coffee_machine_1', 'Lamp_1', 'Kitchen', 'Oven_1', 'Bedroom', 'Brightness_sensor_1', 'Lamp_3', 'Lamp_2', 'Air_conditioner_1', 'Air_conditioner_2', 'Bathroom', 'Smoke_sensor_1', 'Robot_vacuum_1', 'Living_room']`
- Esempi per `:ObjectProperty`: `['contains', 'located_in']`
- Esempi per `:Room`: `['Study', 'Kitchen', 'Bedroom', 'Bathroom', 'Living_room']`


## Schema delle Relazioni
Di seguito sono elencati i pattern di relazione esistenti tra i nodi.

- (:Class)-[:SUBCLASSOF]->(:Class)
- (:Class)-[:TYPE]->(:Class)
- (:DatatypeProperty)-[:TYPE]->(:Class)
- (:NamedIndividual)-[:CONTAINS]->(:NamedIndividual)
- (:NamedIndividual)-[:LOCATED_IN]->(:NamedIndividual)
- (:NamedIndividual)-[:LOCATED_IN]->(:Room)
- (:NamedIndividual)-[:MEMBEROF]->(:Class)
- (:NamedIndividual)-[:TYPE]->(:Class)
- (:ObjectProperty)-[:TYPE]->(:Class)
- (:Room)-[:CONTAINS]->(:NamedIndividual)
- (:Room)-[:TYPE]->(:Class)

[System] Setup complete. You can now ask questions about the graph.
[User] > 
Goodbye.

Process finished with exit code 0

"""