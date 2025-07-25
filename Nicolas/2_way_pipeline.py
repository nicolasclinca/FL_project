import asyncio
from collections.abc import AsyncIterator

import ollama as ol
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase, exceptions

# --- CONFIGURAZIONE ---
# Inserisci qui i dati di connessione per il tuo database Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Passworddineo4j1!" 

# Modello Ollama da utilizzare 
OLLAMA_MODEL = "codellama:7b"    # codellama:7b oppure llama3.1

# Prompt per l'interfaccia utente
USER_PROMPT = "[User] > "
AGENT_PROMPT = "[Agent] > "

FEW_SHOT_EXAMPLES = [
    {
        "user_query": "Which people live in Paris?",
        "cypher_query": "MATCH (p:Person)-[:LIVES_IN]->(c:City {name: 'Paris'}) RETURN p.name"
    },
    {
        "user_query": "Which books were published after the year 2000?",
        "cypher_query": "MATCH (b:Book) WHERE b.year > 2000 RETURN b.title"
    },
    {
        "user_query": "Who are the friends of John?",
        "cypher_query": "MATCH (p:Person {name: 'John'})-[:FRIEND_OF]-(f:Person) RETURN f.name"
    },
    {
        "user_query": "Which resources are related to something containing the word climate?",
        "cypher_query": "MATCH (r:Resource)-[:RELATED_TO]->(t:Topic) WHERE t.uri CONTAINS 'climate' RETURN r"
    },
    {
        "user_query": "Which employees work for companies based in Germany?",
        "cypher_query": "MATCH (e:Person)-[:WORKS_AT]->(c:Company)-[:BASED_IN]->(:Country {name: 'Germany'}) RETURN e.name"
    },
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
        async for chunk in await self._client.chat(self._model, messages, stream=True):
            yield chunk['message']['content']
            
            
            
            
async def get_neo4j_schema(driver) -> str:
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
                from: fromNodeLabels,
                type: relationshipType,
                to: toNodeLabels
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
            #rel_types = record.get("relTypes", [])
            #prop_keys = record.get("propKeys", [])
            #relationships = record.get("relationships", [])

    
            # PASSO 2: Recupera gli individui per ogni etichetta
            LABELS_TO_EXCLUDE = {'_GraphConfig', 'Resource'}
            labels = [l for l in all_labels if l not in LABELS_TO_EXCLUDE]
            individuals_by_label = {}
            for label in labels:
                individual_query = f"""
                MATCH (n:`{label}`)
                WHERE n.uri IS NOT NULL AND NOT n.uri STARTS WITH 'bnode://'
                WITH n.uri AS individual_id LIMIT 5
                RETURN COLLECT(individual_id) AS individuals
                """
            
                individual_result = await session.run(individual_query)
                record = await individual_result.single()
                if record and record["individuals"]:
                    individuals_by_label[label] = record["individuals"]

            # PASSO 3: Formatta tutto in un unico contesto per l'LLM
            formatted_context = f"""
                This is the vocabulary and a sample of individuals from the graph.

                ** Node Labels in use:**
                {all_labels}


                ** Node Label and their Individuals:**
                """
            for label, individuals in individuals_by_label.items():
                formatted_context += f"- **{label}**: {individuals}\n"

            return formatted_context.strip()


    except Exception as e:
        print(f"\n[FATAL ERROR] An error occurred while fetching the schema: {e}")
        return ""
    

ALTRO = """
                ** Relationship Types in use:**
                {rel_types}

                ** Property Keys in use:**
                {prop_keys}
"""
    

async def run_rag_pipeline(user_query: str, graph_schema: str, neo4j_driver, llm_client: ol.AsyncClient) -> AsyncIterator[str]:
    """
    Orchestra la pipeline RAG a due passaggi:
    1. Genera una query Cypher.
    2. Esegue la query e usa i risultati per rispondere all'utente.
    """
    
    # === PASSO 1: GENERARE LA QUERY CYPHER ===
    cypher_gen_system_prompt = f"""
    
    # ROLE: Expert Neo4j Cypher Query Generator
    
    ## GOAL
    You are an expert Cypher query translator with deep knowledge of Neo4j graph databases. 
    Your primary function is to convert natural language questions into syntactically correct and 
    semantically efficient Cypher queries based on a provided graph schema. You must adhere 
    strictly to the schema and instructions.

    ## GRAPH SCHEMA
    The graph schema is as follows:
    
    ---
    {graph_schema}
    ---
    
    ## CORE INSTRUCTIONS:
    1. **CRITICAL**: Use only the node labels, relationship types, and property keys defined in the graph schema.
    2. Do not invent or assume schema elements or properties that are not explicitly defined.
    3. Assume a minimal, consistent, and plausible graph structure if details are missing.
    4. Keep Cypher queries syntactically correct, simple, and readable.
    5. Access node properties using dot notation (e.g., n.name).
    6. Prefer URI-based matching or string operations (e.g., CONTAINS, STARTS WITH) over name-based filters when appropriate.
    
    ## FINAL OUTPUT:
    Always output a valid Cypher query and **NOTHING ELSE**.
    """ 

    ALTRE_ISTRUZIONI = """
            7. In MATCH clauses, always use the appropriate node labels (e.g., (:Person)), not unlabeled nodes.
    """
    

    
     # Inizializza la lista di messaggi con il system prompt
    messages_for_cypher_gen = [
        ol.Message(role="system", content=cypher_gen_system_prompt)
    ]

    # --- INIEZIONE DEGLI ESEMPI FEW-SHOT ---
    # Aggiungi ogni esempio come una coppia di messaggi user/assistant
    # Vengono aggiunti in coda al prompt di sistema, questo dà l'impressione di una chat history
    for example in FEW_SHOT_EXAMPLES:
        messages_for_cypher_gen.append(ol.Message(role="user", content=example["user_query"]))
        messages_for_cypher_gen.append(ol.Message(role="assistant", content=example["cypher_query"]))
    # ----------------------------------------

    # Infine, aggiungi la domanda reale dell'utente in coda agli esempi few-shot
    messages_for_cypher_gen.append(ol.Message(role="user", content=user_query))
    
    # Invia la richiesta completa (system + examples + query) all'LLM
    response = await llm_client.chat(model=OLLAMA_MODEL, messages=messages_for_cypher_gen)
    generated_cypher = response['message']['content']
    
    
    #generated_cypher = await cypher_agent.chat(user_query)

    # Pulizia della query generata (a volte gli LLM aggiungono ```cypher ... ```)
    generated_cypher = generated_cypher.strip().replace("```cypher", "").replace("```", "").strip()
    
    print(f"{generated_cypher}")

    # === PASSO 2: ESEGUIRE LA QUERY E GENERARE LA RISPOSTA FINALE ===
    query_results = ""
    try:
        async with neo4j_driver.session() as session:
            result = await session.run(generated_cypher)
            results_list = [str(record.data()) async for record in result]
            query_results = "\n".join(results_list)
            
            if not query_results:
                query_results = "The query returned no results."

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
            graph_schema = await get_neo4j_schema(driver)
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
        pass # Gestisce l'uscita con Ctrl+C
    finally:
        await aprint("\nGoodbye.")



if __name__ == "__main__":
    asyncio.run(main())