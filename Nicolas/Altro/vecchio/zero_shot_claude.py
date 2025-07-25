import asyncio
import json
from collections.abc import AsyncIterator
from typing import Dict, List, Any, Optional, Tuple
import logging
import re

import ollama as ol
from aioconsole import ainput, aprint
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import CypherSyntaxError, CypherTypeError

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# fmt: off
USER_PROMPT  = "[User]  "
AGENT_PROMPT = "[Agent] "
# fmt: on


class Neo4jConnection:
    """Gestisce la connessione a Neo4j e l'esecuzione delle query"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "Passworddineo4j1!"):
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        await self._driver.close()
    
    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Esegue una query Cypher e restituisce i risultati"""
        try:
            async with self._driver.session() as session:
                result = await session.run(query)
                return [record.data() for record in await result.data()]
        except (CypherSyntaxError, CypherTypeError) as e:
            logger.error(f"Errore nell'esecuzione della query: {e}")
            raise
    
    async def get_detailed_schema(self) -> Dict[str, Any]:
        """Ottiene uno schema dettagliato del database Neo4j usando solo Cypher standard"""
        try:
            async with self._driver.session() as session:
                # Schema base
                nodes_query = "CALL db.labels() YIELD label RETURN collect(label) as labels"
                nodes_result = await session.run(nodes_query)
                labels = (await nodes_result.single())["labels"]
                
                relationships_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"
                rel_result = await session.run(relationships_query)
                relationship_types = (await rel_result.single())["types"]
                
                properties_query = "CALL db.propertyKeys() YIELD propertyKey RETURN collect(propertyKey) as properties"
                prop_result = await session.run(properties_query)
                properties = (await prop_result.single())["properties"]
                
                schema_info = {
                    "node_labels": labels,
                    "relationship_types": relationship_types,
                    "properties": properties
                }
                
                # Prova a ottenere informazioni più dettagliate usando solo Cypher standard
                try:
                    # Schema delle relazioni
                    detailed_schema_query = """
                    MATCH (n)-[r]->(m)
                    RETURN DISTINCT labels(n) as from_labels, type(r) as relationship, labels(m) as to_labels
                    LIMIT 20
                    """
                    detailed_result = await session.run(detailed_schema_query)
                    relationships_structure = []
                    async for record in detailed_result:
                        relationships_structure.append({
                            "from": record["from_labels"],
                            "relationship": record["relationship"],
                            "to": record["to_labels"]
                        })
                    schema_info["relationships_structure"] = relationships_structure
                    
                    # Proprietà per ogni label (solo per i primi 5 labels)
                    properties_per_label = {}
                    for label in labels[:5]:  # Limita a 5 labels per evitare troppi dati
                        try:
                            prop_query = f"""
                            MATCH (n:{label})
                            WITH n LIMIT 5
                            RETURN keys(n) as properties
                            """
                            prop_result = await session.run(prop_query)
                            props = set()
                            async for record in prop_result:
                                props.update(record["properties"])
                            properties_per_label[label] = list(props)
                        except Exception as label_error:
                            logger.warning(f"Errore nel recuperare proprietà per {label}: {label_error}")
                            properties_per_label[label] = []
                    
                    schema_info["properties_per_label"] = properties_per_label
                    
                except Exception as e:
                    logger.warning(f"Impossibile ottenere schema dettagliato: {e}")
                
                return schema_info
                
        except Exception as e:
            logger.error(f"Errore nell'ottenere lo schema: {e}")
            return {"node_labels": [], "relationship_types": [], "properties": []}
    
    async def get_sample_data(self, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """Ottiene campioni di dati per ogni tipo di nodo"""
        try:
            schema = await self.get_detailed_schema()
            samples = {}
            
            for label in schema.get("node_labels", [])[:3]:  # Limita a 3 labels
                query = f"MATCH (n:{label}) RETURN n LIMIT {limit}"
                result = await self.execute_query(query)
                samples[label] = result
            
            return samples
        except Exception as e:
            logger.error(f"Errore nell'ottenere campioni di dati: {e}")
            return {}


class LLM:
    """Gestisce l'interazione con il modello LLM tramite Ollama"""
    
    def __init__(self, model: str = "llama3.1", system: str = "You are a helpful assistant."):
        self.system = system
        self._client = ol.AsyncClient("localhost")
        self._model = model

    async def chat(self, query: str, system_override: Optional[str] = None) -> str:
        """Invia una query al modello e restituisce la risposta completa"""
        system_message = system_override if system_override else self.system
        
        messages = [
            ol.Message(role="system", content=system_message),
            ol.Message(role="user", content=query),
        ]
        
        response = await self._client.chat(self._model, messages, stream=False)
        return response.message.content

    async def chat_stream(self, query: str, system_override: Optional[str] = None) -> AsyncIterator[str]:
        """Invia una query al modello e restituisce la risposta in streaming"""
        system_message = system_override if system_override else self.system
        
        messages = [
            ol.Message(role="system", content=system_message),
            ol.Message(role="user", content=query),
        ]
        
        async for chunk in await self._client.chat(self._model, messages, stream=True):
            yield chunk.message.content


class RAGPipeline:
    """Pipeline RAG avanzata per la generazione di query Cypher corrette"""
    
    def __init__(self, llm: LLM, neo4j_conn: Neo4jConnection):
        self.llm = llm
        self.neo4j_conn = neo4j_conn
        self.schema = None
        self.sample_data = None
        self.few_shot_examples = []
    
    async def initialize(self):
        """Inizializza la pipeline ottenendo schema e campioni di dati"""
        self.schema = await self.neo4j_conn.get_detailed_schema()
        self.sample_data = await self.neo4j_conn.get_sample_data()
        logger.info(f"Schema caricato: {len(self.schema.get('node_labels', []))} labels, {len(self.schema.get('relationship_types', []))} relationship types")
    
    def _build_enhanced_cypher_prompt(self, schema: Dict[str, Any], include_examples: bool = False) -> str:
        """Costruisce un prompt avanzato per la generazione di query Cypher"""
        
        # Schema base
        schema_info = f"""Database Schema:
- Node Labels: {', '.join(schema.get('node_labels', []))}
- Relationship Types: {', '.join(schema.get('relationship_types', []))}
- Properties: {', '.join(schema.get('properties', []))}"""
        
        # Aggiungi struttura delle relazioni se disponibile
        if 'relationships_structure' in schema:
            schema_info += "\n\nRelationship Patterns:"
            for rel in schema['relationships_structure'][:10]:  # Limita a 10
                schema_info += f"\n- {rel['from']} -[:{rel['relationship']}]-> {rel['to']}"
        
        # Aggiungi proprietà per label se disponibile
        if 'properties_per_label' in schema:
            schema_info += "\n\nProperties per Label:"
            for label, props in schema['properties_per_label'].items():
                schema_info += f"\n- {label}: {', '.join(props[:5])}"  # Limita a 5 proprietà
        
        prompt = f"""You are an expert Cypher query generator. Generate ONLY valid Cypher queries.

{schema_info}

CRITICAL RULES:
1. Output ONLY the Cypher query, no explanations or markdown
2. Use exact node labels and relationship types from the schema
3. Use proper Cypher syntax with correct property access
4. For boolean questions, return boolean expressions
5. For count questions, use COUNT() function
6. When referencing specific entities, use property matching (e.g., {{name: "EntityName"}})
7. Use MATCH clauses to find nodes and relationships
8. Use RETURN to specify what to output

Common Cypher Patterns:
- Find node by property: MATCH (n:Label {{property: "value"}}) RETURN n
- Count nodes: MATCH (n:Label) RETURN COUNT(n) as count
- Find related nodes: MATCH (a:Label1)-[r:RELATIONSHIP]->(b:Label2) RETURN a, b
- Boolean check: MATCH (n:Label {{property: "value"}}) RETURN EXISTS(n) as exists
- Property value: MATCH (n:Label {{name: "EntityName"}}) RETURN n.property as result"""

        # Aggiungi esempi few-shot se richiesto
        if include_examples and self.few_shot_examples:
            prompt += "\n\nExamples:"
            for example in self.few_shot_examples:
                prompt += f"\nUser: {example['user']}\nQuery: {example['query']}\n"
        
        prompt += "\n\nGenerate the Cypher query for:"
        return prompt
    
    def _extract_cypher_query(self, llm_response: str) -> str:
        """Estrae la query Cypher dalla risposta del modello"""
        # Rimuovi markdown code blocks
        response = llm_response.strip()
        
        # Rimuovi ``` blocks
        if "```" in response:
            # Estrai contenuto tra ```
            matches = re.findall(r'```(?:cypher)?\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
            if matches:
                response = matches[0].strip()
        
        # Rimuovi linee che non sono query Cypher
        lines = response.split('\n')
        query_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                query_lines.append(line)
        
        query = ' '.join(query_lines).strip()
        
        # Rimuovi spiegazioni dopo la query
        if ';' in query:
            query = query.split(';')[0] + ';'
        
        return query
    
    async def generate_cypher_query_with_retry(self, user_query: str, max_attempts: int = 3) -> Tuple[str, bool]:
        """Genera una query Cypher con retry in caso di errori"""
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                # Usa esempi few-shot dopo il primo tentativo fallito
                use_examples = attempt > 0 and self.few_shot_examples
                
                cypher_prompt = self._build_enhanced_cypher_prompt(self.schema, include_examples=use_examples)
                
                # Aggiungi contesto dell'errore precedente
                query_with_context = user_query
                if last_error:
                    query_with_context += f"\n\nNote: Previous attempt failed with error: {last_error}. Please generate a corrected query."
                
                llm_response = await self.llm.chat(query_with_context, system_override=cypher_prompt)
                cypher_query = self._extract_cypher_query(llm_response)
                
                # Testa la query
                await self.neo4j_conn.execute_query(cypher_query)
                
                logger.info(f"Query Cypher generata con successo al tentativo {attempt + 1}: {cypher_query}")
                return cypher_query, True
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Tentativo {attempt + 1} fallito: {e}")
                
                if attempt == max_attempts - 1:
                    logger.error(f"Tutti i tentativi falliti. Ultimo errore: {e}")
                    return "", False
        
        return "", False
    
    def add_few_shot_example(self, user_query: str, correct_cypher: str):
        """Aggiunge un esempio few-shot alla collezione"""
        self.few_shot_examples.append({
            "user": user_query,
            "query": correct_cypher
        })
        # Mantieni solo gli ultimi 5 esempi per non sovraccaricare il prompt
        if len(self.few_shot_examples) > 5:
            self.few_shot_examples = self.few_shot_examples[-5:]
    
    async def generate_final_response(self, user_query: str, query_result: List[Dict[str, Any]]) -> str:
        """Genera la risposta finale basata sui risultati della query"""
        response_prompt = f"""You are a helpful assistant that explains query results conversationally.

Query Result: {json.dumps(query_result, indent=2)}

Task: Provide a clear, natural response to the user's question based on the query results.

Rules:
1. Be conversational and natural
2. If result is empty, say no data was found
3. If result has data, explain what was found clearly
4. Be concise but informative
5. Don't mention technical details about the query

Respond naturally to the user's question:"""
        
        try:
            final_response = await self.llm.chat(user_query, system_override=response_prompt)
            return final_response
        except Exception as e:
            logger.error(f"Errore nella generazione della risposta finale: {e}")
            return f"I found some results but had trouble explaining them: {query_result}"
    
    async def process_query(self, user_query: str) -> Tuple[str, List[Dict[str, Any]], str, bool]:
        """Processa una query utente attraverso l'intera pipeline RAG"""
        try:
            # Step 1: Genera query Cypher con retry
            cypher_query, success = await self.generate_cypher_query_with_retry(user_query)
            
            if not success:
                return "", [], "Mi dispiace, non sono riuscito a generare una query corretta per la tua domanda.", False
            
            # Step 2: Esegue la query
            query_result = await self.neo4j_conn.execute_query(cypher_query)
            
            # Step 3: Genera risposta finale
            final_response = await self.generate_final_response(user_query, query_result)
            
            return cypher_query, query_result, final_response, True
            
        except Exception as e:
            logger.error(f"Errore nel processamento della query: {e}")
            return "", [], f"Si è verificato un errore: {str(e)}", False


async def user_input() -> str:
    return await ainput(USER_PROMPT)


async def main() -> None:
    # Configurazione componenti
    llm = LLM()
    neo4j_conn = Neo4jConnection()  # Modifica le credenziali se necessario
    
    # Inizializzazione pipeline RAG
    rag_pipeline = RAGPipeline(llm, neo4j_conn)
    
    try:
        await rag_pipeline.initialize()
        await aprint("Pipeline RAG avanzata inizializzata.")
        await aprint("Comandi speciali: 'quit' per uscire, 'add_example' per aggiungere un esempio few-shot")
        
        while True:
            query = await user_input()
            
            if query.lower() in ['quit', 'exit', 'bye']:
                break
            
            if query.lower().startswith('add_example'):
                await aprint("Inserisci la query utente:")
                user_q = await user_input()
                await aprint("Inserisci la query Cypher corretta:")
                cypher_q = await user_input()
                rag_pipeline.add_few_shot_example(user_q, cypher_q)
                await aprint("Esempio aggiunto!")
                continue
            
            try:
                # Processa la query attraverso la pipeline RAG
                cypher_query, query_result, final_response, success = await rag_pipeline.process_query(query)
                
                if success:
                    # Mostra i risultati
                    await aprint(f"\n[Debug] Query Cypher generata:")
                    await aprint(f"  {cypher_query}")
                    await aprint(f"\n[Debug] Risultati query ({len(query_result)} record):")
                    await aprint(f"  {query_result}")
                    await aprint(f"\n{AGENT_PROMPT}{final_response}\n")
                else:
                    await aprint(f"\n{AGENT_PROMPT}{final_response}\n")
                
            except Exception as e:
                await aprint(f"\n{AGENT_PROMPT}Si è verificato un errore: {str(e)}\n")
    
    except KeyboardInterrupt:
        await aprint("\nArrivederci!")
    
    finally:
        await neo4j_conn.close()


if __name__ == "__main__":
    asyncio.run(main())