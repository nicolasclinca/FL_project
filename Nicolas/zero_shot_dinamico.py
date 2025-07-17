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
    print("[System] Retrieving in-use graph vocabulary with a single query...")

    schema_query = """
        CALL () {
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN COLLECT(DISTINCT label) AS labels
        }
        CALL () {
            MATCH ()-[r]->()
            RETURN COLLECT(DISTINCT type(r)) AS relTypes
        }
        CALL () {
            MATCH (n)
            UNWIND keys(n) AS key
            RETURN COLLECT(DISTINCT key) AS propKeys
        }
        RETURN labels, relTypes, propKeys
        """
    
    try:
        async with driver.session() as session:
            result = await session.run(schema_query)
            record = await result.single()

            if not record:
                return "Graph is empty or schema could not be retrieved."

            labels = record.get("labels", [])
            rel_types = record.get("relTypes", [])
            prop_keys = record.get("propKeys", [])

            formatted_schema = f"""
                This is the vocabulary of the graph you can use to build a Cypher query.

                **1. Node Labels in use:**
                {labels}

                **2. Relationship Types in use:**
                {rel_types}

                **3. Property Keys in use (on nodes):**
                {prop_keys}
                """
            return formatted_schema.strip()

    except Exception as e:
        print(f"\n[FATAL ERROR] An error occurred while fetching the in-use schema: {e}")
        return ""
    
    
    

async def run_rag_pipeline(user_query: str, graph_schema: str, neo4j_driver) -> AsyncIterator[str]:
    """
    Orchestra la pipeline RAG a due passaggi:
    1. Genera una query Cypher.
    2. Esegue la query e usa i risultati per rispondere all'utente.
    """
    
    # === PASSO 1: GENERARE LA QUERY CYPHER ===
    cypher_gen_prompt = f"""
    Generate the Cypher query that best answers the user query.
    Follow these guidelines:

    1. Always output a syntactically correct Cypher query.
    2. Use only the node labels, relationship types, and property keys provided in the schema.
    3. Use specific names only if explicitly mentioned in the question.
    4. Do not invent properties or overly specific details.
    5. Keep queries syntactically correct, simple, and readable.
    6. Access node properties using dot notation (e.g., `n.name`).
    7. Use `WHERE` clauses for precise filtering of nodes and relationships.
    
    The graph schema is as follows:
    ---
    {graph_schema}
    ---
    Always output a valid Cypher query and **NOTHING ELSE**.
    """ 

    cypher_agent = LLM(model=OLLAMA_MODEL, system=cypher_gen_prompt)
    generated_cypher = await cypher_agent.chat(user_query)

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
        # Inizializza il driver di Neo4j [cite: 12, 13]
        async with AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
            graph_schema = await get_neo4j_schema(driver)
            if not graph_schema:
                print("[System] Could not retrieve schema. Exiting.")
                return

            print("\n[System] Setup complete. You can now ask questions about the graph.")
            
            while True:
                user_query = await ainput(USER_PROMPT)
                if user_query.lower() in ["exit", "quit", "esci"]:
                    break
                
                await aprint(AGENT_PROMPT, end="")
                async for chunk in run_rag_pipeline(user_query, graph_schema, driver):
                    await aprint(chunk, end="")
                await aprint()

    except asyncio.CancelledError:
        pass # Gestisce l'uscita con Ctrl+C
    finally:
        await aprint("\nGoodbye.")


if __name__ == "__main__":
    asyncio.run(main())