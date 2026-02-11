---
title: Sprachen Projekt Guidelines
esame: "[[Formal Languages]]"
---
# Project Structure

## Root Directory

- `main_manual.py`: run this file to use the chatbot directly by writing your questions in the run console
- `main_automatic.py`: run this file to test multiple queries sequentially, by using their IDs.

- `neo4j_client.py`: this file implements the Neo4j client the interacts with the database
- `language_model.py`: this file includes the LLM agent implementation
- `embedding_model.py`: this file contains the embedding model used to calculate the cosine similarity
- `retriever.py`: the retriever is the component that processes the database schema; 
it relies on the embedder and the Neo4j client 


- `auto_queries.py`: this file contains all the auto-queries (_automatic queries_)
  that are launched to create the database schema
- `configuration.py`: this file includes all the configuration parameters; 
you can edit them in order to adapt the system to your specifical needs 


## Inputs

These files represent the input resources for the agents.

- `prompts.py`: this files comprehends the LLM prompts and the examples lists

## Outputs

These are the files where the main outputs get written on.

- `automatic_results.txt`: this file includes the results from the `main_automatic` execution
- `manual_results.txt`: this file obtains the results from the `main_manual` execution

## Utilities

These are the utility files
- 'query_execution.py': this is a utility file to directly get the results in a readable format
- `spinner.py`: this class creates an animated spinner during the waiting phases

# Database preprocessing
Before running the pipeline, it's necessary to preprocess the database; 
otherwise, the system won't be able to properly query the Neo4j server. 

## Necessary Plugins 
- NeoSemantics (to import the database from .ttl file) 
- APOC (to dynamically assing labels)

1) Import the original ontology into your own Neo4j server 
2) Create the `name` property with this query: 
    ```cypher
    MATCH (n:Resource)
    WHERE n.uri IS NOT NULL AND n.name IS NULL
    SET n.name = CASE 
      WHEN n.uri CONTAINS '#' 
        THEN split(n.uri, '#')[-1] 
        ELSE split(n.uri, '/')[-1] 
      END;
    ```
3) Create the ontology hierarchy by executing:
```cypher
MATCH (sc)-[:SUBCLASSOF]->(bn)-[:INTERSECTIONOF]->(l)
MATCH (l)-[:REST*0..]->(restNode),
      (restNode)-[:FIRST]->(tc)
CREATE (sc)-[:SUBCLASSOF]->(tc);
```

4) Assign the class labels to the objects 
```cypher 
MATCH (red)-[:TYPE]->(beige) 
MATCH (beige)-[:INTERSECTIONOF]->(blue) 
MATCH (blue)-[:REST*0..]->(subList)
MATCH (subList)-[:FIRST]->(c:Class)
CALL apoc.create.addLabels(red, [c.name]) 
YIELD node RETURN count(node) AS NewNodes 
```

5) Delete the b-nodes 
```cypher 
MATCH (n:Resource)
WHERE n.uri STARTS WITH 'bnode://'
DETACH DELETE n;
```

# How to Configure the system

The `configuration.py` file contains the dictionary with all the parameters you can configure.

- `n4j_usr`: username
- `n4j_psw` : password
- `n4j_url`: Neo4j URI / URL
- `sys_classes`: System classes (ignored in the auto-queries )
- `sys_rel_types`: System relationship types (ignored in the auto-queries)


- `llm`: the name of the LLM used for the LanguageModel class (implemented via ollama library)
- `quit_key_words`: write one of these word in the chat to close the session (only for manual sessions)
- `embedder`: embedding model name 

- `k_lim`: Maximum number of examples to be extracted in the auto-queries 
- `thresh`: Minimum similarity threshold for schema filtering 


- `aq_tuple`: the tuple with the autoqueries to be run; here, you can choose which auto-queries to launch and their 
execution order  
  - the first element is the name of the auto-query, used in the AQ dictionary (`auto_query.py`) to get the 
data of the auto-query
  - the second element is the filtering modality (see later) 
  - the first two parameters are mandatory; if present, the other elements are additional parameters for the auto-query

## Filtering modalities 
- `dense-thresh` selects only entities with a cosine similarity greater than a minimum threshold;
- `dense-klim` selects only the k most relevant results
- `dense-both` combines the two previous modes, selecting only elements with a similarity greater than the minimum threshold, with a maximum limit of k elements. 
- Finally, the `launch` value applies to queries that must be launched directly during the filtering phase, as their input must already be filtered.

## Prompt parameters 

- `question_prompt`: the prompt for the first LLM operation: initially, it includes the instructions only; 
then, the retriever transcribes the database schema and adds it. 
- `answer_prompt`: this is the prompt for the second LLM operation, i.e. the results explanation
- `examples`: these are the examples feeded to the LLM, presented as a history of previous correct messages 

# How to run a Manual Session

After the configuration, if you want to manually test the system, follow this guide:

1) run `main_manual.py`
2) write your question after the `[User] >` 
3) the system will process the Cypher query (`[Query] >`)
4) `[Neo4j] >` will return the exact server results
5) `[Agent] >` will explain the results in natural  language

All the information about the outcome is printed onto `manual_results.txt`.

- `Question Prompt`: this prompts includes the instructions and the database schema, processed by the auto-queries
- `Chat History`: these are the examples passed to the LLM as previous messages
- `Answer Prompt`: this is the prompt send through the second call to LLM agent
- `Context`: this is the knowledge that enables LLM to answer the question: 
it includes the user query and the results produced by Neo4j. 

# How to run an Automatic Session

If you want to test multiple queries in a row, run the `main_automatic.py` file, after having configurated it.

- In the `configuration.py`, choose the query IDs and insert them in the `config['test_queries']` list; 
you can insert a 2-element tuple in order to test all the queries between them.
- For instance, if you set the list to `[1, 5, (9, 12), (15,18), 38]`, the system will test the following queries: 
1, 5, 9, 10, 11, 12, 15, 16, 17, 18 and 38.
- You can check for queries IDs in `Queries_with_ID.json`.
- The file `automatic_results.txt` inlcudes all the results, query by query, including: 
  - configuration data 
  - user question 
  - transcripted filtered schema 
  - generated Cypher query 
  - Neo4j results 
  - generated answer (natural language)
  - expected answer (natural language)
