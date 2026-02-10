"""
Schemas and base prompts for queries and answers
"""


class ExampleLists:

    examples_list = [
        {
            "user_query": "Which are the roles of the employees?",
            "cypher_query": "MATCH (e:Employee) RETURN e.name, e.role"
        },
        {
            "user_query": "Which are the names of John's friends?",
            "cypher_query":
                "MATCH (f)-[:FRIEND]->(j:Person {name: 'John'}) RETURN f.name"
        },
        {
            "user_query": "Is there any user with age 38?",
            "cypher_query":
                "MATCH (u:User) RETURN u.age = 38 AS answer",
        },
    ]


class QuestionPrompts:

    instructions_prompt = """
You are an expert Cypher generator: your task is to generate Cypher query that best answers the user question.

Follow these guidelines:
    1. Write ONLY a syntactically correct Cypher query: NOTHING ELSE. 
    2. DO NOT invent properties: read the database schema.
    3. Use ONLY the relationships in the database.    
    4. Write the queries according to the schema 
    5. Keep the queries simple, readable and deterministic.
    6. Try to require also the names of entities
    
    """


class AnswerPrompts:
    answer_prompt = """
You are a helpful smart assistant.
You'll receive the outputs of the query, written in Cypher language: explain these outputs in a natural way.
Don't mention Neo4j explicitly: describe the results in natual way. 
Please, be synthetic: read the outputs and explain them by answering to the user question.  
    """


EL = ExampleLists
AP = AnswerPrompts
QP = QuestionPrompts

if __name__ == "__main__":
    pass
