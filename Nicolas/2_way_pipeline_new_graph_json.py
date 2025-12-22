import asyncio
from collections.abc import AsyncIterator
from collections import defaultdict
import argparse
import ollama as ol
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase, exceptions
import random, json

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
    def __init__(self, model: str, system: str = "You are a helpful assistant."):
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
        async for chunk in await self._client.chat(self._model, messages, stream=True):
            yield chunk['message']['content']       
            
            
            
async def genera_schema_strutturato(driver)->str:
    """
    Genera una rappresentazione JSON strutturata dello schema del grafo Neo4j.
    Questa versione è più robusta: prima trova tutte le etichette dei nodi, 
    poi aggiunge le proprietà, garantendo che anche i nodi senza proprietà vengano inclusi.
    """
    schema = {"nodes": {}, "relationships": []}
    etichette_da_ignorare = {"_GraphConfig", "Resource", "Ontology"}

    async with driver.session() as session:
        try:
            # 1. Ottenere TUTTE le etichette dei nodi esistenti
            risultati_labels = await session.run("CALL db.labels()")
            async for record in risultati_labels:
                label = record["label"]
                if label not in etichette_da_ignorare:
                    # Inizializza ogni etichetta con una lista di proprietà vuota
                    schema["nodes"][label] = {"properties": {}}

            # 2. Ottenere le proprietà e i loro tipi e aggiungerle ai nodi esistenti
            risultati_props = await session.run("CALL db.schema.nodeTypeProperties()")
            async for record in risultati_props:
                node_labels = record["nodeLabels"]
                prop_name = record["propertyName"]
                
                # Trova l'etichetta principale non ignorata
                main_label = next((l for l in node_labels if l not in etichette_da_ignorare), None)
                
                if main_label and main_label in schema["nodes"]:
                    schema["nodes"][main_label]["properties"][prop_name] = ""

            # 2.5 Ottenere esempi di istanze per ogni etichetta usando la proprietà 'name'
            proprieta_identificativa = 'name'
            limite_esempi = 50 # Limita il numero di esempi per non appesantire lo schema
            for label in schema["nodes"]:
                # Controlla se il nodo ha la proprietà 'name' prima di fare la query
                if proprieta_identificativa in schema["nodes"][label]["properties"]:
                    query_esempio = (
                        f"MATCH (n:`{label}`) "
                        f"WHERE n.{proprieta_identificativa} IS NOT NULL "
                        f"RETURN n.{proprieta_identificativa} AS instance_name LIMIT {limite_esempi}"
                    )
                    risultati_esempi = await session.run(query_esempio)
                    esempi = [record["instance_name"] async for record in risultati_esempi]
                    if esempi:
                        schema["nodes"][label]["examples"] = esempi
            
            # 3. Ottenere i Pattern delle Relazioni (invariato)
            relazioni_uniche = set()
            risultati_relazioni = await session.run("CALL db.schema.visualization()")
            
            async for record in risultati_relazioni:
                for relazione in record["relationships"]:
                    start_node_labels = [l for l in relazione.start_node.labels if l not in etichette_da_ignorare]
                    end_node_labels = [l for l in relazione.end_node.labels if l not in etichette_da_ignorare]
                    
                    if not start_node_labels or not end_node_labels:
                        continue

                    etichetta_partenza = start_node_labels[0]
                    etichetta_arrivo = end_node_labels[0]
                    tipo_relazione = relazione.type
                    
                    pattern = f"(:{etichetta_partenza})-[:{tipo_relazione}]->(:{etichetta_arrivo})"
                    relazioni_uniche.add(pattern)
            
            schema["relationships"] = sorted(list(relazioni_uniche))

        except Exception as e:
            print(f"Error during generating the JSON schema: {e}")
            return None

    return json.dumps(schema, indent=2) 





async def extract_sub_schema(user_query: str, full_graph_schema: str, llm_client: ol.AsyncClient, ollama_model: str) -> str:
    """
    Passo 1: Usa l'LLM per analizzare lo schema completo e la query utente, 
    restituendo solo le parti dello schema rilevanti per la query.
    """
    
    system_prompt = f"""
    # ROLE: Graph Schema Analyst

    ## GOAL
    You are a top-tier algorithm designed for analyzing a graph database schema and a user query to extract 
    all relevant entities (nodes), relationships, and properties. Your goal is to identify only the parts 
    of the schema that are strictly necessary to answer the user's question.

    
    ## FULL GRAPH SCHEMA
    ---
    {full_graph_schema}
    ---
    
    ## INSTRUCTIONS
    1. Your task is to analyze the provided schema and the user's query.
    2. You MUST identify all nodes, relationships, and properties from the schema that are directly relevant to the query.
    3. You MUST NOT include any node, relationship, or property that is not explicitly defined in the provided schema.
    
    ## FINAL OUTPUT
    Produce a reduced schema that is a perfect subset of the original, maintaining the exact same formatting.
    Output ONLY the reduced schema and NOTHING ELSE.
    """
    
    messages = [
        ol.Message(role="system", content=system_prompt),
        ol.Message(role="user", content=user_query),
    ]

    response = await llm_client.chat(model=ollama_model, messages=messages, options={"temperature": 0.2})
    reduced_schema = response['message']['content'] 
    return reduced_schema


async def cypher_query_generator(user_query: str, subgraph_schema: str, llm_client: ol.AsyncClient, ollama_model: str) -> str:
    """
    Passo 2:
    """
    
    cypher_query_prompt = f"""
    # ROLE: Expert Neo4j Cypher Query Generator
    
    ## GOAL
    You are an expert Cypher query translator. Your function is to convert natural language questions 
    into syntactically correct and semantically efficient Cypher queries based on the provided graph schema.

    ## GRAPH SCHEMA
    This is the ONLY information you are allowed to use. Adhere to it strictly.
    The schema is provided in JSON format.
    - `nodes` contains labels, their properties with data types, and an optional `examples` list of instance names.
    - `relationships` describes the connections between nodes.

    ```json
    {subgraph_schema}
    ```

    ## CORE INSTRUCTIONS:
    1.  **Strict Schema Adherence**: You MUST ONLY use the node labels, relationship types, and property keys defined in the JSON schema. Do not invent or assume any elements.
    2.  **Finding Specific Things (Instances)**: When the user's query refers to a specific item by name (e.g., "Television_1", "the kitchen"), use the `examples` list in the schema to find the correct node label and name. Then, filter by its `name` property.
    3.  **Finding Types of Things (Categories)**: When the user's query is about a general category (e.g., "all lights", "properties of a sensor"), identify the appropriate node label from the schema that represents that category.
    4.  **Data Types are Critical**: Pay close attention to the data types of properties provided in the schema. For example, a property of type `StringArray` requires a list in the query (e.g., `n.state = ["on"]`), while a `Long` requires a number.
    5.  **Relationship Direction**: Pay close attention to relationship directions as defined in the `relationships` list (e.g., `(node1)-[:REL_TYPE]->(node2)`).
    6.  **Impossible Queries**: If a query cannot be answered with the provided schema, output the single word "IMPOSSIBLE".
    
    ## FINAL OUTPUT:
    Output a valid Cypher query and NOTHING ELSE. Do not add explanations, comments, or markdown formatting like ```cypher.
    """
    
    messages = [
        ol.Message(role="system", content=cypher_query_prompt),
    ]

    for example in FEW_SHOT_EXAMPLES:
        messages.append(ol.Message(role="user", content=example["user_query"]))
        messages.append(ol.Message(role="assistant", content=example["cypher_query"]))
    
    messages.append(ol.Message(role="user", content=user_query))         # aggiunta query utente
    
    response = await llm_client.chat(model=ollama_model, messages=messages, options={"temperature": 0.2})
    generated_cypher = response['message']['content']
    
    
    return generated_cypher.strip().replace("```cypher", "").replace("```", "").strip()
    
    


async def run_rag_pipeline(user_query: str, graph_schema: str, neo4j_driver, llm_client: ol.AsyncClient, ollama_model: str) -> AsyncIterator[str]:
    """
    Esecuzione della pipeline a 2(o 3) vie
    """
    
    # === PASSO 1: ESTRARRE IL SOTTO-GRAFO RILEVANTE ===
    print(f"Extracting relevant subgraph from full schema...")
    relevant_schema = await extract_sub_schema(user_query, graph_schema, llm_client, ollama_model)
    print(f"Relevant subgraph extracted:\n---\n{relevant_schema}\n---")
    
    # === PASSO 2: GENERARE LA QUERY CYPHER DAL SOTTO-GRAFO ===
    print(AGENT_PROMPT + f"Generating Cypher query from relevant subgraph...")
    generated_cypher = await cypher_query_generator(user_query, relevant_schema, llm_client, ollama_model)
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
    
    response_agent = LLM(model=ollama_model, system=response_gen_prompt)
    async for chunk in response_agent.stream_chat(user_query):
        yield chunk




async def main(args):
    """
    Funzione principale che avvia la chat loop.
    """
    SCHEMA_FILE_PATH = "graph_schema.json"
    graph_schema_json = None

    # 1. Prova a caricare lo schema dal file
    try:
        with open(SCHEMA_FILE_PATH, 'r') as f:
            graph_schema_json = f.read()
        print(f"[System] Schema loaded from {SCHEMA_FILE_PATH}")
    except FileNotFoundError:
        print(f"[System] {SCHEMA_FILE_PATH} not found. Generating schema from database...")
    except Exception as e:
        print(f"[System] Error loading schema from file: {e}")

    # 2. Se lo schema non è stato caricato, generalo e salvalo
    if not graph_schema_json:
        try:
            async with AsyncGraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)) as driver:
                graph_schema_json = await genera_schema_strutturato(driver)
                if graph_schema_json:
                    with open(SCHEMA_FILE_PATH, 'w') as f:
                        f.write(graph_schema_json)
                    print(f"[System] Schema generated and saved to {SCHEMA_FILE_PATH}")
                else:
                    print("[System] Could not generate schema. Exiting.")
                    return
        except Exception as e:
            print(f"[System] Failed to connect to Neo4j or generate schema: {e}")
            return

    # 3. Avvia il loop della chat
    try:
        async with AsyncGraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)) as driver:
            llm_client = ol.AsyncClient()
            print("\n[System] Setup complete. You can now ask questions about the graph.")
            
            while True:
                user_query = await ainput(USER_PROMPT)
                if user_query.lower() in ["exit", "quit", "esci"]:
                    break
                
                async for chunk in run_rag_pipeline(user_query, graph_schema_json, driver, llm_client, args.ollama_model):
                    await aprint(chunk, end="")
                await aprint()

    except asyncio.CancelledError:
        pass
    finally:
        await aprint("\nGoodbye.")


if __name__ == "__main__":
    try:
        
        parser = argparse.ArgumentParser(description="Text2Cypher")
        parser.add_argument("--neo4j_user", type=str, default="neo4j", help="Neo4j username")
        parser.add_argument("--neo4j_password", type=str, default="Passworddineo4j1!", help="Neo4j password")
        parser.add_argument("--neo4j_uri", type=str, default="bolt://localhost:7687", help="Neo4j URI")
        parser.add_argument("--ollama_model", type=str, default="codellama:7b", help="Ollama model - llama3.1 or codellama:7b - Default:codellama:7b")
        args = parser.parse_args()
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass