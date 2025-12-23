---
title: Sprachen Projekt Guidelines
esame: "[[Formal Languages]]"
---

# Project Structure   
## Root Directory   
- `main_manual.py`: file use to test the pipeline manually. Run this file to use the chatbot directly  
- `main_automatic.py`: file used to execute tests with multiple queries, by using their IDs.   
- `neo4j_client.py`: this file implements the Neo4j client the interacts with the database  
- `language_model.py`: this file includes the LLM agent implementation   
- `retriever.py`: the retriever is the component that processes the database scheme    
## Outputs   
- `automatic_results.txt`: this file includes the results from the `main_automatic` execution  
- `manual_results.txt`: this file obtains the results from the `main_manual` execution  
## Inputs   
- `configuration.py`: this file includes all the configuration parameters   
- `prompts.py`: this files comprehends the LLM prompts and the examples lists   
## Utilities   
These are the utility files  
- `auto_queries.py`: this file contains all the auto-queries (_automatic queries_)  
that are launched to create the database scheme  
- `spinner.py`: this class creates an animated spinner during the waiting phases
# Configure the system
The file `configuration.py` contains the dictionary with all the parameters you can configure. 
- `n4j_usr`: username 
- `n4j_psw` : password 
- `n4j_url`: Neo4j URI / URL 

- `sys_classes`: System classes
- `sys_rel_types`: System relationship types
	These two parameters are ignored in the auto-queries 

- `aq_tuple`: this is the tuple with the autoqueries
	- first element is the name of the auto-query
	- second element is the phase parameter: it indicates if the auto-query must be execute during the initialization (`init`) or the filtering (`filter`) phase
	- if present, other elements are additional parameters for the auto-query

- `llm`: the name of the LLM used for the LanguageModel class 
- `quit_key_words`: write one of these word in the chat to close the session 
- `embd`: embedding model name 

# Testing a Manual Session
If you want to manually test the system:
1) run `main_manual.py`
2) write your question after the `[User] >`
3) system will process the  Cypher query (`[Query] >`)
4) `[Neo4j] >` will return the database results 
5) `[Agent] >` will explain the results in a natural way

All the information about the outcome is printed onto `manual_results.txt`. 
- `Question Prompt`: this prompts comprehends the instructions and the database schema, processed by the auto-queries 
- `Chat History`: these are the examples passed to the LLM as previous messages 
- `Answer Prompt`: this is the prompt send through the second call to LLM agent
- `Context`: this part represents the second 'query' send to the LLM, that includes the original question and the database results. 
# Testing an Automatic Session
If you want to test multiple queries in a row, run the `main_automatic.py` file, after having configurated it. 
At the end of the file, choose the query IDs and insert them in the `formal_queries` list; you can insert a 2-element tuple in order to test all the queries between them. 
For instance, if `formal_queries = [1, 5, (9, 12), (15,18), 38]`, the system will test queries number 1, 5, 9, 10, 11, 12, 15, 16, 17, 18 and 38. 
You can check for query IDs in `Queries_with_ID.json`. 
