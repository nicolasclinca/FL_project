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


SYSTEM_PROMPT_RESPONSE_GENERATION = """
Respond to the user in a conversational fashion by explaining the Cypher query output
"""


class Neo4jHandler:
    """Gestisce le interazioni con il database Neo4j."""
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password)) 

    async def close(self) -> None:
        """Chiude la connessione al driver Neo4j."""
        await self._driver.close()

    async def get_dynamic_schema(self) -> str:
        """
        Costruisce una descrizione SEMPLIFICATA e mirata dello schema, 
        ideale per il prompt del LLM.
        """
        schema_parts = []
        try:
            # 1. Definiamo le etichette principali che ci interessano per le query.
            #    Ignoriamo le etichette dell'ontologia come Class, Resource, etc.
            main_labels = ["Room", "NamedIndividual"]
            
            schema_parts.append("This is a simplified schema of a smart home graph, focusing on queryable entities.")
            
            # 2. Per ogni etichetta principale, troviamo le sue proprietà.
            schema_parts.append("\nNode Types and their properties:")
            for label in main_labels:
                props_query = f"MATCH (n:`{label}`) WITH n LIMIT 200 UNWIND keys(n) AS key RETURN COLLECT(DISTINCT key) as properties"
                props_result = await self.execute_query(props_query)
                properties = props_result[0]['properties'] if props_result and props_result[0]['properties'] else []
                
                description = f"- Node with label `{label}`"
                # NamedIndividual rappresenta tutti i dispositivi, sensori, etc.
                if label == "NamedIndividual":
                    description += " (represents devices, sensors, and other individuals)."
                if properties:
                    description += f" It has properties like: `{', '.join(properties)}`."
                
                schema_parts.append(description)

            # 3. Descriviamo esplicitamente le relazioni chiave per le query.
            schema_parts.append("\nKey Relationships:")
            schema_parts.append("- A `(:NamedIndividual)` node (a device/sensor) can be `[:located_in]` a `(:Room)` node.")
            schema_parts.append("- A `(:Room)` node can `[:contains]` one or more `(:NamedIndividual)` nodes.")
            schema_parts.append("- A `(:NamedIndividual)` node has a `[:type]` relationship pointing to a `(:Class)` node that defines its type (e.g., Light, Sensor).")

            return "\n".join(schema_parts)
            
        except Exception as e:
            await aprint(AGENT_PROMPT + f"Error dynamically fetching simplified schema: {e}")
            return "Simplified schema information could not be retrieved."
        
        
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
    def __init__(self, model: str = "llama3.1") -> None:
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
    llm_agent = LLM()
    neo4j_handler = Neo4jHandler(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # --- NUOVA PARTE: Generazione Dinamica dello Schema ---
    await aprint(AGENT_PROMPT + "Connecting to Neo4j to retrieve graph schema...")
    try:
        dynamic_schema = await neo4j_handler.get_dynamic_schema()
        if "could not be retrieved" in dynamic_schema:
             await aprint(AGENT_PROMPT + "Failed to get schema. Exiting.")
             return
        await aprint(AGENT_PROMPT + "Schema retrieved successfully.")
    except Exception as e:
        await aprint(AGENT_PROMPT + f"Could not connect to Neo4j or retrieve schema: {e}")
        await neo4j_handler.close()
        return

    # Costruisci il system prompt usando lo schema dinamico
    SYSTEM_PROMPT_CYPHER_GENERATION = f"""
        Generate the Cypher query that best answers the user query. The graph schema is as follows:
        {dynamic_schema}.
        Always output a valid Cypher query and nothing else.
        """
    
    
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