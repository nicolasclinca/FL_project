from neo4j import GraphDatabase
import ast

uri = 'bolt://localhost:7687'
auth = ("neo4j", "4Neo4Jay!")

home = "http://swot.sisinflab.poliba.it/home#"

driver = GraphDatabase.driver(uri, auth=auth)

def schema_query_1():
    with open('query_shell.txt', 'r') as file:
        lista = ast.literal_eval(file.read())
        print(lista)

schema_query_1()
