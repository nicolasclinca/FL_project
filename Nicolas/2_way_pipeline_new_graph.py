import asyncio
from collections.abc import AsyncIterator
from collections import defaultdict
import argparse
import ollama as ol
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase, exceptions
import random 

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
             "## List of nodes and their properties",
             "Nodes and their respective properties are listed below.\n"
        ]
            # Ordina le etichette per un output consistente
        for etichetta in sorted(nodi_e_proprieta.keys()):
            if etichetta in etichette_da_ignorare:
                continue
            proprieta = sorted(list(nodi_e_proprieta[etichetta]))
            schema_nodi.append(f"- Node`:{etichetta}` has the following properties:: `{proprieta}`.")
        
        schema_finale.append("\n".join(schema_nodi))

        # ---  2. Campionare Istanze per Ogni Etichetta ---
        try:
            esempi_per_etichetta = {}
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
                schema_esempi = ["\n## Elements for each Node of the graph schema"]
                for etichetta, esempi in esempi_per_etichetta.items():
                    schema_esempi.append(f"- Examples for `:{etichetta}`: `{esempi}`")
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
                "\n## Relationships between nodes in the graph",
                "Lists the existing relationship patterns between nodes.\n"
            ]
            # Ordina i pattern per un output consistente
            for pattern in sorted(list(relazioni_uniche)):
                schema_relazioni.append(f"- {pattern}")
                
            schema_finale.append("\n".join(schema_relazioni))

        except Exception as e:
            schema_finale.append(f"## Errore nel recupero dello schema delle relazioni: {e}")
    
    return "\n\n".join(schema_finale)  





async def extract_sub_schema(user_query: str, full_graph_schema: str, llm_client: ol.AsyncClient, ollama_model: str) -> str:
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
    1.  **CRITICAL**: You MUST NOT invent any new elements (node labels, properties, relationships) that are not explicitly listed in the schema.
                      You MUST ONLY use the node labels, relationship types, and property keys defined in the provided schema.
    2.  **NEVER INVENT** elements. If the schema doesn't contain a concept from the user's query, you cannot answer it.
    3.  **ALWAYS** specify the node label in a MATCH clause. 
    4.  To find an individual, you MUST first specify its label, then filter by its `name` property 
    5.  Pay close attention to relationship directions `(node1)-[:REL_TYPE]->(node2)`.
    6.  If a query cannot be answered with the provided schema, output the single word "IMPOSSIBLE".
    
    ## FINAL OUTPUT:
    Always output a valid Cypher query and **NOTHING ELSE**. Do not add explanations or markdown formatting.
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
    try:
        # Inizializza il driver di Neo4j 
        async with AsyncGraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)) as driver:
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
                async for chunk in run_rag_pipeline(user_query, graph_schema, driver, llm_client, args.ollama_model):
                    await aprint(chunk, end="")
                await aprint()

    except asyncio.CancelledError:
        pass # Gestisce l'uscita con Ctrl+C
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