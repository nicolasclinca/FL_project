
# Sprachen Projekt Guidelines

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
